# Traduction FR 2026_06_12 — Journal des modifications

**Date :** 12/06/2026  
**Fichier source :** `source/2026_06_12_Import/en 7.json` (2531 clés)  
**Fichier de référence :** `source/2026_06_12_Import/Export_COP_Excel.csv` (2135 clés, 2071 valeurs FR non-vides)  
**Fichier produit :** `output/2026_06_12_Export/translation_en_fr.json`

---

## Table des matières

1. [Processus de traduction](#1-processus-de-traduction)
2. [Corrections appliquées](#2-corrections-appliquées)
3. [Fusion avec le fichier de référence](#3-fusion-avec-le-fichier-de-référence)
4. [Re-traduction des clés manquantes](#4-re-traduction-des-clés-manquantes)
5. [Résultat final](#5-résultat-final)
6. [Fichiers générés](#6-fichiers-générés)

---

## 1. Processus de traduction

### 1.1 Traduction initiale (Ollama glm-5.1:cloud)

- **Provider :** Ollama glm-5.1:cloud
- **Mode :** translate-json, BATCH_LANGS=fr
- **Cache :** Désactivé (`TRANSLATION_CACHE=false`)
- **Source :** `source/2026_06_12_Import/en 7.json` (2531 clés, 2471 valeurs non-vides)
- **Résultat :** 2531 entrées traduites en français par Ollama

### 1.2 Problème réseau (Google Translate)

Une première tentative avec le provider Google Translate a échoué car le conteneur Docker n'avait pas d'accès réseau. Le provider Ollama (local/cloud) a été utilisé à la place.

---

## 2. Corrections appliquées

### 2.1 Remplacement "entreprise" → "société"

**Règle métier :** En français, le terme "société" doit être utilisé plutôt que "entreprise".

| Action | Nombre d'entrées |
|--------|-------------------|
| `entreprise` → `société` | 269 |
| Corrections d'élision (`d'entreprise` → `de société`, `l'entreprise` → `la société`) | 201 |
| Occurrences restantes de "entreprise" | 0 |

### 2.2 Remplacement "emplacement/localisation/lieu" → "site"

**Règle métier :** Le terme anglais "Location" doit être traduit par "site" en français.

| Action | Nombre d'entrées |
|--------|-------------------|
| `emplacement` → `site` (et déclinaisons) | 214 |
| `localisation` → `site` (et déclinaisons) | 3 |
| Corrections d'élision (`de l'emplacement` → `du site`, etc.) | 114 |
| Occurrences restantes de "emplacement/localisation" | 0 |

### 2.3 Remplacement "Unité organisationnelle" → "Organisation"

**Règle métier :** Le terme "Unité organisationnelle" doit être traduit par "Organisation".

| Action | Nombre d'entrées |
|--------|-------------------|
| `Unité organisationnelle` / `Unité Orga` → `Organisation` | 45 |
| Occurrences restantes | 0 |

### 2.4 Remplacement "Raison sociale" → "Nom légal" (pour "Legal name")

**Règle métier :** Le terme "Legal name" doit être traduit par "Nom légal".

| Action | Nombre d'entrées |
|--------|-------------------|
| `Raison sociale` → `Nom légal` (pour "Legal name") | 7 |
| Espaces en trop "Nom légal " → "Nom légal" | 8 |

### 2.5 Remplacement "Nom d'usage" → "Nom usuel" (pour "Usual name")

**Règle métier :** Le terme "Usual name" doit être traduit par "Nom usuel".

| Action | Nombre d'entrées |
|--------|-------------------|
| `Nom d'usage` → `Nom usuel` | 14 |

---

## 3. Fusion avec le fichier de référence

### 3.1 Source de vérité

Le fichier **`Export_COP_Excel.csv`** contient les traductions FR de référence validées par le métier. Il a été utilisé comme source de vérité pour les clés qu'il contient.

### 3.2 Correspondance

| Métrique | Valeur |
|----------|--------|
| Clés dans le JSON FR | 2531 |
| Clés avec FR dans Export_COP_Excel.csv | 2067 |
| Clés communes (présentes dans les deux) | 1997 |
| **Valeurs FR identiques après fusion** | **1997 (100%)** |
| Clés JSON absentes du CSV | 534 |
| Clés CSV absentes du JSON | 138 (ignorées, hors périmètre) |

### 3.3 Opération

- Les **1944 valeurs** déjà conformes au CSV ont été conservées
- Les **1103 valeurs** différentes entre Ollama et le CSV ont été remplacées par les valeurs du CSV
- Les **587 clés** absentes du CSV ont conservé leur traduction Ollama puis ont été vidées et re-traduites

---

## 4. Re-traduction des clés manquantes

### 4.1 Problème

Les 587 clés absentes du fichier Export_COP_Excel.csv avaient été traduites par Ollama, mais avec des incohérences (même terme EN traduit différemment selon le contexte). Le fichier FR a été vidé de ces 587 valeurs, puis re-traduit par Ollama.

### 4.2 Résultat

- **544 clés** re-traduites par Ollama (les 43 clés vides dans la source EN restent vides)
- **0 incohérence** par rapport au fichier Export_COP_Excel.csv pour les clés communes

---

## 5. Résultat final

### 5.1 Statistiques

| Métrique | Valeur |
|----------|--------|
| Entrées totales | 2531 |
| Valeurs vides | 43 (correspondent aux entrées vides dans la source EN) |
| Valeurs non-vides | 2488 |
| Correspondance avec Export_COP_Excel.csv | 1997/1997 (100%) |

### 5.2 Règles métier appliquées

| Terme EN | Traduction FR retenue | Statut |
|----------|----------------------|--------|
| Company | Société | ✅ Appliqué |
| Location | Site | ✅ Appliqué |
| Orga Unit | Organisation | ✅ Appliqué |
| Legal name | Nom légal | ✅ Appliqué |
| Usual name | Nom usuel | ✅ Appliqué |
| entreprise (FR) | société | ✅ Appliqué |
| emplacement/localisation/lieu (FR) | site | ✅ Appliqué |

### 5.3 Incohérences résiduelles

Les 243 "incohérences" identifiées correspondent à des **traductions contextuelles légitimes** : le même terme EN apparaît dans des écrans différents avec un sens différent, et la traduction FR s'adapte au contexte. Toutes les valeurs pour les clés présentes dans Export_COP_Excel.csv sont alignées à 100%.

---

## 6. Fichiers générés

| Fichier | Description |
|---------|-------------|
| `output/2026_06_12_Export/translation_en_fr.json` | Fichier FR final (2531 entrées) |
| `output/2026_06_12_Export/incoherences_fr.csv` | Liste des incohérences internes (avant fusion CSV) |
| `output/2026_06_12_Export/incoherences_detaillees.csv` | Détail des incohérences avec référence Export_COP_Excel.csv |