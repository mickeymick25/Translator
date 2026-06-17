# COP Generic Translation Service

Service de traduction générique pour le projet COP, avec support Google Translate, DeepL et **Ollama** (LLM local/cloud).

## Modes d'opération

| Mode | Description |
|------|-------------|
| `translate-json` | Traduit un fichier JSON plat source (EN) vers une langue cible |
| `translate-dropdowns` | Génère les fichiers de traduction multi-langues depuis un XLSX source |
| `analyze` | Analyse la structure d'un fichier XLSX et génère un rapport JSON |

## Providers

| Provider | Clé API | Qualité | Réseau |
|----------|---------|---------|--------|
| **Google Translate** | Aucune | Standard | Oui (scraping) |
| **DeepL** | Requise | Supérieure | Oui (API) |
| **Ollama** | Aucune | Variable | Non (local/cloud) |

## Utilisation avec Docker

```bash
# Google Translate (par défaut)
docker compose up --build

# Ollama (modèle cloud)
TRANSLATION_PROVIDER=ollama docker compose up --build

# Ollama avec modèle spécifique
TRANSLATION_PROVIDER=ollama OLLAMA_MODEL=glm-5.1:cloud docker compose up --build

# DeepL
TRANSLATION_PROVIDER=deepl DEEPL_API_KEY=xxx docker compose up --build

# Tests
docker compose run --rm --build test

# Lint
docker compose run --rm lint
```

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MODE` | `translate-json` | Mode d'opération |
| `SOURCE_LANG` | `en` | Langue source |
| `TARGET_LANG` | `cs` | Langue cible |
| `BATCH_LANGS` | `en,fr,cz,sk,de,it,ar` | Langues batch |
| `TRANSLATION_PROVIDER` | `google` | Provider : `google`, `deepl` ou `ollama` |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | URL serveur Ollama |
| `OLLAMA_MODEL` | `minimax-m3:cloud` | Modèle Ollama |
| `OLLAMA_CHUNK_SIZE` | `50` | Entrées par chunk |
| `OLLAMA_TEMPERATURE` | `0` | Température (0 = déterministe) |
| `OLLAMA_TIMEOUT` | `300` | Timeout par chunk (s) |
| `OLLAMA_MAX_RETRIES` | `2` | Max retries par chunk |
| `DEEPL_API_KEY` | *(vide)* | Clé API DeepL |
| `DEEPL_USE_FREE_API` | `true` | API gratuite DeepL |
| `TRANSLATION_FALLBACK` | `false` | Fallback automatique |

## Structure du projet

```
translator/
├── service.py                          # Point d'entrée CLI
├── core/
│   ├── config.py                       # Configuration (env + CLI)
│   ├── ollama_provider.py              # Provider Ollama (IMP3)
│   ├── translator.py                   # Logique de traduction
│   ├── translator_factory.py           # Factory (Google, DeepL, Ollama, Fallback)
│   ├── cache.py                        # Cache intelligent
│   ├── rate_limiter.py                # Rate limiter adaptatif
│   ├── io_json.py                      # Lecture/écriture JSON
│   └── io_xlsx.py                      # Lecture/écriture XLSX
├── modes/
│   ├── mode_translate_json.py          # Mode translate-json (checkpoint par chunk)
│   ├── mode_translate_dropdowns.py      # Mode translate-dropdowns
│   └── mode_analyze.py                 # Mode analyze
├── tests/                              # 723 tests (94% couverture)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

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