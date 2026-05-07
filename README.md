# Translation Service

**Service de traduction générique pour le projet COP**

Ce projet fournit un service de traduction capable de traduire des fichiers JSON plats et de générer des traductions multi-langues pour des dropdowns (XLSX/JSON).

## Table des matières

- [Fonctionnalités](#fonctionnalités)
- [Structure du projet](#structure-du-projet)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Modes d'opération](#modes-dopération)
- [Langues supportées](#langues-supportées)
- [Documentation](#documentation)
- [Contribution](#contribution)
- [License](#license)

## Fonctionnalités

- **Traduction JSON unilingue** — Traduit un fichier JSON plat (EN) vers une langue cible via Google Translate
- **Génération dropdowns multi-langues** — Génère les fichiers de traduction multi-langues depuis un XLSX source
- **Analyse de structure XLSX** — Analyse et génère un rapport JSON de la structure d'un fichier Excel
- **Rate limiting intelligent** — Gestion automatique des limites de requêtes Google Translate avec backoff exponentiel
- **Checkpoint automatique** — Sauvegarde intermédiaire tous les 100 entrées
- **Docker Ready** — Entièrement conteneurisé avec Docker

## Structure du projet

```
COP_translations/
├── .git/                         # Repository Git
├── Doc/                          # Documentation
│   └── 2026_05_05_COP_Translation_Service_Study.md
├── translator/                    # Code du service de traduction
│   ├── service.py                # Point d'entrée unique
│   ├── core/                     # Modules communs
│   │   ├── config.py             # Configuration centralisée
│   │   ├── translator.py        # Logique de traduction
│   │   ├── io_json.py            # Lecture/écriture JSON
│   │   └── io_xlsx.py            # Lecture/écriture XLSX
│   ├── modes/                    # Implémentation des modes
│   │   ├── mode_translate_json.py
│   │   ├── mode_translate_dropdowns.py
│   │   └── mode_analyze.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── source/                       # Fichiers JSON source
├── output/                        # Fichiers JSON traduits
├── excel/                        # Fichiers XLSX source
└── README.md                    # Ce fichier
```

## Prérequis

- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **Python 3.11+** (pour le développement local)

## Installation

### Avec Docker

```bash
# Cloner le repository
git clone https://github.com/[username]/COP_translations.git
cd COP_translations

# Builder l'image Docker
docker build -t translator-translator ./translator
```

### Développement local

```bash
cd translator
pip install -r requirements.txt
```

## Utilisation

### Docker (recommandé)

```bash
# Mode par défaut : traduction JSON
docker compose up --build

# Traduction JSON EN → FR
SOURCE_LANG=en TARGET_LANG=fr MODE=translate-json docker compose up --build

# Génération des dropdowns multi-langues
MODE=translate-dropdowns docker compose up --build

# Analyse d'un fichier XLSX
MODE=analyze docker compose up --build
```

### Développement local

```bash
cd translator
python service.py
```

## Modes d'opération

| Mode | Description |
|------|-------------|
| `translate-json` | Traduit un fichier JSON plat source (EN) vers une langue cible via Google Translate |
| `translate-dropdowns` | Génère les fichiers de traduction multi-langues depuis un XLSX source (dropdowns) |
| `analyze` | Analyse la structure d'un fichier XLSX et génère un rapport JSON |

## Langues supportées

| Code | Langue | Cible API |
|------|--------|-----------|
| `en` | Anglais | `en` |
| `fr` | Français | `fr` |
| `cz` | Tchèque | `cs` |
| `sk` | Slovaque | `sk` |
| `de` | Allemand | `de` |
| `it` | Italien | `it` |
| `ar` | Arabe | `ar` |

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MODE` | `translate-json` | Mode d'opération |
| `SOURCE_LANG` | `en` | Langue source |
| `TARGET_LANG` | `cs` | Langue cible (mode `translate-json`) |
| `SOURCE_FILE` | *(auto)* | Chemin vers le fichier source |
| `OUTPUT_DIR` | `/app/output` | Répertoire de sortie |
| `EXCEL_DIR` | `/app/excel` | Répertoire des fichiers Excel |
| `DOC_DIR` | `/app/doc` | Répertoire de documentation |
| `SOURCE_DIR` | `/app/source` | Répertoire des fichiers source JSON |
| `BATCH_LANGS` | `en,fr,cz,sk,de,it,ar` | Langues à générer (mode `translate-dropdowns`) |
| `OUTPUT_FORMAT` | `auto` | Format de sortie — `json`, `xlsx`, ou `auto` |

## Documentation

La documentation technique et fonctionnelle complète se trouve dans le répertoire `Doc/` :

- [`Doc/2026_05_05_COP_Translation_Service_Study.md`](Doc/2026_05_05_COP_Translation_Service_Study.md) — Étude fonctionnelle et technique complète

Pour plus de détails sur l'architecture et les décisions techniques, consultez cette étude.

## Gestion des Rate Limits

Le service intègre un **rate limiter intelligent** pour gérer les limites de Google Translate (5 requêtes/seconde) :

- **Détection automatique** des erreurs 429 (Too Many Requests)
- **Backoff exponentiel** : le délai double après chaque erreur de rate limit
- **Reprise automatique** via le système de checkpoints

### Recommandations

| Recommandation | Description |
|---------------|-------------|
| **Exécution séquentielle** | Préférer un seul conteneur à la fois pour les traductions critiques |
| **Checkpoint fréquents** | Vérifier le nombre d'entrées après chaque traduction |
| **API key dédiée** | Pour une utilisation intensive, utiliser une Google Cloud API key |

## Contribution

### Branches

| Branche | Rôle |
|---------|------|
| `main` | Production (code stable) |
| `develop` | Développement (code en cours) |
| `feature/*` | Nouvelles fonctionnalités |
| `hotfix/*` | Corrections urgentes |

### Convention de commits

```
type(scope): description
feat(translator): add exponential backoff
fix(rate-limiter): improve error detection
docs: update README
```

Types de commits : `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Historique des versions

| Version | Date | Description |
|---------|------|-------------|
| v1.0.0 | 2026-05-05 | Version initiale avec rate limiter intelligent |
| v0.9.0 | 2026-04-20 | Analyse de fusion et refactoring modulaire |

## License

Ce projet est privé et confidentiel. Tous droits réservés.

---

*Document généré le 2026-05-05*
