# Étude de comparaison — Traductions EN9 vs EN10 (export 2026_06_26 vs 2026_07_08)

- **Date** : 2026-07-13
- **Demandeur** : Michael Boitin
- **Contexte** : la page "société détails" est cassée après publication des fichiers en10. Étude de comparaison pour identifier les différences.

## 1. Périmètre

| Élément | EN9 | EN10 |
|---|---|---|
| Source | `source/2026_06_25_Import/en 9.json` | `source/2026_07_08_Import/en 10.json` |
| Export | `output/2026_06_26_Export/` | `output/2026_07_08_Export/` |
| Clés source | 2542 | 2545 |
| Clés traduites (FR) | 2542 | 2545 |
| Langues | 9 (fr, cz, sk, de, it, ar, pt, es, hu) | 9 (idem) |

## 2. Synthèse des différences

| Type | Nombre | Détail |
|---|---:|---|
| Clés ajoutées | 3 | `LO_PR_CH_2174`, `MS_SUCCESS_ERROR_273`, `PA_AU_MO_2174` |
| Clés supprimées | 0 | — |
| Clés modifiées (source) | 2 | `LO_AF_CR_1285`, `MS_SUCCESS_ERROR_272` |
| Traductions vides apparues | 0 | Aucune traduction devenue vide |
| Placeholders divergents | 0 | Tous les placeholders sont préservés dans toutes les langues |
| Ordre des clés | ✅ | FR10 suit l'ordre de EN10 |
| Clés sur-remplies (source vide, trad non vide) | 17 | Back-fill manuel FR (inchangé vs en9) |
| Traductions FR identiques à EN10 | 147 | Noms propres, abréviations (normal) |

## 3. Détail des clés ajoutées (3)

| Clé | Source EN10 | FR10 | Toutes langues |
|---|---|---|---|
| `LO_PR_CH_2174` | "Change Partner" | "Changer de partenaire" | ✅ toutes traduites |
| `MS_SUCCESS_ERROR_273` | "The animation link partner has been successfully updated." | "Le partenaire de lien d'animation a été mis à jour avec succès." | ✅ toutes traduites |
| `PA_AU_MO_2174` | "Warning" | "Avertissement" | ✅ toutes traduites |

## 4. Détail des clés modifiées (2)

### LO_AF_CR_1285 — Changement de libellé significatif

| | EN9 | EN10 |
|---|---|---|
| **Source** | "Parent company" | "Current Profile" |
| **FR** | "Société parent" | "Profil actuel" |
| **CZ** | "Mateřská společnost" | "Aktuální profil" |
| **SK** | "Materská spoločnosť" | "Aktuálny profil" |
| **DE** | "Muttergesellschaft" | "Aktuelles Profil" |
| **IT** | "Azienda madre" | "Profilo attuale" |
| **AR** | "الشركة الأم" | "الملف الشخصي الحالي" |
| **PT** | "Empresa matriz" | "Perfil Atual" |
| **ES** | "Empresa matriz" | "Perfil actual" |
| **HU** | "Anyavállalat" | "Aktuális profil" |

⚠️ **Cette clé change de "Société parent" à "Profil actuel" dans toutes les langues.** Si elle est utilisée comme titre d'onglet, fil d'Ariane ou identifiant de section dans la page "société détails", ce changement de wording peut faire apparaître la page comme "cassée" (le libellé attendu n'est plus affiché).

**Hypothèse** : c'est probablement le changement qui impacte la page "société détails". Le libellé "Société parent" (ou "Parent company") était peut-être utilisé par le frontend comme identifiant ou condition d'affichage.

### MS_SUCCESS_ERROR_272 — Message avec placeholders HTML ajoutés

| | EN9 | EN10 |
|---|---|---|
| **Source** | "Location links regeneration has been done" | "The Location `<strong>{{locationId}} - {{locationName}}</strong>` links have been updated successfully." |
| **FR** | "La régénération des liens de localisation a été effectuée" | "Les liens de l'emplacement `<strong>{{locationId}} - {{locationName}}</strong>` ont été mis à jour avec succès." |

✅ **Placeholders préservés** : `<strong>`, `</strong>`, `{{locationId}}`, `{{locationName}}` sont identiques entre source et traduction dans toutes les langues.

## 5. Coquilles NON corrigées dans EN10

Le dictionnaire `source_typos.json` contient 6 coquilles connues. Le pipeline JSON n'a pas été lancé en mode correction sur `en 10.json` (seulement le pipeline dropdown a corrigé le XLSX). **5 clés contiennent encore les coquilles d'origine** :

| Clé | Coquille restante | Correction attendue |
|---|---|---|
| `LO_LI_HE_2006` | "Hiearchy" | "Hierarchy" |
| `PA_ID_HE_880` | "TItle" | "Title" |
| `CO_CO_PA_162` | "Parners" | "Partners" |
| `PA_US_TA_684` | "Desactive" | "Deactivate" |
| `PA_US_US_1277` | "Desactive" | "Deactivate" |

⚠️ **Recommandation** : lancer le pipeline JSON en mode correction sur `en 10.json` pour corriger ces 5 coquilles restantes, puis re-traduire les clés affectées.

## 6. Clés sur-remplies (17)

17 clés ont une source EN10 vide mais une traduction FR non vide (back-fill manuel). Ces clés sont inchangées entre en9 et en10 — elles ne sont pas la cause du problème.

Exemples : `PA_NE_TA_729` ("Type de nœud"), `PA_NE_HI_743` ("Supprimer"), `PA_NE_NO_756` ("Désactiver").

## 7. Conclusions

### Le changement qui impacte probablement la page "société détails"

**`LO_AF_CR_1285`** : changement de "Parent company" → "Current Profile" (FR : "Société parent" → "Profil actuel"). Ce changement de libellé dans toutes les langues est le plus susceptible de casser l'affichage si :
- Le frontend utilise cette clé comme titre/onglet de la page société détails
- Le frontend fait un switch/condition sur la valeur "Parent company" ou "Société parent"
- Le fil d'Ariane ou la navigation dépend de ce libellé

### Autres changements (impact faible)

- 3 nouvelles clés : correctement traduites dans toutes les langues, ne devraient pas casser l'affichage
- `MS_SUCCESS_ERROR_272` : message avec placeholders HTML, correctement traduit, ne devrait pas casser l'affichage
- 5 coquilles non corrigées dans EN10 : peuvent causer des affichages incorrects pour ces 5 clés spécifiques

### Recommandations

1. **Vérifier côté frontend** si la clé `LO_AF_CR_1285` est utilisée comme condition d'affichage ou titre dans la page "société détails"
2. **Corriger les 5 coquilles restantes** dans `en 10.json` (lancer le pipeline JSON en mode correction)
3. **Si le libellé "Parent company" doit être conservé** : il faut soit restaurer la valeur dans la source EN10, soit ajuster le frontend pour accepter le nouveau libellé "Current Profile"