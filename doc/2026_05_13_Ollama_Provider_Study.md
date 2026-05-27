# Étude : Intégration d'un Provider Ollama (LLM Local) — Service de Traduction COP

**Date :** 2026-05-13
**Auteur :** Étude technique
**Version :** 1.0
**Statut :** PROPOSÉ
**Référence :** [Roadmap v2.0](2026_05_11_Roadmap_v2_0_Plan.md) | [Étude d'Améliorations](2026_05_06_COP_Translation_Service_Improvements_Study.md)

---

## 1. Résumé Exécutif

L'ajout d'un provider **Ollama** (LLM local) résout le problème critique identifié en production : le scraping de Google Translate génère un trafic réseau agressif (~6,7 req/s, ~24 000 req/h) qui sature les partages de connexion mobile et déclenche du rate limiting. L'approche proposée remplace le modèle « 1 clé = 1 requête HTTP » par « 1 chunk de 50-200 entrées = 1 requête locale », réduisant le nombre d'appels de **99%** et éliminant toute dépendance réseau.

### Bénéfices attendus

| Critère | Google (actuel) | DeepL API | Ollama (proposé) |
|---------|-----------------|-----------|-------------------|
| Dépendance réseau | Oui (scraping) | Oui (API) | **Non** (local) |
| Requêtes pour 2642 entrées | ~2642 | ~2642 | **~15-30** |
| Saturation hotspot | Oui | Modéré | **Non** |
| Coût | Gratuit | 500k chars/mois gratuit | **Gratuit** |
| Qualité traduction | Standard | Supérieure | **Variable** (modèle) |
| Confidentialité | Non (Google) | Non (DeepL) | **Oui** (local) |
| Stabilité | Fragile | Stable | **Stable** |
| Vitesse (2642 entrées) | ~30-45 min | ~15-20 min | **~5-15 min** |

---

## 2. Problème Actuel

### 2.1 Architecture existante

```
JSON source (2642 entrées)
    ↓
translate_batch() → pour chaque entrée :
    ↓
    translate_text() → 1 requête HTTP
        ↓
        GoogleProvider.translate() → GoogleTranslator().translate(text)
            ↓
            Requête HTTPS vers translate.google.com/m?tl=...&sl=...&q=...
            ↓
            Parsing HTML de la réponse
    ↓
    rate_limit_seconds=0.15 (6,7 req/s)
    ↓
    checkpoint tous les 100 entrées
```

### 2.2 Problèmes identifiés

| Problème | Impact | Gravité |
|----------|--------|---------|
| **1 clé = 1 requête HTTP** | ~2642 requêtes pour un fichier moyen | 🔴 Critique |
| **Scraping Google Translate** | Chargement HTML complet, TLS handshake, DNS lookup | 🔴 Critique |
| **6,7 requêtes/seconde** | Saturation NAT, CPU modem, tables de connexions | 🔴 Critique |
| **Pas de keep-alive** | Nouvelle connexion TCP/TLS pour chaque entrée | 🔴 Élevée |
| **Pas de batching API** | Chaque texte est envoyé individuellement | 🟡 Moyenne |
| **Retry agressif** | 3 tentatives avec backoff exponentiel → trafic explose | 🟡 Moyenne |
| **Checkpoint bug** | Écrase les traductions existantes (corrigé en IMP2-T002) | 🟡 Corrigé |

### 2.3 Impact sur les partages de connexion

Sur un partage de connexion mobile (4G/5G) :

- ~6,7 connexions HTTPS/seconde
- ~400 connexions/minute
- Chaque connexion : DNS lookup + TLS handshake + HTTP request + close
- Le téléphone/modem ne peut pas suivre → **chute de la connexion**
- Google détecte le scraping → **rate limiting 429** → **boucle de retry** → trafic exponentiel

---

## 3. Architecture Proposée

### 3.1 Principe : Chunking + LLM Local

```
JSON source (2642 entrées)
    ↓
Découpage en chunks (50-200 entrées)
    ↓
Pour chaque chunk :
    ↓
    Construction du prompt (JSON + règles de traduction)
    ↓
    1 requête Ollama HTTP (localhost:11434)
        ↓
        LLM génère le JSON traduit
    ↓
    Validation JSON (clés présentes, structure correcte)
    ↓
    Retry si JSON invalide (max 2 tentatives)
    ↓
    Fusion dans le résultat final
    ↓
Checkpoint tous les 100 entrées (réutilise le mécanisme existant)
```

**Réduction du nombre de requêtes : 2642 → ~15-30** (chunks de 100-200 entrées)

### 3.2 Diagramme de composants

```
                    ┌─────────────────────────────────┐
                    │       translator_factory.py       │
                    │  create_provider("ollama", ...)   │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │        OllamaProvider             │
                    │  ┌─────────────────────────────┐  │
                    │  │     translate(text, src, tgt) │  │
                    │  └──────────────┬──────────────┘  │
                    │                 │                  │
                    │  ┌──────────────▼──────────────┐  │
                    │  │   _translate_chunk(chunk)    │  │
                    │  │   - Construction prompt      │  │
                    │  │   - Appel Ollama API         │  │
                    │  │   - Validation JSON           │  │
                    │  │   - Retry si invalide        │  │
                    │  └─────────────────────────────┘  │
                    └─────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │      Ollama (localhost:11434)    │
                    │  qwen3 / mistral / nllb / etc.  │
                    └─────────────────────────────────┘
```

### 3.3 Intégration dans l'architecture existante

L'OllamaProvider s'intègre dans le pattern existant (`TranslationProvider` ABC) **sans modifier** les providers Google et DeepL :

```python
# translator_factory.py — Ajout minimal
class OllamaProvider(TranslationProvider):
    """Translation provider using local Ollama LLM with chunking."""

    def translate(self, text: str, source: str, target: str) -> str:
        # Délègue au chunking interne
        ...

    @property
    def name(self) -> str:
        return "Ollama"
```

Le `translate_batch()` existant dans `translator.py` appelle `translate_text()` pour chaque entrée. Avec Ollama, le batch processing se fera au niveau du provider (chunking), pas au niveau du batch externe.

**Deux approches d'intégration sont possibles :**

#### Approche A : Provider avec chunking interne (recommandée)

```python
class OllamaProvider(TranslationProvider):
    def translate(self, text: str, source: str, target: str) -> str:
        # Traduction unitaire (pour le cache et les entrées isolées)
        result = self._call_ollama({text: text}, source, target)
        return result.get(text, text)

    def translate_batch(self, items: dict[str, str], source: str, target: str) -> dict[str, str]:
        # Chunking et traduction par blocs
        results = {}
        for chunk in self._chunk_items(items, self.chunk_size):
            chunk_result = self._call_ollama(chunk, source, target)
            results.update(chunk_result)
        return results
```

#### Approche B : Mode Ollama dédié dans `mode_translate_json.py`

Ajouter un chemin alternatif dans le mode translate-json qui utilise le chunking Ollama directement, en contournant le `translate_batch()` par entrée.

**Recommandation : Approche A** — Elle s'intègre naturellement dans l'architecture existante et permet le fallback entre providers.

---

## 4. Spécification Détaillée

### 4.1 OllamaProvider

```python
# Fichier : translator/core/ollama_provider.py

class OllamaProvider(TranslationProvider):
    """Translation provider using local Ollama LLM with chunking."""

    def __init__(
        self,
        model: str = "qwen3",
        base_url: str = "http://localhost:11434",
        chunk_size: int = 100,
        max_retries: int = 2,
        timeout: int = 300,
        temperature: float = 0.1,
    ):
        self._model = model
        self._base_url = base_url
        self._chunk_size = chunk_size
        self._max_retries = max_retries
        self._timeout = timeout
        self._temperature = temperature

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    def translate(self, text: str, source: str, target: str) -> str:
        """Translate a single text using Ollama."""
        if not text or not text.strip():
            return text
        result = self._call_ollama({"__single__": text}, source, target)
        return result.get("__single__", text)

    def translate_batch(
        self,
        items: dict[str, str],
        source: str,
        target: str,
    ) -> dict[str, str]:
        """Translate a batch of texts using chunking."""
        results = {}
        chunks = self._chunk_items(items)

        for i, chunk in enumerate(chunks):
            logger.info(
                "Ollama chunk %d/%d (%d items)",
                i + 1, len(chunks), len(chunk)
            )
            for attempt in range(self._max_retries + 1):
                try:
                    chunk_result = self._call_ollama(chunk, source, target)
                    results.update(chunk_result)
                    break
                except OllamaValidationError as e:
                    logger.warning(
                        "Ollama chunk %d attempt %d failed: %s",
                        i + 1, attempt + 1, str(e)
                    )
                    if attempt == self._max_retries:
                        logger.error(
                            "Ollama chunk %d failed after %d attempts, keeping original text",
                            i + 1, self._max_retries + 1
                        )
                        results.update({k: v for k, v in chunk.items()})

        return results

    def _chunk_items(self, items: dict[str, str]) -> list[dict[str, str]]:
        """Split items into chunks of chunk_size."""
        keys = list(items.keys())
        chunks = []
        for i in range(0, len(keys), self._chunk_size):
            chunk_keys = keys[i:i + self._chunk_size]
            chunks.append({k: items[k] for k in chunk_keys})
        return chunks

    def _call_ollama(
        self,
        items: dict[str, str],
        source: str,
        target: str,
    ) -> dict[str, str]:
        """Send a chunk to Ollama and parse the response."""
        prompt = self._build_prompt(items, source, target)
        response = self._make_request(prompt)
        return self._parse_response(response, items)

    def _build_prompt(
        self,
        items: dict[str, str],
        source: str,
        target: str,
    ) -> str:
        """Build the translation prompt for the LLM."""
        lang_names = {
            "en": "English", "fr": "French", "de": "German",
            "cs": "Czech", "sk": "Slovak", "it": "Italian", "ar": "Arabic",
        }
        source_name = lang_names.get(source, source)
        target_name = lang_names.get(target, target)

        json_input = json.dumps(items, ensure_ascii=False, indent=2)

        return f"""You are a professional software localization translator.

STRICT RULES:
- Return VALID JSON only — no markdown, no explanations, no comments
- Keep ALL keys exactly as they are — do NOT rename, reorder, or remove any key
- Translate VALUES only from {source_name} to {target_name}
- Preserve ALL placeholders: {{name}}, %s, %d, {{count}}, {{value}}, etc.
- Preserve ALL escape characters: \\n, \\t, \\", etc.
- Preserve ALL HTML tags: <b>, <br/>, <strong>, etc.
- If a value is empty, keep it empty
- If a value is a technical term that doesn't need translation, keep it as-is
- Output ONLY the JSON object — no other text before or after

JSON to translate:
{json_input}"""

    def _make_request(self, prompt: str) -> str:
        """Make a request to the Ollama API."""
        import requests
        response = requests.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self._temperature,
                    "num_predict": 8192,
                },
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["response"]

    def _parse_response(
        self,
        response: str,
        original_items: dict[str, str],
    ) -> dict[str, str]:
        """Parse and validate the LLM response."""
        # Extract JSON from response (may contain markdown fences)
        json_str = self._extract_json(response)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise OllamaValidationError(f"Invalid JSON response: {e}")

        # Validate keys
        original_keys = set(original_items.keys())
        parsed_keys = set(parsed.keys())

        if original_keys != parsed_keys:
            missing = original_keys - parsed_keys
            extra = parsed_keys - original_keys
            logger.warning(
                "Ollama key mismatch: %d missing, %d extra",
                len(missing), len(extra)
            )
            # Keep original values for missing keys
            for key in missing:
                parsed[key] = original_items[key]
            # Remove extra keys
            for key in extra:
                del parsed[key]

        return parsed

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handle markdown fences)."""
        # Remove markdown code fences if present
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.rindex("```")
            return text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.rindex("```")
            return text[start:end].strip()
        # Try to find JSON object boundaries
        if "{" in text and "}" in text:
            start = text.index("{")
            end = text.rindex("}") + 1
            return text[start:end]
        return text
```

### 4.2 Configuration

Ajouter les variables de configuration dans `config.py` :

```python
# Ollama provider settings
OLLAMA_URL: str = field(
    default_factory=lambda: os.environ.get("OLLAMA_URL", "http://localhost:11434")
)
OLLAMA_MODEL: str = field(
    default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen3")
)
OLLAMA_CHUNK_SIZE: int = field(
    default_factory=lambda: int(os.environ.get("OLLAMA_CHUNK_SIZE", "100"))
)
```

### 4.3 CLI Flags

Ajouter dans `service.py` :

```python
parser.add_argument(
    "--ollama-url",
    default=None,
    help="URL du serveur Ollama (défaut: http://localhost:11434)",
)
parser.add_argument(
    "--ollama-model",
    default=None,
    help="Modèle Ollama à utiliser (défaut: qwen3)",
)
parser.add_argument(
    "--ollama-chunk-size",
    type=int,
    default=None,
    help="Taille des chunks pour Ollama (défaut: 100)",
)
```

### 4.4 Docker Integration

Dans `docker-compose.yml`, ajouter un accès au service Ollama du host :

```yaml
services:
  translator:
    # ... configuration existante ...
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OLLAMA_URL=http://host.docker.internal:11434
```

### 4.5 Factory Update

Mettre à jour `translator_factory.py` :

```python
class OllamaProvider(TranslationProvider):
    """Translation provider using local Ollama LLM with chunking."""
    # ... (voir spécification détaillée ci-dessus)

def create_provider(
    provider_type: str = "google",
    deepl_api_key: str = "",
    deepl_use_free_api: bool = True,
    fallback_enabled: bool = False,
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "qwen3",
    ollama_chunk_size: int = 100,
) -> TranslationProvider:
    """Factory function to create a translation provider."""
    # ... cas existants ...
    elif provider_lower == "ollama":
        return OllamaProvider(
            base_url=ollama_url,
            model=ollama_model,
            chunk_size=ollama_chunk_size,
        )
    # ... fallback avec ollama ...
```

---

## 5. Stratégie de Chunking et Validation

### 5.1 Taille des chunks

| Taille | Avantages | Inconvénients |
|--------|-----------|---------------|
| 50 entrées | Faible risque de troncature, JSON stable | Plus de requêtes |
| 100 entrées | Bon équilibre | **Recommandé** |
| 200 entrées | Moins de requêtes | Risque de troncature sur petits modèles |

**Recommandation : 100 entrées par défaut**, configurable via `OLLAMA_CHUNK_SIZE`.

### 5.2 Validation JSON

Pour chaque chunk retourné par le LLM :

1. **Extraction JSON** : Retirer les éventuels markdown fences (` ```json ... ``` `)
2. **Parsing JSON** : Valider que la réponse est du JSON valide
3. **Vérification des clés** : Comparer les clés retournées avec les clés envoyées
   - Clés manquantes → conserver la valeur originale
   - Clés en trop → les supprimer
   - Clés correctes → utiliser la traduction
4. **Retry si invalide** : Maximum 2 tentatives par chunk
5. **Fallback** : Si toutes les tentatives échouent, conserver le texte original

### 5.3 Gestion des placeholders

Le prompt doit explicitement préserver :

| Placeholder | Exemple | Comportement |
|-------------|---------|-------------|
| `{{name}}` | `"Hello {{name}}"` | → `"Bonjour {{name}}"` |
| `%s`, `%d` | `"Delete %s?"` | → `"Supprimer %s ?"` |
| Balises HTML | `"<b>Important</b>"` | → `"<b>Important</b>"` |
| Termes techniques | `"COP_ID"`, `"SIRET"` | → Conserver tel quel |

---

## 6. Prompt Engineering

### 6.1 Prompt de base

```
You are a professional software localization translator.

STRICT RULES:
- Return VALID JSON only — no markdown, no explanations, no comments
- Keep ALL keys exactly as they are — do NOT rename, reorder, or remove any key
- Translate VALUES only from {source} to {target}
- Preserve ALL placeholders: {{name}}, %s, %d, {{count}}, {{value}}, etc.
- Preserve ALL escape characters: \n, \t, \", etc.
- Preserve ALL HTML tags: <b>, <br/>, <strong>, etc.
- If a value is empty, keep it empty
- If a value is a technical term that doesn't need translation, keep it as-is
- Output ONLY the JSON object — no other text before or after

JSON to translate:
{json_input}
```

### 6.2 Optimisations possibles

| Technique | Description | Impact |
|-----------|-------------|--------|
| **Few-shot examples** | Inclure 2-3 exemples de traduction | +10-15% qualité |
| **System prompt** | Utiliser le paramètre `system` de l'API Ollama | Meilleure consistance |
| **Température basse** | `temperature: 0.1` pour réduire les hallucinations | Stabilité JSON |
| **Max tokens élevé** | `num_predict: 8192` pour éviter la troncature | Complétude |
| **Modèle spécialisé** | Utiliser un modèle fine-tuned pour la traduction | Qualité optimale |

### 6.3 Modèles recommandés

| Modèle | Taille | Qualité FR | Qualité DE | Qualité CS | Vitesse | Recommandation |
|--------|--------|-----------|-----------|-----------|---------|----------------|
| **qwen3** | 4.7GB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | **Recommandé** |
| mistral | 4.1GB | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Bon compromis |
| llama3.1 | 4.7GB | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | Correct |
| nllb | 1.5GB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Spécialisé traduction |

**Installation :** `ollama pull qwen3`

---

## 7. Plan d'Implémentation

### 7.1 Étapes (TDD)

| # | Tâche | Tests | Fichiers | Priorité |
|---|-------|-------|---------|----------|
| 1 | Créer `OllamaProvider` avec `translate()` | Test unitaire : traduction simple | `core/ollama_provider.py` | Haute |
| 2 | Implémenter le chunking | Test unitaire : découpage et fusion | `core/ollama_provider.py` | Haute |
| 3 | Implémenter `translate_batch()` | Test unitaire : batch de 100+ entrées | `core/ollama_provider.py` | Haute |
| 4 | Validation JSON et retry | Test unitaire : JSON cassé, clés manquantes | `core/ollama_provider.py` | Haute |
| 5 | Prompt engineering | Test d'intégration : qualité FR/DE/CS | `core/ollama_provider.py` | Moyenne |
| 6 | Configuration `config.py` | Test unitaire : résolution des paramètres | `core/config.py` | Haute |
| 7 | Factory update | Test unitaire : `create_provider("ollama")` | `core/translator_factory.py` | Haute |
| 8 | CLI flags | Test CLI : `--provider ollama --ollama-model qwen3` | `service.py` | Haute |
| 9 | Intégration `translate_batch()` | Test d'intégration : traduction complète | `core/translator.py` | Moyenne |
| 10 | Docker `host.docker.internal` | Test manuel | `docker-compose.yml` | Moyenne |
| 11 | Fallback Ollama → Google | Test unitaire : FallbackProvider avec Ollama | `core/translator_factory.py` | Basse |

### 7.2 Fichiers à créer/modifier

| Fichier | Action | Description |
|--------|--------|-------------|
| `core/ollama_provider.py` | **CRÉER** | Provider Ollama avec chunking |
| `core/translator_factory.py` | MODIFIER | Ajouter `ollama` au factory |
| `core/config.py` | MODIFIER | Ajouter config Ollama |
| `core/translator.py` | MODIFIER | Support `translate_batch()` dans le provider |
| `service.py` | MODIFIER | Ajouter flags CLI Ollama |
| `docker-compose.yml` | MODIFIER | Ajouter `extra_hosts` pour Ollama |
| `tests/test_ollama_provider.py` | **CRÉER** | Tests unitaires du provider |
| `requirements.txt` | MODIFIER | Ajouter `requests` (déjà présent) |

### 7.3 Ordre de développement

```
IMP3-T001: OllamaProvider.translate()           → core/ollama_provider.py + tests
IMP3-T002: OllamaProvider.translate_batch()     → core/ollama_provider.py + tests
IMP3-T003: Validation JSON + retry              → core/ollama_provider.py + tests
IMP3-T004: Configuration + Factory + CLI        → config.py + factory.py + service.py
IMP3-T005: Intégration translate_json + Docker  → mode_translate_json.py + docker-compose.yml
IMP3-T006: Tests d'intégration end-to-end       → tests/
```

---

## 8. Risques et Points d'Attention

### 8.1 Risques identifiés

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **JSON cassé par le LLM** | Élevée | Moyen | Validation stricte + retry + fallback valeur originale |
| **Clés manquantes/triées** | Moyenne | Faible | Vérification des clés + ajout des manquantes |
| **Hallucination du LLM** | Moyenne | Moyen | Température basse (0.1) + prompt strict |
| **Troncature de la réponse** | Faible | Élevé | Chunks de 100 + `num_predict: 8192` + vérification complétude |
| **Modèle non installé** | Faible | Élevé | Vérification au démarrage + message d'erreur clair |
| **Ollama non démarré** | Faible | Élevé | Vérification connectivité au démarrage + fallback |
| **Performance modèle** | Variable | Faible | Benchmark des modèles + recommandation qwen3 |

### 8.2 Limitations connues

| Limitation | Description | Workaround |
|-----------|-------------|------------|
| **Qualité variable** | Les LLM ne traduisent pas aussi bien que DeepL | Choisir un bon modèle (qwen3) + few-shot |
| **Temps de réponse** | 10-30s par chunk sur CPU, 2-5s sur GPU | Acceptable pour du batch |
| **Consommation mémoire** | 4-8 GB RAM pour le modèle | Utiliser un modèle quantifié (Q4) |
| **Cohérence** | Un terme peut être traduit différemment entre chunks | Prompt strict + post-processing |
| **Placeholders** | Risque de modification des placeholders | Prompt explicite + validation regex |

### 8.3 Stratégie de fallback

```
OllamaProvider.translate() échoue
    ↓
translate_text() retry (max 3 tentatives)
    ↓
Si échec → retourne le texte original (comportement existant)
    ↓
Le cache stocke le texte original comme "échec de traduction"
    ↓
Au prochain run, le cache évitera de re-tenter (optimisation future)
```

---

## 9. Benchmark Attendu

### 9.1 Nombre de requêtes

| Provider | Requêtes pour 2642 entrées | Réduction |
|----------|---------------------------|-----------|
| Google (actuel) | ~2642 | — |
| DeepL (actuel) | ~2642 | 0% |
| **Ollama (proposé)** | **~15-30** | **~99%** |

### 9.2 Temps estimé

| Provider | Temps estimé | Conditions |
|----------|-------------|------------|
| Google (actuel) | 30-45 min | Connexion stable |
| DeepL (actuel) | 15-20 min | Clé API + connexion |
| **Ollama (proposé)** | **5-15 min** | Modèle local, pas de réseau |

### 9.3 Impact réseau

| Métrique | Google | Ollama |
|----------|--------|--------|
| Requêtes HTTPS | ~2642 | 0 |
| Volume upload | ~500 KB | 0 |
| Volume download | ~2 MB | 0 |
| Connexions TLS | ~2642 | 0 |
| Trafic total | ~2.5 MB | 0 (local) |

---

## 10. Utilisation Prévue

### 10.1 CLI

```bash
# Installation du modèle (une seule fois)
ollama pull qwen3

# Traduction avec Ollama
python service.py translate-json \
  --provider ollama \
  --ollama-model qwen3 \
  --ollama-url http://localhost:11434 \
  --ollama-chunk-size 100 \
  -s en \
  --batch-langs fr,cz,sk,de,it,ar \
  -i "source/2026_05_13_Import/en 4.json"

# Avec Docker (Ollama sur le host)
docker compose run --rm \
  -e MODE=translate-json \
  -e SOURCE_LANG=en \
  -e "SOURCE_FILE=/app/source/2026_05_13_Import/en 4.json" \
  -e "BATCH_LANGS=fr,cz,sk,de,it,ar" \
  -e TRANSLATION_PROVIDER=ollama \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=qwen3 \
  translator
```

### 10.2 Fallback Ollama → Google

```bash
# Ollama en primaire, Google en fallback
python service.py translate-json \
  --provider ollama \
  --fallback \
  -s en -t fr
```

### 10.3 Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `TRANSLATION_PROVIDER` | `google` | Provider : `google`, `deepl`, `ollama` |
| `OLLAMA_URL` | `http://localhost:11434` | URL du serveur Ollama |
| `OLLAMA_MODEL` | `qwen3` | Modèle Ollama à utiliser |
| `OLLAMA_CHUNK_SIZE` | `100` | Taille des chunks (entrées par requête) |
| `OLLAMA_TEMPERATURE` | `0.1` | Température du modèle |
| `OLLAMA_TIMEOUT` | `300` | Timeout par chunk (secondes) |

---

## 11. Conclusion et Recommandation

L'intégration d'un provider Ollama résout le problème critique du scraping Google Translate en éliminant complètement la dépendance réseau pour la traduction. L'approche proposée :

1. **S'intègre** dans l'architecture existante (pattern Provider)
2. **Ne casse rien** (Google et DeepL continuent à fonctionner)
3. **Réduit le nombre de requêtes de 99%** (2642 → ~15-30)
4. **Fonctionne localement** (pas de réseau nécessaire)
5. **Est configurable** (modèle, chunk size, URL, température)

**Recommandation :** Implémenter l'OllamaProvider en priorité (IMP3-T001 à T006) en suivant l'approche TDD, avec le modèle **qwen3** comme défaut pour sa bonne gestion du JSON et ses qualités multilingues.