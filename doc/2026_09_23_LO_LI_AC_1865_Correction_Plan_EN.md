# Action Plan & Tracking — `LO_LI_AC_1865` correction (and related duplicates)

**Creation date:** 2026-09-23
**Last updated:** 2026-09-23
**Overall status:** ✅ Plan executed (FIX-1865-01..06, 2026-09-23) — next: business decision on R4 (promote or close)
**Reference:** [Anomaly analysis](2026_09_23_LO_LI_AC_1865_FR_Misalignment_Analysis.md) (EN, shared with devs) · [Plan FR](2026_09_23_LO_LI_AC_1865_Correction_Plan.md)

---

## 1. Context and objective

Key `LO_LI_AC_1865` ("Add logistic link") has carried a wrong FR translation
("Ajouter un lien d'animation") since the `2026_06_12` export — root cause: a
duplicated key in the business reference CSV `Export_COP_Excel.csv`
(lines 1981-1982), silently overwritten via *last-occurrence-wins* during the
FR↔CSV merge. The corruption propagated from export to export through
prepopulation (pipeline step 6). Never detected by any existing control
(`FR_Misalignment_History.md`, step 10).

**Objective:** fix the value shipped to the business, fix the source of truth,
prevent recurrence, and audit the twin cases.

## 2. Principles

| Principle | Description |
|-----------|-------------|
| **Governance** | Agent proposes, human validates, Git traces (cf. root AGENTS.md) |
| **Sequential** | One action at a time, in the priority order defined below |
| **Branches** | Each FIX gets its own branch `fix/FIX-1865-0x-description` |
| **Commits** | Convention: `type(scope): description` (fix, test, feat, docs, chore) |
| **History preserved** | Exports 06_12 → 09_03 (except Final) are archives: do **not** patch them, document them |
| **RAG trace** | Every update of this doc is followed by a reindex of the hub |

## 3. Execution order

| Order | ID | Action | Priority | Status |
|-------|----|--------|----------|--------|
| 1 | **FIX-1865-01** | Fix the reference CSV (duplicated key + typo) | High | ❌ Dropped |
| 2 | **FIX-1865-02** | Fix the FR value in the final shipped export | High | ✅ Done |
| 3 | **FIX-1865-03** | FR duplication detector (wired into pipeline step 10) | High | ✅ Done |
| 4 | **FIX-1865-04** | Audit `PA_CO_VI_859` and `LO_LO_AD_413` (other duplicates) | Medium | ✅ Done (analysis only) |
| 5 | **FIX-1865-05** | Duplicate-key guard for any future reference-CSV loader | Medium | ✅ Done |
| 6 | **FIX-1865-06** | RAG reindex + governance (state-B candidate) | Low | ✅ Done |

## 4. Detailed tracking per action

### FIX-1865-01 — Fix the reference CSV

**Status:** ❌ Dropped (2026-09-23) — human decision
**File:** `translator/source/2026_06_12_Import/Export_COP_Excel.csv`

**Drop rationale:** this CSV is a historical import artifact, no longer
consumed by the pipeline (the 06_12 CSV merge was ad hoc, scripts removed in
`b61f0aa`). No correction planned: if a reference-CSV merge ever comes back,
the duplicated value would be caught by the guard (FIX-1865-05). The wrong
business-facing value remains covered by FIX-1865-02 (final export) and
FIX-1865-03 (recurrence detection).

#### Sub-tasks

- [x] Line 1982: key `LO_LI_AC_1865` → `LO_LI_AC_1866` — *not applied, action dropped*
- [x] Line 1982: label "Activate **Amination** link" → "Activate **Animation** link" — *not applied, action dropped*
- [x] Check that no other reference consumes the wrong value from line 1982 — *checked: only the 06_12+ exports consume it (covered by FIX-1865-02)*

**Validation:** n/a (action dropped).

### FIX-1865-02 — Fix the FR value in the final export

**Status:** ✅ Done (2026-09-23)
**File:** `translator/output/2026_09_03_Final_Export/translation_en_fr.json`
**Change:** `LO_LI_AC_1865`: "Ajouter un lien d'animation" → **"Ajouter un lien logistique"**

#### Sub-tasks

