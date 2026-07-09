# Pipeline de traduction orchestré — Analyse et suivi

- **Date** : 2026-07-08
- **Demandeur** : Michael Boitin
- **Objectif** : fournir aux développeurs un parcours guidé en une seule commande pour produire les fichiers traduits à partir d'une nouvelle source EN, de façon autonome et reproductible.

## Contexte

Le projet dispose aujourd'hui de plusieurs scripts indépendants :
- `compare_sources.py` — compare deux sources JSON (ajouts/suppressions/modifications, deltas de placeholders, groupement par préfixe).
- `analyze_translation_gap.py` — analyse l'écart entre un export existant et une nouvelle source (add/remove/modify/incomplete/over-filled par langue).
- `translator/service.py translate-json` — traduit via Google/DeepL/Ollama avec cache, reprise, checkpoint.
- `translator/validate_translations.py` — valide les fichiers traduits vs source (manquantes/excédantes/vides/placeholders/doublons/non traduits).

Ces outils fonctionnent mais nécessitent de connaître l'ordre des étapes, les paramètres, et les actions manuelles intermédiaires (pré-peuplement du dossier, suppression des clés à retraduire, réordonnancement, gestion des coquilles source). Un développeur non familier avec le processus ne peut pas être autonome.

## Besoin

**Une seule commande** qui enchaîne tout le parcours, de l'analyse à la validation, avec un rapport à chaque étape et une confirmation avant action.

```
python translator/pipeline.py
```

### Parcours attendu

