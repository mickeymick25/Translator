# Amendement IMP3 — Retour Direction Technique

**Date :** 2026-05-14
**Contexte :** Avis de la direction technique sur l'étude `2026_05_13_Ollama_Provider_Study.md`
**Impact :** Modifications de la spécification détaillée et du plan d'implémentation IMP3

---

## 0. Verdict global

La direction technique valide l'architecture proposée (pattern Provider + chunking + validation). Le passage d'un scraping réseau fragile vers un pipeline batch local maîtrisable est confirmé comme la bonne direction.

Les renforcements ci-dessous ne changent pas l'architecture — ils durcissent la spécification pour fiabiliser le comportement en production.

---

## 1. Ce qui est déjà couvert dans l'étude (confirmé)

| Point | Référence étude | Verdict |
|-------|----------------|---------|
| Chunking 50-200 entrées | §5.1 | ✅ Validé, voir §2.1 pour ajustement |
| Validation JSON (parsing, clés manquantes/supplémentaires) | §4.1 `_parse_response` | ✅ Validé, voir §2.2 pour renforcement |
| Placeholders dans le prompt | §5.3 | ✅ Validé, mais insuffisant — voir §2.3 |
| Température basse (0.1) | §6.2 | ✅ Validé, voir §2.5 |
| `stream: false` | §4.1 `_make_request` | ✅ Validé, confirmé |
| Retry limité (2 tentatives) | §4.1 `translate_batch` | ✅ Validé, mais le mécanisme est insuffisant — voir §2.4 |
| Pattern Provider (ABC) | §3.2 | ✅ Validé, confirmé |
| Fallback vers valeur originale | §4.1 | ✅ Validé, confirmé |

---

## 2. Renforcements demandés par la direction technique

### 2.1 Chunking conservateur — Démarrer à 50

**Ce que dit l'étude :** Chunk par défaut à 100 entrées.

**Ce que demande la direction :** Commencer plus conservateur (50-100), puis benchmark pour monter.

**Décision :**
- `OLLAMA_CHUNK_SIZE` par défaut passe de **100** à **50**
- Ajout d'une constante `OLLAMA_CHUNK_SIZE_MAX = 200` comme limite haute
- Le benchmark réel déterminera la taille optimale

**Impact code :** Modification du default dans `config.py`, `_build_prompt`, et tests.

---

### 2.2 Validation structurelle stricte — Au-delà du JSON valide

**Ce que dit l'étude :** Vérifier que le JSON est valide et que les clés correspondent.

**Ce que demande la direction :** Ne pas se contenter de "JSON valide". Vérifier aussi :

