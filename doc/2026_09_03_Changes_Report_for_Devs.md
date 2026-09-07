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

All corrections below are **FR-only**. No other language was affected.

### 2.1 Systematic offset error in `PA_US_TA_633–710` (69 keys re-translated)

A systematic offset was discovered in the French translations for keys `PA_US_TA_633` through `PA_US_TA_710`. Each translation was shifted by one position — `FR[key N]` contained the translation for `EN[key N-1]`. This caused completely wrong labels for 69 table action keys.

**Full list of corrected keys:**

| Key | EN source | FR (before — wrong) | FR (after — corrected) |
|---|---|---|---|
| `PA_US_TA_630` | Grouping | Transverse | Regroupement |
| `PA_US_TA_633` | Add Organization Identifier value | Submit | Ajouter une valeur d'identifiant d'organisation |
| `PA_US_TA_634` | Edit Organization Identifier value | Ajouter un identifiant | Modifier la valeur de l'identifiant de l'organisation |
| `PA_US_TA_635` | Edit Organization | Modifier l'identifiant... | Modifier l'organisation |
| `PA_US_TA_638` | View Company Details | Voir la liste des organisations | Afficher les détails de la société |
| `PA_US_TA_639` | Remove Company | Voir une société en détail | Supprimer la société |
| `PA_US_TA_640` | View Organization details | Supprimer la société... | Afficher les détails de l'organisation |
| `PA_US_TA_641` | Add Company in Organization | Voir l'organisation en détail... | Ajouter une société dans l'organisation |
| `PA_US_TA_642` | View Company list | Ajouter une société... | Voir la liste des sociétés |
| `PA_US_TA_644` | Edit Company Address | Voir une société en détails | Modifier l'adresse de la société |
| `PA_US_TA_645` | Add a new Company Role | Modifier l'adresse d'une société | Ajouter un nouveau rôle dans la société |
| `PA_US_TA_646` | Edit a Company Role | Ajouter un rôle à société | Modifier un rôle dans la société |
| `PA_US_TA_647` | Add a new Company Identifier value | Modifier le rôle d'une société | Ajouter une nouvelle valeur d'identifiant de société |
| `PA_US_TA_648` | Edit Company Identifier value | Ajouter un identifiant de société | Modifier la valeur de l'identifiant de la société |
| `PA_US_TA_649` | Edit Company | Modifier les identifiants... | Modifier la société |
| `PA_US_TA_650` | Add Company | Modifier une société | Ajouter une société |
| `PA_US_TA_652` | View Location | Ajouter un site | Voir le site |
| `PA_US_TA_653` | Edit Location | Voir le site | Modifier le site |
| `PA_US_TA_655` | Add Partner | Modifier un point d'accès | Ajouter un partenaire |
| `PA_US_TA_656` | Edit Partner Link | Ajouter un lien | Modifier le lien du partenaire |
| `PA_US_TA_659` | View Organization | Ajouter une organisation | Voir l'organisation |
| `PA_US_TA_660` | Remove Organization | Voir une organisation | Supprimer l'organisation |
| `PA_US_TA_661` | Add Company Address | Supprimer une organisation | Ajouter l'adresse de la société |
| `PA_US_TA_662` | Context | Ajouter une adresse à une société | Contexte |
| `PA_US_TA_664` | Preferred language | Voir les profils | Langue préférée |
| `PA_US_TA_665` | Delete a Location Identifier | Gerer les langues | Supprimer un identifiant de site |
| `PA_US_TA_666` | Create Node Type | Supprimer un identifiant de site | Créer un type de nœud |
| `PA_US_TA_667` | Edit Node Type | Créer un type de nœud | Modifier le type de nœud |
| `PA_US_TA_668` | Animation Link attribute list | Modifier un type de nœud | Liste d'attributs de lien d'animation |
| `PA_US_TA_669` | Create an Animation Link attribute | Liste des attributs de lien animation | Créer un attribut de lien d'animation |
| `PA_US_TA_670` | Create an Organization Identifier | Créer un attribut de lien animation | Créer un identifiant d'organisation |
| `PA_US_TA_671` | Edit an Organization Identifier | Créer un identifiant d'organisation | Modifier un identifiant d'organisation |
| `PA_US_TA_672` | Delete an Organization Identifier | Modifier un identifiant d'organisation | Supprimer un identifiant d'organisation |
| `PA_US_TA_674` | Edit a Location Identifier | Liste des points d'accès | Modifier un identifiant de site |
| `PA_US_TA_675` | Organization Identifier list | Modifier un identifiant de site | Liste des identifiants de l'organisation |
| `PA_US_TA_676` | Create new Hierarchy Type | Liste des identifiants d'organisation | Créer un nouveau type de hiérarchie |
| `PA_US_TA_677` | Edit Hierarchy Type | Créer un nouveau type de hiérarchie | Modifier le type de hiérarchie |
| `PA_US_TA_678` | Remove Hierarchy Type | Modifier un type de hiérarchie | Supprimer le type de hiérarchie |
| `PA_US_TA_679` | Edit a Logistic Link attribute | Supprimer un type de hiérarchie | Modifier un attribut de lien logistique |
| `PA_US_TA_680` | Edit Company Role Type | Modifier un attribut de lien logistique | Modifier le type de rôle dans la société |
| `PA_US_TA_681` | Logistic Link attribute list | Modifier un type de rôle société | Liste d'attributs de lien logistique |
| `PA_US_TA_682` | Create a Logistic Link attribute | Liste des attributs de lien logistique | Créer un attribut de lien logistique |
| `PA_US_TA_685` | Company Role Type list | Désactiver un type de nœud | Liste des types de rôle dans la société |
| `PA_US_TA_686` | New Company Role Type | Liste des types de rôle des sociétés | Nouveau type de rôle dans la société |
| `PA_US_TA_687` | Delete an Animation Link attribute | Nouveau type de rôle de société | Supprimer un attribut de lien d'animation |
| `PA_US_TA_688` | Company Identifier list | Supprimer un attribut de lien animation | Liste des identifiants de la société |
| `PA_US_TA_689` | Create a Company Identifier | Liste des identifiants société | Créer un identifiant de société |
| `PA_US_TA_690` | Edit a Company Identifier | Créer un identifiant société | Modifier un identifiant de société |
| `PA_US_TA_691` | Delete a Company Identifier | Modifier un identifiant société | Supprimer un identifiant de société |
| `PA_US_TA_692` | View Company Role Type | Supprimer un identifiant société | Afficher le type de rôle dans la société |
| `PA_US_TA_695` | Location Identifier list | Créer un point d'accès | Liste des identifiants de site |
| `PA_US_TA_696` | Create a Location Identifier | Liste des identifiants des sites | Créer un identifiant de site |
| `PA_US_TA_697` | Hierarchy Type list | Créer un identifiant de site | Liste des types de hiérarchie |
| `PA_US_TA_698` | Edit an Animation Link attribute | Liste des types de hiérarchie | Modifier un attribut de lien d'animation |
| `PA_US_TA_699` | Delete Company Role Type | Modifier un attribut de lien animation | Supprimer le type de rôle dans la société |
| `PA_US_TA_700` | View Hierarchy Type | Supprimer un type de rôle de société | Afficher le type de hiérarchie |
| `PA_US_TA_701` | Node Type list | Voir un type de hiérarchie | Liste des types de nœuds |
| `PA_US_TA_702` | View Location list | Liste des types de nœud | Voir la liste des sites |
| `PA_US_TA_703` | View Location details | Voir la liste des sites | Afficher les détails du site |
| `PA_US_TA_704` | View Business Transfer list | Voir les détails du site | Voir la liste des transferts d'entreprise |
| `PA_US_TA_705` | Create new Business Transfer | Voir la liste des transferts d'activité | Créer un nouveau transfert d'entreprise |
| `PA_US_TA_706` | Download CSV File | Créer un nouveau transfert d'activité | Télécharger le fichier CSV |
| `PA_US_TA_707` | View Business Transfert Report | Télécharger le fichier CSV | Voir le rapport sur la transmission d'entreprise |
| `PA_US_TA_709` | Download Business Transfert Report | Télécharger | Télécharger le rapport sur la transmission d'entreprise |
| `PA_US_TA_712` | Edit Location Identifier value | Ajouter une valeur d'identifiant de site | Modifier une valeur d'identifiant de site |
| `PA_US_TA_714` | Create new Logistic US Transfer | Modifier les horaires d'ouverture | Créer un nouveau transfert logistique US |
| `PA_US_TA_722` | Add Partner | Modifier un point d'accès | Ajouter un partenaire |

