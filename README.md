# COP Translation Service

**Service de traduction générique pour le projet COP — Version 2.0**

Traduction automatique de fichiers JSON et XLSX via Google Translate ou DeepL, avec cache intelligent, rate limiting adaptatif, et interface CLI complète.

## Table des matières

- [Fonctionnalités](#fonctionnalités)
- [Structure du projet](#structure-du-projet)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Modes d'opération](#modes-dopération)
- [Multi-Provider et Fallback](#multi-provider-et-fallback)
- [Cache intelligent](#cache-intelligent)
- [Rate limiter adaptatif](#rate-limiter-adaptatif)
- [Langues supportées](#langues-supportées)
- [Configuration](#configuration)
- [Tests](#tests)
- [Qualité de code](#qualité-de-code)
- [Documentation](#documentation)
- [Contribution](#contribution)
- [Licence](#licence)

## Fonctionnalités

| Fonctionnalité | Description |
|---------------|-------------|
| **Multi-Provider** | Google Translate (gratuit) ou DeepL (API key), avec fallback automatique |
| **Cache intelligent** | Traductions mises en cache sur disque, évitant les re-traductions |
| **Rate limiter adaptatif** | Backoff exponentiel avec persistance, sans double pénalité |
| **Interface CLI** | `translate-json`, `translate-dropdowns`, `analyze` avec options complètes |
| **CLI Provider** | Flags `--provider`, `--deepl-api-key`, `--deepl-use-free-api`, `--fallback` sur tous les subcommands |
| **Exécution locale** | Détection Docker/local automatique, chemins adaptés |
| **Checkpoint automatique** | Sauvegarde intermédiaire tous les 100 entrées |
| **Pre-commit hooks** | ruff lint+format, trailing whitespace, YAML/JSON check, pytest-quick |
| **CI optionnelle** | GitHub Actions : lint, test, build Docker |

## Structure du projet

```
COP_translations/
├── .github/workflows/ci.yml        # CI GitHub Actions (optionnel)
├── .pre-commit-config.yaml          # Pre-commit hooks
├── doc/                             # Documentation technique
│   ├── 2026_05_06_*_Study.md        # Étude d'améliorations
│   └── 2026_05_08_*_Tracking.md    # Suivi d'implémentation
├── translator/
│   ├── core/
│   │   ├── cache.py                 # Cache intelligent de traductions
│   │   ├── config.py                # Configuration centralisée (env + CLI)
│   │   ├── io_json.py               # Lecture/écriture JSON (plat + structuré)
│   │   ├── io_xlsx.py               # Lecture/écriture XLSX
│   │   ├── rate_limiter.py          # Rate limiter adaptatif avec persistance
│   │   ├── translator.py             # Logique de traduction (provider + cache + rate limit)
│   │   └── translator_factory.py     # Factory de providers (Google, DeepL, Fallback)
│   ├── modes/
│   │   ├── mode_translate_json.py   # Mode traduction JSON
│   │   ├── mode_translate_dropdowns.py # Mode génération dropdowns
│   │   └── mode_analyze.py           # Mode analyse XLSX
│   ├── tests/                       # 620 tests unitaires (96% couverture)
│   ├── service.py                   # Point d'entrée CLI
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pytest.ini
├── source/                           # Fichiers source (.gitkeep)
├── output/                           # Fichiers traduits (.gitkeep)
└── README.md
```

## Prérequis

- **Docker** (version 20.10+) et **Docker Compose** (version 2.0+)
- **Python 3.11+** uniquement pour le développement local (pre-commit, tests)
- **Clé API DeepL** (optionnel, pour utiliser DeepL ou le fallback)

## Installation

### Avec Docker (recommandé)

```bash
git clone https://github.com/mickeymick25/Translator.git
cd COP_translations

# Builder l'image
docker compose -f translator/docker-compose.yml build

# Lancer les tests
docker compose -f translator/docker-compose.yml run --rm --build test

# Lancer une traduction
docker compose -f translator/docker-compose.yml up --build
```

### Développement local

> **Note :** L'installation locale de Python et d'un virtualenv (`.venv/`) n'est **pas requise**. Tout tourne en Docker, y compris les pre-commit hooks (lint + tests). Le hook git `pre-commit` exécute automatiquement `ruff check`, `ruff format --check` et `pytest` via Docker.

```bash
cd COP_translations

# Lancer les tests
docker compose -f translator/docker-compose.yml run --rm --build test

# Lancer le lint (ruff check + ruff format --check)
docker compose -f translator/docker-compose.yml run --rm lint

# Les pre-commit hooks s'exécutent automatiquement via Docker avant chaque commit
# (pas besoin d'installer Python ou pre-commit localement)
```

## Utilisation

### Docker (mode par défaut)

```bash
# Traduction JSON EN → CS
docker compose -f translator/docker-compose.yml up --build

# Traduction JSON EN → FR
SOURCE_LANG=en TARGET_LANG=fr docker compose -f translator/docker-compose.yml up --build
```

### CLI (interface complète)

```bash
# Aide générale
python translator/service.py --help

# Traduction JSON
python translator/service.py translate-json --source-lang en --target-lang fr --input source.json

# Génération dropdowns multi-langues
python translator/service.py translate-dropdowns --input dropdown.xlsx --batch-langs en,fr,cz,sk,de,it,ar

# Analyse XLSX
python translator/service.py analyze --input dropdown.xlsx

# Mode dry-run (simule sans appeler l'API)
python translator/service.py translate-json --dry-run

# Mode verbose
python translator/service.py translate-json -v

# Mode quiet
python translator/service.py translate-json -q

# Utiliser DeepL comme provider
python translator/service.py translate-json --provider deepl --deepl-api-key YOUR_KEY -s en -t fr

# Activer le fallback entre providers
python translator/service.py translate-json --provider google --fallback --deepl-api-key YOUR_KEY

# Mode dry-run avec provider DeepL
python translator/service.py translate-json --provider deepl --deepl-api-key YOUR_KEY --dry-run
```

La CLI résout les paramètres dans cet ordre : **arguments CLI > variables d'environnement > valeurs par défaut**.

## Modes d'opération

| Mode | CLI | Description |
|------|-----|-------------|
| `translate-json` | `translate-json` | Traduit un fichier JSON plat vers une langue cible |
| `translate-dropdowns` | `translate-dropdowns` | Génère les traductions multi-langues depuis un XLSX |
| `analyze` | `analyze` | Analyse la structure d'un fichier XLSX |

## Multi-Provider et Fallback

Le service supporte deux providers de traduction avec fallback automatique :

| Provider | Clé API | Limite | Qualité |
|----------|---------|--------|---------|
| **Google Translate** | Aucune | 5 req/s | Standard |
| **DeepL (Free)** | Requise | 500k chars/mois | Supérieure |
| **DeepL (Pro)** | Requise | Selon forfait | Supérieure |

### Fallback automatique

Si le fallback est activé (`--fallback` ou `TRANSLATION_FALLBACK=true`) et qu'une clé DeepL est fournie, le service bascule automatiquement vers le provider secondaire après **3 erreurs 429 consécutives** sur le provider principal. La bascule est réversible : un appel réussi au fallback ramène au provider principal.

### Configuration des providers

| Variable | Défaut | Description |
|----------|--------|-------------|
| `TRANSLATION_PROVIDER` | `google` | Provider à utiliser : `google` ou `deepl` |
| `DEEPL_API_KEY` | *(vide)* | Clé API DeepL (requise pour `deepl`) |
| `DEEPL_USE_FREE_API` | `true` | Utiliser l'API gratuite DeepL (`true`/`false`) |
| `TRANSLATION_FALLBACK` | `false` | Activer le fallback automatique (`true`/`false`) |

```bash
# Via CLI flags (priorité sur les env vars)
python translator/service.py translate-json --provider deepl --deepl-api-key YOUR_KEY --fallback

# Via variables d'environnement
TRANSLATION_PROVIDER=deepl DEEPL_API_KEY=xxx TRANSLATION_FALLBACK=true \
  docker compose -f translator/docker-compose.yml up --build

# DeepL avec fallback Google
TRANSLATION_PROVIDER=deepl DEEPL_API_KEY=xxx TRANSLATION_FALLBACK=true \
  docker compose -f translator/docker-compose.yml up --build

# Google avec fallback DeepL
TRANSLATION_PROVIDER=google DEEPL_API_KEY=xxx TRANSLATION_FALLBACK=true \
  docker compose -f translator/docker-compose.yml up --build
```

## Cache intelligent

Le cache de traductions persiste sur disque (`output/.translation_cache.json`). Chaque traduction est stockée avec la clé `{source}:{target}:{text}`, garantissant l'unicité par paire de langues.

| Fonctionnalité | Détail |
|---------------|--------|
| **Activation** | `TRANSLATION_CACHE=true` (activé par défaut) |
| **Chemin du cache** | `output/.translation_cache.json` (Docker) ou `cwd/output/.translation_cache.json` (local) |
| **Flush différé** | Écrit en fin de batch, pas à chaque `put()` |
| **Statistiques** | Hits, misses, hit rate, total entries |

Le cache est consulté **avant** tout appel API : les termes déjà traduits ne sont jamais re-traduits.

## Rate limiter adaptatif

Le rate limiter gère automatiquement les limites de l'API Google Translate :

| Fonctionnalité | Détail |
|---------------|--------|
| **Détection 429** | Reconnu les erreurs "Too Many Requests" |
| **Backoff exponentiel** | Délai croissant : 0.2s → 0.4s → 0.8s → 1.6s... |
| **Pas de double pénalité** | Rate limiter et retry n'appliquent pas de backoff simultané |
| **Persistance** | État sauvegardé dans `output/.rate_limiter_state.json` |
| **Record success/error** | Lissé sur les appels, les succès reset progressivement les délais |

| Variable | Défaut | Description |
|----------|--------|-------------|
| `RATE_LIMITER_STATE_PATH` | *(auto)* | Chemin du fichier d'état du rate limiter |

## Langues supportées

| Code | Langue | Cible API | Colonne source |
|------|--------|-----------|----------------|
| `en` | Anglais | `en` | `origin` |
| `fr` | Français | `fr` | `french` |
| `cz` | Tchèque | `cs` | `origin` |
| `sk` | Slovaque | `sk` | `origin` |
| `de` | Allemand | `de` | `origin` |
| `it` | Italien | `it` | `origin` |
| `ar` | Arabe | `ar` | `origin` |

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MODE` | `translate-json` | Mode d'opération |
| `SOURCE_LANG` | `en` | Langue source |
| `TARGET_LANG` | `cs` | Langue cible (mode `translate-json`) |
| `SOURCE_FILE` | *(auto)* | Chemin vers le fichier source |
| `OUTPUT_DIR` | *(auto)* | Répertoire de sortie (`/app/output` en Docker, `cwd/output` en local) |
| `EXCEL_DIR` | *(auto)* | Répertoire des fichiers Excel |
| `DOC_DIR` | *(auto)* | Répertoire de documentation |
| `SOURCE_DIR` | *(auto)* | Répertoire des fichiers source JSON |
| `BATCH_LANGS` | `en,fr,cz,sk,de,it,ar` | Langues à générer (mode `translate-dropdowns`) |
| `OUTPUT_FORMAT` | `auto` | Format de sortie : `json`, `xlsx` ou `auto` |
| `TRANSLATION_CACHE` | `true` | Activer le cache de traductions |
| `TRANSLATION_CACHE_PATH` | *(auto)* | Chemin du fichier cache |
| `TRANSLATION_PROVIDER` | `google` | Provider : `google` ou `deepl` |
| `DEEPL_API_KEY` | *(vide)* | Clé API DeepL |
| `DEEPL_USE_FREE_API` | `true` | API gratuite DeepL |
| `TRANSLATION_FALLBACK` | `false` | Fallback automatique |

### Détection Docker/local

Les chemins par défaut s'adaptent automatiquement :

| Variable | Docker | Local |
|----------|--------|-------|
| `OUTPUT_DIR` | `/app/output` | `{cwd}/output` |
| `SOURCE_DIR` | `/app/source` | `{cwd}/source` |
| `EXCEL_DIR` | `/app/excel` | `{cwd}/excel` |
| `DOC_DIR` | `/app/doc` | `{cwd}/Doc` |

La détection repose sur la présence de `/.dockerenv` ou `/run/.containerenv`.

### Priorité de résolution

```
Arguments CLI > Variables d'environnement > Valeurs par défaut
```

## Tests

```bash
# Lancer tous les tests (Docker)
docker compose -f translator/docker-compose.yml run --rm --build test

# Lancer les tests en local (si env Python disponible)
python -m pytest translator/tests/ -x -q --tb=short

# Couverture par module
docker compose -f translator/docker-compose.yml run --rm --build test
```

| Module | Stmts | Miss | Cover |
|--------|-------|------|-------|
| core/cache.py | 70 | 2 | 97% |
| core/config.py | 111 | 0 | 100% |
| core/io_json.py | 46 | 0 | 100% |
| core/io_xlsx.py | 95 | 7 | 93% |
| core/rate_limiter.py | 67 | 2 | 97% |
| core/translator.py | 93 | 0 | 100% |
| core/translator_factory.py | 96 | 8 | 92% |
| modes/mode_analyze.py | 76 | 2 | 97% |
| modes/mode_translate_json.py | 123 | 13 | 89% |
| modes/mode_translate_dropdowns.py | 195 | 3 | 98% |
| **Total** | **972** | **37** | **96%** |

**620 tests** — TDD pour toutes les fonctionnalités métier.

## Qualité de code

### Pre-commit hooks

Les hooks s'exécutent automatiquement avant chaque commit, **entièrement via Docker** (aucune installation Python locale requise) :

| Étape | Commande Docker | Description |
|-------|----------------|-------------|
| Lint | `docker compose -f translator/docker-compose.yml run --rm lint` | `ruff check . && ruff format --check .` |
| Tests | `docker compose -f translator/docker-compose.yml run --rm --build test` | `pytest` avec couverture |

Le hook git `pre-commit` appelle automatiquement ces deux étapes. Il est installé dans `.git/hooks/pre-commit` et ne nécessite ni Python local ni virtualenv.

```bash
# Exécuter le lint manuellement
docker compose -f translator/docker-compose.yml run --rm lint

# Exécuter les tests manuellement
docker compose -f translator/docker-compose.yml run --rm --build test
```

> **Note :** Les hooks `ruff`, `ruff-format`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json` et `check-merge-conflict` sont toujours configurés dans `.pre-commit-config.yaml` et peuvent être activés si un environnement Python local est disponible.

### CI GitHub Actions (optionnel)

Le workflow `.github/workflows/ci.yml` se déclenche sur push `main`/`develop` et sur PR :

1. **lint** — ruff check + black check
2. **test** — pytest avec couverture
3. **build** — Docker build + smoke test

## Documentation

| Document | Description |
|----------|-------------|
| [`doc/2026_05_06_*_Study.md`](doc/2026_05_06_COP_Translation_Service_Improvements_Study.md) | Étude d'améliorations (spécification complète) |
| [`doc/2026_05_08_*_Tracking.md`](doc/2026_05_08_Implementation_Tracking.md) | Suivi d'implémentation détaillé (TDD, commits, couverture) |
| [`doc/2026_05_05_*_Study.md`](doc/2026_05_05_COP_Translation_Service_Study.md) | Étude fonctionnelle et technique initiale |
| [`doc/2026_05_11_*Roadmap*.md`](doc/2026_05_11_Roadmap_v2_0_Plan.md) | Roadmap v2.0 — Plan d'améliorations (IMP2-Txxx) |

## Contribution

### Branches

| Branche | Rôle |
|---------|------|
| `main` | Code stable |
| `feat/IMP-Txxx-description` | Branche par tâche |
| `feat/IMP2-Txxx-description` | Branche par tâche v2.0 |

Squash-merge vers `main` quand la tâche est terminée.

### Convention de commits

```
feat(scope): description
fix(scope): description
test(scope): description
docs(scope): description
chore: description
```

### Qualité

- **Pre-commit hooks** obligatoires (ruff lint+format, checks, pytest-quick)
- **TDD** pour toutes les fonctionnalités métier
- **89% couverture** minimum sur les modules core

## Historique des versions

| Version | Date | Description |
|---------|------|-------------|
| v2.0.0 | 2026-05-11 | Cache intelligent, rate limiter adaptatif, CLI, multi-provider, CLI Provider flags, pre-commit hooks, chemins locaux, 620 tests, 96% couverture |
| v1.0.0 | 2026-05-05 | Version initiale avec rate limiter intelligent |

## Licence

Ce projet est privé et confidentiel. Tous droits réservés.
