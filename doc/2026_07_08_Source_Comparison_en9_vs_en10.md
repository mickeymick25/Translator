# Comparaison des sources COP : en 9.json -> en 10.json

- Ancienne source : `translator/source/2026_06_25_Import/en 9.json`
- Nouvelle source : `translator/source/2026_07_08_Import/en 10.json`

## Synthèse

| Métrique | Valeur |
|---|---|
| Clés (ancienne) | 2542 |
| Clés (nouvelle) | 2545 |
| Communes | 2542 |
| Inchangées | 2539 |
| Modifiées (valeur) | 3 |
| Ajoutées | 3 |
| Supprimées | 0 |
| Modifs avec placeholder divergent | 1 |

## Clés ajoutées (3)

### Par préfixe

| Préfixe | Nombre | Exemples |
|---|---:|---|
| LO | 1 | `LO_PR_CH_2174` |
| MS | 1 | `MS_SUCCESS_ERROR_273` |
| PA | 1 | `PA_AU_MO_2174` |

### Liste complète

- `LO_PR_CH_2174` : Change Partner
- `MS_SUCCESS_ERROR_273` : The animation link partner has been successfully updated.
- `PA_AU_MO_2174` : Warning

## Clés supprimées (0)

_Aucune_


## Clés modifiées (3)

### Modifs avec divergences de placeholders (1)

| Clé | Placeholders old | Placeholders new |
|---|---|---|
| `MS_SUCCESS_ERROR_272` | [] | ['</strong>', '<strong>', '{{locationId}', '{{locationName}'] |

### Détail de ces divergences

#### `MS_SUCCESS_ERROR_272`

- old: Location links regeneration has been done
- new: The Location <strong>{{locationId}} - {{locationName}}</strong> links have been updated successfully.

### Détail des valeurs modifiées (échantillon <= 120)

#### `BU_ST_ME_2169`

```diff
--- BU_ST_ME_2169 (old)
+++ BU_ST_ME_2169 (new)
@@ -1 +1 @@
-Pairing Error
+Paring Error
```

#### `LO_AF_CR_1285`

```diff
--- LO_AF_CR_1285 (old)
+++ LO_AF_CR_1285 (new)
@@ -1 +1 @@
-Parent company
+Current Profile
```

#### `MS_SUCCESS_ERROR_272`

```diff
--- MS_SUCCESS_ERROR_272 (old)
+++ MS_SUCCESS_ERROR_272 (new)
@@ -1 +1 @@
-Location links regeneration has been done
+The Location <strong>{{locationId}} - {{locationName}}</strong> links have been updated successfully.
```


## Mouvement par préfixe (ajouts - suppressions)

| Préfixe | Ajouts | Suppressions | Solde |
|---|---:|---:|---:|
| MS | 1 | 0 | 1 |
| PA | 1 | 0 | 1 |
| LO | 1 | 0 | 1 |
