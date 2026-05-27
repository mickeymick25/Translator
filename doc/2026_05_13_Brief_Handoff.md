# Brief de Transmission — COP Translation Service

**Date :** 2026-05-13
**Contexte :** Session de traduction du fichier `en 4.json` (2642 entrées, 6 langues cibles)
**Prochaine étape :** Implémentation du provider Ollama (IMP3)

---

## 1. État du Projet

### 1.1 Dépôt

- **Chemin :** `/Users/michaelboitin/Documents/02_Dev/COP_translations`
- **Structure :** `translator/` contient le code principal (`core/`, `modes/`, `tests/`, `service.py`)
- **Docker :** `translator/docker-compose.yml` (services: translator, test, lint)
- **Documentation :** `doc/` contient 7 documents d'étude et roadmap

### 1.2 Architecture actuelle

```
translator/
├── core/
│   ├── config.py                 # Configuration centralisée (env + CLI)
│   ├── cache.py                  # Cache intelligent de traductions
│   ├── rate_limiter.py           # Rate limiter adaptatif avec persistance
│   ├── translator.py              # Logique de traduction (provider + cache + rate limit)
│   ├── translator_factory.py     # Factory : GoogleProvider, DeepLProvider, FallbackProvider
│   ├── io_json.py                # Lecture/écriture JSON
│   └── io_xlsx.py                # Lecture/écriture XLSX
├── modes/
│   ├── mode_translate_json.py    # Mode traduction JSON (avec checkpoint, resume, batch)
│   ├── mode_translate_dropdowns.py
│   └── mode_analyze.py
├── tests/                         # 620+ tests (96% couverture)
├── service.py                     # CLI argparse (3 subcommands)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt / requirements-dev.txt
```

### 1.3 Providers actuels

| Provider | Classe | Implémentation | Problème |
|----------|--------|---------------|----------|
| Google | `GoogleProvider` | Scraping `translate.google.com` via `deep_translator` | **1 clé = 1 requête HTTP**, agressif pour le réseau |
| DeepL | `DeepLProvider` | API officielle via `deep_translator` | **1 clé = 1 requête**, nécessite clé API |
| Fallback | `FallbackProvider` | Composite (primaire + secondaire) | Même problème que les providers sous-jacents |

---

## 2. État des Traductions (2026_05_13_Import/en 4.json)

### 2.1 Fichier source