- [x] Prerequisite arbitrated — evidence: `doc/2026_09_03_Changes_Report_for_Devs.md` §6 "Files to Deploy" explicitly lists `2026_09_03_Final_Export/` (10 languages × 2689 keys)
- [x] Patch the value (1 key, line 2302)
- [x] Re-run `validate_translations.py` on the patched FR file → **0 missing, 0 extra, 0 placeholder issue, 0 duplicate** (41 empties expected = empty EN; 150 EN-identical — expected)
- [x] Check that no downstream FR file reuses the corrupted value — full scan of `output/**/*.json`: only 9 **archives** remain (06_12, 06_23, 06_25, 06_26, 07_08, 09_03, run2-4), kept as-is; `Final_Export` and every downstream file clean

**Documentation decision:** historical exports 06_12 → 09_03 contain the
corrupted value — kept as-is (archives), cross-referenced in the analysis doc.

**Validation:** ✅ `LO_LI_AC_1865` = "Ajouter un lien logistique" ≠ `LO_LI_AC_1866`
in the final file; 2689 keys intact; full structural check passed.
Note: `output/` is gitignored — the audit trail of this patch is this journal.

### FIX-1865-03 — FR duplication detector (recurrence prevention)

**Status:** ✅ Done (2026-09-23)
**Files:** `translator/pipeline.py` (step 10), tests in `translator/tests/test_pipeline.py`

The current detector (`detect_misalignments`, pipeline.py:921) covers the
inverse case (same EN → diverging translations). The 1865 anomaly is the
**twin** case: different ENs → identical translation.

#### Sub-tasks

- [x] New function `detect_duplicated_translations()` (pipeline.py): groups of keys sharing a non-empty identical translation whose EN source texts differ after token normalization (case/accents/punctuation ignored, C15 for token-less texts) — entry flagged `type: "duplicated_translation"`, merged into `step10_detect_misalignments` output and rendered in report section 8 (dedicated sub-table)
- [x] Unit test with the 1865/1866 case as fixture (`TestDetectDuplicatedTranslations`, 6 tests: 1865 detection, case-only EN difference not flagged, legit synonyms flagged as advisory, single key, empty EN, token-less EN)
- [x] Backfill: scan of all historical exports — **105 files scanned, the 1865/1866 pair detected in exactly the 9 corrupted FR archives** (06_12, 06_23, 06_25, 06_26, 07_08, 09_03, run2-4); absent from clean exports (04_13 → 06_11) and from the patched `Final_Export`

**Validation:** ✅ full `test_pipeline.py` suite: **170/170 passed**
(includes the 1865/1866 case and existing step10/report tests). Advisory
volume measured on `Final_Export` (all languages): 404 flags
(FR 87, cz 45, sk 46, de 41, hu 42, ar 42, pl 34, it 28, es 22, pt 17) —
legit synonym pairs appear in the list, output to be verified manually,
consistent with step 10's advisory philosophy.

### FIX-1865-04 — Audit the other CSV duplicates

**Status:** ✅ Done (2026-09-23) — **analysis only, no change applied**
**File:** `translator/source/2026_06_12_Import/Export_COP_Excel.csv`
**Michael's decision:** no change in the exports, sources untouched — the
finding is documented; acting on it (or not) remains an open business call.

| Key | Occurrences | Finding (source 04_13 → 09_03) | Conclusion |
|-----|-------------|--------------------------------|------------|
| `PA_CO_VI_859` | ×3 (Start date / End date / Save) | EN **empty in all 11 source versions**; FR empty until 06_11 then **"Soumettre"** since 06_12 (injected by the CSV merge, duplicated "Save" row) | EN empty / FR filled inconsistency — **found, not fixed** (analysis only); arbitrate FR if the key ever comes back to life |
| `LO_LO_AD_413` | ×2 (Fax / Mobile) | EN "Mobile number" constant; current FR "Numéro de téléphone portable" consistent | **RAS** — closed; archive note: FR "Mobilní číslo" (Czech) in the 05_27 export, fixed afterwards |

#### Sub-tasks

- [x] Factual audit of both keys (11 source versions + 10 FR exports)
- [x] Decision traced: **no change** (export/source untouched) — 859 anomaly documented for a future business decision

**Validation:** ✅ facts verified via systematic trace (no write).

### FIX-1865-05 — Duplicate-key guard (reference CSV loader)

**Status:** ✅ Done (2026-09-23)
**Files:** `translator/pipeline_common.py`, `translator/pipeline.py` (step 3), tests

The 06_12 merge was ad hoc (scripts removed in `b61f0aa`); the current
pipeline has no CSV merge step. If it comes back (or any equivalent script),
the loader must detect duplicated keys.

#### Sub-tasks