1. **Détecter** la nouvelle source (dernier `*_Import/*.json`) et la source précédente.
2. **Comparer** les deux sources (ajouts, suppressions, modifications).
3. **Détecter les coquilles source** connues et proposer correction.
4. **Analyser** l'écart entre le dernier export et la nouvelle source (par langue).
5. **Produire un rapport** consolidé et **demander confirmation**.
6. **Pré-peupler** le nouveau dossier d'output (copie du dernier export).
7. **Gérer les clés modifiées** (retraduire vs garder l'existant vs saisie manuelle).
8. **Lancer la traduction** (provider approprié).
9. **Réordonner** les fichiers selon l'ordre de la source.
10. **Valider** (validation structurelle + détection de mésalignements).
11. **Produire un rapport final** consolidé dans `doc/`.

## Axes d'amélioration proposés

### 1. Détection automatique des coquilles source

Un dictionnaire de coquilles récurrentes (constitué au fil des cycles) permet de détecter et proposer correction avant traduction.

Coquilles connues à date :
- `Paring Error` → `Pairing Error` (BU_ST_ME_2169, revenu 3 fois)
- `Inprogress` → `In progress` (PA_AU_MO_1069, revenu 2 fois)
- `Hiearchy` → `Hierarchy` (LO_LI_HE_2006)
- `TItle` → `Title` (PA_ID_HE_880)
- `Parners` → `Partners` (DA_TA_LA_2110)
- `Desactive` → `Deactivate` (PA_US_TA_684, source en10)

Le dictionnaire serait stocké dans un fichier `translator/source_typos.json` (maintenable, enrichissable).

### 2. Sélection hybride du provider

Le pipeline analyse les clés à traduire et choisit le provider :
- **Clés avec placeholders** (`{{...}}`, `<strong>`, `%s`, `{name}`, ICU) → **Ollama** (la validation structurelle 5 contrôles protège les placeholders, avec retry).
- **Clés simples** (labels courts, pas de placeholders) → **Google** (rapide, cohérent par texte via cache legacy).
- **Mode manuel** : le développeur peut forcer un provider unique.

Justification : on a constaté qu'Ollama peut produire des incohérences sur les labels courts (traduit par clé, pas par texte), tandis que Google garantit la cohérence (cache legacy par texte). Mais Ollama préserve mieux les placeholders (validation + retry). Le hybride tire le meilleur des deux.

### 3. Réordonnancement automatique

Après le run de traduction, le pipeline réordonne **automatiquement** tous les fichiers de sortie selon l'ordre des clés de la source. Plus besoin d'étape manuelle.

Cause : le chemin Ollama (chunking 50 entrées) produit les clés en ordre de chunks, pas en ordre source. Le chemin Google préserve l'ordre source (itération sur `list(source_data.keys())`). Le réordonnancement uniformise les deux.

### 4. Détection de mésalignements post-traduction

Le pipeline exécute un contrôle de **cohérence intra-langue** : pour chaque texte source partagé par plusieurs clés, vérifier que la traduction est cohérente (pas de valeurs divergentes sans rapport). Signaler les écarts dans le rapport final.

Cette détection est **heuristique** (comparaison de tokens) et produit des faux positifs (synonymes, cognates, pluriels). Le pipeline **signale** mais ne **corrige pas** automatiquement — la correction reste humaine.

### 5. Mode dry-run

```
python translator/pipeline.py --dry-run
```

Affiche le rapport complet (comparaison, écart, coquilles, plan d'action) sans rien exécuter. Utile pour validation avant run réel.

### 6. Rapport consolidé

Un seul fichier `doc/{date}_Pipeline_Report.md` avec toutes les sections :

| Section | Contenu |
|---|---|
| 1. Source | Fichier détecté, nombre de clés, précédent source |
| 2. Comparaison | Ajouts, suppressions, modifications (avec détail) |
| 3. Coquilles source | Coquilles détectées + corrections appliquées |
| 4. Écart de traduction | Par langue : add/remove/modify/incomplete/over-filled |
| 5. Plan d'action | Clés à traduire, à retraduire, à conserver |
| 6. Traduction | Provider utilisé, clés traduites, durée, fallbacks |
| 7. Validation | 6 contrôles × N langues (manquantes, excédantes, vides, placeholders, doublons, non traduits) |
| 8. Mésalignements | Écarts de cohérence intra-langue signalés |
| 9. Ordre | Confirmation que tous les fichiers sont alignés sur la source |

### 7. Gestion des clés modifiées (interactive)

Pour chaque clé source modifiée, le pipeline présente :

```
Clé modifiée: LO_AF_CR_1285
  ancien source: "Parent company"
  nouveau source: "Current Profile"
  traduction actuelle (FR): "Société parent"
Action: [1] Retraduire  [2] Garder l'existant  [3] Saisir manuellement
```

- **Option 1 (Retraduire)** : supprimer la clé du fichier de sortie → la reprise la retraduit.
- **Option 2 (Garder l'existant)** : conserver la traduction actuelle (cas des coquilles source qui reviennent — on garde la bonne traduction basée sur la source correcte).
- **Option 3 (Saisie manuelle)** : le développeur saisit la traduction voulue.

### 8. Sauvegarde automatique

Avant chaque run, backup automatique des fichiers existants :
```
output/{date}_Export/translation_en_{lang}.json.bak_pre_pipeline
```

### 9. Choix des langues

Le pipeline permet de sélectionner les langues à traiter :
```
python translator/pipeline.py --languages fr,de
```
Par défaut : toutes les langues configurées dans `LANGUAGES` (hors `en`).

## Architecture technique

```
translator/pipeline.py              # Pipeline orchestré (nouveau)
├── Étape 1: Détection source + précédente (réutilise core/config.py)
├── Étape 2: Comparaison sources (réutilise compare_sources.py)
├── Étape 3: Coquilles source (nouveau — source_typos.json)
├── Étape 4: Analyse écart (réutilise analyze_translation_gap.py)
├── Étape 5: Rapport + confirmation interactive
├── Étape 6: Pré-peuplement + gestion clés modifiées
├── Étape 7: Traduction (réutilise service.py translate-json)
├── Étape 8: Réordonnancement auto (nouveau)
├── Étape 9: Validation (réutilise validate_translations.py)
├── Étape 10: Détection mésalignements (nouveau)
└── Étape 11: Rapport consolidé → doc/{date}_Pipeline_Report.md
```

### Dépendances

| Composant | Réutilisé | Nouveau |
|---|---|---|
| `compare_sources.py` | Import des fonctions | — |
| `analyze_translation_gap.py` | Import des fonctions | — |
| `translator/validate_translations.py` | Import des fonctions | — |
| `translator/service.py` | Appel via subprocess ou import | — |
| `translator/core/config.py` | Auto-détection source | — |
| `translator/source_typos.json` | — | Dictionnaire de coquilles |
| Réordonnancement | — | Fonction utilitaire |
| Détection mésalignements | — | Fonction heuristique |
| Rapport consolidé | — | Générateur markdown |
| Flow interactif | — | Confirmations + saisies |

### Scripts existants — non modifiés

Les scripts `compare_sources.py`, `analyze_translation_gap.py`, `validate_translations.py` restent **utilisables indépendamment**. Le pipeline importe leurs fonctions (refactoring mineur pour exposer des fonctions importables, sans casser l'usage CLI existant).

## Ce qui est hors périmètre

- **Correction automatique des mésalignements** : le pipeline signale mais ne corrige pas (trop de faux positifs, correction humaine requise).
- **Gestion des overrides manuels** (dictionnaire de surcharge FR, `Email`→ar, `Monitoring`→FR, `R1` conservé) : outil séparé si besoin, pas dans le pipeline.
- **Traduction dropdowns** (mode `translate-dropdowns`) : le pipeline couvre uniquement `translate-json` (le cas d'usage principal).
- **Push/git** : le pipeline ne committe pas (pas de remote, gestion manuelle).

## Suivi d'avancement

| # | Tâche | Statut | Dépendance |
|---|---|---|---|
| 1 | Refactoring : rendre `compare_sources.py` importable (fonctions séparées du `main()`) | ✅ | — |
| 2 | Refactoring : rendre `analyze_translation_gap.py` importable | ✅ | — |
| 3 | Refactoring : rendre `validate_translations.py` importable | ✅ | — |
| 4 | Créer `translator/source_typos.json` (dictionnaire de coquilles) | ✅ | — |
| 5 | Étape 1 : détection source + précédente | ✅ | config.py (existant) |
| 6 | Étape 2 : comparaison sources (intégration) | ✅ | Tâche 1 |
| 7 | Étape 3 : détection coquilles source | ✅ | Tâche 4 |
| 8 | Étape 4 : analyse écart de traduction | ✅ | Tâche 2 |
| 9 | Étape 5 : rapport + confirmation interactive | ✅ | Tâches 5-8 |
| 10 | Étape 6 : pré-peuplement + gestion clés modifiées | ✅ | Tâche 9 |
| 11 | Étape 7 : appel à `service.py translate-json` | ✅ | Tâche 10 |
| 12 | Étape 8 : réordonnancement auto | ✅ | Tâche 11 |
| 13 | Étape 9 : validation structurelle | ⬜ | Tâches 3, 12 |
| 14 | Étape 10 : détection mésalignements | ⬜ | Tâche 12 |
| 15 | Étape 11 : rapport consolidé markdown | ⬜ | Tâches 13-14 |
| 16 | Tests unitaires du pipeline | 🟡 | Tâches 5-15 |
| 17 | Mode dry-run | 🟡 | Tâches 5-15 |
| 18 | Documentation README (FR + EN) | ⬜ | Tâche 15 |
| 19 | Test end-to-end avec la source en10 | ⬜ | Tâche 15 |

### Légende

- ✅ terminé — ⬜ à faire — 🟡 partiel

### Notes de progression

- **2026-07-08 — Phase 1 terminée (tâches 1-9)** : refactoring des 3 scripts (fonctions importables + helpers `compare()`, `analyze_export()`, `validate()` / `render_report()`), dictionnaire `source_typos.json` (6 coquilles), pipeline `translator/pipeline.py` (étapes 1-5 : détection, comparaison, coquilles, écart, rapport + confirmation). Validation : 771 tests existants OK, ruff propre, dry-run sur en10 fonctionnel.
- **2026-07-08 — Rattrapage TDD Phase 1 (tâche 16 partielle)** : `translator/tests/test_pipeline.py` — 89 characterization tests couvrant les étapes 1-5 (classes `TestXxx` par fonction, fixtures fs de test via `tmp_path`, mocks `input`/`load_typos`, `@parametrize` sur `confirm()`). Couverture `pipeline.py` : **98%** (cible ≥ 90% atteinte). Suite complète : 860 tests OK (771 + 89), régression = 0.
- **2026-07-09 — Phase 2 terminée (tâches 10-12)** : étapes 6-8 développées en **TDD strict** (Red → Green → Refactor). Étape 6 : `backup_translation_file()`, `prepopulate_output()`, `manage_modified_keys()` (actions 1/2/3 interactives), `step6_prepopulate_and_manage()` (confirmation [ÉTAPE CLÉ]). Étape 7 : `step7_translate()` pilote `_translate_single_language` directement (évite le sous-dossier daté de `run()`), provider propagé via singleton Config. Étape 8 : `reorder_translation_file()` + `step8_reorder()`. `run_pipeline()` enchaîne les étapes 6-8 après confirmation. 34 nouveaux tests TDD (121 total sur pipeline), couverture 94%. Suite complète : 892 tests OK.
- **Tâche 17 (dry-run)** : implémenté pour les étapes 1-5 (rapport d'analyse sans exécution). Le dry-run complet (couvrant aussi étapes 6-11) sera finalisé après Phase 2/3.
- **Tâche 16 (tests)** : Phase 1 couverte (🟡). Tests Phase 2/3 à écrire en TDD strict au fil des étapes.

## Décisions tranchées (2026-07-08)

1. **Interactivité** : **confirmation aux étapes clés** (pas à chaque étape, pas une seule globale). Les étapes clés sont : (a) après le rapport d'analyse (comparaison + écart + coquilles), (b) après la gestion des clés modifiées, (c) avant le lancement de la traduction.
2. **Provider** : **choix laissé à l'utilisateur**. Le pipeline demande quel provider utiliser (Google / Ollama / hybride auto) au moment du lancement. Défaut proposé : hybride (Ollama pour les clés avec placeholders, Google pour les clés simples).
3. **Coquilles source** : **demander la correction du fichier source**. Le pipeline détecte les coquilles, affiche la liste, et demande confirmation pour corriger le fichier source avant de poursuivre. Le dictionnaire de coquilles est créé dès le départ avec les 6 coquilles connues.
4. **Scope langues** : **demander à l'utilisateur**. Le pipeline demande quelles langues traiter (toutes par défaut, ou un sous-ensemble). Option `--languages fr,de` en CLI également.
5. **Ordre d'implémentation** : **incrémental**. Phase 1 : étapes 1-5 (détection, comparaison, coquilles, écart, rapport + confirmation). Phase 2 : étapes 6-8 (pré-peuplement, gestion clés modifiées, traduction, réordonnancement). Phase 3 : étapes 9-11 (validation, mésalignements, rapport consolidé). Chaque phase est testée et validée indépendamment.

## Estimation

| Phase | Effort |
|---|---|
| Refactoring scripts (tâches 1-3) | ~1h |
| Dictionnaire coquilles (tâche 4) | ~15min |
| Pipeline étapes 5-11 (cœur) | ~3-4h |
| Tests + dry-run (tâches 16-17) | ~1h |
| Documentation (tâche 18) | ~30min |
| Test end-to-end (tâche 19) | ~30min |
| **Total** | **~6-7h** |