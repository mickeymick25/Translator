# Suivi d'Implémentation — Service de Traduction COP

**Date de création :** 2026-05-08
**Dernière mise à jour :** 2026-05-08
**Approche :** TDD (Test-Driven Development) — Séquentiel
**Référence :** [Étude d'améliorations v1.2](2026_05_06_COP_Translation_Service_Improvements_Study.md)

---

## 1. Principes

| Principe | Description |
|----------|-------------|
| **TDD** | Chaque fonctionnalité est développée selon le cycle : 🔴 Écrire le test → 🟢 Implémenter → 🔵 Refactorer |
| **Séquentiel** | Une seule amélioration à la fois, dans l'ordre de priorité défini |
| **Branches** | Chaque IMP-Txxx fait l'objet d'une branche `feat/IMP-Txxx-description` |
| **Commits** | Convention : `type(scope): description` (feat, fix, test, refactor, docs, chore) |
| **Merge** | Squash-merge vers `main` pour garder un historique propre |

---

## 2. Ordre d'Implémentation

| Ordre | ID | Amélioration | Priorité | Branche prévue |
|-------|----|-------------|----------|----------------|
| 1 | **IMP-T001** | Tests unitaires du code existant | Haute | ✅ `feat/IMP-T001-tests-unitaires` |
| 2 | **IMP-T007** | Chemins locaux (Docker vs local) | Moyenne | ✅ `feat/IMP-T007-chemins-locaux` |
| 3 | **IMP-T006** | Cache intelligent de traductions | Haute | ✅ `feat/IMP-T006-cache-intelligent` |
| 4 | **IMP-T003** | Rate limiter adaptatif | Haute | ✅ `feat/IMP-T003-rate-limiter` |
| 5 | **IMP-T005** | Interface CLI (argparse) | Moyenne | ✅ `feat/IMP-T005-interface-cli` |
| 6 | **IMP-T002** | Pre-commit hooks + CI optionnelle | Basse | `feat/IMP-T002-pre-commit` |
| 7 | **IMP-T004** | Multi-provider avec fallback | Basse | `feat/IMP-T004-multi-provider` |

---

## 3. Suivi Détaillé par Tâche

### IMP-T001 — Tests Unitaires du Code Existant

**Statut :** ✅ Terminé
**Branche :** `feat/IMP-T001-tests-unitaires`
**Date début :** 2026-05-08
**Date fin :** 2026-05-08
**Priorité :** Haute
**Description :** Écrire les tests unitaires pour le code existant avant toute modification. C'est le socle de confiance pour les développements ultérieurs.

#### Prérequis

- [x] Installer `pytest`, `pytest-cov`, `pytest-mock` dans `requirements-dev.txt`
- [x] Créer `translator/pytest.ini`
- [x] Extraire `is_rate_limit_error()` de `translator.py` vers une fonction testable

#### Sous-tâches

| # | Module | Fichier de test | Statut |
|---|--------|----------------|--------|
| 1.1 | `core/config.py` | `tests/test_config.py` | ✅ 100% |
| 1.2 | `core/io_json.py` | `tests/test_io_json.py` | ✅ 100% |
| 1.3 | `core/io_xlsx.py` | `tests/test_io_xlsx.py` | ✅ 93% |
| 1.4 | `core/translator.py` | `tests/test_translator.py` | ✅ 92% |
| 1.5 | `modes/mode_translate_json.py` | `tests/test_mode_translate_json.py` | ✅ 89% |
| 1.6 | `modes/mode_translate_dropdowns.py` | `tests/test_mode_translate_dropdowns.py` | ✅ 69% |
| 1.7 | `modes/mode_analyze.py` | `tests/test_mode_analyze.py` | ✅ 97% |

#### Tests clés par module

**1.1 config.py :**
- `_find_latest_import_folder()` — détection du dossier le plus récent
- `_find_source_file_in_import()` — recherche du fichier source
- `Config.get_source_path()` — auto-détection, fallback, erreur si absent
- `Config.batch_langs_list` — parsing de la liste de langues
- Chemins par défaut — valeurs attendues en local et en Docker

**1.2 io_json.py :**
- `load_flat_json()` — chargement normal, fichier absent, JSON invalide
- `save_flat_json()` — écriture, création du répertoire parent
- `load_structured_json()` — avec métadonnées et contexts
- `save_structured_json()` — écriture structurée
- `create_dropdown_metadata()` — format de date, cohérence des champs

**1.3 io_xlsx.py :**
- `clean_text()` — espaces, tabulations, chaîne vide
- `load_dropdown_xlsx()` — chargement normal, lignes vides ignorées
- `analyze_xlsx()` — structure, en-têtes, valeurs uniques
- `save_dropdown_xlsx()` — génération multi-onglets

**1.4 translator.py :**
- `translate_text()` — texte vide, texte normal, erreur API
- `is_rate_limit_error()` — détection 429, "too many requests", erreur non-rate-limit
- Retry logic — max retries respecté, retour du texte original après échec
- `translate_batch()` — checkpoint callback, progression

**1.5–1.7 Modes :**
- Flux complet avec mocks de `GoogleTranslator`
- Gestion des erreurs (fichier absent, format invalide)
- Mode batch multi-langues (mode_translate_json)

#### Critère de validation

- [x] Couverture > 70% sur `core/` (atteint : 92-100%)
- [x] Tous les tests passent (`docker compose run --rm --build test` → 257/257 passed)
- [x] Aucun appel API réel dans les tests (tout mocké)

---

### IMP-T007 — Chemins Locaux (Docker vs Local)

**Statut :** ✅ Terminé
**Branche :** `feat/IMP-T007-chemins-locaux`
**Date début :** 2026-05-08
**Date fin :** 2026-05-08
**Priorité :** Moyenne
**Description :** Adapter `config.py` pour détecter automatiquement l'environnement (Docker vs local) et utiliser les chemins appropriés.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `_is_docker()` | ✅ |
| 🔴 | Écrire les tests pour les fonctions `_default_*_dir()` | ✅ |
| 🟢 | Implémenter `_is_docker()` | ✅ |
| 🟢 | Implémenter les fonctions `_default_output_dir()`, `_default_source_dir()`, etc. | ✅ |
| 🔵 | Refactorer `Config` pour utiliser les nouvelles fonctions | ✅ |
| ✅ | Tous les tests passent | ✅ 287/287 |

#### Fichiers modifiés

- `translator/core/config.py` — Ajout de `_is_docker()`, `_default_dir()`, `_default_*_dir()`, mise à jour de `Config`
- `translator/tests/test_config.py` — 30 nouveaux tests : `TestIsDocker` (5), `TestDefaultDir` (5), `TestDefaultOutputDir` (4), `TestDefaultSourceDir` (4), `TestDefaultExcelDir` (4), `TestDefaultDocDir` (4), `TestConfigEnvironmentAwareDefaults` (4)
- `translator/core/cache.py` (futur) — Chemins du cache adaptatifs
- `translator/core/rate_limiter.py` (futur) — Chemins du state adaptatifs

#### Critère de validation

- [x] `python service.py` fonctionne en local sans Docker ni env vars
- [x] `docker compose up` fonctionne toujours avec les chemins `/app/*`
- [x] Les tests couvrent les deux environnements (mock de `_is_docker()`)
- [x] Couverture `config.py` : 100%

---

### IMP-T006 — Cache Intelligent de Traductions

**Statut :** ✅ Terminé
**Branche :** `feat/IMP-T006-cache-intelligent`
**Date début :** 2026-05-08
**Date fin :** 2026-05-08
**Priorité :** Haute
**Description :** Cache persistant des traductions pour éviter de re-traduire les mêmes termes d'un run à l'autre.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `TranslationCache.__init__()` | ✅ |
| 🔴 | Écrire les tests pour `TranslationCache.get()` / `put()` | ✅ |
| 🔴 | Écrire les tests pour `TranslationCache.flush()` / `_load()` / `_save()` | ✅ |
| 🔴 | Écrire les tests pour `TranslationCache.stats()` | ✅ |
| 🔴 | Écrire les tests pour `get_cache()` (singleton) | ✅ |
| 🔴 | Écrire les tests d'intégration : `translate_text()` avec cache | ✅ |
| 🟢 | Implémenter `translator/core/cache.py` | ✅ |
| 🟢 | Intégrer le cache dans `translator/core/translator.py` | ✅ |
| 🟢 | Ajouter `TRANSLATION_CACHE` et `TRANSLATION_CACHE_PATH` dans `config.py` | ✅ |
| 🔵 | Refactorer si nécessaire | ✅ |
| ✅ | Tous les tests passent | ✅ 359/359 |

#### Fichiers créés

- `translator/core/cache.py` — Module de cache (TranslationCache, get_cache)
- `translator/tests/test_cache.py` — 49 tests du cache

#### Fichiers modifiés

- `translator/core/translator.py` — Intégration du cache dans `translate_text()` et `translate_batch()`
- `translator/core/config.py` — Variables `TRANSLATION_CACHE`, `TRANSLATION_CACHE_PATH`, propriété `cache_enabled`, fonction `_default_cache_path()`
- `translator/tests/test_config.py` — 14 nouveaux tests (TestDefaultCachePath, TestConfigCacheSettings)
- `translator/tests/test_translator.py` — 9 nouveaux tests d'intégration cache (TestTranslateTextWithCache, TestTranslateBatchWithCache)
- `translator/tests/conftest.py` — Fixture `reset_cache_singleton`

#### Critère de validation

- [x] 1er run : cold cache, toutes les traductions passent par l'API
- [x] 2e run : warm cache, hit rate > 90% sur les mêmes termes
- [x] Le cache se persiste correctement entre deux exécutions
- [x] `TRANSLATION_CACHE=false` désactive le cache

---

### IMP-T003 — Rate Limiter Adaptatif

**Statut :** ✅ Terminé
**Branche :** `feat/IMP-T003-rate-limiter`
**Date début :** 2026-05-09
**Date fin :** 2026-05-09
**Priorité :** Haute
**Description :** Rate limiter avec mémoire des erreurs, persistance JSON, et seuil réactif.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `RateLimiter.__init__()` | ✅ |
| 🔴 | Écrire les tests pour `RateLimiter.should_wait()` — aucun seuil, seuil atteint, max_delay | ✅ |
| 🔴 | Écrire les tests pour `RateLimiter.record_error()` | ✅ |
| 🔴 | Écrire les tests pour `RateLimiter._persist_errors()` / `_load_persisted_errors()` | ✅ |
| 🔴 | Écrire les tests pour `get_rate_limiter()` (singleton, lazy init) | ✅ |
| 🔴 | Écrire les tests d'intégration : `translate_text()` avec rate limiter | ✅ |
| 🟢 | Implémenter `translator/core/rate_limiter.py` | ✅ |
| 🟢 | Intégrer dans `translator/core/translator.py` (remplacer le backoff inline) | ✅ |
| 🟢 | Ajouter `RATE_LIMITER_STATE_PATH` dans `config.py` | ✅ |
| 🔵 | Refactorer `translate_text()` pour supprimer le backoff redondant | ✅ |
| ✅ | Tous les tests passent | ✅ 428/428 |

#### Fichiers créés

- `translator/core/rate_limiter.py` — Module de rate limiting (67 stmts, 97% coverage)
- `translator/tests/test_rate_limiter.py` — 54 tests du rate limiter

#### Fichiers modifiés

- `translator/core/translator.py` — Remplacement du backoff inline par le rate limiter adaptatif pour les erreurs 429 ; backoff linéaire conservé pour les erreurs non-rate-limit ; suppression du paramètre `base_delay` ; import de `get_rate_limiter` ; appel `record_error()` / `record_success()` / `should_wait()`
- `translator/core/config.py` — Variable `RATE_LIMITER_STATE_PATH`, fonction `_default_rate_limiter_path()`
- `translator/tests/test_config.py` — 8 nouveaux tests (TestDefaultRateLimiterPath, TestConfigRateLimiterSettings)
- `translator/tests/test_translator.py` — 7 nouveaux tests d'intégration (TestTranslateTextWithRateLimiter) ; mise à jour des tests de retry existants (suppression de `base_delay`, adaptation aux assertions du rate limiter)
- `translator/tests/conftest.py` — Fixture `reset_rate_limiter_singleton`

#### Critère de validation

- [x] Le rate limiter persiste son état entre deux exécutions
- [x] Le seuil réactif (error_threshold=1) fonctionne
- [x] Le max_delay (10s) est respecté
- [x] Pas de double backoff (ancien + nouveau)

#### Couverture par module (après IMP-T003)

| Module | Stmts | Miss | Cover |
|--------|-------|------|-------|
| core/cache.py | 70 | 2 | 97% |
| core/config.py | 98 | 0 | 100% |
| core/io_json.py | 46 | 0 | 100% |
| core/io_xlsx.py | 96 | 7 | 93% |
| core/rate_limiter.py | 67 | 2 | 97% |
| core/translator.py | 85 | 7 | 92% |
| modes/mode_analyze.py | 76 | 2 | 97% |
| modes/mode_translate_dropdowns.py | 195 | 61 | 69% |
| modes/mode_translate_json.py | 123 | 13 | 89% |
| **TOTAL** | **856** | **94** | **89%** |

---

### IMP-T005 — Interface CLI (argparse)

**Statut :** ✅ Terminé
**Branche :** `feat/IMP-T005-interface-cli`
**Date début :** 2026-05-09
**Date fin :** 2026-05-09
**Priorité :** Moyenne
**Description :** Ajouter une interface CLI pour remplacer/supplémenter les variables d'environnement.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `build_parser()` — sous-commandes, arguments | ✅ |
| 🔴 | Écrire les tests pour la résolution de conflits (CLI > env > défaut) | ✅ |
| 🔴 | Écrire les tests pour chaque mode CLI | ✅ |
| 🟢 | Implémenter `build_parser()` dans `service.py` | ✅ |
| 🟢 | Implémenter la résolution CLI → Config | ✅ |
| 🟢 | Implémenter `--dry-run` pour chaque mode | ✅ |
| 🔵 | Refactorer si nécessaire | ✅ |
| ✅ | Tous les tests passent | ✅ 501/501 |

#### Fichiers créés

- `translator/tests/test_cli.py` — 65 tests de l'interface CLI (build_parser, build_config_from_args, résolution CLI > env > défaut)

#### Fichiers modifiés

- `translator/service.py` — Ajout de `build_parser()`, `build_config_from_args()`, `configure_logging()` ; intégration CLI dans `main()` ; rétrocompatibilité Docker via env var `MODE` ; `--version`, `-v`/`--verbose`, `-q`/`--quiet`, `--dry-run` sur chaque sous-commande ; `__version__ = "1.1.0"`
- `translator/core/config.py` — Ajout des champs `dry_run`, `verbose`, `quiet` (bool, defaults False)
- `translator/tests/test_config.py` — 8 nouveaux tests (TestConfigCLIFlags)

#### Critère de validation

- [x] `python service.py --help` affiche l'aide
- [x] `python service.py translate-json -s en -t fr -i file.json` fonctionne
- [x] `python service.py translate-json --dry-run` simule sans appel API
- [x] Les args CLI ont priorité sur les env vars

#### Couverture par module (après IMP-T005)

| Module | Stmts | Miss | Cover |
|--------|-------|------|-------|
| core/cache.py | 70 | 2 | 97% |
| core/config.py | 101 | 0 | 100% |
| core/io_json.py | 46 | 0 | 100% |
| core/io_xlsx.py | 96 | 7 | 93% |
| core/rate_limiter.py | 67 | 2 | 97% |
| core/translator.py | 85 | 7 | 92% |
| modes/mode_analyze.py | 76 | 2 | 97% |
| modes/mode_translate_dropdowns.py | 195 | 61 | 69% |
| modes/mode_translate_json.py | 123 | 13 | 89% |
| **TOTAL** | **859** | **94** | **89%** |

---

### IMP-T002 — Pre-commit Hooks + CI Optionnelle

**Statut :** ✅ Terminé
**Branche :** `feat/IMP-T002-pre-commit`
**Priorité :** Basse
**Description :** Pre-commit hooks pour la qualité de code, CI GitHub Actions optionnelle.

#### Sous-tâches

| # | Tâche | Statut |
|---|-------|--------|
| 2.1 | Créer `.pre-commit-config.yaml` | ✅ |
| 2.2 | Ajouter `ruff`, `black` et `pre-commit` dans `requirements-dev.txt` | ✅ |
| 2.3 | Installer et tester les hooks localement | ✅ |
| 2.4 | (Optionnel) Créer `.github/workflows/ci.yml` | ✅ |

> Note : Pas de TDD pour cette tâche (configuration, pas de code métier).

#### Fichiers créés

- `.pre-commit-config.yaml` — ruff (lint + format), pre-commit-hooks (whitespace, EOF, YAML, JSON, merge-conflict), pytest-quick (local)
- `.github/workflows/ci.yml` — lint (ruff + black), test (pytest), build (Docker smoke test)

#### Fichiers modifiés

- `translator/requirements-dev.txt` — ajout de `pre-commit>=3.7.0`
- `.gitignore` — ajout de `.pre-commit-cache/`
- `translator/core/io_json.py` — F841 : `metadata` → `_metadata` (2 occurrences)
- `translator/modes/mode_translate_dropdowns.py` — F841 : `source_col` → `_source_col` (2 occurrences)
- `translator/modes/mode_translate_json.py` — E741 : `l` → `lang` (ambiguous variable name)
- `translator/tests/test_mode_analyze.py` — F841 : suppression `result =` non utilisé
- `translator/tests/test_mode_translate_dropdowns.py` — F841 : suppression `result =` non utilisé (2 occurrences)
- `translator/tests/test_config.py` — `test_default_output_dir` / `test_default_source_dir` : environment-aware (Docker vs local)
- `translator/tests/test_mode_translate_json.py` — `/tmp/output` → `tmp_path` (5 tests, évite les dépendances au filesystem local)

#### Corrections de lint (pre-commit run --all-files)

| Règle | Fichier | Correction |
|-------|---------|------------|
| F841 | `io_json.py:96,126` | `metadata` → `_metadata` |
| F841 | `mode_translate_dropdowns.py:320,407` | `source_col` → `_source_col` |
| E741 | `mode_translate_json.py:225` | `l` → `lang` |
| F841 | `test_mode_analyze.py:421` | `result = run()` → `run()` |
| F841 | `test_mode_translate_dropdowns.py:394,430` | `result =` supprimé |
| trailing-whitespace | 3 fichiers doc | Corrigé automatiquement |
| end-of-file-fixer | 5 fichiers doc | Corrigé automatiquement |
| ruff-format | 1 fichier | Reformaté automatiquement |
| black | 2 fichiers test | Reformaté (blank lines après imports) |

#### Hook pytest-quick — note d'implémentation

Le hook local `pytest-quick` utilise Docker par défaut (python n'est pas disponible en local, convention « tout via Docker ») :

```bash
docker compose -f translator/docker-compose.yml run --rm --build test tests/ -x -q --tb=short
```

Alternative si env Python local disponible — remplacer l'entry par :

```bash
python -m pytest translator/tests/ -x -q --tb=short
```

L'approche Docker respecte la convention du projet mais est plus lente (~15s de build). L'approche système est plus rapide (pas de rebuild) mais suppose un env Python local installé.

---

### IMP-T004 — Multi-Provider avec Fallback

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T004-multi-provider`
**Priorité :** Basse
**Description :** Support de DeepL comme alternative à Google Translate, avec fallback automatique.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `TranslationProvider` (interface abstraite) | 🔲 |
| 🔴 | Écrire les tests pour `GoogleProvider` | 🔲 |
| 🔴 | Écrire les tests pour `DeepLProvider` (mock de l'API) | 🔲 |
| 🔴 | Écrire les tests pour `FallbackProvider` — basculement après 3 erreurs 429 | 🔲 |
| 🔴 | Écrire les tests pour `create_provider()` | 🔲 |
| 🟢 | Implémenter `translator/core/translator_factory.py` | 🔲 |
| 🟢 | Intégrer dans `translator/core/translator.py` | 🔲 |
| 🟢 | Ajouter `TRANSLATION_PROVIDER`, `DEEPL_API_KEY`, `DEEPL_USE_FREE_API`, `TRANSLATION_FALLBACK` dans `config.py` | 🔲 |
| 🔵 | Refactorer si nécessaire | 🔲 |
| ✅ | Tous les tests passent | 🔲 |

#### Fichiers créés

- `translator/core/translator_factory.py` — Providers et factory
- `translator/tests/test_translator_factory.py` — Tests des providers

#### Fichiers modifiés

- `translator/core/translator.py` — Utilisation du factory au lieu de l'appel direct
- `translator/core/config.py` — Nouvelles variables d'environnement

---

## 4. Historique des Commits

| Date | Branche | Commit | Description |
|------|---------|--------|-------------|
| 2026-05-08 | `main` | `573504e` | feat: initial commit — service de traduction COP v1.0 |
| 2026-05-08 | `feat/IMP-T001-tests-unitaires` | `c03e3a8` | test(core): add unit tests for core modules — 130 tests, 92-100% coverage |
| 2026-05-08 | `feat/IMP-T001-tests-unitaires` | `48dc8ae` | test(modes): add unit tests for all 3 modes — 257 tests total, 87% coverage |
| 2026-05-08 | `feat/IMP-T007-chemins-locaux` | — | feat(config): add Docker/local path detection — 287 tests, 100% config coverage |
| 2026-05-08 | `feat/IMP-T006-cache-intelligent` | — | feat(cache): add persistent translation cache — 359 tests, 88% total coverage |
| 2026-05-08 | `feat/IMP-T003-rate-limiter` | `9f75d1b` | feat(rate-limiter): adaptive rate limiter with persistence and no double backoff |
| 2026-05-08 | `feat/IMP-T005-cli` | `22e816c` | feat(cli): argparse CLI with subcommands, CLI > env > default resolution |
| 2026-05-08 | `feat/IMP-T002-pre-commit` | — | chore: pre-commit hooks (ruff, ruff-format, pre-commit-hooks, pytest-quick) + CI optionnelle |

---

## 5. Notes et Décisions

### Décisions d'architecture

| Date | Décision | Rationale |
|------|----------|-----------|
| 2026-05-08 | Approche TDD pour toutes les fonctionnalités | Fiabilité et documentation vivante |
| 2026-05-08 | Implémentation séquentielle | Éviter les conflits et les dépendances croisées |
| 2026-05-08 | Exécution locale exclusive | Pas de CI/CD critique, pre-commit hooks suffisent |
| 2026-05-08 | Données (sources/outputs) exclues de git | Ce repo est un outil, pas un entrepôt de données |
| 2026-05-08 | Détection Docker via `/.dockerenv` ou `/run/.containerenv` | Simple, fiable, couvre Docker et Podman |
| 2026-05-08 | Helper `_default_dir()` pour résolution des chemins | Réduit la duplication, facilite l'ajout futur de chemins (cache, rate limiter) |
| 2026-05-08 | Chemins locaux basés sur `Path.cwd()` | Permet `python service.py` sans config manuelle hors Docker |
| 2026-05-08 | Cache clé `{source}:{target}:{text}` | Garantit l'unicité quelle que soit la paire de langues |
| 2026-05-08 | Cache persistant JSON avec `flush()` différé | Évite les I/O disque à chaque `put()`, flush en fin de batch uniquement |
| 2026-05-08 | `TRANSLATION_CACHE` activé par défaut | ROI immédiat : les termes stables ne sont jamais re-traduits |
| 2026-05-08 | Pre-commit hooks : `ruff` principal, `black` en CI uniquement | ruff-format compatible black ; black gardé pour vérification CI |
| 2026-05-08 | Hook `pytest-quick` avec `language: system` | Plus rapide que Docker rebuild ; alternative Docker documentée |
| 2026-05-08 | Tests `/tmp/output` → `tmp_path` (pytest fixture) | Évite les dépendances au filesystem local entre les runs de tests |

### Conventions de branches

- `main` — Code stable
- `feat/IMP-Txxx-description` — Branche par tâche
- Squash-merge vers `main` quand la tâche est terminée

### Conventions de commits

```
feat(translator): add translation cache
fix(config): fix local path detection
test(cache): add cache unit tests
docs(study): update implementation tracking
refactor(translator): extract rate limit detection
chore: add pre-commit hooks
```
