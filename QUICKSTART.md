# Quick Start Guide — COP Translation Service

This guide helps developers set up and use the COP Translation Service, including the orchestrated pipeline for JSON and XLSX (dropdown) translations.

---

## Prerequisites

### Option A — Docker (Recommended)

1. **Install Docker Desktop**: https://www.docker.com/products/docker-desktop/
2. **Launch Docker Desktop** (wait until the whale icon in the status bar is steady)
3. **Verify installation** in a terminal:
   ```bash
   docker --version
   docker compose version
   docker info
   ```
   All three commands should return version/info without errors.

### Option B — Local Python (if Docker is not available)

1. **Install Python 3.11+**: https://www.python.org/downloads/
2. **Verify installation**:
   ```bash
   python --version
   ```
   Should display `Python 3.11.x` or higher.

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url> COP_translations
cd COP_translations
```

### 2a. Docker setup (no installation needed)

Docker builds the environment automatically on first run. No manual setup required — just run any command from the sections below.

### 2b. Local Python setup

```bash
cd translator
python -m venv .venv

# Activate the virtual environment:
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
```

---

## Using the Pipeline (Orchestrated Translation)

The pipeline (`pipeline.py`) orchestrates the full translation workflow in a single command: detection → comparison → typo correction → gap analysis → report → confirmation → pre-population → translation → reordering → validation → misalignment detection → final report.

### Basic Usage

#### Docker

```bash
# Dry-run (analysis only, no translation, no file writes)
docker compose -f translator/docker-compose.yml run --rm --build pipeline --dry-run --languages fr,de

# Full run with Google Translate (interactive confirmations)
docker compose -f translator/docker-compose.yml run --rm --build pipeline --languages fr,de

# Full run with auto-confirm (non-interactive)
docker compose -f translator/docker-compose.yml run --rm --build pipeline --yes --languages fr,de --provider google

# Dropdown (XLSX) mode
docker compose -f translator/docker-compose.yml run --rm --build pipeline --mode dropdown --source /app/source/dropdown.xlsx --languages pt,es,hu --yes
```

#### Local Python

```bash
cd translator

# Dry-run
python pipeline.py --dry-run --languages fr,de

# Full run with auto-confirm
python pipeline.py --yes --languages fr,de --provider google

# Dropdown mode
python pipeline.py --mode dropdown --source source/dropdown.xlsx --languages pt --yes
```

### CLI Options

| Option | Description | Default |
|---|---|---|
| `--dry-run` | Analysis only — no translation, no file writes | `false` |
| `--languages fr,de` | Target languages (comma-separated) | All (except `en`) |
| `--provider` | `google` / `ollama` / `hybride` | `hybride` |
| `--source PATH` | Override source file detection | Auto-detect latest `*_Import` |
| `--prev-source PATH` | Override previous source detection | Auto-detect |
| `--mode` | `json` or `dropdown` | Auto-detect by file extension |
| `--yes` / `-y` | Non-interactive mode (auto-confirm all steps) | `false` |
| `--report PATH` | Write analysis report to a markdown file | stdout |
| `--format` | `json` / `xlsx` / `auto` (dropdown only) | `auto` |
| `--retranslate-all` | Ignore cache (column B) — re-translate all languages | `false` |
| `--retranslate fr,de` | Re-translate specific languages only | — |
| `--no-cache` | Disable translation cache (`.translation_cache.json`) | `false` |

### The 11 Steps

| Step | Description | Confirmation? |
|---:|---|:---:|
| 1 | Detect source file (latest `*_Import`) + previous source | |
| 2 | Compare sources (added/removed/modified keys) | |
| 3 | Detect known source typos + interactive correction + reference-CSV duplicate-key check (`Export_*.csv`, advisory) | |
| 4 | Analyze translation gap per language | |
| 5 | Consolidated report + confirmation | ✅ |
| 6 | Pre-populate output folder + handle modified keys | ✅ |
| 7 | Translation (Google/Ollama, with cache reuse) | |
| 8 | Auto-reorder files to match source key order | |
| 9 | Structural validation (missing/extra/empty/placeholders/duplicates) | |
| 10 | Misalignment detection (intra-language token overlap) + duplicated translations (different EN → identical translation) | |
| 11 | Final consolidated report → `doc/{date}_Pipeline_Report.md` | |

---

## Using the Classic Translation Service

For direct translation without the full pipeline orchestration:

### Docker

```bash
# Translate JSON (EN → FR)
docker compose -f translator/docker-compose.yml up --build

# Translate JSON (EN → FR) with Ollama
TRANSLATION_PROVIDER=ollama docker compose -f translator/docker-compose.yml up --build

