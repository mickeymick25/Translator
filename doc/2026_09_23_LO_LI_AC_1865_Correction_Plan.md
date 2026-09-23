# Plan d'action & suivi — Correction `LO_LI_AC_1865` (et doublons associés)

**Date de création :** 2026-09-23
**Dernière mise à jour :** 2026-09-23
**Statut global :** ⏸ Plan proposé — en attente de validation humaine
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
| 4 | **FIX-1865-04** | Auditer `PA_CO_VI_859` et `LO_LO_AD_413` (autres doublons) | Moyenne | ⏸ Proposé |
| 5 | **FIX-1865-05** | Garde-fou anti-doublon pour tout futur chargement de CSV de référence | Moyenne | ⏸ Proposé |
| 6 | **FIX-1865-06** | Réindexation RAG + gouvernance (candidat état B) | Basse | ⏸ Proposé |

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

**Statut :** ⏸ Proposé
**Fichier :** `translator/source/2026_06_12_Import/Export_COP_Excel.csv`

| Clé | Occurrences | État actuel | Décision attendue |
|-----|-------------|-------------|-------------------|
| `PA_CO_VI_859` | ×3 (Start date / End date / Save) | FR finale « Soumettre », EN **vide** dans le master actuel | Le métier tranche (valeur conservée ? clé morte ?) |
| `LO_LO_AD_413` | ×2 (Fax / Mobile) | FR « Numéro de téléphone portable », cohérente avec l'EN | RAS documenté, clôturer |

#### Sous-tâches

- [ ] Demander arbitrage métier sur `PA_CO_VI_859`
- [ ] Documenter la décision dans ce doc (journal) et clôturer

### FIX-1865-05 — Garde-fou anti-doublon (loader CSV de référence)

**Statut :** ⏸ Proposé
**Contexte :** la fusion 06_12 était ad hoc (scripts supprimés dans `b61f0aa`) ;
le pipeline actuel n'a pas d'étape de fusion CSV. Si elle est réintégrée (ou
tout script équivalent), le chargement doit détecter les clés dupliquées.

#### Sous-tâches

- [ ] Fonction utilitaire `load_reference_csv()` dans `pipeline_common.py` : lève une erreur explicite listant les clés dupliquées (au minimum avertissement bloquant avec confirmation)
- [ ] Test unitaire (cas doublon → erreur avec les 3 clés connues du CSV réel)
- [ ] Ajouter la détection des clés dupliquées du CSV à l'étape 3 du pipeline (coquilles) ou au rapport d'analyse, si la fusion CSV revient dans le pipeline

### FIX-1865-06 — Réindexation RAG + gouvernance

**Statut :** ⏸ Proposé

#### Sous-tâches

- [ ] Réindexer le hub après création des docs : `/Users/michaelboitin/Documents/02_Dev/01_LocalRag_engine/AI/chroma/index-project.sh <racine du projet>`
- [ ] Inscrire en **état B** (registre `docs/gouvernance-connaissances.md` racine COP) la connaissance candidat à promotion : *« un fichier de référence métier indexé par clé peut écraser silencieusement des valeurs si la clé est dupliquée (last-occurrence-wins) — tout chargement de référence doit détecter les doublons »* (test de promotabilité : formulable sans termes propres au sous-projet, touche tout domaine COP ingérant des références CSV)

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

## 6. Règles de mise à jour

- Chaque changement de statut fait l'objet d'une ligne dans le journal (§5) : date, ID, événement, auteur.
- Statuts : ⏸ Proposé · 🔄 En cours · ⏸ En attente validation métier · ✅ Terminé · ❌ Rejeté/Abandonné.
- Une action n'est ✅ que si sa section « Validation » est satisfaite et tracée.
- À la clôture complète : archiver ce doc (il reste l'historique d'audit) et
  indexer le résumé de la correction dans le hub RAG via le workflow mémoire.