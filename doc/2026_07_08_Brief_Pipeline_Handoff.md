# Brief — Pipeline de traduction orchestré (nouveau thread)

## Contexte

Le projet **COP Translation Service** (dans `COP_translations/`) est un service de traduction automatique de fichiers JSON (interface COP) vers 9 langues cibles (FR, CZ, SK, DE, IT, AR, PT, ES, HU). Il utilise Google Translate, DeepL ou Ollama (LLM local/cloud) avec cache intelligent, rate limiting, validation structurelle et interface CLI.

Aujourd'hui, le processus de traduction d'une nouvelle version source nécessite d'enchaîner manuellement plusieurs scripts indépendants. L'objectif est de construire un **pipeline orchestré en une seule commande** (`translator/pipeline.py`) pour rendre les développeurs autonomes.

## Document de référence

`doc/2026_07_08_Pipeline_Orchestre_Analyse.md` — analyse complète, architecture, suivi d'avancement (19 tâches), et **décisions tranchées**.

## Décisions already tranchées

1. **Interactivité** : confirmation aux **étapes clés** (après rapport d'analyse, après gestion clés modifiées, avant lancement traduction).
2. **Provider** : **choix utilisateur** au lancement (Google / Ollama / hybride auto). Défaut : hybride.
3. **Coquilles source** : **demander correction du fichier source** avant de poursuivre. Dictionnaire `translator/source_typos.json` avec 6 coquilles connues : `Paring Error`→`Pairing Error`, `Inprogress`→`In progress`, `Hiearchy`→`Hierarchy`, `TItle`→`Title`, `Parners`→`Partners`, `Desactive`→`Deactivate`.
4. **Langues** : **demander à l'utilisateur** (toutes par défaut, ou `--languages fr,de`).
5. **Implémentation** : **incrémentale en 3 phases**.

## Plan d'implémentation incrémental

### Phase 1 — Analyse + rapport interactif (étapes 1-5)

| Tâche | Description |
|---|---|
| Refactoring `compare_sources.py` | Rendre les fonctions importables (séparer logique du `main()`) |
| Refactoring `analyze_translation_gap.py` | Idem |
| Refactoring `translator/validate_translations.py` | Idem |
| Créer `translator/source_typos.json` | Dictionnaire des 6 coquilles connues |
| `pipeline.py` étape 1 | Détection auto du dernier `*_Import/*.json` et du précédent (réutilise `core/config.py`) |
| `pipeline.py` étape 2 | Comparaison sources (réutilise `compare_sources.py`) |
| `pipeline.py` étape 3 | Détection coquilles source + demande de correction |
| `pipeline.py` étape 4 | Analyse écart de traduction (réutilise `analyze_translation_gap.py`) |
| `pipeline.py` étape 5 | Rapport consolidé + confirmation interactive |

### Phase 2 — Exécution (étapes 6-8)

| Tâche | Description |
|---|---|
| `pipeline.py` étape 6 | Pré-peuplement du dossier output + gestion clés modifiées (retraduire/garder/saisie manuelle) |
| `pipeline.py` étape 7 | Lancement traduction via `service.py translate-json` (provider choisi par utilisateur) |
| `pipeline.py` étape 8 | Réordonnancement auto des fichiers vers l'ordre source |

### Phase 3 — Validation + rapport final (étapes 9-11)

| Tâche | Description |
|---|---|
| `pipeline.py` étape 9 | Validation structurelle (réutilise `validate_translations.py`) |
| `pipeline.py` étape 10 | Détection mésalignements intra-langue (heuristique token overlap) |
| `pipeline.py` étape 11 | Rapport consolidé final → `doc/{date}_Pipeline_Report.md` |
| Tests | Tests unitaires du pipeline |
| Mode dry-run | `--dry-run` : rapport sans exécution |
| Documentation | README FR + EN |
| Test end-to-end | Validation avec source en10 |

## Scripts existants à réutiliser (ne pas réécrire)

| Script | Rôle | Chemin |
|---|---|---|
| `compare_sources.py` | Compare deux sources JSON (ajouts/suppressions/modifications, placeholders, préfixes) | Racine projet |
| `analyze_translation_gap.py` | Écart entre export et nouvelle source (add/remove/modify/incomplete/over-filled par langue) | Racine projet |
| `translator/validate_translations.py` | Validation structurelle (manquantes/excédantes/vides/placeholders/doublons/non traduits) | `translator/` |
| `translator/service.py` | Service de traduction CLI (`translate-json` mode) | `translator/` |
| `translator/core/config.py` | Auto-détection source (`_find_latest_import_folder`, `_find_source_file_in_import`) | `translator/core/` |

**Important** : ces scripts doivent rester **utilisables indépendamment** en CLI. Le pipeline importe leurs fonctions (refactoring mineur : séparer la logique du `main()` en fonctions importables, sans casser l'usage CLI).

## Architecture du pipeline

```
translator/pipeline.py
├── Étape 1: Détection source + précédente (auto)
├── Étape 2: Comparaison sources (import compare_sources)
├── Étape 3: Coquilles source (source_typos.json + correction interactive)
├── Étape 4: Analyse écart (import analyze_translation_gap)
├── Étape 5: Rapport + confirmation ──── [ÉTAPE CLÉ : confirmation]
├── Étape 6: Pré-peuplement + gestion clés modifiées ──── [ÉTAPE CLÉ : confirmation]
├── Étape 7: Traduction (service.py, provider choisi)
├── Étape 8: Réordonnancement auto
├── Étape 9: Validation (import validate_translations)
├── Étape 10: Mésalignements
└── Étape 11: Rapport consolidé → doc/{date}_Pipeline_Report.md
```

## État actuel du projet

- **Source courante** : `translator/source/2026_07_08_Import/en 10.json` (2545 clés, corrigée : `Pairing Error`).
- **Dernier export** : `translator/output/2026_07_08_Export/` (9 langues × 2545 clés, ordre EN10, validé).
- **Suite verte** : 771 tests, ruff propre.
- **Commits** : 18 commits sur `main` (pas de remote — pas de push).
- **Venv local** : `translator/.venv/` (Python 3.13, `deep_translator`, `openpyxl`, `requests`, `pytest`, `ruff`).
- **Docker** : fonctionnel (pre-commit hooks via Docker), mais le venv local est utilisé pour les runs interactifs.
- **Ollama** : `minimax-m3:cloud` accessible sur `localhost:11434`.
- **README** : bilingue FR/EN (`README.md` + `README.en.md`), à jour (v3.2.0, 9 langues).

## Conventions du projet

- **Commits** : Conventional Commits (`feat(scope):`, `fix(scope):`, `docs:`, `chore:`, `test(scope):`).
- **Pre-commit hooks** : ruff lint+format + pytest (via Docker). Tout commit passe par les hooks.
- **Langues** : codes projet `cz`/`sk` (différents des codes API `cs`/`sk`), gérés dans `core/config.py` `LANGUAGES`.
- **Cache** : `translator/output/.translation_cache.json` (gitignoré), format composite v2 `src:tgt:key_id:text`.
- **Output** : dossiers datés `output/{YYYY_MM_DD}_Export/` (gitignorés `output/**/*.json`).
- **Source** : dossiers datés `source/{YYYY_MM_DD}_Import/` (gitignorés `source/**/*.json`).

## Ce qui est hors périmètre

- Correction automatique des mésalignements (le pipeline signale, ne corrige pas).
- Gestion des overrides manuels (dictionnaire de surcharge FR, Email→ar, Monitoring→FR, R1 conservé).
- Mode `translate-dropdowns` (le pipeline couvre uniquement `translate-json`).
- Push/git (pas de remote).

## Démarrage

Commencer par la **Phase 1** :
1. Lire `doc/2026_07_08_Pipeline_Orchestre_Analyse.md` pour le contexte complet.
2. Refactorer `compare_sources.py`, `analyze_translation_gap.py`, `validate_translations.py` (rendre importable).
3. Créer `translator/source_typos.json`.
4. Construire `translator/pipeline.py` étapes 1-5.
5. Tester avec la source en10.