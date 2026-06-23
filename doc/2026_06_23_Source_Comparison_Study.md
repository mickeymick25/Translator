# Étude de comparaison des sources — en7 (2026-06-12) → en8 (2026-06-23)

- **Date** : 2026-06-23
- **Ancienne source** : `translator/source/2026_06_12_Import/en 7.json` (2531 clés)
- **Nouvelle source** : `translator/source/2026_06_23_Import/en8.json` (2541 clés)
- **Outil** : `compare_sources.py` (à la racine du projet)
- **Sorties générées** :
  - `doc/2026_06_23_Source_Comparison_en7_vs_en8.md` (rapport détaillé)
  - `doc/2026_06_23_Source_Comparison_en7_vs_en8.json` (export machine-readable)

## Synthèse

| Métrique | Valeur |
|---|---|
| Clés (ancienne) | 2531 |
| Clés (nouvelle) | 2541 |
| Communes | 2531 |
| Inchangées | 2530 |
| Modifiées (valeur) | 1 |
| Ajoutées | 10 |
| Supprimées | 0 |
| Modifs avec placeholder divergent | 0 |

**Verdict** : évolution mineure et additive. Aucune clé retirée, aucune rupture de placeholder. Le périmètre à retraduire est très réduit.

## Clés ajoutées (10)

Toutes nouvelles, aucune suppression symétrique. Groupées par préfixe :

| Préfixe | Nombre | Clés |
|---|---:|---|
| `BU` | 6 | `BU_ST_ME_2168` … `BU_ST_ME_2173` |
| `LO` | 3 | `LO_LO_CT_2167`, `LO_LO_DI_2168`, `LO_LO_DI_2169` |
| `PA` | 1 | `PA_AU_SU_2166` |

Détail :

| Clé | Valeur (EN) | Domaine probable |
|---|---|---|
| `BU_ST_ME_2168` | `Done` | Statut bulk/transfer |
| `BU_ST_ME_2169` | `Paring Error` | Statut bulk/transfer |
| `BU_ST_ME_2170` | `Rejected Source` | Statut bulk/transfer |
| `BU_ST_ME_2171` | `Rejected : Target Location` | Statut bulk/transfer |
| `BU_ST_ME_2172` | `Rejected Parent: DMS or Nature Code Conflict` | Statut bulk/transfer |
| `BU_ST_ME_2173` | `R1 links not transferred` | Statut bulk/transfer |
| `LO_LO_CT_2167` | `Refresh exported data` | Action UI (refresh export) |
| `LO_LO_DI_2168` | `Are you Sure ?` | Dialogue de confirmation |
| `LO_LO_DI_2169` | `The exported data will be refreshed with the latest available information. Continue?` | Dialogue de confirmation |
| `PA_AU_SU_2166` | `Your local date & time` | Profil utilisateur / settings |

> **Note qualité** : `BU_ST_ME_2172` contient `:` et `or` — s'assurer que le traducteur préserve la ponctuation et la conjonction. `Paring Error` (2169) est probablement une faute de frappe pour `Pairing Error` côté source ; à faire valider avant traduction (ne pas « corriger » dans la cible sans confirmation).

## Clé modifiée (1)

| Clé | old (en7) | new (en8) |
|---|---|---|
| `PA_AU_MO_1069` | `In progress` | `Inprogress` |

- Modification purement cosmétique/source : fusion des deux mots en un seul (`Inprogress`).
- **Impact traduction** : la valeur de la cible précédente (`In progress` → ex. FR « En cours ») reste sémantiquement correcte. Selon la stratégie de cache, cette clé sera considérée comme **à retraduire** car la chaîne source a changé. Deux options :
  1. Accepter la retraduction (coût : 1 entrée).
  2. Si le cache est indexé par hash de valeur source, forcer la réutilisation de l'ancienne traduction pour éviter un changement cosmétique inutile côté cible.

## Placeholders / format

Aucune divergence de placeholder détectée sur la modification. Les 10 ajouts ne contiennent ni `%s`, `{name}`, `<b>`, ni ICU — ce sont des chaînes simples, sans risque structurel.

## Impacts pour le pipeline de traduction

1. **Volume à retraduire** : 10 nouvelles + 1 modifiée = **11 entrées** par langue cible.
2. **Aucune suppression** → pas de nettoyage de cache à faire pour des clés disparues.
3. **Aucun risque placeholder** → la validation structurelle (5 contrôles) passera sans ajustement.
4. **Recommandation cache** :
   - Pour `PA_AU_MO_1069`, vérifier la politique du cache (`translator/core/cache.py`) : si la clé est indexée par `(key, source_hash)`, la retraduction sera déclenchée automatiquement ; sinon, forcer un invalidation ponctuelle ou réinjecter la traduction existante.
5. **Domaines fonctionnels concernés** :
   - Bulk/Transfer status (`BU_ST_ME_*`) — nouveau bloc de statuts, vraisemblablement lié à un écran de reporting/erreurs de transfert.
   - Location export refresh (`LO_LO_CT/DI_*`) — nouvelle action de rafraîchissement des données exportées avec dialogue de confirmation.
   - User profile (`PA_AU_*`) — complément d'info « date & heure locale » et correction cosmétique.

## Plan d'action proposé

1. Faire valider côté métier la chaîne `Paring Error` (`BU_ST_ME_2169`) — coquille suspecte.
2. Décider de la politique pour `PA_AU_MO_1069` (retraduire vs. réutiliser l'ancienne cible).
3. Lancer la traduction incrémentale des 11 entrées via le service (`translate-json`) en mode cache intelligent — seules ces entrées seront effectivement traduites, le reste sera servi par le cache.
4. Archer le rapport détaillé : `doc/2026_06_23_Source_Comparison_en7_vs_en8.md`.

## Commande pour reproduire

```bash
python3 compare_sources.py \
  "translator/source/2026_06_12_Import/en 7.json" \
  "translator/source/2026_06_23_Import/en8.json" \
  --report "doc/2026_06_23_Source_Comparison_en7_vs_en8.md" \
  --json   "doc/2026_06_23_Source_Comparison_en7_vs_en8.json"
```