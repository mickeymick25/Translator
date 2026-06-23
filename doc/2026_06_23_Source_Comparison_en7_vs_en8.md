# Comparaison des sources COP : en 7.json -> en8.json

- Ancienne source : `translator/source/2026_06_12_Import/en 7.json`
- Nouvelle source : `translator/source/2026_06_23_Import/en8.json`

## Synthèse

| Métrique | Valeur |
|---|---|
| Clés (ancienne) | 2531 |
| Clés (nouvelle) | 2541 |
| Communes | 2531 |
| Inchangées | 2531 |
| Modifiées (valeur) | 0 |
| Ajoutées | 10 |
| Supprimées | 0 |
| Modifs avec placeholder divergent | 0 |

## Clés ajoutées (10)

### Par préfixe

| Préfixe | Nombre | Exemples |
|---|---:|---|
| BU | 6 | `BU_ST_ME_2168`, `BU_ST_ME_2169`, `BU_ST_ME_2170`, `BU_ST_ME_2171`, `BU_ST_ME_2172` (+1) |
| LO | 3 | `LO_LO_CT_2167`, `LO_LO_DI_2168`, `LO_LO_DI_2169` |
| PA | 1 | `PA_AU_SU_2166` |

### Liste complète

- `BU_ST_ME_2168` : Done
- `BU_ST_ME_2169` : Pairing Error
- `BU_ST_ME_2170` : Rejected Source
- `BU_ST_ME_2171` : Rejected : Target Location
- `BU_ST_ME_2172` : Rejected Parent: DMS or Nature Code Conflict
- `BU_ST_ME_2173` : R1 links not transferred
- `LO_LO_CT_2167` : Refresh exported data
- `LO_LO_DI_2168` : Are you Sure ?
- `LO_LO_DI_2169` : The exported data will be refreshed with the latest available information. Continue?
- `PA_AU_SU_2166` : Your local date & time

## Clés supprimées (0)

_Aucune_


## Clés modifiées (0)

_Aucune valeur modifiée._


## Mouvement par préfixe (ajouts - suppressions)

| Préfixe | Ajouts | Suppressions | Solde |
|---|---:|---:|---:|
| BU | 6 | 0 | 6 |
| LO | 3 | 0 | 3 |
| PA | 1 | 0 | 1 |
