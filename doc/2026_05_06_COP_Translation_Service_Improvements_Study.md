# Étude d'Améliorations — Service de Traduction COP

**Date :** 2026-05-06
**Auteur :** Analyse technique
**Version :** 1.2
**Statut :** MIS À JOUR
**Révision v1.1 :** 2026-05-07 — Revue critique des recommandations, correction des implémentations proposées, révision des priorités, ajout IMP-T006
**Révision v1.2 :** 2026-05-08 — Ajustement au contexte d'exécution locale (pas de déploiement serveur/CI), révision des priorités IMP-T002 et IMP-T005, ajout du suivi d'implémentation

> **Contexte d'exécution** : Ce service est conçu pour être exécuté **localement** par les développeurs, pas pour un déploiement serveur ou cloud. Cela modifie sensiblement la pertinence de certaines recommandations (CI/CD, CLI, Docker).

---

## 1. Résumé Exécutif

Cette étude identifie les axes d'amélioration du Service de Traduction COP suite à son utilisation en production. Le service est fonctionnel et stable, mais présente des opportunités significatives en termes de fiabilité, maintenabilité, et extensibilité.

### Points clés identifiés

| Axe | Impact | Complexité | Priorité initiale | Priorité v1.1 | Priorité v1.2 | Motif de révision v1.2 |
|-----|--------|------------|-------------------|---------------|---------------|------------------------|
| Cache intelligent | Élevée | Faible | Moyenne | **Haute** | **Haute** | = — ROI maximisé en local (runs répétés) |
| Tests unitaires | Élevée | Moyenne | Haute | **Haute** | **Haute** | = — Sécurise les itérations locales |
| Rate limiter adaptatif | Élevée | Faible | Haute | **Haute** | **Haute** | = — Utile même en local |
| Interface CLI | Élevée | Moyenne | Moyenne | Basse | **Moyenne** ⬆️ | Essentiel en local : les devs utilisent CLI, pas Docker Compose |
| CI/CD / Pre-commit | Faible | Faible | Haute | Moyenne | **Basse** ⬇️ | Pas de déploiement ; pre-commit hooks suffisent |
| Support Multi-provider | Moyenne | Élevée | Moyenne | Basse | **Basse** | = — Nécessite clé API, reste optionnel |
| Monitoring dashboard | Faible | Élevée | Basse | Basse | **Basse** | = — Non adapté à un outil batch local |

---

## 2. Évaluation de l'État Actuel

### 2.1 Forces du système actuel

| Force | Description |
|-------|-------------|
| **Architecture modulaire** | Séparation claire entre `core/` (moteur) et `modes/` (fonctionnalités) |
| **Rate limiting intelligent** | Backoff exponentiel implémenté avec succès |
| **Checkpoint automatique** | Sauvegarde tous les 100 entrées, permettant la reprise après interruption |
| **Docker Ready** | Service entièrement conteneurisé et reproductible |
| **Multi-mode** | Trois modes distincts (`translate-json`, `translate-dropdowns`, `analyze`) |

> **Note v1.2** : Le Docker Ready est un atout pour la reproductibilité, mais en contexte local exclusif, un simple `venv` + `Makefile` pourrait être plus léger et plus rapide. Les chemins par défaut dans `config.py` (`/app/output`, `/app/source`) sont inadaptés à une exécution hors Docker.

### 2.2 Faiblesses identifiées

| Faiblesse | Impact | Gravité |
|-----------|--------|---------|
| **Pas de cache de traductions** | Re-traduction systématique des mêmes termes, gaspillage API | 🔴 Haute |
| **Pas de tests unitaires** | Risque de régression élevé | ⚠️ Haute |
| **Rate limiter sans mémoire** | Chaque exécution recommence à zéro | ⚠️ Haute |
| **Configuration via env vars uniquement** | Pas d'aide en ligne de commande, ergonomie médiocre en local | ⚠️ Haute |
| **Chemins par défaut Docker-only** | `config.py` utilise `/app/*` — inutilisable sans Docker | ⚠️ Moyenne |
| **Pas de CI/CD automatisé** | Pas de vérification automatique au commit | ⚠️ Basse |
| **Dépendant uniquement de Google Translate** | Pas d'alternative si rate limit permanent | ⚠️ Basse |

> **Note v1.2** : La faiblesse « Configuration via env vars » passe de Moyenne à Haute car en local, les développeurs tapent directement des commandes — les env vars sont peu ergonomiques sans Docker Compose. La faiblesse CI/CD passe de Haute à Basse car sans déploiement serveur, seuls des pre-commit hooks sont nécessaires.

### 2.3 Statistiques de qualité code

| Métrique | Valeur actuelle | Cible recommandée |
|----------|-----------------|-------------------|
| Couverture de tests | ~0% | >70% |
| Documentation API | Partielle | Complète |
| Nombre de dépendances directes | 2 | Maintenir au minimum |
| Taux de hit cache | 0% (pas de cache) | >50% (sur les runs répétés) |
| Temps moyen d'exécution (2629 entrées) | ~45 min | <30 min (avec cache : <10 min) |
| Taux de réussite traduction | ~95% | >99% |

---

## 3. Améliorations Détaillées

### 3.1 IMP-T001 : Tests Unitaires

#### Description

Ajouter une suite de tests unitaires complète pour valider le comportement des modules core et modes.

> ⚠️ **Revue v1.1** — Le code d'exemple original contenait des appels réels à l'API Google Translate dans les tests, ce qui les rend non-déterministes, lents et dépendants du réseau. La fonction `is_rate_limit_error()` était référencée mais n'existe pas dans le code actuel. Les corrections ci-dessous intègrent les mocks obligatoires, extraient la logique de détection, et enrichissent les fixtures.

#### Modules à tester

| Module | Tests prioritaires | Estimation | Estimation révisée |
|--------|-------------------|------------|--------------------|
| `core/translator.py` | `translate_text()`, retry logic, rate limit detection | 2h | 3h |
| `core/io_json.py` | Lecture/écriture JSON plat et structuré | 1h | 1.5h |
| `core/io_xlsx.py` | Chargement XLSX, extraction contexts | 1.5h | 2h |
| `core/config.py` | Validation variables d'environnement | 0.5h | 1h |
| `modes/mode_translate_json.py` | Flux complet de traduction JSON | 2h | 3h |
| `modes/mode_translate_dropdowns.py` | Génération multi-langues | 2h | 3h |
| **Total** | | **9h** | **13.5h** |

