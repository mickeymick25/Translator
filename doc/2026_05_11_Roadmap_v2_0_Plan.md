# Roadmap v2.0 — Suite d'Améliorations du Service de Traduction COP

**Date de création :** 2026-05-11
**Dernière mise à jour :** 2026-05-11
**Approche :** TDD (Test-Driven Development) — Séquentiel
**Référence :** [Suivi d'Implémentation v1.0](2026_05_08_Implementation_Tracking.md)
**Base :** Commit `1a2b1ed` — `docs: rewrite README.md for v2.0` (branche `main`)

---

## 0. État actuel

Toutes les tâches IMP-T (v1.0) et IMP2-T001 (v2.0) sont terminées. Le service dispose de :

| Fonctionnalité | Statut |
|---------------|--------|
| Tests unitaires (620 tests, 96% couverture) | ✅ |
| Chemins locaux Docker vs local | ✅ |
| Cache intelligent persistant | ✅ |
| Rate limiter adaptatif | ✅ |
| Interface CLI argparse (3 subcommands) | ✅ |
| Pre-commit hooks + CI optionnelle | ✅ |
| Multi-provider (Google, DeepL, Fallback) | ✅ |
| CLI Provider flags (--provider, --deepl-api-key, --fallback) | ✅ |

**Problème résolu (IMP2-T001) :** Les configurations provider sont désormais accessibles via les flags CLI (`--provider`, `--deepl-api-key`, `--deepl-use-free-api`, `--fallback`) en plus des variables d'environnement, suivant la priorité CLI > env > default.

---

## 1. Principes

| Principe | Description |
|----------|-------------|
| **TDD** | Chaque fonctionnalité est développée selon le cycle : 🔴 Écrire le test → 🟢 Implémenter → 🔵 Refactorer |
| **Séquentiel** | Une seule amélioration à la fois, dans l'ordre de priorité défini |
| **Branches** | Chaque IMP2-Txxx fait l'objet d'une branche `feat/IMP2-Txxx-description` |
| **Commits** | Convention : `type(scope): description` (feat, fix, test, refactor, docs, chore) |
| **Merge** | Squash-merge vers `main` pour garder un historique propre |
| **Pas d'installation locale** | Tout via Docker (`docker compose run --rm --build test`) |
| **Données exclues de git** | `translator/source/` et `translator/output/` ignorés |

---

## 2. Pistes d'amélioration identifiées

| # | Piste | Intérêt | Priorité | ID prévue |
|---|-------|---------|----------|-----------|
| 1 | **Intégration CLI des providers** — Ajouter `--provider`, `--deepl-api-key`, `--fallback` au CLI argparse | Élevé | Haute | IMP2-T001 |
| 2 | **Améliorer couverture `mode_translate_dropdowns.py`** — 69%, le module le plus bas. ~20 tests à ajouter | Moyen | Moyenne | IMP2-T002 |
| 3 | **Tester le workflow CI GitHub Actions** — `.github/workflows/ci.yml` existe mais n'a jamais été déclenché | Faible | Basse | IMP2-T003 |
| 4 | **Nettoyer `.venv/`** — Virtualenv local de 83 Mo plus nécessaire (tout tourne en Docker) | Faible | Basse | IMP2-T004 |
| 5 | **Améliorer couverture `translator.py`** — 92% mais `get_provider()` lazy init + logs non couverts | Faible | Basse | IMP2-T005 |

---

## 3. Ordre d'Implémentation

| Ordre | ID | Amélioration | Priorité | Branche prévue |
|-------|----|-------------|----------|----------------|
| 1 | **IMP2-T001** | Intégration CLI des providers | Haute | `feat/IMP2-T001-cli-providers` |
| 2 | **IMP2-T002** | Couverture `mode_translate_dropdowns.py` | Moyenne | `feat/IMP2-T002-dropdowns-coverage` |
| 3 | **IMP2-T004** | Nettoyer `.venv/` | Basse | `chore/IMP2-T004-cleanup-venv` |
| 4 | **IMP2-T005** | Couverture `translator.py` — `get_provider()` | Basse | `test/IMP2-T005-translator-coverage` |
| 5 | **IMP2-T003** | Valider CI GitHub Actions | Basse | `ci/IMP2-T003-ci-validation` |

> **Note :** IMP2-T004 est rapide (suppression fichier) et placé avant IMP2-T005 pour libérer l'espace disque. IMP2-T003 est en fin de liste car il s'observe naturellement au premier push.

---

## 4. Suivi Détaillé par Tâche

### IMP2-T001 — Intégration CLI des Providers

**Statut :** ✅ Terminé
**Branche :** `feat/IMP2-T001-cli-providers`
**Priorité :** Haute
**Description :** Les configurations provider (`TRANSLATION_PROVIDER`, `DEEPL_API_KEY`, `DEEPL_USE_FREE_API`, `TRANSLATION_FALLBACK`) ne sont accessibles que via les variables d'environnement. L'utilisateur CLI ne peut pas les configurer sans recourir aux env vars, ce qui contredit l'ergonomie CLI établie par IMP-T005. Il faut exposer ces 4 paramètres via des flags argparse, suivant la priorité existante : **CLI > env vars > defaults**.

#### Cycle TDD

1. 🔴 **Tests** — ~~Ajouter les tests CLI pour les nouveaux flags~~ ✅ 34 tests ajoutés
2. 🟢 **Implémentation** — ~~Modifier les fichiers~~ ✅ `_add_provider_args()`, propagation, log, docker-compose
3. 🔵 **Refactor** — ~~Vérifier que `build_config_from_args()` reste lisible~~ ✅ Helper `_add_provider_args()` extrait dès l'implémentation

#### Fichiers modifiés (prévus)

| Fichier | Changement |
|---------|-----------|
| `translator/service.py` | Ajout flags CLI provider + propagation dans `build_config_from_args()` + log provider |
| `translator/tests/test_cli.py` | Tests des nouveaux flags et de la priorité CLI > env > default |
| `translator/docker-compose.yml` | Ajout env vars provider |

#### Fichiers modifiés (réels)

| Fichier | Changement |
|---------|-----------|
| `translator/service.py` | Ajout `_add_provider_args()`, flags CLI provider, propagation `build_config_from_args()`, log provider, bump version 2.0.0 |
| `translator/tests/test_cli.py` | 34 nouveaux tests (3 classes: TestProviderFlagsOnParser, TestBuildConfigFromArgsProviderPriority, TestBuildConfigFromArgsProviderCombined) |
| `translator/docker-compose.yml` | Ajout env vars TRANSLATION_PROVIDER, DEEPL_API_KEY, DEEPL_USE_FREE_API, TRANSLATION_FALLBACK |

#### Critère de validation

- [x] `--provider google` → `config.TRANSLATION_PROVIDER == "google"`
- [x] `--provider deepl --deepl-api-key KEY` → `config.TRANSLATION_PROVIDER == "deepl"` + `config.DEEPL_API_KEY == "KEY"`
- [x] `--fallback` → `config.fallback_enabled == True`
- [x] Sans flag CLI → env vars utilisées (comportement inchangé)
- [x] Sans flag CLI ni env var → defaults utilisés (comportement inchangé)
- [x] Priorité CLI > env > default vérifiée pour les 4 paramètres
- [x] `docker compose run --rm --build test` : tous les tests passent (597 passed)
- [x] Couverture globale ≥ 89%

---

### IMP2-T002 — Améliorer couverture `mode_translate_dropdowns.py`

**Statut :** ✅ Terminé
**Branche :** `feat/IMP2-T002-dropdowns-coverage`
**Priorité :** Moyenne
**Description :** Le module `mode_translate_dropdowns.py` est à 69% de couverture, le plus bas du projet. Environ 20 tests sont nécessaires pour couvrir les branches non exercées.

#### Branches non couvertes identifiées

| Lignes | Fonction | Branche non couverte | Type de test à ajouter |
|--------|----------|---------------------|----------------------|
| 43-51 | `_translate_dropdown_entry()` | Empty/whitespace input + unknown lang code | Input vide, langue inconnue |
| 162-165 | `_load_or_create_output()` | Resume path avec fichier existant | Mock `load_structured_json` + fichier existant |
| 255 | `_translate_dropdown_entries_batch()` | Checkpoint callback log | Vérifier l'appel au callback |
| 316-380 | `_generate_all_json()` | Resume branch (existing translations) + full translation branch | Mock `_load_or_create_output` + `_translate_dropdown_entries_batch` |
| 398-432 | `_generate_all_xlsx()` | `json_file.exists()` branches + on-the-fly translation branch | JSON existant vs absent, en/fr skip |
| 510-514 | `run()` → `__main__` block | Bloc `if __name__ == "__main__"` | Test d'exécution standalone |

#### Cycle TDD

1. 🔴 **Tests** — ~~Écrire ~20 tests ciblant les branches ci-dessus~~ ✅ 14 tests ajoutés
2. 🟢 **Implémentation** — ~~Aucune modification de code métier~~ ✅ Aucun changement métier (les tests révèlent les chemins existants)
3. 🔵 **Refactor** — ~~Si des dead branches sont identifiées, les nettoyer~~ ✅ Pas de dead branches identifiées

#### Fichiers modifiés (prévus)

| Fichier | Changement |
|---------|-----------|
| `translator/tests/test_mode_translate_dropdowns.py` | ~20 nouveaux tests |

#### Fichiers modifiés (réels)

| Fichier | Changement |
|---------|-----------|
| `translator/tests/test_mode_translate_dropdowns.py` | 14 nouveaux tests (5 classes: TestTranslateDropdownEntry, TestLoadOrCreateOutput, TestGenerateAllJson, TestGenerateAllXlsx, TestMainBlock) |

#### Critère de validation

- [x] Couverture `mode_translate_dropdowns.py` ≥ 85% (actual: 98%)
- [x] Couverture globale ≥ 89% (actual: 95%)
- [x] Tous les tests passent (`docker compose run --rm --build test`) — 611 passed
- [x] Aucune régression sur les tests existants

---

### IMP2-T003 — Valider le workflow CI GitHub Actions

**Statut :** 🔲 À faire
**Branche :** `ci/IMP2-T003-ci-validation`
**Priorité :** Basse
**Description :** Le fichier `.github/workflows/ci.yml` existe (créé lors de IMP-T002) mais n'a jamais été déclenché. Il s'activera au prochain push/PR. Il faut valider son bon fonctionnement et harmoniser le linter (le workflow utilise `black --check` mais le projet standardise sur `ruff-format` via pre-commit).

#### Sous-tâches

- [ ] Observer le résultat du premier déclenchement CI (au push du présent commit)
- [ ] Si échec : corriger le workflow (chemins, commandes, dépendances)
- [ ] Harmoniser : remplacer `black --check` par `ruff format --check` dans le job `lint`
- [ ] Vérifier que le job `build` Docker fonctionne (le Dockerfile ne copie pas `tests/` en production)

#### Fichiers modifiés (prévus)

| Fichier | Changement |
|---------|-----------|
| `.github/workflows/ci.yml` | Remplacer `black --check` par `ruff format --check` |

#### Critère de validation

- [ ] CI passe sur un push `main` (vert sur les 3 jobs : lint, test, build)
- [ ] CI passe sur une PR vers `main`
- [ ] Linter harmonisé (`ruff` uniquement, plus `black`)

---

### IMP2-T004 — Nettoyer `.venv/`

**Statut :** ✅ Terminé
**Branche :** `chore/IMP2-T004-cleanup-venv`
**Priorité :** Basse
**Description :** Le virtualenv local `.venv/` (83 Mo) a été créé pour les tests pre-commit. Il n'est plus nécessaire puisque tout tourne en Docker. Le répertoire est déjà dans `.gitignore` mais reste présent sur le disque local.

#### Sous-tâches

- [x] Supprimer le répertoire `.venv/`
- [x] Vérifier que `pre-commit run --all-files` fonctionne toujours (il utilise Docker pour pytest-quick)
- [x] Documenter dans le README que l'installation locale n'est pas requise

#### Fichiers modifiés (prévus)

| Fichier | Changement |
|---------|-----------|
| `.venv/` | Suppression du répertoire (déjà dans `.gitignore`, changement local uniquement) |
| `README.md` | Note : installation locale Python/venv non requise |

#### Fichiers modifiés (réels)

| Fichier | Changement |
|---------|-----------|
| `.venv/` | Supprimé du disque local (83 Mo libérés) |
| `README.md` | Ajout note : installation locale non requise, tout tourne en Docker |
| `translator/docker-compose.yml` | Ajout service `lint` (ruff check + ruff format --check via Docker) |
| `.git/hooks/pre-commit` | Remplacé par script Docker (lint + test), plus de dépendance Python locale |

#### Critère de validation

- [x] `.venv/` n'existe plus sur le disque
- [x] `pre-commit run --all-files` passe toujours
- [x] `docker compose run --rm --build test` passe toujours (611 passed, 95%)

---

### IMP2-T005 — Améliorer couverture `translator.py` — `get_provider()`

**Statut :** ✅
**Branche :** `test/IMP2-T005-translator-coverage`
**Priorité :** Basse
**Description :** `translator.py` est à 92% de couverture. La fonction `get_provider()` (lignes 33-41) effectue un lazy init du provider avec logs, mais ces logs ne sont pas vérifiés par des tests dédiés. Les tests existants (`TestGetProvider`) couvrent les types de provider retournés mais pas le comportement du lazy init ni les messages de log.

#### Branches non couvertes identifiées

| Lignes | Fonction | Branche non couverte | Type de test à ajouter |
|--------|----------|---------------------|----------------------|
| 33-41 | `get_provider()` | Lazy init : premier appel crée le provider, logs de création | Vérifier que `_provider` passe de `None` à une instance, vérifier les logs |
| 128-133 | `translate_text()` | Rate limit error sur dernière tentative | Test avec 429 sur toutes les tentatives |
| 153 | `translate_text()` | `return text` final après boucle | Test avec `max_retries=0` |
| 203 | `translate_batch()` | `time.sleep(rate_limit_seconds)` avec délai > 0 | Test batch avec `rate_limit_seconds > 0` |
| 213 | `translate_batch()` | Progress log à 100 items | Test batch avec ≥101 items |
| 271 | `translate_batch_generator()` | `time.sleep(rate_limit_seconds)` avec délai > 0 | Test générateur avec `rate_limit_seconds > 0` |
| 274 | `translate_batch_generator()` | Progress log à 100 items | Test générateur avec ≥101 items |

#### Cycle TDD

1. 🔴 **Tests** — Ajout de 9 tests :
   - `test_lazy_init_provider_none_then_instance` : `_provider` est `None` avant le premier appel, instance valide après
   - `test_lazy_init_logs_provider_creation` : vérifier que `logger.info` est appelé lors du premier appel → **échoue** (pas de log existant)
   - `test_idempotent_second_call_does_not_recreate` : deuxième appel retourne la même instance sans recréer (`create_provider` appelé 1 seule fois)
   - `test_rate_limit_exhausted_returns_original` : 429 sur toutes les tentatives → retourne le texte original
   - `test_max_retries_zero_returns_original` : `max_retries=0` → aucun appel API, retourne le texte original
   - `test_batch_with_rate_limit_sleep` : `rate_limit_seconds > 0` → `time.sleep` appelé
   - `test_batch_progress_log_at_100_items` : ≥101 items → log "Progress" émis
   - `test_generator_with_rate_limit_sleep` : `rate_limit_seconds > 0` → `time.sleep` appelé
   - `test_generator_progress_log_at_100_items` : ≥101 items → log "Progress" émis

2. 🟢 **Implémentation** — Aucune modification de code métier existant

3. 🔵 **Refactor** — Ajout de `logger.info("Creating translation provider: %s (fallback=%s)", ...)` dans `get_provider()` pour traçabilité. Le test `test_lazy_init_logs_provider_creation` passe ensuite.

#### Fichiers modifiés (réels)

| Fichier | Changement |
|---------|-----------|
| `translator/tests/test_translator.py` | +9 tests (3 lazy init `TestGetProvider`, 2 retry edge-cases, 2 batch, 2 generator) |
| `translator/core/translator.py` | Ajout `logger.info()` de création provider dans `get_provider()` |

#### Critère de validation

- [x] Couverture `translator.py` ≥ 95% → **100%** (92% → 100%)
- [x] Lazy init de `get_provider()` vérifié par test
- [x] Couverture globale ≥ 89% → **96%** (95% → 96%)

---

## 5. Couverture cible par module

| Module | Couverture actuelle | Couverture cible | Tâche |
|--------|--------------------|------------------|-------|
| `core/cache.py` | 97% | 97% | — |
| `core/config.py` | 100% | 100% | — |
| `core/io_json.py` | 100% | 100% | — |
| `core/io_xlsx.py` | 93% | 93% | — |
| `core/rate_limiter.py` | 97% | 97% | — |
| `core/translator.py` | 100% | 100% | IMP2-T005 ✅ |
| `core/translator_factory.py` | 92% | 92% | — |
| `modes/mode_analyze.py` | 97% | 97% | — |
| `modes/mode_translate_json.py` | 89% | 89% | — |
| `modes/mode_translate_dropdowns.py` | 98% | 98% | IMP2-T002 |
| **TOTAL** | **96%** | **≥ 96%** | — |

---

## 6. Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|-----------|
| IMP2-T001 : `--deepl-api-key` expose la clé dans le process list | Moyen | Moyen | Documenter le risque, recommander env var ou fichier `.env` en production ; le flag CLI est pour le dev local |
| IMP2-T001 : Ajout de flags à 3 subcommands = duplication dans `build_parser()` | Faible | Faible | ✅ Extraire une fonction `_add_provider_args(parser)` partagée — fait lors de l'implémentation |
| IMP2-T002 : Branches non couvertes révèlent des bugs | Faible | Moyen | C'est l'objectif de TDD — les bugs seront corrigés |
| IMP2-T003 : CI échoue sur le Docker build | Moyen | Faible | Le Dockerfile de test copie `tests/`, le workflow CI ne build pas en prod |

---

## 7. Décisions d'architecture (v2.0)

| Date | Décision | Rationale |
|------|----------|-----------|
| 2026-05-11 | Flags CLI provider disponibles sur **tous** les subcommands | Cohérence UX : le provider est un paramètre global, pas lié à un mode |
| 2026-05-11 | `--deepl-api-key` accepté en CLI malgré le risque process list | Usage local uniquement (pas de déploiement serveur), env var recommandée pour les clés sensibles |
| 2026-05-11 | `--deepl-use-free-api` comme `store_true` (défaut : env var ou `true`) | DeepL Free API est le cas d'usage le plus courant ; le flag explicite l'override |
| 2026-05-11 | `--fallback` comme `store_true` (défaut : env var ou `false`) | Fallback désactivé par défaut pour ne pas gaspiller le quota DeepL |
| 2026-05-11 | Harmonisation CI : `ruff format --check` remplace `black --check` | Un seul outil de format (ruff), suppression de la dépendance black en CI |
| 2026-05-11 | Suppression `.venv/` — remplacé par hook git Docker | Tout tourne en Docker ; le hook `pre-commit` exécute `ruff check` + `ruff format --check` (service `lint`) et `pytest` (service `test`) via `docker compose`. Plus aucune dépendance Python locale. |
| 2026-05-11 | Ajout `logger.info()` dans `get_provider()` à la création du provider | Traçabilité : le lazy init est silencieux sans log ; le message `Creating translation provider: %s (fallback=%s)` permet de diagnostiquer quel provider est instancié et si le fallback est actif, sans impacter le comportement métier |

---

## 8. Historique des Commits (v2.0)

| Date | Branche | Commit | Description |
|------|---------|--------|-------------|
| 2026-05-11 | `main` | `1a2b1ed` | docs: rewrite README.md for v2.0 |
| 2026-05-11 | `main` | — | docs: add roadmap v2.0 plan |
| 2026-05-11 | `test/IMP2-T005-translator-coverage` | `b08a8de` | feat(IMP2-T005): translator.py 92%→100% coverage, lazy init + log tests |
| 2026-05-11 | `feat/IMP2-T001-cli-providers` | `8a93f06` | feat(cli): add provider flags to CLI (IMP2-T001) |
| 2026-05-11 | `feat/IMP2-T002-dropdowns-coverage` | `2c19018` | test(dropdowns): add coverage for mode_translate_dropdowns.py (IMP2-T002) |
| 2026-05-11 | `chore/IMP2-T004-cleanup-venv` | *(local)* | chore: remove .venv/ (83 Mo), add note to README (IMP2-T004) |

---

## 9. Notes

- **Version** : Le bump de version `1.1.0` → `2.0.0` a été effectué lors du commit IMP2-T001 (changement fonctionnel majeur : CLI complet pour les providers).
- **IMP2-T003** est observationnelle : le premier push déclenchera la CI. On observera le résultat et on corrigera si nécessaire.
- **IMP2-T004** est terminée : `.venv/` supprimé (83 Mo libérés). Le hook git `pre-commit` a été remplacé par un script Docker qui exécute `ruff check + ruff format --check` (service `lint`) et `pytest` (service `test`). Plus aucune dépendance Python locale.
