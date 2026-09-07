# Translation Changes Report — EN11 (2026_09_03) for Developers

**Date**: 2026-09-03
**Source**: `master_EN.json` (2689 keys, up from 2545 in EN10)
**Export**: `2026_09_03_Final_Export/` (10 languages × 2689 keys)
**Languages**: FR, DE, CZ, SK, IT, AR, PT, ES, HU, PL

---

## 1. Source Changes (EN10 → EN11)

### 150 new keys added

| Prefix | Count | Examples |
|---|---:|---|
| PA | 114 | `PA_GE_*` (Territories), `PA_MO_*` (Batch/Analysis), `PA_AU_MO_2176` |
| MS | 27 | `MS_SUCCESS_ERROR_274` to `MS_SUCCESS_ERROR_300` |
| LO | 6 | `LO_LI_*` (Link management), `LO_PR_CH_2177` |
| BU | 2 | `BU_ST_ME_2174`, `BU_ST_ME_2175` |
| NE | 1 | `NE_LO_PA_2229` |

### 6 keys removed

| Key | Previous EN value |
|---|---|
| `___1075` | (empty) |
| `___1076` | (empty) |
| `BU_ST_ME_2168` | Done |
| `BU_ST_ME_2169` | Pairing Error |
| `LO_PR_CH_2174` | Change Partner |
| `PA_AU_MO_2174` | Warning |

> These keys have been removed from all translation files. If any frontend code still references them, it should be updated to use the replacement keys.

### 4 keys modified (source value changed)

| Key | EN10 value | EN11 value |
|---|---|---|
| `BU_ST_ME_2170` | Rejected Source | Done |
| `BU_ST_ME_2171` | Rejected : Target Location | Pairing Error |
| `BU_ST_ME_2172` | Rejected Parent: DMS or Nature Code Conflict | Rejected Source |
| `BU_ST_ME_2173` | R1 links not transferred | Rejected : Target Location |

### 4 source typos corrected

The following typos were detected and corrected in `master_EN.json` before translation:

| Key | Typo | Correction |
|---|---|---|
| `LO_LI_HE_2006` | Hiearchy | **Hierarchy** |
| `PA_ID_HE_880` | TItle | **Title** |
| `CO_CO_PA_162` | Parners | **Partners** |
| `PA_US_TA_684` | Desactive Node Type | **Deactivate** Node Type |
| `PA_US_US_1277` | Desactive Node Type | **Deactivate** Node Type |

---

## 2. French (FR) Translation Corrections

### 2.1 Systematic offset error in `PA_US_TA_633–710` (69 keys re-translated)

A systematic offset was discovered in the French translations for keys `PA_US_TA_633` through `PA_US_TA_710`. Each translation was shifted by one position — `FR[key N]` contained the translation for `EN[key N-1]`. This caused completely wrong labels for 69 table action keys.

**Examples:**

| Key | EN source | FR (before — wrong) | FR (after — corrected) |
|---|---|---|---|
| `PA_US_TA_633` | Add Organization Identifier value | Submit (← from 632) | Ajouter une valeur d'identifiant d'organisation |
| `PA_US_TA_635` | Edit Organization | Modifier l'identifiant... (← from 634) | Modifier l'organisation |
| `PA_US_TA_638` | View Company Details | Voir la liste des organisations (← from 637) | Afficher les détails de la société |
| `PA_US_TA_639` | Remove Company | Voir une société en détail (← from 638) | Supprimer la société |
| `PA_US_TA_655` | Add Partner | Modifier un point d'accès (← from 654) | Ajouter un partenaire |
| `PA_US_TA_660` | Remove Organization | Voir une organisation (← from 659) | Supprimer l'organisation |
| `PA_US_TA_666` | Create Node Type | Supprimer un identifiant de site (← from 665) | Créer un type de nœud |
| `PA_US_TA_670` | Create an Organization Identifier | Créer un attribut de lien animation (← from 669) | Créer un identifiant d'organisation |

> **Impact**: If the frontend renders table action labels from these keys, users were seeing wrong actions (e.g., "View" instead of "Delete", "Add" instead of "Edit"). All 69 keys have been re-translated to match their correct EN source.

### 2.2 Other FR translation corrections

