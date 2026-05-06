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
| 1 | **IMP-T001** | Tests unitaires du code existant | Haute | `feat/IMP-T001-tests-unitaires` |
| 2 | **IMP-T007** | Chemins locaux (Docker vs local) | Moyenne | `feat/IMP-T007-chemins-locaux` |
| 3 | **IMP-T006** | Cache intelligent de traductions | Haute | `feat/IMP-T006-cache-intelligent` |
| 4 | **IMP-T003** | Rate limiter adaptatif | Haute | `feat/IMP-T003-rate-limiter` |
| 5 | **IMP-T005** | Interface CLI (argparse) | Moyenne | `feat/IMP-T005-interface-cli` |
| 6 | **IMP-T002** | Pre-commit hooks + CI optionnelle | Basse | `feat/IMP-T002-pre-commit` |
| 7 | **IMP-T004** | Multi-provider avec fallback | Basse | `feat/IMP-T004-multi-provider` |

---

## 3. Suivi Détaillé par Tâche

### IMP-T001 — Tests Unitaires du Code Existant

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T001-tests-unitaires`
**Priorité :** Haute
**Description :** Écrire les tests unitaires pour le code existant avant toute modification. C'est le socle de confiance pour les développements ultérieurs.

#### Prérequis

- [ ] Installer `pytest`, `pytest-cov`, `pytest-mock` dans `requirements.txt`
- [ ] Créer `translator/pytest.ini`
- [ ] Extraire `is_rate_limit_error()` de `translator.py` vers une fonction testable

#### Sous-tâches

| # | Module | Fichier de test | Statut |
|---|--------|----------------|--------|
| 1.1 | `core/config.py` | `tests/test_config.py` | 🔲 |
| 1.2 | `core/io_json.py` | `tests/test_io_json.py` | 🔲 |
| 1.3 | `core/io_xlsx.py` | `tests/test_io_xlsx.py` | 🔲 |
| 1.4 | `core/translator.py` | `tests/test_translator.py` | 🔲 |
| 1.5 | `modes/mode_translate_json.py` | `tests/test_mode_translate_json.py` | 🔲 |
| 1.6 | `modes/mode_translate_dropdowns.py` | `tests/test_mode_translate_dropdowns.py` | 🔲 |
| 1.7 | `modes/mode_analyze.py` | `tests/test_mode_analyze.py` | 🔲 |

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

- [ ] Couverture > 70% sur `core/`
- [ ] Tous les tests passent (`pytest translator/tests/ -v`)
- [ ] Aucun appel API réel dans les tests (tout mocké)

---

### IMP-T007 — Chemins Locaux (Docker vs Local)

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T007-chemins-locaux`
**Priorité :** Moyenne
**Description :** Adapter `config.py` pour détecter automatiquement l'environnement (Docker vs local) et utiliser les chemins appropriés.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `_is_docker()` | 🔲 |
| 🔴 | Écrire les tests pour les fonctions `_default_*_dir()` | 🔲 |
| 🟢 | Implémenter `_is_docker()` | 🔲 |
| 🟢 | Implémenter les fonctions `_default_output_dir()`, `_default_source_dir()`, etc. | 🔲 |
| 🔵 | Refactorer `Config` pour utiliser les nouvelles fonctions | 🔲 |
| ✅ | Tous les tests passent | 🔲 |

#### Fichiers modifiés

- `translator/core/config.py` — Ajout de `_is_docker()`, `_default_*_dir()`
- `translator/core/cache.py` (futur) — Chemins du cache adaptatifs
- `translator/core/rate_limiter.py` (futur) — Chemins du state adaptatifs
- `translator/tests/test_config.py` — Tests des nouveaux chemins

#### Critère de validation

- [ ] `python service.py` fonctionne en local sans Docker ni env vars
- [ ] `docker compose up` fonctionne toujours avec les chemins `/app/*`
- [ ] Les tests couvrent les deux environnements (mock de `_is_docker()`)

---