- [x] Utility function `load_reference_csv()` in `pipeline_common.py`: raises `DuplicateReferenceKeysError` listing duplicated keys (with line numbers) — read-only, never writes
- [x] Unit test: clean CSV parsed; duplicate CSV (fixture = the 3 real keys from the 06_12 CSV) → explicit error with line numbers
- [x] Advisory detection wired into pipeline step 3: every `Export_*.csv` found in the import folder is checked (⚠️ with duplicate detail, or ✅ clean) — the CSV merge is not back in the pipeline, this hook only signals

**Validation:** ✅ `test_pipeline.py` suite: **174/174 passed** (4 new guard
tests + step3 integration); ruff OK; the guard never writes to sources.

### FIX-1865-06 — RAG reindex + governance

**Status:** ✅ Done (2026-09-23)

#### Sub-tasks

- [x] Reindex the hub after the docs are created: `/Users/michaelboitin/Documents/02_Dev/01_LocalRag_engine/AI/chroma/index-project.sh <project root>` — ✅ run (knowledge 37 → 39 chunks, modified `gouvernance-connaissances.md` reindexed to 11 chunks)
- [x] Register as **state B** (registry `docs/gouvernance-connaissances.md`, COP root): entry **R4** — *key-indexed business reference: detect duplicates before any merge (last-occurrence-wins)* — verified retrievable (chunk `gouvernance-connaissances.md::6`); promotion B → C left to human evaluation

**Observation (out of scope for this activity):** the `.rag.yaml` scans the
root `docs/` only — sub-project docs (`COP_translations/doc/`) are outside
the hub scope. Extending the scope is a separate governance decision.

## 5. Tracking journal

| Date | Action | Event | Author |
|------|--------|-------|--------|
| 2026-09-23 | — | Plan created (prior analysis: [report](2026_09_23_LO_LI_AC_1865_FR_Misalignment_Analysis.md)) | Agent (proposal) |
| 2026-09-23 | — | EN analysis report shared with devs | Michael |
| 2026-09-23 | — | EN action plan created for devs handover | Agent (proposal) |
| 2026-09-23 | **FIX-1865-01** | ❌ Dropped: reference CSV is an archived artifact, no longer consumed by the pipeline — Michael's decision. Value fix moved to FIX-1865-02, recurrence to FIX-1865-03 | Michael |
| 2026-09-23 | **FIX-1865-02** | ✅ FR patch applied to `2026_09_03_Final_Export/translation_en_fr.json` (export arbitrated via Changes_Report §6) + structural validation OK + downstream scan OK | Agent |
| 2026-09-23 | **FIX-1865-03** | ✅ `detect_duplicated_translations()` wired into step 10 + report section 8 rendering + 6 unit tests (1865/1866 fixture) — 170/170 tests OK — backfill: 9/9 corrupted archives detected, 105 files scanned | Agent |
| 2026-09-23 | **FIX-1865-03** | Commit `bf38039` on branch `fix/FIX-1865-03-detecteur-duplication` (hooks OK: lint + 873 container tests; pre-existing Dockerfile fix: COPY validate_translations.py) — **constraint: no push to remote origin, local work only** | Michael |
| 2026-09-23 | **FIX-1865-03** | ✅ Squash-merge to `main` (`2571ece`) — local branch kept | Agent |
| 2026-09-23 | **FIX-1865-04** | ✅ Factual audit (analysis only): 859 EN empty ×11 / FR "Soumettre" since 06_12 (CSV merge) — 413 RAS; decision: no export/source change | Michael |
| 2026-09-23 | **FIX-1865-05** | ✅ Guard `load_reference_csv()` + `DuplicateReferenceKeysError` + step3 advisory hook — 174/174 tests | Agent |
| 2026-09-23 | **FIX-1865-06** | ✅ R4 registered in the state-B registry (root, outside any Git repo — no root .git) + hub reindex OK (37→39 chunks, R4 retrievable); observation: hub scope = root docs/ only | Agent |
| 2026-09-23 | — | Push to `origin` authorized (local-only constraint lifted) — `main` pushed with all local commits | Michael |

## 6. Update rules

- Every status change gets a journal line (§5): date, ID, event, author.
- Statuses: ⏸ Proposed · 🔄 In progress · ⏸ Awaiting business validation · ✅ Done · ❌ Rejected/Dropped.
- An action is ✅ only if its "Validation" section is satisfied and traced.
- On full completion: archive this doc (it remains the audit history) and
  index the correction summary into the RAG hub via the memory workflow.