| Contrôle | Description | Exemple de rejet |
|----------|-------------|------------------|
| **Mêmes clés** | Toutes les clés présentes, ni plus ni moins | Clé manquante ou ajoutée |
| **Même profondeur** | La structure doit être plate (pas d'objets imbriqués) | `{"k": {"nested": "v"}}` au lieu de `{"k": "v"}` |
| **Mêmes types** | Les valeurs restent des strings | `"5"` ne doit pas devenir `5` |
| **Mêmes placeholders** | Tous les placeholders préservés | `"{count} items"` ne doit pas devenir `"articles"` |

**Décision :** Ajouter une méthode `_validate_structure()` avec 4 contrôles distincts :

```python
class OllamaValidationError(Exception):
    """Raised when Ollama response fails structural validation."""
    def __init__(self, message: str, error_type: str = "unknown"):
        self.error_type = error_type  4 contrôles possibles : "missing_keys", "extra_keys", "type_mismatch", "placeholder_mismatch"
        super().__init__(message)

def _validate_structure(
    self,
    parsed: dict,
    original: dict[str, str],
) -> dict[str, str]:
    """Validate and repair the LLM response structure.

    5 checks in order:
    0. Minimum completion threshold (< 80% keys → reject entirely)
    1. Keys match exactly (missing → inject original, extra → remove)
    2. All values are strings (coerce if possible, else keep original)
    3. No nested objects (flatten or keep original)
    4. Placeholders preserved (compare before/after)
    """
```

**Impact code :** Nouvelle méthode `_validate_structure()` dans `OllamaProvider`, remplace la validation partielle dans `_parse_response`. Tests unitaires dédiés pour chaque contrôle.

---

### 2.3 Validation des placeholders — Le vrai piège prod

**Ce que dit l'étude :** Le prompt demande de préserver les placeholders. Pas de validation programmatique.

**Ce que demande la direction :** Les placeholders sont le vrai piège production. Il faut une validation programmatique stricte.

**Placeholders à protéger :**

| Catégorie | Patterns | Exemples |
|-----------|----------|----------|
| Format Python | `%s`, `%d`, `%f`, `%r`, `%.2f` | `"Delete %s?"` |
| ICU / Mustache | `{name}`, `{{count}}`, `{0}`, `{value}` | `"{count} items"`, `"Hello {{name}}"` |
| Balises HTML | `<b>`, `</b>`, `<br/>`, `<strong>`, `<i>` | `"<b>Important</b>"` |
| Échappements | `\n`, `\t`, `\"`, `\\` | `"Line1\nLine2"` |
| Syntaxe ICU complète | `{count, plural, one{...} other{...}}` | `"{count, plural, one{item} other{items}}"` |
| Termes techniques | Identifiants préservés | `"SIRET"`, `"COP_ID"` |

**Décision :** Ajouter une méthode `_extract_placeholders()` qui utilise des regex pour extraire tous les placeholders d'une chaîne, et `_validate_placeholders()` qui compare les placeholders avant/après traduction.

```python
# Patterns de placeholder à protéger
PLACEHOLDER_PATTERNS = [
    re.compile(r'%[sdrfifFeEgG]'),           # %s, %d, %f, etc.
    re.compile(r'\{[a-zA-Z_]\w*\}'),          # {name}, {count}
    re.compile(r'\{\{[a-zA-Z_]\w*\}\}'),      # {{name}}, {{count}}
    re.compile(r'\{\d+\}'),                    # {0}, {1}
    re.compile(r'\{[^}]+,\s*\w+,'),           # ICU plural/select
    re.compile(r'<[^>]+>'),                    # HTML tags
    re.compile(r'\\[nt"\\]'),                 # Escape sequences
]

def _extract_placeholders(self, text: str) -> list[str]:
    """Extract all placeholder patterns from a text string."""
    placeholders = []
    for pattern in self.PLACEHOLDER_PATTERNS:
        placeholders.extend(pattern.findall(text))
    return sorted(placeholders)

def _validate_placeholders(
    self,
    original: str,
    translated: str,
    key: str,
) -> bool:
    """Verify that all placeholders from original are preserved in translation.

    Returns True if valid, False if placeholders are missing or altered.
    """
    original_ph = self._extract_placeholders(original)
    translated_ph = self._extract_placeholders(translated)

    if original_ph and sorted(original_ph) != sorted(translated_ph):
        logger.warning(
            "Placeholder mismatch for key '%s': expected %s, got %s",
            key, original_ph, translated_ph
        )
        return False
    return True
```

**Comportement en cas d'échec :** Si un placeholder est manquant dans une valeur traduite, cette valeur **est remplacée par le texte original** (pas de traduction partielle dégradée). Le chunk n'est PAS entièrement rejeté — seule la valeur problématique est fallback.

**Impact code :** Nouvelles méthodes `_extract_placeholders()` et `_validate_placeholders()` dans `OllamaProvider`. Tests unitaires dédiés pour chaque pattern de placeholder.

---

### 2.4 Retry intelligent — Ne pas renvoyer le même prompt

**Ce que dit l'étude :** Retry avec `max_retries=2`, mais le même prompt est renvoyé tel quel.

**Ce que demande la direction :** Le retry DOIT injecter l'erreur détectée dans le prompt pour que le LLM corrige le problème. Sinon, même erreur → même sortie.

**Décision :** Ajouter un mécanisme de **retry avec injection d'erreur** dans `_call_ollama()`.

```python
def _call_ollama(
    self,
    items: dict[str, str],
    source: str,
    target: str,
    error_context: str | None = None,
) -> dict[str, str]:
    """Send a chunk to Ollama and parse the response.

    Args:
        error_context: If provided, injected into the prompt to help the LLM
                       correct a previous error.
    """
    prompt = self._build_prompt(items, source, target, error_context=error_context)
    response = self._make_request(prompt)
    return self._validate_structure(response, items)
```

Et dans `translate_batch()` :

```python
for attempt in range(self._max_retries + 1):
    try:
        chunk_result = self._call_ollama(chunk, source, target, error_context=error_context)
        results.update(chunk_result)
        error_context = None  # Reset on success
        break
    except OllamaValidationError as e:
        error_context = str(e)  # Inject error into next retry
        logger.warning(
            "Ollama chunk %d/%d attempt %d/%d failed: %s",
            chunk_idx + 1, total_chunks, attempt + 1, self._max_retries + 1, e
        )
        if attempt == self._max_retries:
            logger.error(
                "Ollama chunk %d/%d failed after %d attempts — keeping original text",
                chunk_idx + 1, total_chunks, self._max_retries + 1
            )
            # Fallback: keep original values for this chunk
            results.update({k: v for k, v in chunk.items()})
```

**Modification du prompt :** `_build_prompt()` accepte un paramètre optionnel `error_context`. Si présent, il est injecté après les règles :

```
CORRECTION NEEDED:
Previous attempt failed with this error: {error_context}
Please fix the issue and return valid JSON following ALL the rules above.
```

**Impact code :** Modification de `_call_ollama()`, `_build_prompt()`, `translate_batch()`. Tests unitaires pour retry avec et sans error_context.

---

### 2.5 Température — 0 plutôt que 0.1

**Ce que dit l'étude :** `temperature: 0.1`

**Ce que demande la direction :** Pour la traduction JSON, la créativité est inutile. Température 0 (ou au maximum 0.1) pour maximiser le déterminisme.

**Décision :**
- `OLLAMA_TEMPERATURE` par défaut passe de **0.1** à **0**
- La valeur 0.1 reste disponible via configuration pour les cas où le déterminisme total pose problème
- Documentation : expliquer que 0 = déterministe, 0.1 = légère variation

**Impact code :** Modification du default dans `config.py` et `_make_request()`.

---

### 2.6 Désactivation du streaming — Confirmé

**Ce que dit l'étude :** `"stream": False` dans l'appel API.

**Ce que demande la direction :** Confirmation — toujours `stream: false` pour ce use case.

**Décision :** Aucun changement, déjà correct. Ajout d'un commentaire explicatif dans le code et dans la doc pour expliciter pourquoi.

```python
# IMPORTANT: stream=False is mandatory for batch translation.
# Streaming adds complexity without benefit here — we need the full
# response to validate JSON structure before processing.
"stream": False,
```

**Impact code :** Commentaire uniquement.

---

### 2.7 Mode "Resume on Failure" — Checkpoint par chunk

**Ce que dit l'étude :** Le checkpoint existe dans `mode_translate_json.py` (tous les 100 entrées), mais il sauvegarde au niveau des entrées individuelles, pas au niveau des chunks.

**Ce que demande la direction :** Sur 2600+ entrées, un crash arrivera. Il faut un checkpoint **par chunk** pour permettre la reprise partielle sans tout recommencer.

**Décision :** Deux niveaux de checkpoint dans `mode_translate_json.py` quand le provider est Ollama :

1. **Checkpoint par chunk** (nouveau) : Après chaque chunk réussi, sauvegarder les résultats dans le fichier de sortie
2. **Checkpoint existant** : Tous les N entrées (inchangé pour Google/DeepL)

Le checkpoint par chunk est activé automatiquement quand le provider supporte `translate_batch()`. Il se déclenche après chaque chunk plutôt qu'après chaque entrée individuelle.

**Impact code :** Modification de `mode_translate_json.py` pour détecter le mode batch et ajuster la fréquence du checkpoint. Test unitaire pour vérifier la reprise après échec.

---

### 2.8 Seuil minimal de complétude — Anti-dégradation silencieuse

**Problème identifié par la direction technique :** Si le LLM retourne un objet vide `{}` ou très partiel `{"a": "ok"}` sur un chunk de 50 entrées, la réparation par fallback valeur par valeur masque une dégradation massive de qualité. Sans garde-fou, le système pourrait silencieusement produire un fichier où 90% des entrées sont en anglais original.

**Décision :** Ajouter un **seuil minimal de complétude** dans `_validate_structure()`. Si le taux de clés présentes dans la réponse LLM est inférieur à un seuil, la réponse est considérée comme **totalement invalide** — on ne tente PAS de réparation partielle, on déclenche directement le retry.

```python
# Seuil de complétude : si moins de 80% des clés sont présentes,
# la réponse est considérée comme totalement invalide.
COMPLETION_THRESHOLD = 0.8

def _validate_structure(
    self,
    parsed: dict,
    original: dict[str, str],
) -> dict[str, str]:
    # Check 0: Minimum completion threshold
    parsed_keys = set(parsed.keys())
    original_keys = set(original.keys())
    completion_ratio = len(parsed_keys & original_keys) / len(original_keys)

    if completion_ratio < self.COMPLETION_THRESHOLD:
        raise OllamaValidationError(
            f"Response completion too low: {completion_ratio:.0%} "
            f"({len(parsed_keys & original_keys)}/{len(original_keys)} keys). "
            f"Minimum required: {self.COMPLETION_THRESHOLD:.0%}",
            error_type="completion_threshold"
        )

    # ... reste de la validation (clés, types, placeholders)
```

**Comportement :**

| Taux de complétude | Action |
|-------------------|--------|
| ≥ 80% | Réparation valeur par valeur (fallback ciblé) |
| < 80% | Rejet du chunk entier → retry avec injection d'erreur |
| Après max retries | Fallback complet sur valeurs originales |

**Impact code :** Ajout de `COMPLETION_THRESHOLD` comme constante de classe et vérification en début de `_validate_structure()`. Test unitaire pour les cas limites (0%, 50%, 79%, 80%, 100%).

---

### 2.9 Limites connues des regex de placeholders

La validation des placeholders par regex est une approche **pragmatique "best effort"** pour IMP3. Deux limitations identifiées par la direction technique doivent être documentées.

#### 2.9.1 ICU nested — Regex insuffisante

**Regex actuelle :** `r'\{[^}]+,\s*\w+,'`

**Problème :** Ne couvre PAS correctement :
- Les plurals ICU imbriqués complexes
- Les structures multi-lignes

**Exemple problématique :**
```
{count, plural,
  one{# item}
  other{# items}
}
```

La regex capturera `{count, plural,` mais pas la structure complète imbriquée.

**Décision pour IMP3 :** Approche **best effort** acceptable. La regex capture le début des patterns ICU, ce qui suffit pour détecter leur présence. La validation compare les placeholders extraits avant/après — si le pattern ICU est partiellement capturé des deux côtés, la comparaison fonctionnera.

**Action future (post-IMP3) :** Évaluer l'ajout d'un parser ICU dédié (via `babel` ou une librairie spécialisée) ou d'un pattern regex plus robuste couvrant les nested braces.

#### 2.9.2 Faux positifs HTML

**Regex actuelle :** `r'<[^>]+>'`

**Problème :** Capture les balises HTML, MAIS aussi du texte non HTML.

**Exemple problématique :**
```
"value < threshold"  →  "< threshold" capturé comme placeholder
```

**Décision pour IMP3 :** Accepter ce compromis. Le coût est quelques faux positifs (des textes contenant `<` seront considérés comme contenant des placeholders HTML). Le bénéfice est une protection forte contre la corruption des vraies balises HTML.

**Tradeoff acceptable car :**
- Les fichiers de traduction COP contiennent majorité de vraies balises HTML, peu de comparaisons mathématiques
- Un faux positif = conserver le texte original au lieu de le traduire → impact minimal
- Un faux négatif = balise HTML supprimée → impact critique en production

**Action future (post-IMP3) :** Affiner la regex HTML pour exclure les patterns mathématiques courants (ex: `value < 10`, `x < y`).

---

## 3. Ce qu'il ne faut PAS faire (contre-architecture)

La direction technique est claire sur les anti-patterns à éviter :

| Anti-pattern | Pourquoi l'éviter |
|-------------|-------------------|
| **1 énorme prompt de 1800+ lignes** | Sature le contexte du LLM → JSON corrompu, hallucinations, réponses tronquées |
| **Streaming** | Complexe à parser, pas de bénéfice pour du batch, impossible de valider avant traitement |
| **Multi-thread agressif** | Concorrence sur un modèle local = contention mémoire + résultats imprévisibles |
| **Retry infini** | Boucle sans fin si le LLM ne peut pas produire un JSON valide → timeout |
| **Traduction clé par clé** | 2600 requêtes = même problème que Google, annule le bénéfice du chunking |

**Décision :** Ces anti-patterns sont **explicitement exclus** de l'implémentation. Aucun paramètre de configuration pour les activer.

---

## 4. Spécification mise à jour — `OllamaProvider`

### 4.1 Signature du constructeur (modifiée)

```python
class OllamaProvider(TranslationProvider):
    """Translation provider using local Ollama LLM with chunking.

    Uses batch translation with structural validation and
    intelligent retry to ensure production-grade output quality.
    """

    # Placeholder patterns to protect during translation
    PLACEHOLDER_PATTERNS: list[re.Pattern] = [
        re.compile(r'%[sdrfifFeEgG]'),           # %s, %d, %f, etc.
        re.compile(r'\{[a-zA-Z_]\w*\}'),          # {name}, {count}
        re.compile(r'\{\{[a-zA-Z_]\w*\}\}'),      # {{name}}, {{count}}
        re.compile(r'\{\d+\}'),                    # {0}, {1}
        re.compile(r'\{[^}]+,\s*\w+,'),           # ICU plural/select
        re.compile(r'<[^>]+>'),                    # HTML tags
        re.compile(r'\\[nt"\\]'),                  # Escape sequences: \n, \t, \", \\
    ]

    # Minimum completion threshold — if less than 80% of keys are present,
    # the response is considered totally invalid (no silent partial repair).
    COMPLETION_THRESHOLD: float = 0.8

    def __init__(
        self,
        model: str = "qwen3",
        base_url: str = "http://localhost:11434",
        chunk_size: int = 50,        # Changed: 100 → 50 (conservative start)
        max_retries: int = 2,
        timeout: int = 300,
        temperature: float = 0,      # Changed: 0.1 → 0 (max determinism)
    ):
        self._model = model
        self._base_url = base_url
        self._chunk_size = chunk_size
        self._max_retries = max_retries
        self._timeout = timeout
        self._temperature = temperature
```

### 4.2 Nouvelles méthodes de validation

```python
def _extract_placeholders(self, text: str) -> list[str]:
    """Extract all placeholder patterns from a text string.

    Protected patterns: %s/%d, {name}, {{count}}, {0},
    ICU syntax, HTML tags, escape sequences.
    """
    placeholders = []
    for pattern in self.PLACEHOLDER_PATTERNS:
        placeholders.extend(pattern.findall(text))
    return sorted(placeholders)

def _validate_placeholders(
    self,
    original: str,
    translated: str,
    key: str,
) -> bool:
    """Verify that all placeholders from original are preserved in translation.

    Returns True if valid, False if any placeholder is missing or altered.
    On mismatch, the original value should be used instead.
    """
    original_ph = self._extract_placeholders(original)
    translated_ph = self._extract_placeholders(translated)

    if original_ph and sorted(original_ph) != sorted(translated_ph):
        logger.warning(
            "Placeholder mismatch for key '%s': expected %s, got %s",
            key, original_ph, translated_ph
        )
        return False
    return True

def _validate_structure(
    self,
    parsed: dict,
    original: dict[str, str],
) -> dict[str, str]:
    """Validate and repair the LLM response structure.

    5 checks in order:
    0. Minimum completion threshold (< 80% keys → reject entirely, trigger retry)
    1. Keys match exactly (missing → inject original, extra → remove)
    2. All values are strings (coerce numbers, else keep original)
    3. No nested objects (keep original for nested values)
    4. Placeholders preserved (compare before/after for each value)

    Returns a cleaned dict. Raises OllamaValidationError if structural
    issues are too severe to repair.
    """
    result = {}
    errors = []
    original_keys = set(original.keys())
    parsed_keys = set(parsed.keys())

    # Check 0: Minimum completion threshold
    # If less than 80% of keys are present, the response is totally invalid.
    # Do NOT attempt partial repair — trigger a retry with error injection.
    completion_ratio = len(parsed_keys & original_keys) / len(original_keys) if original_keys else 1.0
    if completion_ratio < self.COMPLETION_THRESHOLD:
        raise OllamaValidationError(
            f"Response completion too low: {completion_ratio:.0%} "
            f"({len(parsed_keys & original_keys)}/{len(original_keys)} keys). "
            f"Minimum required: {self.COMPLETION_THRESHOLD:.0%}",
            error_type="completion_threshold"
        )

    # Check 1: Missing keys
    missing_keys = original_keys - parsed_keys
    if missing_keys:
        errors.append(f"Missing keys: {missing_keys}")

    # Check 1: Extra keys
    extra_keys = parsed_keys - original_keys
    if extra_keys:
        errors.append(f"Extra keys: {extra_keys}")

    # Build result with validation per value
    for key in original_keys:
        if key not in parsed:
            # Missing key: keep original
            result[key] = original[key]
            continue

        value = parsed[key]

        # Check 2: Type — value must be a string
        if not isinstance(value, str):
            if isinstance(value, (int, float, bool)):
                value = str(value)
            else:
                # Nested object or other — keep original
                errors.append(f"Key '{key}': expected string, got {type(value).__name__}")
                result[key] = original[key]
                continue

        # Check 3: (strings are always flat, no nested check needed for flat JSON)

        # Check 4: Placeholders preserved
        if not self._validate_placeholders(original[key], value, key):
            result[key] = original[key]  # Fallback to original
            errors.append(f"Key '{key}': placeholder mismatch")
            continue

        result[key] = value

    if errors:
        # Raise with details so retry can inject them
        raise OllamaValidationError(
            "; ".join(errors),
            error_type="structural_validation"
        )

    return result

def _parse_response(
    self,
    response: str,
    original_items: dict[str, str],
) -> dict[str, str]:
    """Parse and structurally validate the LLM response.

    1. Extract JSON from response (handle markdown fences)
    2. Parse JSON
    3. Validate structure (keys, types, placeholders)
    """
    json_str = self._extract_json(response)
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise OllamaValidationError(
            f"Invalid JSON response: {e}",
            error_type="json_parse"
        )

    return self._validate_structure(parsed, original_items)
```

### 4.3 Prompt avec injection d'erreur (modifié)

```python
def _build_prompt(
    self,
    items: dict[str, str],
    source: str,
    target: str,
    error_context: str | None = None,
) -> str:
    """Build the translation prompt for the LLM.

    Args:
        items: Key-value pairs to translate.
        source: Source language code.
        target: Target language code.
        error_context: If provided, injected to help the LLM correct
                       a previous error on retry.
    """
    lang_names = {
        "en": "English", "fr": "French", "de": "German",
        "cs": "Czech", "sk": "Slovak", "it": "Italian", "ar": "Arabic",
    }
    source_name = lang_names.get(source, source)
    target_name = lang_names.get(target, target)

    json_input = json.dumps(items, ensure_ascii=False, indent=2)

    prompt = f"""You are a professional software localization translator.

STRICT RULES:
- Return VALID JSON only — no markdown, no explanations, no comments
- Keep ALL keys exactly as they are — do NOT rename, reorder, or remove any key
- Translate VALUES only from {source_name} to {target_name}
- Preserve ALL placeholders exactly: {{name}}, %s, %d, {{count}}, {{value}}, etc.
- Preserve ALL escape characters exactly: \\n, \\t, \\", etc.
- Preserve ALL HTML tags exactly: <b>, <br/>, <strong>, etc.
- If a value is empty, keep it empty
- If a value is a technical term that doesn't need translation, keep it as-is
- Output ONLY the JSON object — no other text before or after

JSON to translate:
{json_input}"""

    if error_context:
        prompt += f"""

CORRECTION NEEDED:
Previous attempt failed with this error: {error_context}
Please fix the issue and return valid JSON following ALL the rules above."""

    return prompt
```

### 4.4 `translate_batch()` avec retry intelligent (modifié)

```python
def translate_batch(
    self,
    items: dict[str, str],
    source: str,
    target: str,
) -> dict[str, str]:
    """Translate a batch of texts using chunking with intelligent retry."""
    results = {}
    chunks = self._chunk_items(items)
    total_chunks = len(chunks)

    for chunk_idx, chunk in enumerate(chunks):
        logger.info(
            "Ollama chunk %d/%d (%d items)",
            chunk_idx + 1, total_chunks, len(chunk)
        )
        error_context = None

        for attempt in range(self._max_retries + 1):
            try:
                chunk_result = self._call_ollama(
                    chunk, source, target,
                    error_context=error_context
                )
                results.update(chunk_result)
                error_context = None  # Reset on success
                break
            except OllamaValidationError as e:
                error_context = str(e)  # Inject error into next retry
                logger.warning(
                    "Ollama chunk %d/%d attempt %d/%d failed: %s",
                    chunk_idx + 1, total_chunks,
                    attempt + 1, self._max_retries + 1, e
                )
                if attempt == self._max_retries:
                    logger.error(
                        "Ollama chunk %d/%d failed after %d attempts — "
                        "keeping original text",
                        chunk_idx + 1, total_chunks,
                        self._max_retries + 1
                    )
                    # Fallback: keep original values for this chunk
                    results.update({k: v for k, v in chunk.items()})

    return results
```

### 4.5 Variables de configuration (modifiées)

| Variable | Ancien défaut | Nouveau défaut | Raison |
|----------|---------------|----------------|--------|
| `OLLAMA_CHUNK_SIZE` | `100` | **`50`** | Démarrage conservateur |
| `OLLAMA_TEMPERATURE` | `0.1` | **`0`** | Déterminisme maximal |
| `OLLAMA_URL` | `http://localhost:11434` | `http://localhost:11434` | Inchangé |
| `OLLAMA_MODEL` | `qwen3` | `qwen3` | Inchangé |
| `OLLAMA_TIMEOUT` | `300` | `300` | Inchangé |
| `OLLAMA_MAX_RETRIES` | — (hardcodé 2) | **`2`** (configurable) | Nouvelle variable |
| Complétude minimale | Pas de seuil | **80%** des clés requises | Anti-dégradation silencieuse |
| Placeholders ICU | Regex basique | **Best effort** (regex + fallback) | Voir §2.9.1 — parser dédié en post-IMP3 |
| Faux positifs HTML | Non documenté | **Accepté** (regex large) | Voir §2.9.2 — tradeoff documenté |

---

## 5. Plan d'implémentation mis à jour (IMP3)

### 5.1 Tâches révisées

| ID | Tâche | Fichiers | Modifications vs étude originale |
|----|-------|---------|----------------------------------|
| IMP3-T001 | `OllamaProvider.translate()` | `core/ollama_provider.py` + tests | Ajout `PLACEHOLDER_PATTERNS`, `_extract_placeholders()` |
| IMP3-T002 | `OllamaProvider.translate_batch()` + chunking | `core/ollama_provider.py` + tests | Retry intelligent avec `error_context`, chunk_size=50 |
| IMP3-T003 | Validation structurelle stricte | `core/ollama_provider.py` + tests | **Élargi** : 5 contrôles (complétude, clés, types, profondeur, placeholders) + `OllamaValidationError` avec type + seuil 80% |
| IMP3-T004 | Configuration + Factory + CLI | `core/config.py` + `core/translator_factory.py` + `service.py` | Defaults modifiés : chunk=50, temp=0, nouveau `OLLAMA_MAX_RETRIES` |
| IMP3-T005 | Intégration mode_translate_json + Docker + checkpoint par chunk | `modes/mode_translate_json.py` + `docker-compose.yml` | **Élargi** : checkpoint par chunk quand provider=batch |
| IMP3-T006 | Tests d'intégration end-to-end | `tests/` | Tests placeholder, retry intelligent, validation structurelle |

### 5.2 Détail IMP3-T003 — Validation structurelle stricte

Tests unitaires à créer dans `tests/test_ollama_provider.py` :

| Test | Ce qu'il vérifie |
|------|-------------------|
| `test_validate_structure_completion_threshold_pass` | 80%+ clés présentes → réparation ciblée |
| `test_validate_structure_completion_threshold_fail` | < 80% clés présentes → rejet complet + `completion_threshold` |
| `test_validate_structure_completion_empty_response` | `{}` sur chunk de 50 → rejet complet |
| `test_validate_structure_completion_near_threshold` | 79% → rejet, 80% → réparation |
| `test_validate_structure_keys_match` | Clés identiques → OK |
| `test_validate_structure_missing_keys` | Clés manquantes → inject original + raise |
| `test_validate_structure_extra_keys` | Clés en trop → supprimer + raise |
| `test_validate_structure_type_coercion_int` | `5` → `"5"` (coercion OK) |
| `test_validate_structure_type_coercion_float` | `3.14` → `"3.14"` (coercion OK) |
| `test_validate_structure_type_nested_object` | `{"k": {"nested": "v"}}` → garder original |
| `test_validate_structure_type_bool` | `true` → `"True"` (coercion) |
| `test_validate_structure_type_null` | `null` → garder original |
| `test_placeholder_percent_s` | `"%s"` conservé dans traduction |
| `test_placeholder_percent_d` | `"%d items"` → `"%d articles"` |
| `test_placeholder_curly_name` | `"{name}"` conservé |
| `test_placeholder_double_curly` | `"{{count}}"` conservé |
| `test_placeholder_icu_plural` | `"{count, plural, one{item} other{items}}"` conservé |
| `test_placeholder_html_tags` | `"<b>text</b>"` conservé |
| `test_placeholder_escape_sequences` | `"Line1\\nLine2"` conservé |
| `test_placeholder_mismatch_fallback` | Placeholder manquant → fallback original |
| `test_placeholder_multiple` | Plusieurs placeholders dans une même chaîne |
| `test_placeholder_icu_nested_limitation` | ICU nested partiellement capturé → best effort + fallback |
| `test_placeholder_html_false_positive` | `"value < threshold"` → `< threshold` capturé comme HTML (faux positif accepté) |
| `test_retry_injects_error_context` | Le 2e essai contient le contexte d'erreur |
| `test_retry_success_after_error` | Retry réussit après injection d'erreur |
| `test_retry_exhausted_fallback` | Après max retries → garder original |

### 5.3 Détail IMP3-T005 — Checkpoint par chunk

**Comportement actuel** (`mode_translate_json.py`) :
- Checkpoint tous les N entrées individuelles
- Le callback fusionne les résultats

**Nouveau comportement** (quand `provider` supporte `translate_batch`) :
- Checkpoint après chaque **chunk** réussi
- Le checkpoint sauvegarde les résultats du chunk dans le fichier de sortie
- En cas de crash, la reprise commence au prochain chunk non traduit

**Logique de détection :**
```python
# Dans mode_translate_json.py
if hasattr(provider, 'translate_batch'):
    # Mode batch : checkpoint par chunk
    use_batch_mode = True
else:
    # Mode classique : checkpoint par entrées individuelles
    use_batch_mode = False
```

---

## 6. Vision stratégique (direction technique)

Le directeur technique souligne que le vrai gain n'est pas seulement la réduction du trafic réseau :

| Avantage | Description |
|----------|-------------|
| **Déterminisme** | Température 0, même entrée → même sortie |
| **Contrôle** | Validation structurelle stricte, pas de surprise |
| **Stabilité** | Pas de rate limiting externe, pas de 429 |
| **Confidentialité** | Aucune donnée ne quitte la machine |
| **Coût prévisible** | Zéro coût par requête, coût fixe (RAM + modèle) |
| **Indépendance réseau** | Fonctionne offline, sur connexion mobile instable |

C'est une **amélioration d'architecture**, pas une optimisation : passage d'un scraping fragile vers un pipeline de localisation industrialisable.

---

## 7. Récapitulatif des modifications vs étude originale

| Point | Étude originale | Amendement | Impact |
|-------|----------------|------------|--------|
| Chunk size par défaut | 100 | **50** | `config.py`, `_chunk_items` |
| Température par défaut | 0.1 | **0** | `config.py`, `_make_request` |
| Validation | Clés + JSON valide | **5 contrôles** : complétude (80%), clés, types, profondeur, placeholders | `_validate_structure` (nouvelle) + `COMPLETION_THRESHOLD` |
| Placeholders | Mentionnés dans le prompt | **Validation programmatique** : extraction + comparaison | `_extract_placeholders`, `_validate_placeholders` (nouvelles) |
| Retry | Même prompt renvoyé | **Injection d'erreur** dans le prompt de retry | `_build_prompt` (modifié), `translate_batch` (modifié) |
| `stream` | `False` | `False` (confirmé) | Aucun changement |
| Checkpoint | Par entrées | **Par chunk** quand provider=batch | `mode_translate_json.py` (modifié) |
| `OLLAMA_MAX_RETRIES` | Hardcodé (2) | **Configurable** via env var | `config.py` (ajout) |
| Anti-patterns | Non listés | **Explicitement exclus** | Documentation |
| Complétude minimale | Pas de seuil | **Seuil 80%** des clés requises, sinon rejet complet | `_validate_structure` (Check 0) + `COMPLETION_THRESHOLD` |
| Placeholders ICU | Regex basique | **Best effort** (regex partielle + fallback valeur par valeur) | Voir §2.9.1 — parser ICU dédié en post-IMP3 |
| Faux positifs HTML | Non documenté | **Accepté** (regex large `<[^>]+>` capte les comparaisons mathématiques) | Voir §2.9.2 — tradeoff documenté |
| Benchmark | Chunk size uniquement | **8 KPIs** : JSON invalide, corruption placeholders, temps/chunk, RAM, retries, fallbacks, tokens/sec, troncature | Voir §9 |


---

## 8. Prochaines étapes

1. ✅ Amendement validé par la direction technique
2. 🔲 Créer la branche `feat/IMP3-T001-ollama-provider`
3. 🔲 Implémenter IMP3-T001 : `OllamaProvider` + `translate()` + placeholders
4. 🔲 Implémenter IMP3-T002 : `translate_batch()` + chunking + retry intelligent
5. 🔲 Implémenter IMP3-T003 : Validation structurelle stricte
6. 🔲 Implémenter IMP3-T004 : Config + Factory + CLI
7. 🔲 Implémenter IMP3-T005 : Intégration mode_translate_json + checkpoint par chunk + Docker
8. 🔲 Implémenter IMP3-T006 : Tests d'intégration end-to-end
9. 🔲 `ollama pull qwen3`
10. 🔲 Benchmark détaillé (voir §9 ci-dessous)
11. 🔲 Reconstruire l'image Docker : `docker compose build translator`

---

## 9. Spécification du benchmark

Le benchmark ne doit PAS se limiter à "chunk size 50 vs 100 vs 200". Il doit mesurer les KPIs critiques pour valider la qualité du pipeline LLM défensif.

### 9.1 Métriques obligatoires

| Métrique | Pourquoi | Seuil acceptable |
|----------|----------|------------------|
| **Taux JSON invalide** | KPI principal — mesure la robustesse du format de sortie | < 5% par chunk |
| **Placeholder corruption rate** | Critique production — mesure la fiabilité de la conservation des patterns | < 1% des valeurs |
| **Temps par chunk** | Throughput réel — inclut appel LLM + validation + retry | Mesurer (baseline) |
| **RAM max** | Stabilité Docker — pic mémoire pendant l'exécution | < 2 GB au-dessus du modèle |
| **Retry frequency** | Qualité du modèle — nombre de retries par chunk | < 10% des chunks |
| **Fallback frequency** | Qualité finale — nombre de valeurs fallback vers original | < 5% des valeurs |
| **Tokens/sec** | Sizing infra — débit effectif du modèle | Mesurer (baseline) |
| **Output truncation rate** | Limite de contexte — réponses incomplètes | < 2% des chunks |

### 9.2 Protocole de benchmark

```
Pour chaque taille de chunk (50, 100, 200) :
  1. Lancer la traduction complète du fichier en 4.json (2642 entrées)
  2. Mesurer pour chaque chunk :
     - Temps de réponse
     - Nombre de retries
     - Nombre de fallbacks (valeurs originales conservées)
     - Nombre de placeholders corrompus
     - Taux de complétude (% de clés retournées)
  3. Mesurer globalement :
     - Temps total
     - RAM max (docker stats)
     - Nombre total de chunks avec au moins 1 retry
     - Nombre total de valeurs fallback
     - Nombre total de placeholders corrompus
     - Taux de troncature
  4. Comparer la qualité de traduction :
     - Échantillon manuel de 50 entrées par langue
     - Vérification programmatique de tous les placeholders
     - Vérification programmatique de toutes les clés
```

### 9.3 Dimensions du benchmark

| Dimension | Valeurs à tester |
|-----------|-----------------|
| Taille de chunk | 50, 100, 200 |
| Modèle | `qwen3` (principal), `mistral` (comparaison) |
| Langue cible | FR (langue proche), CZ (langue éloignée) |
| Température | 0 (défaut), 0.1 (comparaison) |

### 9.4 Résultat attendu

Le benchmark doit permettre de choisir :
1. La **taille de chunk optimale** (qualité vs vitesse)
2. Le **modèle optimal** (qualité vs vitesse vs RAM)
3. La **température optimale** (déterminisme vs légère variation)
4. Le **seuil de complétude** (80% est-il le bon seuil ?)
5. Le **nombre de retries optimal** (2 est-il suffisant ?)