> Les estimations révisées tiennent compte du mocking nécessaire pour les appels API, les systèmes de fichiers temporaires, et le ThreadPoolExecutor.

#### Structure de tests proposée

```
translator/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Configuration pytest + fixtures
│   ├── test_translator.py       # Tests de core/translator.py
│   ├── test_io_json.py          # Tests de core/io_json.py
│   ├── test_io_xlsx.py          # Tests de core/io_xlsx.py
│   ├── test_config.py           # Tests de core/config.py
│   ├── test_mode_translate_json.py
│   ├── test_mode_translate_dropdowns.py
│   └── test_mode_analyze.py
└── pytest.ini                   # Configuration pytest
```

#### Prérequis : extraction de `is_rate_limit_error()`

Avant de pouvoir tester la détection de rate limit, il faut extraire la logique actuellement inline dans `translate_text()` vers une fonction dédiée :

```python
# core/translator.py — Ajout requis avant les tests

def is_rate_limit_error(error_msg: str) -> bool:
    """Détecte si une erreur est liée au rate limiting (429 / Too Many Requests)."""
    msg = error_msg.lower()
    return "too many requests" in msg or "429" in msg
```

#### Exemple de test pour translator.py

```python
# tests/test_translator.py
import pytest
from unittest.mock import patch, MagicMock
from core.translator import translate_text, is_rate_limit_error

class TestTranslateText:
    @patch("core.translator.GoogleTranslator")
    def test_translate_success(self, mock_translator_cls):
        """Test une traduction réussie (mockée)."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_translator_cls.return_value = mock_instance
        
        result = translate_text("Hello", "en", "fr")
        assert result == "Bonjour"
        mock_translator_cls.assert_called_once_with(source="en", target="fr")
    
    def test_translate_empty_returns_empty(self):
        """Test qu'un texte vide retourne une chaîne vide (pas d'appel API)."""
        result = translate_text("", "en", "fr")
        assert result == ""
    
    def test_translate_whitespace_returns_same(self):
        """Test qu'un texte composé d'espaces est retourné tel quel."""
        result = translate_text("   ", "en", "fr")
        assert result == "   "
    
    @patch("core.translator.GoogleTranslator")
    def test_translate_preserves_special_chars(self, mock_translator_cls):
        """Test que les caractères spéciaux sont préservés."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "100 %"
        mock_translator_cls.return_value = mock_instance
        
        result = translate_text("100%", "en", "fr")
        assert "%" in result
    
    def test_rate_limit_detection_too_many_requests(self):
        """Test la détection des erreurs 'Too Many Requests'."""
        assert is_rate_limit_error("Server Error: You made too many requests") is True
    
    def test_rate_limit_detection_429(self):
        """Test la détection du code HTTP 429."""
        assert is_rate_limit_error("HTTP 429 Too Many Requests") is True
    
    def test_rate_limit_not_triggered_on_other_errors(self):
        """Test qu'une erreur non-rate-limit n'est pas détectée comme telle."""
        assert is_rate_limit_error("ConnectionError: Network unreachable") is False

class TestRetryLogic:
    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.time.sleep")
    def test_retries_on_server_error(self, mock_sleep, mock_translator_cls):
        """Test que la logique retry fonctionne après erreur serveur."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = [
            Exception("Server Error: Internal Server Error"),
            Exception("Server Error: Internal Server Error"),
            "Résultat"
        ]
        mock_translator_cls.return_value = mock_instance
        
        result = translate_text("Test", "en", "fr", max_retries=3)
        assert result == "Résultat"
        assert mock_instance.translate.call_count == 3
    
    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.time.sleep")
    def test_max_retries_respected(self, mock_sleep, mock_translator_cls):
        """Test que le nombre max de retries est respecté et retourne le texte original."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception("Server Error: Persistent failure")
        mock_translator_cls.return_value = mock_instance
        
        result = translate_text("Test", "en", "fr", max_retries=2)
        assert result == "Test"  # Retourne l'original après échec
        assert mock_instance.translate.call_count == 2
    
    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.time.sleep")
    def test_rate_limit_triggers_backoff(self, mock_sleep, mock_translator_cls):
        """Test que le rate limit déclenche un backoff spécifique."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = [
            Exception("429 Too Many Requests"),
            "OK"
        ]
        mock_translator_cls.return_value = mock_instance
        
        result = translate_text("Test", "en", "fr", max_retries=3)
        assert result == "OK"
        # Vérifie que sleep a été appelé (backoff rate limit)
        assert mock_sleep.call_count >= 1
```

#### Fichier conftest.py

```python
# tests/conftest.py
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
import tempfile
import shutil

# ─── Fixtures : système de fichiers ────────────────────────────

@pytest.fixture
def temp_output_dir():
    """Crée un répertoire temporaire pour les tests de I/O."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def temp_json_flat_file(temp_output_dir, sample_json_flat):
    """Crée un fichier JSON plat temporaire sur disque."""
    filepath = temp_output_dir / "test_flat.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(sample_json_flat, f, ensure_ascii=False, indent=2)
    return filepath

@pytest.fixture
def temp_json_structured_file(temp_output_dir, sample_json_structured):
    """Crée un fichier JSON structuré temporaire sur disque."""
    filepath = temp_output_dir / "test_structured.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(sample_json_structured, f, ensure_ascii=False, indent=2)
    return filepath

# ─── Fixtures : données de test ─────────────────────────────────

@pytest.fixture
def sample_json_flat():
    """Fixture pour un JSON plat exemple."""
    return {
        "Btn_Home": "Home",
        "Btn_Action": "Action",
        "Btn_Cancel": "Cancel"
    }

@pytest.fixture
def sample_json_structured():
    """Fixture pour un JSON structuré exemple."""
    return {
        "metadata": {
            "language": "FR",
            "language_name": "Français",
            "source_file": "test.xlsx",
            "generated_date": "2026-05-06",
            "total_entries": 2
        },
        "contexts": {
            "btn": {
                "Button": "Bouton",
                "Cancel": "Annuler"
            },
            "menu": {
                "File": "Fichier"
            }
        }
    }

@pytest.fixture
def sample_dropdown_entries():
    """Fixture pour des entrées dropdown (format XLSX loadé)."""
    return [
        {"origin": "Button", "french": "Bouton", "context": "btn"},
        {"origin": "Cancel", "french": "Annuler", "context": "btn"},
        {"origin": "File", "french": "Fichier", "context": "menu"},
    ]

# ─── Fixtures : mocks API ──────────────────────────────────────

@pytest.fixture
def mock_google_translator():
    """Mock de GoogleTranslator qui retourne des traductions prédéfinies."""
    with pytest.mock.patch("core.translator.GoogleTranslator") as mock_cls:
        mock_instance = MagicMock()
        translations = {
            ("Hello", "en", "fr"): "Bonjour",
            ("Action", "en", "fr"): "Action",
            ("Cancel", "en", "fr"): "Annuler",
            ("Button", "en", "de"): "Taste",
            ("File", "en", "de"): "Datei",
        }
        def side_effect(source, target):
            mock_instance = MagicMock()
            def translate_func(text):
                key = (text, source, target)
                return translations.get(key, f"[{target}] {text}")
            mock_instance.translate = translate_func
            return mock_instance
        mock_cls.side_effect = side_effect
        yield mock_cls
```