| Key | EN source | FR (before) | FR (after) | Issue |
|---|---|---|---|---|
| `OR_VI_PA_24` | Organizations | Organisations (Number) | **Organisations** | Removed "(Number)" suffix |
| `CO_CO_TA_137` | Links | Liens (Nombre) | **Liens** | Removed "(Nombre)" suffix |
| `CO_CO_TA_140` | Locations | Sites (nombre) | **Sites** | Removed "(nombre)" suffix |
| `CO_CO_TA_163` | Partners type | Liens (nombre) | **Liens** | Wrong label + removed suffix |
| `LO_LO_CO_377` | Partners location | Sites partenaires (Nombre) | **Sites partenaires** | Removed "(Nombre)" suffix |
| `LO_LO_AC_379` | Access Points | Points d'accès (nombre) | **Points d'accès** | Removed "(nombre)" suffix |
| `PA_US_TA_609` | All Users | Tous les utilisateurs (nombre) | **Tous les utilisateurs** | Removed "(nombre)" suffix |
| `PA_US_CO_617` | Context list | Liste des contextes (nombre) | **Liste des contextes** | Removed "(nombre)" suffix |
| `CO_CO_TA_270` | Access Point | Point d'accès (0) | **Point d'accès** | Removed "(0)" suffix |
| `LO_LO_TA_1047` | Sector | Secteur (0) | **Secteur** | Removed "(0)" suffix |
| `PA_US_DE_1176` | Result | Résultat (0) | **Résultat** | Removed "(0)" suffix |
| `PA_US_TA_654` | Edit Access Point | Modifier le site | **Modifier le point d'accès** | Wrong entity ("site" instead of "access point") |
| `PA_US_TA_673` | Access Point list | Supprimer un identifiant d'organisation | **Liste des points d'accès** | Completely wrong translation |
| `PA_US_TA_693` | Edit an Access Point | Voir un type de rôle société | **Modifier un point d'accès** | Completely wrong translation |
| `PA_US_TA_721` | Edit Access Point | Ajouter un point d'accès | **Modifier le point d'accès** | Wrong action ("Add" instead of "Edit") |
| `PA_US_TA_712` | Edit Location Identifier value | Ajouter une valeur d'identifiant de site | **Modifier une valeur d'identifiant de site** | Wrong action ("Add" instead of "Edit") |
| `PA_US_TA_714` | Create new Logistic US Transfer | Modifier les horaires d'ouverture | **Créer un nouveau transfert logistique US** | Completely wrong translation |
| `PA_US_TA_722` | Add Partner | Modifier un point d'accès | **Ajouter un partenaire** | Wrong action + entity |
| `CO_CR_TI_82` | Create Company | Ajouter une société | **Créer une société** | Wrong action ("Add" instead of "Create") |
| `CO_CO_TA_164` | Add a Partner | Ajouter un lien | **Ajouter un partenaire** | Wrong entity ("link" instead of "partner") |
| `LO_LO_PA_436` | Company Nature | Nature du site partenaire | **Nature de la société** | Wrong entity ("site" instead of "company") |
| `PA_NE_TA_728` | Node type | Type de hiérarchie | **Type de nœud** | Wrong entity ("hierarchy" instead of "node") |
| `BU_ST_ME_2173` | Rejected : Target Location | Liens R1 non transférés | **Rejeté : site cible** | Completely wrong translation |

### 2.3 Terminology harmonization (FR)

The following term replacements were applied across all FR translations to ensure consistency with the project glossary:

| English term | FR term used (incorrect) | FR term corrected to | Keys affected |
|---|---|---|---:|
| Company | entreprise | **société** | 40 |
| Location | emplacement | **site** | 21 |
| Location | localisation | **site** | 11 |

### 2.4 Placeholder corrections (PL)

3 Polish translations had their placeholders translated by Google Translate instead of being preserved:

| Key | EN source | PL (before — broken) | PL (after — fixed) |
|---|---|---|---|
| `MS_SUCCESS_ERROR_132` | ...{{message}}... | ...{{wiadomość}}... | ...{{message}}... |
| `MS_SUCCESS_ERROR_131` | ...{{action}}... | ...{{akcję}}... | ...{{action}}... |
| `MS A03_US00_02` | ...{{legal identifier}}... | ...{{identyfikator prawny}}... | ...{{legal identifier}}... |

> **Impact**: These placeholder mismatches would have caused runtime errors in the frontend (variables not found). All 3 have been restored to match the EN source.

---

## 3. New Language: Polish (PL)

Polish has been added as the 10th target language. Both translation types are available:

| Type | File | Keys/Entries |
|---|---|---|
| i18n JSON | `translation_en_pl.json` | 2689 keys |
| Dropdown XLSX | `dropdown_translations.xlsx` (PL sheet) | 613 entries |

---

## 4. Validation Results

| Check | Result |
|---|---|
| Missing keys | ✅ 0 (all 2689 source keys present in all 10 languages) |
| Extra keys | ✅ 0 (6 removed keys cleaned from all files) |
| Placeholder mismatches | ✅ 0 (all preserved, 3 PL corrections applied) |
| Duplicate keys | ✅ 0 |
| Empty translations | 563 (keys with empty EN source — expected, nothing to translate) |
| Untranslated values | 554 (proper nouns, abbreviations identical to EN — expected) |

---

## 5. Files to Deploy

```
2026_09_03_Final_Export/
├── translation_en_ar.json    (2689 keys)
├── translation_en_cz.json    (2689 keys)
├── translation_en_de.json    (2689 keys)
├── translation_en_es.json    (2689 keys)
├── translation_en_fr.json    (2689 keys)
├── translation_en_hu.json    (2689 keys)
├── translation_en_it.json    (2689 keys)
├── translation_en_pl.json    (2689 keys)
├── translation_en_pt.json    (2689 keys)
└── translation_en_sk.json    (2689 keys)
```

---

## 6. Action Items for Developers

1. **Remove references to deleted keys**: `___1075`, `___1076`, `BU_ST_ME_2168`, `BU_ST_ME_2169`, `LO_PR_CH_2174`, `PA_AU_MO_2174`
2. **Use replacement keys**: `LO_PR_CH_2174` → `LO_PR_CH_2177`, `PA_AU_MO_2174` → `PA_AU_MO_2176`
3. **Verify BU_ST_ME label changes**: Keys 2170–2173 have been reassigned to different labels
4. **Polish language**: PL is now available — ensure the frontend can load `translation_en_pl.json`
5. **FR label fixes**: 69 table action labels (`PA_US_TA_633–710`) were corrected — users may notice different labels in tables
6. **FR suffix removal**: Labels previously showing "(Number)", "(0)" suffixes have been cleaned — these suffixes were causing duplicate counters in the UI (e.g., "Sites (nombre) (1)")