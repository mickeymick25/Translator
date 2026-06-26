# Analyse de l'écart de traduction — fichiers existants vs nouvelle source

- Source (nouvelle) : `translator/output/2026_06_23_Export` vs source EN courante
- Langues analysées : ar, cz, de, fr, it, sk

## Synthèse par langue

| Langue | Clés présentes | À ajouter | À supprimer | À modifier (source modifiée) | Incomplètes (trad vide, source non vide) | Sur-remplies (trad non vide, source vide) |
|---|---:|---:|---:|---:|---:|---:|
| ar | 2541 | 1 | 0 | 2 | 0 | 0 |
| cz | 2541 | 1 | 0 | 2 | 0 | 0 |
| de | 2541 | 1 | 0 | 2 | 0 | 0 |
| fr | 2541 | 1 | 0 | 2 | 0 | 17 |
| it | 2541 | 1 | 0 | 2 | 0 | 0 |
| sk | 2541 | 1 | 0 | 2 | 0 | 0 |

## Clés à ajouter (communes à toutes les langues : 1)

| Clé | Valeur EN source |
|---|---|
| `MS_SUCCESS_ERROR_272` | Location links regeneration has been done |

## Clés à supprimer (communes : 0)

_Aucune._

## Clés à modifier — source modifiée entre ancienne et nouvelle source (communes : 2)

| Clé | Nouvelle valeur EN |
|---|---|
| `BU_ST_ME_2169` | Paring Error |
| `PA_AU_MO_1069` | Inprogress |

## Traductions incomplètes (vide côté cible, texte présent côté source)

### ar : _aucune_

### cz : _aucune_

### de : _aucune_

### fr : _aucune_

### it : _aucune_

### sk : _aucune_

## Traductions sur-remplies (valeur côté cible, source vide)

> Ces clés ont une source EN vide mais une traduction non vide (back-fill manuel). 
Elles ne seront pas régénérées par le pipeline (rien à traduire côté source). 
À propager manuellement vers les autres langues si pertinent.

### ar : _aucune_

### cz : _aucune_

### de : _aucune_

### fr (17)

| Clé | Valeur cible actuelle |
|---|---|
| `PA_CO_CR_823` | Soumettre |
| `PA_CO_ED_835` | Soumettre |
| `PA_CO_IN_811` | Supprimer |
| `PA_CO_VI_849` | Détails |
| `PA_CO_VI_859` | Soumettre |
| `PA_ID_CT_884` | Modifier |
| `PA_ID_NE_878` | Description de l’identifiant |
| `PA_ID_TA_900` | Action |
| `PA_ID_TA_908` | Action |
| `PA_NE_CR_767` | Enregistrer |
| `PA_NE_CR_772` | Soumettre |
| `PA_NE_CR_783` | Soumettre |
| `PA_NE_CR_790` | Valider |
| `PA_NE_ED_797` | Valider |
| `PA_NE_HI_743` | Supprimer |
| `PA_NE_NO_756` | Désactiver |
| `PA_NE_TA_729` | Type de nœud |

### it : _aucune_

### sk : _aucune_

## Plan d'action recommandé

1. **Ajouter** 1 nouvelle(s) clé(s) × 6 langue(s) = 6 traductions à produire.
2. **Supprimer** 0 clé(s) orpheline(s) des fichiers cibles (commun à toutes les langues).
3. **Modifier** 2 clé(s) dont la source a changé (retraduire).
4. **Compléter** les traductions incomplètes (voir section dédiée).
5. **Décider** du sort des traductions sur-remplies (back-fill FR) : propager aux autres langues ou laisser.