#### Priorité : **HAUTE**

---

### 3.2 IMP-T002 : Qualité de Code — Pre-commit Hooks et CI optionnelle

#### Description

Mettre en place des vérifications automatiques de qualité de code exécutées localement à chaque commit via pre-commit hooks, avec une CI GitHub Actions optionnelle pour les projets collaboratifs.

> ⚠️ **Revue v1.1** — La proposition originale était surdimensionnée pour un projet batch privé. Le CD vers Docker Hub public est contradictoire avec le caractère confidentiel du projet.
>
> ⚠️ **Revue v1.2** — En contexte d'exécution locale uniquement, un pipeline CI/CD complet perd l'essentiel de sa valeur. Pas de déploiement, pas de review gate entre contributeurs, pas d'environnement cible. La priorité bascule vers les **pre-commit hooks** qui s'exécutent avant chaque commit sur la machine du développeur.

#### Approche recommandée : Pre-commit hooks (principal)

Les pre-commit hooks fournissent un retour immédiat au développeur, sans dépendre d'un serveur CI externe.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict

  - repo: local
    hooks:
      - id: pytest-quick
        name: pytest (quick)
        entry: python -m pytest translator/tests/ -x -q --tb=short
        language: system
        pass_filenames: false
        always_run: true
```

```bash
# Installation (one-time)
pip install pre-commit
pre-commit install

# Exécution manuelle sur tous les fichiers
pre-commit run --all-files
```

#### CI GitHub Actions (optionnelle — pour les projets collaboratifs)

> Si le projet évolue vers un développement collaboratif avec des PR, la CI reste utile comme filet de sécurité. Configuration recommandée dans ce cas :

| Workflow | Déclencheur | Actions | Statut |
|----------|-------------|---------|--------|
| `ci.yml` | Push sur `develop` + PR vers `main`/`develop` | Lint, tests, build Docker (vérification) | 🟡 Optionnel |
| `cd.yml` | Tag `v*` | Build & push image GHCR (privé) | 🟡 Optionnel |

```yaml
# .github/workflows/ci.yml (optionnel)
name: CI Pipeline

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install lint dependencies
        run: |
          pip install ruff black
          pip install -r translator/requirements.txt

      - name: Run linting (ruff)
        run: ruff check translator/

      - name: Run black check
        run: black --check translator/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r translator/requirements.txt

      - name: Install test dependencies
        run: pip install pytest pytest-cov pytest-mock

      - name: Run tests
        run: pytest translator/tests/ -v --cov=translator --cov-report=xml

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t translator-test translator/

      - name: Run smoke test
        run: docker run --rm translator-test python -c "from core import translator; print('OK')"
```

```yaml
# .github/workflows/cd.yml (optionnel)
name: CD Pipeline

on:
  push:
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract version from tag
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./translator
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

#### Priorité : **BASSE** *(révisée v1.2 — Haute à l'origine, rétrogradée car l'exécution locale rend la CI/CD optionnelle ; seuls les pre-commit hooks sont essentiels)*

---

### 3.3 IMP-T003 : Rate Limiter Adaptatif avec Mémorisation

#### Description

Améliorer le rate limiter actuel pour qu'il mémorise les erreurs récentes et s'adapte automatiquement.

> ⚠️ **Revue v1.1** — L'implémentation originale proposée contenait plusieurs bugs et problèmes de conception critiques : (1) `threading.Lock` dans une dataclass casse `__eq__`/`__hash__`, (2) l'intégration dans `translate_text()` applique un double backoff (rate limiter + backoff exponentiel), (3) la persistance identifiée comme besoin n'est pas implémentée, (4) le seuil `error_threshold=3` est trop élevé pour réagir à temps. La proposition ci-dessous corrige ces problèmes.

#### Limitations de l'implémentation actuelle

1. **Pas de mémoire entre les exécutions** : Chaque run recommence avec le délai de base
2. **Pas de persistance** : Si le conteneur redémarre, la mémoire des erreurs est perdue
3. **Backoff limité** : Le délai maximum n'est pas défini
4. **Pas de détection de rate limit réutilisable** : La logique est inline dans `translate_text()`, non testable

#### Proposition d'amélioration (corrigée)

