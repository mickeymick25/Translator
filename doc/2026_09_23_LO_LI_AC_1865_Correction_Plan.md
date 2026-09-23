# Plan d'action & suivi — Correction `LO_LI_AC_1865` (et doublons associés)

**Date de création :** 2026-09-23
**Dernière mise à jour :** 2026-09-23
**Statut global :** ✅ Plan exécuté (FIX-1865-01..06, 2026-09-23) — suite : décision métier sur R4 (promotion ou clôture)
**Référence :** [Analyse de l'anomalie](2026_09_23_LO_LI_AC_1865_FR_Misalignment_Analysis.md) · rapport EN partagé aux devs

---

## 1. Contexte et objectif

La clé `LO_LI_AC_1865` ("Add logistic link") porte une traduction FR erronée
("Ajouter un lien d'animation") depuis l'export `2026_06_12` — cause racine :
clé dupliquée dans le CSV de référence métier `Export_COP_Excel.csv`
(lignes 1981-1982), écrasement silencieux *last-occurrence-wins* lors de la
fusion FR↔CSV. La corruption s'est propagée d'export en export via le
pré-peuplement (étape 6 du pipeline). Non détectée à ce jour par aucun
contrôle (`FR_Misalignment_History.md`, step10).

**Objectif :** corriger la valeur expédiée au métier, corriger la source de
vérité, empêcher la récurrence, et auditer les cas jumeaux.

## 2. Principes

| Principe | Description |
|----------|-------------|
| **Gouvernance** | L'agent propose, l'humain valide, Git trace (cf. AGENTS.md racine) |
| **Séquenciel** | Une action à la fois, dans l'ordre de priorité défini |
| **Branches** | Chaque FIX fait l'objet d'une branche `fix/FIX-1865-0x-description` |
| **Commits** | Convention : `type(scope): description` (fix, test, feat, docs, chore) |
| **Historique préservé** | Les exports 06_12 → 09_03 (hors Final) sont des archives : on ne les patche pas, on les documente |
| **Trace RAG** | Toute mise à jour de ce doc est suivie d'une réindexation du hub |

## 3. Ordre d'exécution

| Ordre | ID | Action | Priorité | Statut |
|-------|----|--------|----------|--------|
| 1 | **FIX-1865-01** | Corriger le CSV de référence (clé dupliquée + typo) | Haute | ❌ Abandonné |
| 2 | **FIX-1865-02** | Corriger la FR dans l'export final expédié | Haute | ✅ Terminé |
| 3 | **FIX-1865-03** | Détecteur de duplication FR (intégré au pipeline, étape 10) | Haute | ✅ Terminé |
| 4 | **FIX-1865-04** | Audit `PA_CO_VI_859` et `LO_LO_AD_413` (autres doublons) | Moyenne | ✅ Terminé (analyse seule) |
| 5 | **FIX-1865-05** | Garde-fou anti-doublon pour tout futur chargement de CSV de référence | Moyenne | ✅ Terminé |
| 6 | **FIX-1865-06** | Réindexation RAG + gouvernance (candidat état B) | Basse | ✅ Terminé |

## 4. Suivi détaillé par action

### FIX-1865-01 — Corriger le CSV de référence

**Statut :** ❌ Abandonné (2026-09-23) — décision humaine
**Fichier :** `translator/source/2026_06_12_Import/Export_COP_Excel.csv`

**Motif d'abandon :** ce CSV est un artefact d'import historique, plus consommé
par le pipeline (la fusion CSV du 06_12 était ad hoc, scripts supprimés dans
`b61f0aa`). Aucune correction prévue : si une fusion CSV de référence était
réintégrée un jour, la valeur dupliquée serait détectée par le garde-fou
(FIX-1865-05). La valeur métier erronée reste couverte par FIX-1865-02 (export
final) et FIX-1865-03 (détection de récurrence).

#### Sous-tâches

- [x] Ligne 1982 : clé `LO_LI_AC_1865` → `LO_LI_AC_1866` — *non appliqué, action abandonnée*
- [x] Ligne 1982 : label « Activate **Amination** link » → « Activate **Animation** link » — *non appliqué, action abandonnée*
- [x] Vérifier qu'aucune autre référence n'utilise la valeur erronée de la ligne 1982 — *vérifié : seuls les exports 06_12+ la consomment (traités par FIX-1865-02)*

**Validation :** n/a (action abandonnée).

### FIX-1865-02 — Corriger la FR de l'export final

**Statut :** ✅ Terminé (2026-09-23)
**Fichier :** `translator/output/2026_09_03_Final_Export/translation_en_fr.json`
**Modification :** `LO_LI_AC_1865` : "Ajouter un lien d'animation" → **"Ajouter un lien logistique"**

#### Sous-tâches

- [x] Prérequis arbitré — preuve : `doc/2026_09_03_Changes_Report_for_Devs.md` §6 « Files to Deploy » liste explicitement `2026_09_03_Final_Export/` (10 langues × 2689 clés)
- [x] Patch de la valeur (1 clé, ligne 2302)
- [x] Rejouer `validate_translations.py` sur le fichier FR patché → **0 missing, 0 extra, 0 placeholder issue, 0 duplicate** (41 vides attendus = EN vide ; 150 identiques EN — attendus)
- [x] Vérifier qu'aucun fichier FR aval ne reprend la valeur corrompue — scan complet `output/**/*.json` : ne reste que 9 **archives** (06_12, 06_23, 06_25, 06_26, 07_08, 09_03, run2-4), conservées telles quelles ; `Final_Export` et tout fichier aval propres

**Décision documentaire :** les exports historiques 06_12 → 09_03 contiennent
la valeur corrompue — conservés tels quels (archives), référence croisée vers
le doc d'analyse.

**Validation :** ✅ `LO_LI_AC_1865` = "Ajouter un lien logistique" ≠ `LO_LI_AC_1866`
dans le fichier final ; 2689 clés intactes ; contrôle structurel complet passé.
Note : `output/` est gitignore — la trace d'audit de ce patch est ce journal.

### FIX-1865-03 — Détecteur de duplication FR (récurrence)

**Statut :** ✅ Terminé (2026-09-23)
**Fichiers :** `translator/pipeline.py` (étape 10), tests `translator/tests/test_pipeline.py`

Le détecteur actuel (`detect_misalignments`, pipeline.py:921) couvre le cas
inverse (même EN → traductions divergentes). L'anomalie 1865 est le cas
**jumeau** : EN différents → même traduction.

#### Sous-tâches

- [x] Nouvelle fonction `detect_duplicated_translations()` (pipeline.py) : groupes de clés à traduction identique non vide dont les textes source (EN) diffèrent après normalisation token (casse/accents/ponctuation ignorés, C15 pour textes sans token) — entrée marquée `type: "duplicated_translation"`, fusionnée dans le retour de `step10_detect_misalignments` et rendue dans la section 8 du rapport final (sous-tableau dédié)
- [x] Test unitaire avec le cas 1865/1866 comme fixture (`TestDetectDuplicatedTranslations`, 6 tests : détection 1865, EN identique à la casse près non signalé, synonymes légitimes signalés en advisory, clé unique, EN vide, EN sans token)
- [x] Backfill : scan de tous les exports historiques — **105 fichiers scannés, couple 1865/1866 détecté dans exactement les 9 archives FR corrompues** (06_12, 06_23, 06_25, 06_26, 07_08, 09_03, run2-4) ; absent des exports sains (04_13 → 06_11) et du `Final_Export` patché

**Validation :** ✅ suite complète `test_pipeline.py` : **170/170 passés**
(inclut le cas 1865/1866 et les tests step10/rapport existants). Volume
advisory constaté sur `Final_Export` (toutes langues) : 404 signalements
(FR 87, cz 45, sk 46, de 41, hu 42, ar 42, pl 34, it 28, es 22, pt 17) —
des paires légitimes de synonymes y figurent, sortie à vérifier
manuellement, cohérente avec la philosophie advisory de l'étape 10.

### FIX-1865-04 — Audit des autres doublons du CSV

**Statut :** ✅ Terminé (2026-09-23) — **analyse seule, aucun changement**
**Fichier :** `translator/source/2026_06_12_Import/Export_COP_Excel.csv`
**Décision Michael :** pas de changement dans les exports, sources non
modifiées — le constat est documenté, la décision d'exploiter (ou non) ces
connaissances reste ouverte.

| Clé | Occurrences | Constat (versions 04_13 → 09_03) | Conclusion |
|-----|-------------|----------------------------------|------------|
| `PA_CO_VI_859` | ×3 (Start date / End date / Save) | EN **vide dans les 11 versions source** ; FR vide jusqu'au 06_11 puis **« Soumettre »** depuis le 06_12 (injection par la fusion CSV, ligne dupliquée « Save ») | incohérence EN vide / FR rempli — **constaté, non corrigé** (analyse seule) ; si la clé reprenait vie, arbitrer FR |
| `LO_LO_AD_413` | ×2 (Fax / Mobile) | EN « Mobile number » constant ; FR actuel « Numéro de téléphone portable » cohérent | **RAS** — clôturé ; archive : FR « Mobilní číslo » (tchèque) dans l'export 05_27, corrigé ensuite |

#### Sous-tâches

- [x] Audit factuel des deux clés (11 versions source + 10 exports FR)
- [x] Décision tracée : **aucun changement** (export/source intacts) — anomalie 859 documentée pour décision métier future

**Validation :** ✅ faits vérifiés par trace systématique (aucune écriture).

### FIX-1865-05 — Garde-fou anti-doublon (loader CSV de référence)

**Statut :** ✅ Terminé (2026-09-23)
**Fichiers :** `translator/pipeline_common.py`, `translator/pipeline.py` (étape 3), tests

La fusion 06_12 était ad hoc (scripts supprimés dans `b61f0aa`) ; le pipeline
actuel n'a pas d'étape de fusion CSV. Si elle est réintégrée (ou tout script
equivalent), le chargement doit détecter les clés dupliquées.

#### Sous-tâches

- [x] Fonction utilitaire `load_reference_csv()` dans `pipeline_common.py` : lève `DuplicateReferenceKeysError` listant les clés dupliquées (avec lignes) — aucune écriture, lecture seule
- [x] Test unitaire : CSV propre parsé ; CSV à doublons (fixture = les 3 clés réelles du CSV 06_12) → erreur explicite avec lignes
- [x] Détection advisory branchée sur l'étape 3 du pipeline : tout `Export_*.csv` présent dans le dossier d'import est contrôlé (⚠️ avec détail des doublons, ou ✅ propre) — la fusion CSV n'est pas de retour, ce hook signale seulement

**Validation :** ✅ suite `test_pipeline.py` : **174/174 passés** (4 nouveaux
tests garde-fou + intégration step3) ; ruff OK ; les sources ne sont jamais
écrites par le garde-fou.

### FIX-1865-06 — Réindexation RAG + gouvernance

**Statut :** ✅ Terminé (2026-09-23)

#### Sous-tâches

- [x] Réindexer le hub après création des docs : `/Users/michaelboitin/Documents/02_Dev/01_LocalRag_engine/AI/chroma/index-project.sh <racine du projet>` — ✅ exécutée (knowledge 37 → 39 chunks, `gouvernance-connaissances.md` modifié réindexé en 11 chunks)
- [x] Inscription en **état B** (registre `docs/gouvernance-connaissances.md` racine COP) : entrée **R4** — *référence métier indexée par clé : détecter les doublons avant toute fusion (last-occurrence-wins)* — vérifiée requêtable (chunk `gouvernance-connaissances.md::6`) ; promotion B → C laissée à évaluer par l'humain

**Observation (hors périmètre chantier) :** le `.rag.yaml` scanne la racine
`docs/` uniquement — les docs du sous-projet (`COP_translations/doc/`) ne sont
pas dans le périmètre du hub. Étendre le périmètre est une décision de
gouvernance séparée.

## 5. Journal de suivi

| Date | Action | Événement | Auteur |
|------|--------|-----------|--------|
| 2026-09-23 | — | Création du plan d'action (analyse préalable : [rapport](2026_09_23_LO_LI_AC_1865_FR_Misalignment_Analysis.md)) | Agent (proposition) |
| 2026-09-23 | — | Rapport EN partagé aux devs | Michael |
| 2026-09-23 | — | Plan EN créé pour handover devs | Agent |
| 2026-09-23 | **FIX-1865-01** | ❌ Abandonné : CSV de référence archivé, plus consommé par le pipeline — décision Michael. Correction valeur portée par FIX-1865-02, récurrence par FIX-1865-03 | Michael |
| 2026-09-23 | **FIX-1865-02** | ✅ Patch FR appliqué sur `2026_09_03_Final_Export/translation_en_fr.json` (arbitrage export prouvé par Changes_Report §6) + validation structurelle OK + scan aval OK | Agent |
| 2026-09-23 | **FIX-1865-03** | ✅ Détecteur `detect_duplicated_translations()` intégré à l'étape 10 + rendu section 8 du rapport + 6 tests unitaires (fixture 1865/1866) — 170/170 tests OK — backfill : 9/9 archives corrompues détectées, 105 fichiers scannés | Agent |
| 2026-09-23 | **FIX-1865-03** | Commit `bf38039` sur branche `fix/FIX-1865-03-detecteur-duplication` (hooks OK : lint + 873 tests conteneur ; correction Dockerfile préexistante : COPY validate_translations.py) — **contrainte : pas de push vers origin, travail local uniquement** | Michael |
| 2026-09-23 | **FIX-1865-03** | ✅ Squash-merge vers `main` (`2571ece`) — branche locale conservée | Agent |
| 2026-09-23 | **FIX-1865-04** | ✅ Audit factuel (analyse seule) : 859 EN vide ×11 / FR « Soumettre » depuis 06_12 (fusion CSV) — 413 RAS ; décision Michael : aucun changement export/source | Michael |
| 2026-09-23 | **FIX-1865-05** | ✅ Garde-fou `load_reference_csv()` + exception `DuplicateReferenceKeysError` + hook advisory étape 3 — 174/174 tests | Agent |
| 2026-09-23 | **FIX-1865-06** | ✅ R4 inscrite au registre état B (racine, hors dépôt Git — pas de .git racine) + réindexation hub OK (37→39 chunks, R4 requêtable) ; observation : périmètre du hub = racine docs/ seulement | Agent |
| 2026-09-23 | — | Push vers `origin` autorisé (contrainte locale levée) — `main` poussé avec l'ensemble des commits locaux | Michael |

## 6. Règles de mise à jour

- Chaque changement de statut fait l'objet d'une ligne dans le journal (§5) : date, ID, événement, auteur.
- Statuts : ⏸ Proposé · 🔄 En cours · ⏸ En attente validation métier · ✅ Terminé · ❌ Rejeté/Abandonné.
- Une action n'est ✅ que si sa section « Validation » est satisfaite et tracée.
- À la clôture complète : archiver ce doc (il reste l'historique d'audit) et
  indexer le résumé de la correction dans le hub RAG via le workflow mémoire.