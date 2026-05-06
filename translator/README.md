
# COP Generic Translation Service

Service de traduction générique pour le projet COP, capable de traduire à la fois des fichiers JSON plats et des fichiers de dropdowns (XLSX/JSON) multi-langues.

## Modes d'opération

| Mode | Description |
|------|-------------|
| `translate-json` | Traduit un fichier JSON plat source (EN) vers une langue cible via Google Translate |
| `translate-dropdowns` | Génère les fichiers de traduction multi-langues depuis un XLSX source (dropdowns) |
| `analyze` | Analyse la structure d'un fichier XLSX et génère un rapport JSON |

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MODE` | `translate-json` | Mode d'opération |
| `SOURCE_LANG` | `en` | Langue source |
| `TARGET_LANG` | `cs` | Langue cible (mode `translate-json` uniquement) |
| `SOURCE_FILE` | *(auto)* | Chemin vers le fichier source |
| `OUTPUT_DIR` | `/app/output` | Répertoire de sortie |
| `EXCEL_DIR` | `/app/excel` | Répertoire des fichiers Excel |
| `DOC_DIR` | `/app/doc` | Répertoire de documentation |
| `SOURCE_DIR` | `/app/source` | Répertoire des fichiers source JSON |
| `BATCH_LANGS` | `en,fr,cz,sk,de,it,ar` | Langues à générer (mode `translate-dropdowns`) |
| `OUTPUT_FORMAT` | `auto` | Format de sortie — `json`, `xlsx`, ou `auto` |

## Utilisation avec Docker

```bash
# Mode par défaut : traduction JSON
docker compose up --build

# Traduction JSON EN → CS
SOURCE_LANG=en TARGET_LANG=cs MODE=translate-json docker compose up --build

# Génération des dropdowns multi-langues
MODE=translate-dropdowns docker compose up --build

# Analyse d'un fichier XLSX
MODE=analyze docker compose up --build
```

## Structure du projet

```
translator/
├── service.py              # Point d'entrée unique
├── core/                   # Modules communs
│   ├── __init__.py
│   ├── config.py           # Configuration centralisée (env vars)
│   ├── translator.py       # Logique de traduction API (retry, rate limiting)
│   ├── io_json.py          # Lecture/écriture JSON (plat et structuré)
│   └── io_xlsx.py          # Lecture/écriture XLSX et analyse
├── modes/                  # Implémentation des modes
│   ├── __init__.py
│   ├── mode_translate_json.py      # Mode translate-json
│   ├── mode_translate_dropdowns.py # Mode translate-dropdowns
│   └── mode_analyze.py             # Mode analyze
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

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

---

*Document généré automatiquement le 2026-04-20*