# Translate dropdowns from XLSX
docker compose -f translator/docker-compose.yml run --rm --build \
  python service.py translate-dropdowns -i /app/source/dropdown.xlsx --batch-langs pt,es,hu --format json
```

### Local Python

```bash
python service.py translate-json -s en -t fr -i source.json
python service.py translate-dropdowns -i dropdown.xlsx --batch-langs pt,es,hu --format json
python service.py --help
```

---

## Running Tests & Lint

### Docker

```bash
# Run all tests (1047 locally; 873 in Docker — repo-root tests skipped by design)
docker compose -f translator/docker-compose.yml run --rm --build test

# Run lint (ruff check + format)
docker compose -f translator/docker-compose.yml run --rm lint
```

### Local Python

```bash
cd translator
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Run tests
pytest tests/ -v

# Run lint
ruff check . && ruff format --check .
```

---

## Supported Languages

| Code | Language | Provider target code |
|---|---|---|
| `fr` | French | `fr` |
| `cz` | Czech | `cs` |
| `sk` | Slovak | `sk` |
| `de` | German | `de` |
| `it` | Italian | `it` |
| `ar` | Arabic | `ar` |
| `pt` | Portuguese | `pt` |
| `es` | Spanish | `es` |
| `hu` | Hungarian | `hu` |
| `pl` | Polish | `pl` |

> `en` is the source language (not a target).

---

## Project Structure

```
COP_translations/
├── translator/
│   ├── pipeline.py              # Orchestrated pipeline (JSON + dispatcher)
│   ├── pipeline_dropdown.py    # Orchestrated pipeline (XLSX dropdown)
│   ├── pipeline_common.py      # Shared kernel (helpers, context)
│   ├── service.py              # Classic CLI service
│   ├── core/                   # Core modules (config, cache, translator, etc.)
│   ├── modes/                  # Translation modes
│   ├── tests/                  # Test suite (1047 tests)
│   ├── source_typos.json       # Known source typos dictionary
│   ├── docker-compose.yml      # Docker services
│   ├── Dockerfile              # Main Docker image
│   ├── Dockerfile.pipeline     # Pipeline Docker image (includes root scripts)
│   └── requirements*.txt      # Python dependencies
├── compare_sources.py          # Source comparison (used by pipeline)
├── analyze_translation_gap.py  # Gap analysis (used by pipeline)
├── README.md                   # Full documentation (FR)
├── README.en.md                # Full documentation (EN)
└── doc/                         # Technical documentation
```

---

## Translation Providers

| Provider | Setup | Rate Limit | Network |
|---|---|---|---|
| **Google Translate** (default) | None | ~5 req/s | Yes (scraping) |
| **Ollama** | Install + run `ollama serve` | Unlimited (local) | No (local) |
| **DeepL** | API key required | 500k chars/month (free) | Yes (API) |

### Using Ollama

```bash
# Start Ollama locally
ollama serve

# Run pipeline with Ollama
python pipeline.py --yes --languages fr,de --provider ollama --ollama-model minimax-m3:cloud
```

---

## Common Workflows

### 1. New source file received

```bash
# 1. Place the new source JSON in translator/source/{date}_Import/
# 2. Run dry-run to see what changed
python pipeline.py --dry-run --languages fr,de

# 3. Run full translation
python pipeline.py --yes --languages fr,de --provider google
```

### 2. Add a new language

```bash
# Add the language to core/config.py LANGUAGES dict
# Then run the pipeline for the new language only
python pipeline.py --yes --languages pl --provider google
```

### 3. Re-translate a specific language (ignore cache)

```bash
python pipeline.py --yes --languages fr --retranslate-all --provider google
```

### 4. Translate dropdown XLSX

```bash
python pipeline.py --mode dropdown --source source/dropdown.xlsx --languages pt,es,hu --yes
```

---

## Troubleshooting

### Docker: "Cannot connect to the Docker daemon"
- Make sure Docker Desktop is running (whale icon in status bar)

### Docker: "No module named 'compare_sources'"
- Use `Dockerfile.pipeline` (already configured in `docker-compose.yml` for the `pipeline` service)

### Python: "ModuleNotFoundError"
- Make sure the virtual environment is activated: `source .venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Google Translate: "Failed to resolve 'translate.google.com'"
- Check internet connection
- Or use Ollama instead: `--provider ollama`

### Pipeline: "FileNotFoundError" for a new language
- The language must be added to `core/config.py` `LANGUAGES` dict first

---

## Questions?

- Full documentation: `README.md` (FR) / `README.en.md` (EN)
- Pipeline architecture: `doc/2026_07_08_Pipeline_Orchestre_Analyse.md`
- Dropdown pipeline: `doc/2026_07_09_Pipeline_Dropdown_Integration_Etude.md`
- Quality audit: `doc/2026_07_13_Code_Quality_Audit.md`