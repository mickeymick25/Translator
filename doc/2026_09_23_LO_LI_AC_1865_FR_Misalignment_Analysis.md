# Analysis — abnormal change on `LO_LI_AC_1865`

**Date:** 23/09/2026
**Sub-project:** `COP_translations`
**Scope:** trace of key `LO_LI_AC_1865` across all source versions and all translation exports
**Status:** investigation complete, fix proposed (not applied)

---

## 1. Executive summary

Your instinct was right: there **was** an abnormal change — but **not in the EN source file**. The **FR translation** got corrupted during the **2026_06_12** run and was never fixed since.

- EN master value is **constant** across all 11 source versions: `"Add logistic link"`.
- FR value flipped from **"Ajouter un lien logistique"** (correct) to **"Ajouter un lien d'animation"** (wrong — it is the value of the sibling key `LO_LI_AC_1866`) at the `2026_06_12_Export`, and **persists in the latest export** (`2026_09_03_Final_Export`).
- Root cause: a **duplicate key in the business reference CSV** `Export_COP_Excel.csv` (two rows with key `LO_LI_AC_1865`; the second one should have been `LO_LI_AC_1866`). The FR↔CSV merge is key-indexed with **last-occurrence-wins** semantics, so the correct "logistic" FR was silently overwritten by the "animation" FR.

## 2. Findings per version

### EN source (`translator/source/*/`)

| Version | File | `LO_LI_AC_1865` (EN) |
|---|---|---|
| 2026_04_13 → 2026_09_03 (11 versions) | `translation_en_en.json` … `master_EN.json` | `"Add logistic link"` (constant) |

No abnormal change on the EN side. (Note: the newest master `2026_09_03_Import/master_EN.json` also adds `LO_LI_AC_2178` = "Close the link" — unrelated.)

### Translations (`translator/output/*/translation_en_*.json`)

| Export | FR `LO_LI_AC_1865` | FR `LO_LI_AC_1866` | Status |
|---|---|---|---|
| 05_05, 05_13, 05_14, 06_11 | "Ajouter un lien **logistique**" | "Ajouter un lien d'animation" | ✅ correct |
| **06_12** and every later export (06_23, 06_25, 06_26, 07_08, 09_03, 09_03_Final, all 09_03 run folders) | "Ajouter un lien **d'animation**" | "Ajouter un lien d'animation" | ❌ 1865 duplicates 1866 |

Other languages are **not** affected: cz, it, es, hu, pt, pl, ar keep a "logistic" wording for 1865 in every version. Only cosmetic rewordings occurred at 06_12 for de (`Logistiklink hinzufügen` → `Logistikverbindung hinzufügen`), sk (`prepojenie` → `odkaz`) and ar — all still "logistic".

## 3. Root cause (traced)

`translator/source/2026_06_12_Import/Export_COP_Excel.csv` contains a **duplicated key** — lines 1981-1982:

```csv
LO_LI_AC_1865;Activate logistic link;Add logistic link;Ajouter un lien logistique;;;
LO_LI_AC_1865;Activate Amination link;Add an animation link;Ajouter un lien d'animation;;;   ← should be LO_LI_AC_1866
```

- The second occurrence (the *animation* row) should carry `LO_LI_AC_1866`.
- The FR↔CSV merge described in `doc/2026_06_12_Translation_FR_Changelog.md` (§3: 1103 values replaced from the CSV) works via a **dictionary keyed by the CSV key**; the **last occurrence overwrites the first**. The correct "logistique" FR was silently replaced by the "animation" FR.
- The committed backup `translation_en_fr.json.bak` (commit `f40f4ae`, 17/06/2026) already contains the corrupted value → corruption happened during the 06_12 build, before that commit.

Corroborating evidence:

- `Export_COP_MessageExcel.csv` does **not** contain this key → the MessageExcel patch (`patch_fr_from_csv.py`) is not the source of the corruption.
- The duplicate was **never detected**: no mention of the key in `doc/` (including `2026_06_26_FR_Misalignment_History.md`, which covers 122 keys but not this one), nor in `2026_09_03_Changes_Report_for_Devs.md`.
- Minor data-quality notes on the same CSV row: label typo **"Activate Amination link"**; the official app mapping (`translator/output/2026_06_12_Export/Analytics/COP_pages_mapping_official.tsv`, lines 1881-1885) labels 1865 "activate logistic link" / 1866 "activate Animation link" while the translator master uses "Add logistic link" / "Add an animation link" — a consistent wording difference between the app mapping and the translator master, not part of this anomaly.

## 4. Wider impact (same mechanism)

`Export_COP_Excel.csv` (2140 rows, 2136 unique keys) contains **3 duplicated keys**:

| Key | Occurrences | Outcome |
|---|---|---|
| `LO_LI_AC_1865` | ×2 (logistic / animation) | ❌ FR corrupted (see above) |
| `LO_LO_AD_413` | ×2 (Fax number / Mobile number) | FR final "Numéro de téléphone portable" — happened to match EN "Mobile number"; correct by luck |
| `PA_CO_VI_859` | ×3 (Start date / End date / Save) | FR final "Soumettre" while EN is **empty** in the current master — needs audit |

Final state verified in `translator/output/2026_09_03_Final_Export/translation_en_fr.json`:

```text
LO_LI_AC_1865  | EN: 'Add logistic link'     | FR: "Ajouter un lien d'animation"   ← wrong
LO_LI_AC_1866  | EN: 'Add an animation link' | FR: "Ajouter un lien d'animation"   ← 1865 and 1866 identical
LO_LO_AD_413   | EN: 'Mobile number'         | FR: 'Numéro de téléphone portable'  ← OK (coincidence)
PA_CO_VI_859   | EN: ''                      | FR: 'Soumettre'                     ← to audit
```

## 5. Proposed fixes (not applied yet)

1. **Correct the FR value** in the final export: `LO_LI_AC_1865` → "Ajouter un lien logistique" (and re-ship to COP).
2. **Fix the CSV reference**: line 1982 → `LO_LI_AC_1866`, plus the "Amination" typo.
3. **Audit** `PA_CO_VI_859` (and `LO_LO_AD_413` for the record).
4. **Add a duplicate-key guard** in the CSV loader used by the merge step: raise (or at minimum warn loudly) when the reference CSV contains the same key twice, instead of silently applying last-occurrence-wins.
5. Optional regression check: re-run the FR misalignment analysis with an explicit *duplication* detector (FR value of key X identical to FR value of key Y where EN values differ — this case would have been caught: FR[1865] = FR[1866] while EN[1865] ≠ EN[1866]).

## 6. Provenance

- RAG hub `cop-commercialpartner__knowledge` queried first per routing contract: **no** content specific to this key (governance-level info only).
- All findings above come from actual reads: `translator/source/*/` JSON exports, `translator/output/*/translation_en_*.json`, `Export_COP_Excel.csv` / `Export_COP_MessageExcel.csv`, `COP_pages_mapping_official.tsv`, `doc/2026_06_12_Translation_FR_Changelog.md`, and the Git history of the `COP_translations` repository (commits `f40f4ae`, `8fefea9`, `b61f0aa`).