### 2.2 Offset error in `PA_CO_HE_798–803` (6 keys corrected)

| Key | EN source | FR (before — wrong) | FR (after — corrected) |
|---|---|---|---|
| `PA_CO_HE_799` | New company role | Type de rôle de société | **Nouveau rôle de société** |
| `PA_CO_HE_800` | Role type ID | Nouveau rôle de société | **ID du type de rôle** |
| `PA_CO_TA_801` | Role name | ID du type de rôle | **Nom du rôle** |
| `PA_CO_TA_802` | Role description | Nom du rôle | **Description du rôle** |
| `PA_CO_TA_803` | Company count | Description du rôle | **Nombre de sociétés** |
| `PA_CO_VI_841` | ID COP | Nombre d'utilisation du role par les sociétés | **ID COP** |

### 2.3 Label suffix corrections (11 keys)

Removed "(Number)", "(nombre)", "(0)" suffixes that caused duplicate counters in the UI (e.g., "Sites (nombre) (1)"):

| Key | EN source | FR (before) | FR (after) |
|---|---|---|---|
| `OR_VI_PA_24` | Organizations | Organisations (Number) | **Organisations** |
| `CO_CO_TA_137` | Links | Liens (Nombre) | **Liens** |
| `CO_CO_TA_140` | Locations | Sites (nombre) | **Sites** |
| `CO_CO_TA_163` | Partners type | Liens (nombre) | **Liens** |
| `LO_LO_CO_377` | Partners location | Sites partenaires (Nombre) | **Sites partenaires** |
| `LO_LO_AC_379` | Access Points | Points d'accès (nombre) | **Points d'accès** |
| `PA_US_TA_609` | All Users | Tous les utilisateurs (nombre) | **Tous les utilisateurs** |
| `PA_US_CO_617` | Context list | Liste des contextes (nombre) | **Liste des contextes** |
| `CO_CO_TA_270` | Access Point | Point d'accès (0) | **Point d'accès** |
| `LO_LO_TA_1047` | Sector | Secteur (0) | **Secteur** |
| `PA_US_DE_1176` | Result | Résultat (0) | **Résultat** |