```python
# core/rate_limiter.py (nouveau fichier)
"""
Rate limiter adaptatif avec mémorisation des erreurs et persistance.
"""
import json
import logging
import time
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter qui s'adapte automatiquement aux erreurs de rate limit.

    Mémorise les erreurs récentes pour ajuster dynamiquement le délai
    entre les requêtes. Supporte la persistance via fichier JSON pour
    survivre aux redémarrages de conteneur.

    Note : Utilise une classe classique (pas de @dataclass) car
    threading.Lock n'est pas compatible avec __eq__/__hash__ générés
    par les dataclasses.
    """

    def __init__(
        self,
        base_delay: float = 0.2,        # Délai de base en secondes (5 req/s)
        max_delay: float = 10.0,          # Délai maximum en secondes (revu : 30s était excessif)
        memory_minutes: int = 30,         # Durée de rétention des erreurs
        error_threshold: int = 1,         # Seuil d'erreurs pour activer le backoff (1 = réactif)
        persist_path: str | None = None,  # Chemin vers le fichier de persistance (optionnel)
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.memory_minutes = memory_minutes
        self.error_threshold = error_threshold
        self.persist_path = Path(persist_path) if persist_path else None

        self._error_timestamps: list[float] = []
        self._lock = Lock()

        # Charger les erreurs persistées si disponibles
        if self.persist_path:
            self._load_persisted_errors()

    def _cleanup_old_errors(self) -> None:
        """Supprime les erreurs plus anciennes que memory_minutes."""
        cutoff = time.time() - (self.memory_minutes * 60)
        self._error_timestamps = [
            t for t in self._error_timestamps if t > cutoff
        ]

    def should_wait(self) -> tuple[bool, float]:
        """
        Détermine s'il faut attendre avant la prochaine requête.

        Returns:
            Tuple (do_wait, wait_seconds)
        """
        with self._lock:
            self._cleanup_old_errors()

            # Pas d'erreur récente → pas d'attente supplémentaire
            if len(self._error_timestamps) < self.error_threshold:
                return False, self.base_delay  # Délai de base uniquement

            # Calcule le délai en fonction du nombre d'erreurs récentes
            error_count = len(self._error_timestamps)
            multiplier = min(2 ** (error_count - self.error_threshold), 16)
            wait_seconds = min(self.base_delay * multiplier, self.max_delay)

            logger.debug(
                "Rate limit active: %d errors in memory, waiting %.1fs",
                error_count, wait_seconds
            )

            return True, wait_seconds

    def record_error(self) -> None:
        """Enregistre une erreur de rate limit et persiste si configuré."""
        with self._lock:
            self._error_timestamps.append(time.time())
            logger.warning(
                "Rate limit error recorded. Total errors in memory: %d",
                len(self._error_timestamps)
            )
            self._persist_errors()

    def record_success(self) -> None:
        """
        Enregistre un succès.
        Optionnel — peut servir au monitoring ou à la décroissance du délai.
        """
        # Future : pourrait réduire progressivement le délai après N succès consécutifs
        pass

    def _persist_errors(self) -> None:
        """Persiste les timestamps d'erreur vers un fichier JSON."""
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("w", encoding="utf-8") as f:
                json.dump({"error_timestamps": self._error_timestamps}, f)
        except Exception as e:
            logger.warning("Failed to persist rate limiter state: %s", e)

    def _load_persisted_errors(self) -> None:
        """Charge les timestamps d'erreur depuis un fichier JSON persisté."""
        if not self.persist_path or not self.persist_path.exists():
            return
        try:
            with self.persist_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._error_timestamps = data.get("error_timestamps", [])
            self._cleanup_old_errors()  # Nettoyer les erreurs expirées
            if self._error_timestamps:
                logger.info(
                    "Loaded %d persisted rate limit errors from %s",
                    len(self._error_timestamps), self.persist_path.name
                )
        except Exception as e:
            logger.warning("Failed to load rate limiter state: %s", e)
            self._error_timestamps = []


# Instance globale pour le service (lazy init)
_global_rate_limiter: RateLimiter | None = None


def get_rate_limiter(persist_path: str | None = None) -> RateLimiter:
    """Retourne l'instance globale du rate limiter (lazy init)."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(
            persist_path=persist_path or "/app/output/.rate_limiter_state.json"
        )
    return _global_rate_limiter
```

#### Intégration dans translator.py (corrigée — sans double backoff)

> ⚠️ **Revue v1.1** — L'intégration originale appliquait un **double backoff** (délai du RateLimiter + backoff exponentiel additionnel), menant à des temps d'attente excessifs. La version corrigée utilise **uniquement** le rate limiter pour gérer l'attente, et le backoff exponentiel uniquement pour les erreurs non-rate-limit.

```python
# Dans core/translator.py, modifier translate_text()
from core.rate_limiter import get_rate_limiter

def translate_text(text: str, source_lang: str, target_lang: str, max_retries: int = 3) -> str:
    if not text or len(text.strip()) == 0:
        return text

    rate_limiter = get_rate_limiter()

    for attempt in range(max_retries):
        try:
            result = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
            if result:
                rate_limiter.record_success()
                return result
            logger.warning("Translation returned empty for: %s...", text[:50])
            return text
        except Exception as e:
            if is_rate_limit_error(str(e)):
                rate_limiter.record_error()

                # Attendre UNIQUEMENT selon le rate limiter (pas de double backoff)
                should_wait, wait_time = rate_limiter.should_wait()
                logger.warning(
                    "Rate limit hit (attempt %d), waiting %.1fs",
                    attempt + 1, wait_time
                )
                time.sleep(wait_time)
            else:
                # Erreur non rate-limit : backoff linéaire classique
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        "Translation attempt %d failed, retrying in %ds: %s",
                        attempt + 1, wait_time, str(e),
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "Failed to translate after %d attempts: %s...",
                        max_retries, text[:50]
                    )
                    return text

    return text
```

#### Priorité : **HAUTE**

---

### 3.4 IMP-T004 : Support Multi-Provider avec Fallback

#### Description

Ajouter le support de DeepL comme alternative à Google Translate pour les cas où :
- Google Translate est bloqué ou limité en rate
- Une meilleure qualité de traduction est requise
- L'utilisateur dispose d'une clé API DeepL

> ⚠️ **Revue v1.1** — L'implémentation originale avait plusieurs problèmes : (1) le mapping des codes langue DeepL était redondant car `config.py` utilise déjà `cs` (pas `cz`) comme code API, (2) l'instanciation de `DeeplTranslator` était incorrecte, (3) pas de mécanisme de fallback automatique Google → DeepL, (4) l'API gratuite DeepL (`FreeTranslator`) n'était pas mentionnée, (5) les providers n'étaient pas intégrés avec le rate limiter. La proposition ci-dessous corrige ces lacunes.

#### Implémentation proposée (corrigée)