### IMP-T006 — Cache Intelligent de Traductions

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T006-cache-intelligent`
**Priorité :** Haute
**Description :** Cache persistant des traductions pour éviter de re-traduire les mêmes termes d'un run à l'autre.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `TranslationCache.__init__()` | 🔲 |
| 🔴 | Écrire les tests pour `TranslationCache.get()` / `put()` | 🔲 |
| 🔴 | Écrire les tests pour `TranslationCache.flush()` / `_load()` / `_save()` | 🔲 |
| 🔴 | Écrire les tests pour `TranslationCache.stats()` | 🔲 |
| 🔴 | Écrire les tests pour `get_cache()` (singleton) | 🔲 |
| 🔴 | Écrire les tests d'intégration : `translate_text()` avec cache | 🔲 |
| 🟢 | Implémenter `translator/core/cache.py` | 🔲 |
| 🟢 | Intégrer le cache dans `translator/core/translator.py` | 🔲 |
| 🟢 | Ajouter `TRANSLATION_CACHE` et `TRANSLATION_CACHE_PATH` dans `config.py` | 🔲 |
| 🔵 | Refactorer si nécessaire | 🔲 |
| ✅ | Tous les tests passent | 🔲 |

#### Fichiers créés

- `translator/core/cache.py` — Module de cache
- `translator/tests/test_cache.py` — Tests du cache

#### Fichiers modifiés

- `translator/core/translator.py` — Intégration du cache dans `translate_text()` et `translate_batch()`
- `translator/core/config.py` — Variables `TRANSLATION_CACHE`, `TRANSLATION_CACHE_PATH`

#### Critère de validation

- [ ] 1er run : cold cache, toutes les traductions passent par l'API
- [ ] 2e run : warm cache, hit rate > 90% sur les mêmes termes
- [ ] Le cache se persiste correctement entre deux exécutions
- [ ] `TRANSLATION_CACHE=false` désactive le cache

---

### IMP-T003 — Rate Limiter Adaptatif

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T003-rate-limiter`
**Priorité :** Haute
**Description :** Rate limiter avec mémoire des erreurs, persistance JSON, et seuil réactif.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `RateLimiter.__init__()` | 🔲 |
| 🔴 | Écrire les tests pour `RateLimiter.should_wait()` — aucun seuil, seuil atteint, max_delay | 🔲 |
| 🔴 | Écrire les tests pour `RateLimiter.record_error()` | 🔲 |
| 🔴 | Écrire les tests pour `RateLimiter._persist_errors()` / `_load_persisted_errors()` | 🔲 |
| 🔴 | Écrire les tests pour `get_rate_limiter()` (singleton, lazy init) | 🔲 |
| 🔴 | Écrire les tests d'intégration : `translate_text()` avec rate limiter | 🔲 |
| 🟢 | Implémenter `translator/core/rate_limiter.py` | 🔲 |
| 🟢 | Intégrer dans `translator/core/translator.py` (remplacer le backoff inline) | 🔲 |
| 🟢 | Ajouter `RATE_LIMITER_STATE_PATH` dans `config.py` | 🔲 |
| 🔵 | Refactorer `translate_text()` pour supprimer le backoff redondant | 🔲 |
| ✅ | Tous les tests passent | 🔲 |

#### Fichiers créés

- `translator/core/rate_limiter.py` — Module de rate limiting
- `translator/tests/test_rate_limiter.py` — Tests du rate limiter

#### Fichiers modifiés

- `translator/core/translator.py` — Remplacer le backoff inline par le rate limiter
- `translator/core/config.py` — Variable `RATE_LIMITER_STATE_PATH`

#### Critère de validation

- [ ] Le rate limiter persiste son état entre deux exécutions
- [ ] Le seuil réactif (error_threshold=1) fonctionne
- [ ] Le max_delay (10s) est respecté
- [ ] Pas de double backoff (ancien + nouveau)

---

### IMP-T005 — Interface CLI (argparse)

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T005-interface-cli`
**Priorité :** Moyenne
**Description :** Ajouter une interface CLI pour remplacer/supplémenter les variables d'environnement.

#### Cycle TDD

| Étape | Action | Statut |
|-------|--------|--------|
| 🔴 | Écrire les tests pour `build_parser()` — sous-commandes, arguments | 🔲 |
| 🔴 | Écrire les tests pour la résolution de conflits (CLI > env > défaut) | 🔲 |
| 🔴 | Écrire les tests pour chaque mode CLI | 🔲 |
| 🟢 | Implémenter `build_parser()` dans `service.py` | 🔲 |
| 🟢 | Implémenter la résolution CLI → Config | 🔲 |
| 🟢 | Implémenter `--dry-run` pour chaque mode | 🔲 |
| 🔵 | Refactorer si nécessaire | 🔲 |
| ✅ | Tous les tests passent | 🔲 |

#### Fichiers modifiés

- `translator/service.py` — Ajout de `build_parser()`, intégration CLI
- `translator/core/config.py` — Support de la résolution CLI > env > défaut
- `translator/tests/test_cli.py` — Tests de l'interface CLI

#### Critère de validation

- [ ] `python service.py --help` affiche l'aide
- [ ] `python service.py translate-json -s en -t fr -i file.json` fonctionne
- [ ] `python service.py --dry-run translate-json` simule sans appel API
- [ ] Les args CLI ont priorité sur les env vars

---

### IMP-T002 — Pre-commit Hooks + CI Optionnelle

**Statut :** 🔲 Non commencé
**Branche :** `feat/IMP-T002-pre-commit`
**Priorité :** Basse
**Description :** Pre-commit hooks pour la qualité de code, CI GitHub Actions optionnelle.

#### Sous-tâches

| # | Tâche | Statut |
|---|-------|--------|
| 2.1 | Créer `.pre-commit-config.yaml` | 🔲 |
| 2.2 | Ajouter `ruff` et `black` dans `requirements-dev.txt` | 🔲 |
| 2.3 | Installer et tester les hooks localement | 🔲 |
| 2.4 | (Optionnel) Créer `.github/workflows/ci.yml` | 🔲 |

> Note : Pas de TDD pour cette tâche (configuration, pas de code métier).

#### Fichiers créés

- `.pre-commit-config.yaml`
- `requirements-dev.txt`
- `.github/workflows/ci.yml` (optionnel)

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

---

## 5. Notes et Décisions

### Décisions d'architecture

| Date | Décision | Rationale |
|------|----------|-----------|
| 2026-05-08 | Approche TDD pour toutes les fonctionnalités | Fiabilité et documentation vivante |
| 2026-05-08 | Implémentation séquentielle | Éviter les conflits et les dépendances croisées |
| 2026-05-08 | Exécution locale exclusive | Pas de CI/CD critique, pre-commit hooks suffisent |
| 2026-05-08 | Données (sources/outputs) exclues de git | Ce repo est un outil, pas un entrepôt de données |

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