### 2.4 Wrong entity/action corrections (9 keys)

| Key | EN source | FR (before) | FR (after) | Issue |
|---|---|---|---|---|
| `PA_US_TA_654` | Edit Access Point | Modifier le site | **Modifier le point d'accès** | Wrong entity |
| `PA_US_TA_673` | Access Point list | Supprimer un identifiant d'organisation | **Liste des points d'accès** | Completely wrong |
| `PA_US_TA_693` | Edit an Access Point | Voir un type de rôle société | **Modifier un point d'accès** | Completely wrong |
| `PA_US_TA_721` | Edit Access Point | Ajouter un point d'accès | **Modifier le point d'accès** | Wrong action |
| `CO_CR_TI_82` | Create Company | Ajouter une société | **Créer une société** | Wrong action |
| `CO_CO_TA_164` | Add a Partner | Ajouter un lien | **Ajouter un partenaire** | Wrong entity |
| `LO_LO_PA_436` | Company Nature | Nature du site partenaire | **Nature de la société** | Wrong entity |
| `PA_NE_TA_728` | Node type | Type de hiérarchie | **Type de nœud** | Wrong entity |
| `BU_ST_ME_2173` | Rejected : Target Location | Liens R1 non transférés | **Rejeté : site cible** | Completely wrong |

### 2.5 "Until date" / "End date" corrections (11 keys)

"Until date" and "End date" were incorrectly translated as "Date d'effet" (effective date) or "Date de début" (start date):

| Key | EN source | FR (before) | FR (after) |
|---|---|---|---|
| `PA_CO_CR_821` | End date | Date de début | **Date de fin** |
| `PA_CO_ED_833` | End date | Date de début | **Date de fin** |
| `PA_CO_TA_806` | Until date | Date d'effet | **Date de fin** |
| `PA_CO_VI_839` | Until date | Date d'effet | **Date de fin** |
| `PA_CO_VI_846` | Until date | Date d'effet | **Date de fin** |
| `PA_NE_CR_765` | Until date | Date d'effet | **Date de fin** |
| `PA_NE_CR_777` | End date | Date de début | **Date de fin** |
| `PA_NE_CR_788` | Until date | Date d'effet | **Date de fin** |
| `PA_NE_ED_795` | Until date | Date d'effet | **Date de fin** |
| `PA_NE_HI_739` | Until date | Date d'effet | **Date de fin** |
| `PA_NE_NO_751` | Until date | Date d'effet | **Date de fin** |

### 2.6 Other label corrections (7 keys)

| Key | EN source | FR (before) | FR (after) | Issue |
|---|---|---|---|---|
| `PA_ID_NE_873` | Company | Type d'identifiant | **Société** | Wrong label |
| `PA_NE_CR_763` | Hierarchy description | Type de hiérarchie | **Description de la hiérarchie** | Wrong label |
| `PA_NE_HI_731` | Create new hierarchy | Type de hiérarchie | **Créer une nouvelle hiérarchie** | Wrong label |
| `PA_NE_NO_745` | Create node type | Type de nœud | **Créer un type de nœud** | Wrong action |
| `PA_US_TA_622` | Dealer Admin | Administrateur corporate | **Administrateur Dealer** | Wrong label |
| `PA_US_TA_625` | Reader | Administrateur NSC | **Lecteur** | Wrong label |
| `PA_NE_CR_775` | Add a node | 0/6 nœuds maximum | **Ajouter un nœud** | Wrong label |