```python
# core/translator_factory.py
"""
Factory pour les providers de traduction avec support fallback.
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional

from core.config import LANGUAGES

logger = logging.getLogger(__name__)


class TranslationProvider(ABC):
    """Interface abstraite pour un provider de traduction."""

    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str:
        """Traduit un texte et retourne le résultat."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du provider pour le logging."""
        pass


class GoogleProvider(TranslationProvider):
    """Provider Google Translate (gratuit, pas de clé API)."""

    def __init__(self):
        from deep_translator import GoogleTranslator
        self._translator_cls = GoogleTranslator

    @property
    def name(self) -> str:
        return "Google Translate"

    def translate(self, text: str, source: str, target: str) -> str:
        result = self._translator_cls(source=source, target=target).translate(text)
        return result or text


class DeepLProvider(TranslationProvider):
    """Provider DeepL (API key requise, version gratuite ou pro)."""

    # Mapping des codes langue internes vers les codes DeepL
    # DeepL utilise les codes ISO 639-1 majuscules (FR, CS, SK, DE, IT, AR)
    # Notre config utilise déjà les codes API corrects (cs, sk, etc.)
    # donc le mapping est principalement une mise en majuscules
    DEEPL_LANG_MAP = {
        "cs": "CS",   # Tchèque
        "sk": "SK",   # Slovaque
        "fr": "FR",   # Français
        "de": "DE",   # Allemand
        "it": "IT",   # Italien
        "ar": "AR",   # Arabe
        "en": "EN",   # Anglais
    }

    def __init__(self, api_key: str, use_free_api: bool = True):
        """
        Initialise le provider DeepL.

        Args:
            api_key: Clé API DeepL.
            use_free_api: Si True, utilise l'API gratuite (500k chars/mois).
                         Si False, utilise l'API Pro (payante).
        """
        from deep_translator import DeeplTranslator
        self._translator_cls = DeeplTranslator
        self._api_key = api_key
        self._use_free_api = use_free_api

    @property
    def name(self) -> str:
        return "DeepL (Free)" if self._use_free_api else "DeepL (Pro)"

    def translate(self, text: str, source: str, target: str) -> str:
        target_code = self.DEEPL_LANG_MAP.get(target, target.upper())
        source_code = self.DEEPL_LANG_MAP.get(source, source.upper())

        # deep_translator.DeeplTranslator s'instancie avec api_key
        # et s'utilise avec .translate() après construction
        translator = self._translator_cls(
            api_key=self._api_key,
            source=source_code,
            target=target_code,
            use_free_api=self._use_free_api,
        )
        result = translator.translate(text)
        return result or text


class FallbackProvider(TranslationProvider):
    """
    Provider composite avec fallback automatique.

    Tente le provider principal, et bascule vers le fallback
    en cas d'erreur de rate limit persistante.
    """

    def __init__(self, primary: TranslationProvider, fallback: TranslationProvider):
        self._primary = primary
        self._fallback = fallback
        self._primary_failures = 0
        self._fallback_active = False

    @property
    def name(self) -> str:
        return f"{self._primary.name} (fallback: {self._fallback.name})"

    def translate(self, text: str, source: str, target: str) -> str:
        if self._fallback_active:
            try:
                result = self._fallback.translate(text, source, target)
                self._primary_failures = 0
                self._fallback_active = False
                return result
            except Exception:
                # Le fallback aussi échoue — retour au primaire
                self._fallback_active = False

        try:
            result = self._primary.translate(text, source, target)
            self._primary_failures = 0
            return result
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "too many requests" in error_msg or "429" in error_msg

            if is_rate_limit:
                self._primary_failures += 1
                if self._primary_failures >= 3:
                    logger.warning(
                        "Primary provider %s hit %d rate limits, switching to fallback %s",
                        self._primary.name, self._primary_failures, self._fallback.name,
                    )
                    self._fallback_active = True
                    return self._fallback.translate(text, source, target)

            raise  # Re-lancer pour que le retry de translate_text() gère


def create_provider(
    provider_type: str = "google",
    deepl_api_key: str = "",
    deepl_use_free_api: bool = True,
    fallback_enabled: bool = False,
) -> TranslationProvider:
    """
    Crée le provider de traduction configuré.

    Args:
        provider_type: 'google' ou 'deepl'.
        deepl_api_key: Clé API DeepL (requise si provider_type='deepl').
        deepl_use_free_api: Utiliser l'API gratuite DeepL (défaut: True).
        fallback_enabled: Activer le fallback Google→DeepL ou DeepL→Google.

    Returns:
        Instance de TranslationProvider configurée.
    """
    providers = {
        "google": lambda: GoogleProvider(),
        "deepl": lambda: DeepLProvider(
            api_key=deepl_api_key,
            use_free_api=deepl_use_free_api,
        ),
    }

    factory = providers.get(provider_type.lower())
    if not factory:
        raise ValueError(
            f"Unknown provider: {provider_type}. "
            f"Supported: {', '.join(providers.keys())}"
        )

    primary = factory()

    if fallback_enabled and deepl_api_key:
        if provider_type == "google":
            fallback = DeepLProvider(api_key=deepl_api_key, use_free_api=deepl_use_free_api)
        else:
            fallback = GoogleProvider()

        return FallbackProvider(primary=primary, fallback=fallback)

    return primary
```

#### Configuration via env vars

```bash
# Variable pour choisir le provider
TRANSLATION_PROVIDER=google  # ou 'deepl'

# Clé API DeepL (requise si provider = deepl ou fallback activé)
DEEPL_API_KEY=votre-cle-api-ici

# Utiliser l'API gratuite DeepL (500k caractères/mois, défaut: True)
DEEPL_USE_FREE_API=true

# Activer le fallback automatique (Google → DeepL ou DeepL → Google)
TRANSLATION_FALLBACK=true
```

#### Priorité : **BASSE** *(révisée v1.2 — Moyenne à l'origine, rétrogradée car l'implémentation nécessite un repensé global et une clé API pour être utile)*

---

### 3.5 IMP-T005 : Interface CLI (argparse)

#### Description

Ajouter une interface en ligne de commande pour remplacer/supplémenter les variables d'environnement.

> ⚠️ **Revue v1.1** — La proposition originale était trop succincte pour être actionnable. Il manquait la gestion des conflits entre args CLI et env vars, les options de verbosité, et le mode dry-run. La proposition ci-dessous est enrichie.
>
> ⚠️ **Revue v1.2** — En contexte d'exécution locale, la CLI devient **essentielle**. Les développeurs n'utilisent pas Docker Compose pour itérer rapidement ; ils lancent `python service.py` directement. Une CLI ergonomique remplace avantageusement les env vars pour ce cas d'usage. Priorité rehaussée de Basse à **Moyenne**.

#### Proposition d'interface (enrichie)