- **Fichier :** `translator/source/2026_05_13_Import/en 4.json`
- **Entrées :** 2642
- **Format :** JSON plat (clé → valeur en anglais)
- **Particularité :** Le nom de fichier contient un espace (`en 4.json`), ce qui nécessite de spécifier `SOURCE_FILE` explicitement (l'auto-détection ne fonctionne pas)

### 2.2 Progression des traductions

Les traductions ont été fusionnées avec l'export précédent (`2026_05_05_Export/`), puis nettoyées (entrées identiques à la source retirées pour re-traduction).

| Langue | Fichier | Entrées traduites | Reste à traduire | Notes |
|--------|---------|-------------------|-----------------|-------|
| 🇫🇷 FR | `translation_en_fr.json` | 2460 (93%) | ~100* | *Termes identiques EN/FR, probablement corrects |
| 🇩🇪 DE | `translation_en_de.json` | 1365 (51%) | ~1277 | Nettoyé, à re-traduire |
| 🇨🇿 CZ | `translation_en_cz.json` | 2565 (97%) | ~77 | Presque complet |
| 🇸🇰 SK | `translation_en_sk.json` | 1227 (46%) | ~1415 | Nettoyé, à re-traduire |
| 🇮🇹 IT | `translation_en_it.json` | 2116 (80%) | ~526 | Partiel |
| 🇸🇦 AR | `translation_en_ar.json` | 2495 (94%) | ~147 | Presque complet |

**Dossier de sortie :** `translator/output/2026_05_13_Export/`

### 2.3 Ancien export disponible

Le dossier `translator/output/2026_05_05_Export/` contient les traductions précédentes (2629 entrées par langue) qui ont été fusionnées dans les fichiers actuels. Ces fichiers peuvent servir de référence si besoin.

---

## 3. Bugs Corrigés Durant la Session

### 3.1 Bug du checkpoint (CRITIQUE — corrigé)

**Fichier :** `translator/modes/mode_translate_json.py`

**Problème :** Le callback de checkpoint écrasait le fichier de sortie avec uniquement les nouvelles traductions, au lieu de les fusionner avec les traductions existantes. Résultat : à chaque interruption, le fichier perdait toutes les traductions précédentes.

**Correctif appliqué :**
- `_create_checkpoint_callback()` reçoit maintenant `existing_data` en paramètre
- Le callback fusionne les nouvelles traductions avec les données existantes avant sauvegarde
- `_translated_data` est mis à jour incrémentalement dans le callback
- Le log du checkpoint affiche maintenant le nombre total d'entrées

**Code modifié :**

```python
# AVANT (bug)
def _create_checkpoint_callback(output_path, keys_to_translate):
    def checkpoint_callback(completed, results):
        checkpoint_data = dict(zip(keys_to_translate[:completed], results[:completed]))
        save_flat_json(output_path, checkpoint_data)  # ÉCRASE les données existantes !

# APRÈS (corrigé)
def _create_checkpoint_callback(output_path, keys_to_translate, existing_data):
    def checkpoint_callback(completed, results):
        new_translations = dict(zip(keys_to_translate[:completed], results[:completed]))
        merged_data = {**existing_data, **new_translations}  # FUSIONNE
        save_flat_json(output_path, merged_data)
        existing_data.update(new_translations)  # Mise à jour incrémentale
```

**Tests ajoutés :** 3 nouveaux tests dans `test_mode_translate_json.py` :
- `test_callback_merges_with_existing_data`
- `test_callback_existing_data_updated_on_subsequent_calls`
- `test_callback_new_translations_override_existing`

**Statut :** ✅ Corrigé et testé (16 tests passent). **L'image Docker n'a PAS été reconstruite** avec le fix — il faut `docker compose build translator` avant de relancer.

### 3.2 Fichier SK corrompu (corrigé)

Le fichier `translation_en_sk.json` était corrompu (entrée sans valeur `"CO_CO_TA_177",` au lieu de `"CO_CO_TA_177": "valeur"`). Corrigé manuellement via regex — 1314 entrées valides récupérées.

### 3.3 Fichier FR écrasé (partiellement récupéré)

Le fichier `translation_en_fr.json` a été écrasé plusieurs fois par le bug du checkpoint :
- 1700 entrées → 700 (1er crash) → 900 (2e run) → 2069 (nettoyage manuel) → 300 (3e crash)
- Récupéré via fusion avec l'ancien export `2026_05_05_Export/translation_en_fr.json` (2629 entrées)
- État final : 2460 entrées correctement traduites + 100 identiques à la source (probablement correctes)

---

## 4. Problème Infrastructure : Google Translate Scraping vs Réseau Mobile

### 4.1 Problème identifié

Le provider Google Translate utilise `googletrans` qui **scrape le site web** Google Translate (`translate.google.com/m?...`). Chaque traduction :
- Ouvre une nouvelle connexion HTTPS (TLS handshake)
- Charge une page HTML complète
- Ferme la connexion

À 0.15s d'intervalle → **~6,7 requêtes/seconde, ~24 000 requêtes/heure**

Sur un partage de connexion mobile :
- Saturation des tables NAT du téléphone
- Surcharge CPU du modem
- Rate limiting de Google (erreurs 429 → boucle de retry → trafic exponentiel)
- Chute de la connexion

### 4.2 Solutions envisagées

| Solution | Avantages | Inconvénients |
|----------|-----------|--------------|
| **Ollama (LLM local)** | Zéro trafic externe, ~15-30 requêtes pour 2642 entrées, confidentialité | Qualité variable, 4-8 GB RAM |
| DeepL API | Qualité supérieure, API officielle | Nécessite clé API, trafic externe |
| Réseau WiFi stable | Fonctionne avec l'existant | Pas toujours disponible |
| Augmenter le rate limit | Simple | Ne résout pas le problème fondamental |

### 4.3 Solution retenue

**Ollama (LLM local)** — Étude complète rédigée dans `doc/2026_05_13_Ollama_Provider_Study.md`

---

## 5. Étude Ollama — Décisions Architecturales

**Document :** `doc/2026_05_13_Ollama_Provider_Study.md` (719 lignes)

### 5.1 Décisions clés

| Décision | Choix | Raison |
|----------|-------|--------|
| Pattern d'intégration | `TranslationProvider` ABC | S'intègre dans l'architecture existante sans casser Google/DeepL |
| Stratégie de traduction | Chunking (50-200 entrées par requête) | Réduit le nombre de requêtes de 99% |
| Modèle recommandé | `qwen3` | Bon multilingue, bon JSON, 4.7GB |
| Taille de chunk par défaut | 100 entrées | Bon équilibre qualité/complétude |
| Validation JSON | Strict : vérification des clés, extraction du JSON, retry | Les LLM peuvent produire du JSON invalide |
| Fallback | Texte original si échec | Comportement identique aux providers existants |
| API Ollama | `/api/generate` avec `stream: False` | API simple, pas de streaming nécessaire |

### 5.2 Plan d'implémentation (TDD)

| ID | Tâche | Fichiers |
|----|-------|---------|
| IMP3-T001 | `OllamaProvider.translate()` | `core/ollama_provider.py` + tests |
| IMP3-T002 | `OllamaProvider.translate_batch()` + chunking | `core/ollama_provider.py` + tests |
| IMP3-T003 | Validation JSON + retry | `core/ollama_provider.py` + tests |
| IMP3-T004 | Configuration + Factory + CLI | `core/config.py` + `core/translator_factory.py` + `service.py` |
| IMP3-T005 | Intégration mode_translate_json + Docker | `modes/mode_translate_json.py` + `docker-compose.yml` |
| IMP3-T006 | Tests d'intégration end-to-end | `tests/` |

### 5.3 Variables de configuration

| Variable | Défaut | Description |
|----------|--------|-------------|
| `TRANSLATION_PROVIDER` | `google` | Ajouter `ollama` |
| `OLLAMA_URL` | `http://localhost:11434` | URL du serveur Ollama |
| `OLLAMA_MODEL` | `qwen3` | Modèle à utiliser |
| `OLLAMA_CHUNK_SIZE` | `100` | Taille des chunks |
| `OLLAMA_TEMPERATURE` | `0.1` | Température du modèle |
| `OLLAMA_TIMEOUT` | `300` | Timeout par chunk (secondes) |

### 5.4 Docker

Pour que le conteneur Docker accède à Ollama sur le host :
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
environment:
  - OLLAMA_URL=http://host.docker.internal:11434
```

### 5.5 Ollama est installé

- **Version :** 0.23.3
- **URL :** `http://localhost:11434`
- **Modèles disponibles :** `glm-5.1:cloud`, `minimax-m2.7:cloud` (cloud uniquement)
- **Action requise :** `ollama pull qwen3` pour installer un modèle local

---

## 6. Commandes Utiles

### 6.1 Reconstruire l'image Docker (incluant le fix du checkpoint)

```bash
cd translator && docker compose build translator
```

### 6.2 Lancer une traduction (une langue à la fois)

```bash
# FR
cd translator && docker compose run --rm -e MODE=translate-json -e SOURCE_LANG=en \
  -e "SOURCE_FILE=/app/source/2026_05_13_Import/en 4.json" \
  -e "BATCH_LANGS=fr" translator

# CZ
cd translator && docker compose run --rm -e MODE=translate-json -e SOURCE_LANG=en \
  -e "SOURCE_FILE=/app/source/2026_05_13_Import/en 4.json" \
  -e "BATCH_LANGS=cz" translator
```

### 6.3 Vérifier l'état des traductions

```bash
python3 -c "
import json, os
d = 'translator/output/2026_05_13_Export'
for f in sorted(os.listdir(d)):
    if f.endswith('.json'):
        try:
            data = json.load(open(os.path.join(d, f)))
            print(f'{f}: {len(data)} / 2642 ({len(data)*100//2642}%)')
        except Exception as e:
            print(f'{f}: ERREUR - {e}')
"
```

### 6.4 Nettoyer les entrées non traduites (identiques à la source)

```python
import json
source = json.load(open('translator/source/2026_05_13_Import/en 4.json'))
for lang in ['fr', 'cz', 'sk', 'de', 'it', 'ar']:
    f = f'translator/output/2026_05_13_Export/translation_en_{lang}.json'
    data = json.load(open(f))
    cleaned = {k: v for k, v in data.items() if v != source.get(k, '') or not source.get(k, '').strip()}
    with open(f, 'w', encoding='utf-8') as fh:
        json.dump(cleaned, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print(f'{lang}: {len(data)} -> {len(cleaned)} entries')
```

---

## 7. Points d'Attention

### 7.1 Image Docker à reconstruire

L'image Docker **n'a pas été reconstruite** avec le fix du checkpoint. Avant de relancer les traductions, il faut :

```bash
cd translator && docker compose build translator
```

### 7.2 Fichier source avec espace

Le fichier `en 4.json` contient un espace dans son nom. L'auto-détection ne fonctionne pas. Il faut toujours spécifier `SOURCE_FILE` explicitement.

### 7.3 Orphan containers

Docker signale un conteneur orphelin `cop_generate_dropdowns`. Pour le nettoyer :

```bash
cd translator && docker compose run --rm --remove-orphans translator
```

### 7.4 Version Docker Compose obsolète

Le `docker-compose.yml` contient `version: "3.8"` qui est obsolète. Docker émet un warning. Peut être retiré sans impact.

---

## 8. Prochaines Étapes

1. **Implémenter IMP3-T001** : Créer `OllamaProvider` avec `translate()` et `translate_batch()`
2. **Installer le modèle** : `ollama pull qwen3`
3. **Reconstruire l'image Docker** : `cd translator && docker compose build translator`
4. **Tester Ollama** : Lancer une traduction avec `--provider ollama`
5. **Compléter les traductions** : Terminer les entrées manquantes pour DE, SK, IT, AR, CZ
6. **Valider la qualité** : Comparer les traductions Ollama vs Google vs DeepL

---

## 9. Documents de Référence

| Document | Chemin |
|----------|--------|
| Étude Ollama | `doc/2026_05_13_Ollama_Provider_Study.md` |
| Étude d'améliorations v1 | `doc/2026_05_06_COP_Translation_Service_Improvements_Study.md` |
| Suivi d'implémentation | `doc/2026_05_08_Implementation_Tracking.md` |
| Roadmap v2.0 | `doc/2026_05_11_Roadmap_v2_0_Plan.md` |
| Étude initiale | `doc/2026_05_05_COP_Translation_Service_Study.md` |
| Analyse comparative | `doc/Translation_Comparison_Analysis.md` |