### 2.7 Terminology harmonization (72 keys)

Applied across all FR translations to ensure consistency with the project glossary:

| English term | FR term used (incorrect) | FR term corrected to | Keys affected |
|---|---|---|---:|
| Company | entreprise | **société** | 40 |
| Location | emplacement | **site** | 21 |
| Location | localisation | **site** | 11 |

### 2.8 Grammar correction (1 key)

| Key | EN source | FR (before) | FR (after) |
|---|---|---|---|
| `LO_ED_LA_1495` | Does this location have a wholesale activity? | Ce site exerce-t-elle | **Ce site exerce-t-il** |

---

## 3. Polish (PL) Placeholder Corrections (3 keys)

3 Polish translations had their placeholders translated by Google Translate instead of being preserved:

| Key | EN source | PL (before — broken) | PL (after — fixed) |
|---|---|---|---|
| `MS_SUCCESS_ERROR_132` | ...{{message}}... | ...{{wiadomość}}... | **...{{message}}...** |
| `MS_SUCCESS_ERROR_131` | ...{{action}}... | ...{{akcję}}... | **...{{action}}...** |
| `MS A03_US00_02` | ...{{legal identifier}}... | ...{{identyfikator prawny}}... | **...{{legal identifier}}...** |

> **Impact**: These placeholder mismatches would have caused runtime errors in the frontend (variables not found). All 3 have been restored to match the EN source.

---

## 4. New Language: Polish (PL)

Polish has been added as the 10th target language:

| Type | File | Keys |
|---|---|---:|
| i18n JSON | `translation_en_pl.json` | 2689 |
| Dropdown XLSX | `dropdown_translations.xlsx` (PL sheet) | 613 |

---

## 5. Validation Results

| Check | Result |
|---|---|
| Missing keys | ✅ 0 (all 2689 source keys present in all 10 languages) |
| Extra keys | ✅ 0 (6 removed keys cleaned from all files) |
| Placeholder mismatches | ✅ 0 (all preserved, 3 PL corrections applied) |
| Duplicate keys | ✅ 0 |
| Empty translations | 563 (keys with empty EN source — expected) |
| Untranslated values | 554 (proper nouns, abbreviations identical to EN — expected) |

---

## 6. Files to Deploy

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

## 7. Summary of All Corrected Variables

### FR corrections (189 keys total)

| Category | Keys | Impact |
|---|---:|---|
| Systematic offset PA_US_TA_633-710 | 69 | Table action labels were showing wrong actions |
| Offset PA_CO_HE_799-803 + PA_CO_VI_841 | 6 | Role type labels were shifted |
| Label suffix removal | 11 | Duplicate counters in UI ("Sites (nombre) (1)") |
| Wrong entity/action | 9 | Wrong labels in tables and forms |
| "Until date" / "End date" | 11 | Date fields showing "Effective date" instead of "End date" |
| Other label corrections | 7 | Miscellaneous wrong labels |
| Terminology: entreprise → société | 40 | Glossary consistency |
| Terminology: emplacement → site | 21 | Glossary consistency |
| Terminology: localisation → site | 11 | Glossary consistency |
| Grammar correction | 1 | Agreement fix |
| Clé supprimée (6 keys × 10 languages) | 60 | Cleanup removed source keys |

### PL corrections (3 keys)

| Category | Keys | Impact |
|---|---:|---|
| Placeholder restoration | 3 | Runtime errors (variables not found) |

---

## 8. Action Items for Developers

1. **Remove references to deleted keys**: `___1075`, `___1076`, `BU_ST_ME_2168`, `BU_ST_ME_2169`, `LO_PR_CH_2174`, `PA_AU_MO_2174`
2. **Use replacement keys**: `LO_PR_CH_2174` → `LO_PR_CH_2177`, `PA_AU_MO_2174` → `PA_AU_MO_2176`
3. **Verify BU_ST_ME label changes**: Keys 2170–2173 have been reassigned to different labels
4. **Polish language**: PL is now available — ensure the frontend can load `translation_en_pl.json`
5. **FR table actions**: 69 table action labels (`PA_US_TA_633–710`) were corrected — users will see different labels in tables
6. **FR date fields**: 11 "Until date" / "End date" labels were corrected from "Effective date" to "End date"
7. **FR role type labels**: 6 labels in the Role Type management screen were corrected (`PA_CO_HE_799–803`)
8. **FR suffix removal**: Labels previously showing "(Number)", "(0)" suffixes have been cleaned — these suffixes were causing duplicate counters in the UI
9. **FR terminology**: "entreprise" → "société", "emplacement"/"localisation" → "site" applied globally
10. **PL placeholders**: 3 keys had translated placeholders ({{message}}, {{action}}, {{legal identifier}}) that would have caused runtime errors — now fixed