```bash
# ─── Commandes principales ─────────────────────────────────────

# Traduction JSON
python service.py translate-json --source-lang en --target-lang fr --input file.json
python service.py translate-json --source-lang en --batch-langs fr,cz,sk,de --input file.json

# Dropdowns multi-langues
python service.py translate-dropdowns --input dropdown.xlsx --format json
python service.py translate-dropdowns --input dropdown.json --format xlsx --batch-langs fr,cz,sk

# Analyse XLSX
python service.py analyze --input file.xlsx

# ─── Options globales ──────────────────────────────────────────

python service.py --help
python service.py --version
python service.py translate-json --dry-run --input file.json   # Simule sans appels API
python service.py translate-json -v --input file.json          # Mode verbeux
python service.py translate-json -q --input file.json          # Mode silencieux

# ─── Priorité des configurations ───────────────────────────────
# 1. Arguments CLI (priorité maximale)
# 2. Variables d'environnement
# 3. Valeurs par défaut du Config
```

#### Règles de résolution des conflits

| Source | Priorité | Exemple |
|--------|----------|---------|
| Argument CLI | 1 (max) | `--target-lang fr` |
| Variable d'environnement | 2 | `TARGET_LANG=cs` |
| Valeur par défaut Config | 3 (min) | `TARGET_LANG = "cs"` |

#### Implémentation squelette

```python
# Dans service.py — Ajout de argparse
import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="service.py",
        description="Service de traduction générique COP",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.1.0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mode verbeux")
    parser.add_argument("-q", "--quiet", action="store_true", help="Mode silencieux")

    subparsers = parser.add_subparsers(dest="mode", help="Mode d'opération")

    # translate-json
    p_json = subparsers.add_parser("translate-json", help="Traduire un JSON plat")
    p_json.add_argument("--source-lang", default=None, help="Langue source (défaut: en)")
    p_json.add_argument("--target-lang", default=None, help="Langue cible (défaut: cs)")
    p_json.add_argument("--batch-langs", default=None, help="Langues batch (séparées par virgules)")
    p_json.add_argument("--input", default=None, help="Fichier source JSON")
    p_json.add_argument("--output-dir", default=None, help="Répertoire de sortie")
    p_json.add_argument("--dry-run", action="store_true", help="Simuler sans appels API")

    # translate-dropdowns
    p_dd = subparsers.add_parser("translate-dropdowns", help="Générer traductions dropdowns")
    p_dd.add_argument("--input", default=None, help="Fichier source XLSX ou JSON")
    p_dd.add_argument("--batch-langs", default=None, help="Langues batch")
    p_dd.add_argument("--format", choices=["json", "xlsx", "auto"], default=None, help="Format de sortie")
    p_dd.add_argument("--output-dir", default=None, help="Répertoire de sortie")
    p_dd.add_argument("--dry-run", action="store_true", help="Simuler sans appels API")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyser un fichier XLSX")
    p_analyze.add_argument("--input", default=None, help="Fichier XLSX à analyser")
    p_analyze.add_argument("--output-dir", default=None, help="Répertoire de sortie du rapport")

    return parser
```

#### Priorité : **MOYENNE** *(révisée v1.2 — Basse en v1.1, rehaussée car l'exécution locale rend la CLI essentielle pour l'ergonomie développeur)*

---

### 3.6 IMP-T006 : Cache Intelligent de Traductions

#### Description

Mettre en place un cache persistant des traductions déjà effectuées pour éviter de re-traduire les mêmes termes d'une exécution à l'autre.

> 🆕 **Ajout v1.1** — Cette amélioration était mentionnée dans le résumé exécutif original sans être détaillée. Elle a été promue en priorité **Haute** car son ROI est immédiat : les termes de dropdown et les clés de traduction JSON sont très stables d'un run à l'autre, et un cache simple peut réduire de 50 à 80% les appels API sur les runs répétés.
>
> ⚠️ **Revue v1.2** — En contexte local, ce cache est encore plus rentable : les développeurs relancent fréquemment le service pour itérer, et chaque run précédent sans cache re-traduisait tout. Le cache élimine ce gaspillage.

#### Problème actuel

Actuellement, chaque exécution du service traduit **l'intégralité** des termes, même si la majorité a déjà été traduite lors d'un run précédent. Le seul mécanisme de reprise est le checkpoint (fichier de sortie partiel), mais il ne fonctionne que pour le même run interrompu — pas entre deux runs distincts.

Pour un batch de 2629 entrées à ~0.2s par entrée, cela représente **~9 minutes** d'appels API à chaque run. Avec un cache, les entrées déjà traduites sont servies instantanément.

#### Proposition d'implémentation

```python
# core/cache.py (nouveau fichier)
"""
Cache persistant des traductions.
Stocke les paires (texte source, langue cible) → traduction
dans un fichier JSON pour survivre aux redémarrages de conteneur.
"""
import json
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class TranslationCache:
    """
    Cache de traductions persistant basé sur un fichier JSON.

    Structure du fichier cache :
    {
        "metadata": {
            "version": 1,
            "created": "2026-05-07",
            "total_entries": 1500
        },
        "entries": {
            "en:fr:Hello": "Bonjour",
            "en:de:Button": "Taste",
            ...
        }
    }

    La clé de cache est composée de : {source_lang}:{target_lang}:{text}
    Cela garantit l'unicité quelle que soit la paire de langues.
    """

    def __init__(self, cache_path: str | Path = "/app/output/.translation_cache.json"):
        self._path = Path(cache_path)
        self._entries: dict[str, str] = {}
        self._lock = Lock()
        self._dirty = False  # Indique si des modifications non-sauvées existent
        self._hits = 0
        self._misses = 0

        self._load()

    @staticmethod
    def _make_key(source_lang: str, target_lang: str, text: str) -> str:
        """Génère une clé de cache unique pour un triplet (source, target, text)."""
        return f"{source_lang}:{target_lang}:{text}"

    def get(self, source_lang: str, target_lang: str, text: str) -> str | None:
        """
        Récupère une traduction du cache.

        Returns:
            La traduction si présente, None sinon.
        """
        key = self._make_key(source_lang, target_lang, text)
        with self._lock:
            if key in self._entries:
                self._hits += 1
                logger.debug("Cache HIT: %s", key[:80])
                return self._entries[key]
            self._misses += 1
            logger.debug("Cache MISS: %s", key[:80])
            return None

    def put(self, source_lang: str, target_lang: str, text: str, translation: str) -> None:
        """Ajoute une traduction au cache."""
        key = self._make_key(source_lang, target_lang, text)
        with self._lock:
            if key not in self._entries or self._entries[key] != translation:
                self._entries[key] = translation
                self._dirty = True

    def flush(self) -> None:
        """Sauvegarde le cache sur disque si modifié."""
        with self._lock:
            if not self._dirty:
                return
            self._save()
            self._dirty = False

    def stats(self) -> dict[str, int | float]:
        """Retourne les statistiques du cache."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "total_entries": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 1),
            }

    def _load(self) -> None:
        """Charge le cache depuis le disque."""
        if not self._path.exists():
            logger.info("No existing translation cache at %s", self._path)
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = data.get("entries", {})
            logger.info(
                "Loaded translation cache: %d entries from %s",
                len(self._entries), self._path.name,
            )
        except Exception as e:
            logger.warning("Failed to load translation cache: %s — starting fresh", e)
            self._entries = {}

    def _save(self) -> None:
        """Écrit le cache sur disque."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "metadata": {
                    "version": 1,
                    "total_entries": len(self._entries),
                },
                "entries": self._entries,
            }
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("Cache saved: %d entries to %s", len(self._entries), self._path.name)
        except Exception as e:
            logger.error("Failed to save translation cache: %s", e)


# Instance globale (lazy)
_cache: TranslationCache | None = None


def get_cache(cache_path: str | None = None) -> TranslationCache:
    """Retourne l'instance globale du cache (lazy init)."""
    global _cache
    if _cache is None:
        _cache = TranslationCache(
            cache_path=cache_path or "/app/output/.translation_cache.json"
        )
    return _cache
```

#### Intégration dans translator.py

```python
# Dans core/translator.py — Modifier translate_text() pour utiliser le cache
from core.cache import get_cache

def translate_text(text: str, source_lang: str, target_lang: str, max_retries: int = 3) -> str:
    if not text or len(text.strip()) == 0:
        return text

    # Vérifier le cache AVANT tout appel API
    cache = get_cache()
    cached = cache.get(source_lang, target_lang, text)
    if cached is not None:
        return cached

    # Traduction via l'API (logique existante avec rate limiter)
    rate_limiter = get_rate_limiter()
    for attempt in range(max_retries):
        try:
            result = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
            if result:
                rate_limiter.record_success()
                # Mettre en cache le résultat
                cache.put(source_lang, target_lang, text, result)
                return result
            # ... (reste de la logique existante)
        except Exception as e:
            # ... (logique existante de retry)
            pass

    return text


# Dans translate_batch() — Ajouter un flush du cache à la fin
def translate_batch(items, source_lang, target_lang, ...):
    # ... logique existante ...

    # Flush du cache à la fin du batch
    cache = get_cache()
    cache.flush()

    # Log des statistiques du cache
    stats = cache.stats()
    logger.info(
        "Cache stats: %d hits, %d misses (%.1f%% hit rate), %d total cached entries",
        stats["hits"], stats["misses"], stats["hit_rate_pct"], stats["total_entries"],
    )

    return results
```

#### Impact estimé

| Scénario | Sans cache | Avec cache (2e run) | Économie |
|----------|-----------|--------------------|----------|
| 2629 entrées, 1re exécution | ~9 min API | ~9 min API | 0% (cold cache) |
| 2629 entrées, 2e exécution (mêmes termes) | ~9 min API | <1 min (I/O uniquement) | ~90% |
| 2629 entrées, 2e exécution (10% nouveaux) | ~9 min API | ~1 min API + I/O | ~89% |
| 2629 entrées, 2e exécution (50% nouveaux) | ~9 min API | ~4.5 min API + I/O | ~50% |

#### Configuration via env vars

```bash
# Activer/désactiver le cache (défaut: activé)
TRANSLATION_CACHE=true

# Chemin du fichier cache (défaut: /app/output/.translation_cache.json)
TRANSLATION_CACHE_PATH=/app/output/.translation_cache.json
```

#### Priorité : **HAUTE** *(promue depuis Moyenne — ROI immédiat sur les coûts API et le temps d'exécution, maximisé en contexte local)*

---

### 3.7 IMP-T007 : Adaptation des Chemins pour l'Exécution Locale

#### Description

Les chemins par défaut dans `config.py` (`/app/output`, `/app/source`, etc.) sont conçus pour Docker et inutilisables en exécution locale directe. Il faut rendre le service utilisable hors Docker sans configuration manuelle.

> 🆕 **Ajout v1.2** — Cette faiblesse a été identifiée dans le contexte d'exécution locale. Les développeurs qui lancent `python service.py` directement doivent configurer manuellement chaque chemin via des env vars, ce qui est fastidieux.

#### Problème actuel

```python
# core/config.py — Chemins actuels (Docker-only)
OUTPUT_DIR: str = field(default_factory=lambda: os.environ.get("OUTPUT_DIR", "/app/output"))
EXCEL_DIR: str = field(default_factory=lambda: os.environ.get("EXCEL_DIR", "/app/excel"))
DOC_DIR: str = field(default_factory=lambda: os.environ.get("DOC_DIR", "/app/doc"))
SOURCE_DIR: str = field(default_factory=lambda: os.environ.get("SOURCE_DIR", "/app/source"))
```

En local, ces chemins n'existent pas. Le développeur doit faire :

```bash
OUTPUT_DIR=./output SOURCE_DIR=./source python service.py
```

#### Proposition d'implémentation

```python
# core/config.py — Détection automatique de l'environnement
import os
from pathlib import Path

def _is_docker() -> bool:
    """Détecte si on s'exécute dans un conteneur Docker."""
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")

def _default_output_dir() -> str:
    if _is_docker():
        return os.environ.get("OUTPUT_DIR", "/app/output")
    return os.environ.get("OUTPUT_DIR", str(Path.cwd() / "output"))

def _default_source_dir() -> str:
    if _is_docker():
        return os.environ.get("SOURCE_DIR", "/app/source")
    return os.environ.get("SOURCE_DIR", str(Path.cwd() / "source"))

def _default_excel_dir() -> str:
    if _is_docker():
        return os.environ.get("EXCEL_DIR", "/app/excel")
    return os.environ.get("EXCEL_DIR", str(Path.cwd() / "excel"))

def _default_doc_dir() -> str:
    if _is_docker():
        return os.environ.get("DOC_DIR", "/app/doc")
    return os.environ.get("DOC_DIR", str(Path.cwd() / "Doc"))


@dataclass
class Config:
    # ... champs existants ...

    OUTPUT_DIR: str = field(default_factory=_default_output_dir)
    EXCEL_DIR: str = field(default_factory=_default_excel_dir)
    DOC_DIR: str = field(default_factory=_default_doc_dir)
    SOURCE_DIR: str = field(default_factory=_default_source_dir)
```

#### Impact sur les chemins de cache et rate limiter

Les chemins par défaut du cache (`/app/output/.translation_cache.json`) et du rate limiter (`/app/output/.rate_limiter_state.json`) doivent également s'adapter :

```python
# core/cache.py
def _default_cache_path() -> str:
    if _is_docker():
        return "/app/output/.translation_cache.json"
    return str(Path.cwd() / "output" / ".translation_cache.json")

# core/rate_limiter.py
def _default_rate_limiter_path() -> str:
    if _is_docker():
        return "/app/output/.rate_limiter_state.json"
    return str(Path.cwd() / "output" / ".rate_limiter_state.json")
```

#### Priorité : **MOYENNE** *(nécessaire pour l'ergonomie locale, mais contournable via env vars)*

---

## 4. Synthèse et Plan de Mise en Œuvre

### 4.1 Ordre de priorité révisé

| Ordre | ID | Amélioration | Priorité v1.2 | Rationale |
|-------|----|-------------|----------------|-----------|
| 1 | **IMP-T006** | Cache intelligent | **Haute** | ROI immédiat, complexité faible, maximisé en local |
| 2 | **IMP-T001** | Tests unitaires | **Haute** | Sécurise les futures modifications, empêche les régressions |
| 3 | **IMP-T003** | Rate limiter adaptatif | **Haute** | Fiabilise les traductions en batch, implémentation corrigée |
| 4 | **IMP-T005** | Interface CLI | **Moyenne** | Essentiel en local pour l'ergonomie développeur |
| 5 | **IMP-T007** | Chemins locaux | **Moyenne** | Nécessaire pour l'exécution hors Docker |
| 6 | **IMP-T002** | Pre-commit hooks | **Basse** | CI optionnelle, pre-commit hooks suffisent en local |
| 7 | **IMP-T004** | Multi-provider + fallback | **Basse** | Nécessite clé API, reste optionnel |

### 4.2 Dépendances entre améliorations

```
IMP-T001 (Tests) ──────► IMP-T003 (Rate Limiter) ──► IMP-T004 (Multi-provider)
     │                         │                           │
     │                         │                           └── Nécessite T001 pour tests
     │                         └── Nécessite T001 pour tester les mocks
     │
     └── IMP-T006 (Cache) ──► Nécessite T001 pour tests unitaires du cache

IMP-T005 (CLI) ──► IMP-T007 (Chemins locaux) ──► Les chemins locaux sont aussi
     │                                                utilisés par le cache et
     │                                                le rate limiter
     └── Peut être fait en parallèle avec T006

IMP-T002 (Pre-commit) ──► Dépend de T001 (tests) pour être utile
```

### 4.3 Planning proposé

| Phase | Semaine | Contenu |
|-------|---------|---------|
| **Phase 1** | S1 | IMP-T001 (Tests unitaires du code existant) |
| **Phase 2** | S2 | IMP-T007 (Chemins locaux) — TDD |
| **Phase 3** | S3 | IMP-T006 (Cache intelligent) — TDD |
| **Phase 4** | S4 | IMP-T003 (Rate limiter adaptatif) — TDD |
| **Phase 5** | S5 | IMP-T005 (Interface CLI) — TDD |
| **Phase 6** | S6 | IMP-T002 (Pre-commit hooks) — Config |
| **Phase 7** | S7+ | IMP-T004 (Multi-provider) — TDD, selon les besoins |

### 4.4 Suivi d'Implémentation

> 🆕 **Ajout v1.2** — Cette section permet de suivre l'avancement de chaque amélioration.

| ID | Amélioration | Statut | Date début | Date fin | Branche | Notes |
|----|-------------|--------|------------|----------|---------|-------|
| IMP-T001 | Tests unitaires | ✅ Terminé | 2026-05-08 | 2026-05-08 | `feat/IMP-T001-tests-unitaires` | 257 tests, 87% coverage total |
| IMP-T002 | Pre-commit hooks + CI optionnelle | 🔲 Non commencé | | | | Pre-commit hooks en priorité, CI optionnelle |
| IMP-T003 | Rate limiter adaptatif | 🔲 Non commencé | | | | Prérequis : IMP-T001 |
| IMP-T004 | Multi-provider + fallback | 🔲 Non commencé | | | | Prérequis : IMP-T001, IMP-T003 |
| IMP-T005 | Interface CLI | 🔲 Non commencé | | | | Peut être fait en parallèle avec IMP-T006 |
| IMP-T006 | Cache intelligent | 🔲 Non commencé | | | | Prérequis : IMP-T001 pour les tests |
| IMP-T007 | Chemins locaux | 🔲 Non commencé | | | | Peut être fait en parallèle avec IMP-T003 |

**Légende des statuts :**

| Statut | Signification |
|--------|---------------|
| 🔲 Non commencé | Pas encore démarré |
| 🔵 En cours | Développement en cours |
| 🟡 En revue | PR soumise, en attente de review |
| ✅ Terminé | Implémenté et mergé |
| ❌ Annulé | Abandonné ou reporté |

> **Instructions de mise à jour** : Remplacer 🔲 par 🔵/🟡/✅/❌ au fur et à mesure de l'avancement. Renseigner les dates et branches quand pertinent.
>
> **v1.2 update** : IMP-T001 terminé — 257 tests, couverture 87% (core: 92-100%, modes: 69-97%).

---

### 4.5 Document de suivi détaillé

> 🆕 **Ajout v1.2** — Un document de suivi détaillé avec l'approche TDD et les sous-tâches par amélioration est disponible dans :
>
> 📄 [`doc/2026_05_08_Implementation_Tracking.md`](2026_05_08_Implementation_Tracking.md)
>
> Ce document contient :
> - Le cycle TDD détaillé pour chaque amélioration (🔴 Écrire le test → 🟢 Implémenter → 🔵 Refactorer)
> - Les sous-tâches avec statut par case à cocher
> - Les fichiers créés/modifiés pour chaque tâche
> - Les critères de validation
> - L'historique des commits et les décisions d'architecture