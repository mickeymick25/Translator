# Analyse du bug de duplication du cache de traduction

**Date :** 17/06/2026
**Auteur :** Analyse technique post-génération des traductions 2026_06_12
**Sévérité :** 🟠 Moyenne (fonctionnel mais sous-optimal)
**Statut :** Identifié — à corriger dans une itération future

---

## 1. Résumé exécutif

Le système de cache de traduction utilise le **texte source** comme partie de la clé de cache, ce qui provoque des **collisions massives** lorsque plusieurs clés i18n partagent la même valeur en anglais. Résultat : environ **40% des traductions sont écrasées** lors du repeuplement du cache, sans perte visible à l'exécution car les clés dupliquées reçoivent la même traduction.

## 2. Flux de traduction observé

```
Fichier source (en 7.json)
   ↓
Clé i18n     → Valeur EN
"Home"       → "Home"
"Cancel"     → "Cancel"
"Confirm"    → "Confirm"

        ↓ (translate_text — translator/core/translator.py:96-104)

Cache.get(source_lang="en", target_lang="cz", text="Home")
   ↓
Clé cache: "en:cz:Home"
   ↓
Cache HIT → renvoie la traduction
```

## 3. Code source de la clé de cache

**Fichier :** `translator/core/cache.py`
**Lignes :** 64-69

```python
@staticmethod
def _make_key(source_lang: str, target_lang: str, text: str) -> str:
    """Generate a unique cache key for a (source, target, text) triplet."""
    src = _normalize_lang_code(source_lang)
    tgt = _normalize_lang_code(target_lang)
    return f"{src}:{tgt}:{text}"
```

**Problème :** Le paramètre `text` est la **valeur source** (ex. "Home"), pas l'**identifiant i18n** (ex. "Btn_Home").

## 4. Impact mesuré sur `en 7.json`

### Statistiques de la source

| Métrique | Valeur |
|---|---|
| Clés totales | 2 531 |
| Clés non vides | 2 471 |
| Valeurs EN uniques | 1 091 |
| Valeurs EN dupliquées | 380 |

### Top 10 des valeurs EN les plus dupliquées

| Valeur EN | Occurrences | Exemples de clés i18n |
|---|---|---|
| `Action` | 37 | `Btn_Action`, `CO_CO_TA_184`, `PA_US_TA_614` |
| `Start date` | 30 | `CO_CR_SE_88`, `CO_CR_SE_103`, `CO_CR_CO_119` |
| `End date` | 29 | `CO_CR_SE_89`, `CO_CR_SE_104`, `CO_CR_CO_120` |
| `Type` | 25 | `OR_VI_TA_28`, `OR_CR_MO_40`, `CO_CR_SE_95` |
| `Effective date` | 23 | `OR_CR_MO_41`, `OR_VI_TA_55`, `CO_CR_CO_114` |
| `Until date` | 23 | `OR_CR_MO_42`, `OR_VI_TA_56`, `CO_CR_CO_115` |
| `Status` | 23 | `CO_CR_SE_90`, `CO_UP_CO_196`, `NE_BU_BU_530` |
| `Cancel` | 16 | `Btn_Cancel`, `PA_NE_CR_770`, `PA_NE_CR_781` |
| `Name` | 16 | `OR_VI_TA_26`, `OR_CR_MO_39`, `CO_CO_TA_178` |
| `Edit` | 14 | `Btn_Edit`, `OR_CR_MO_48`, `PA_NE_HI_741` |

**Total des collisions sur ces 10 valeurs seules :** 236 clés i18n écrasées en 10 entrées de cache.

## 5. Vérification empirique

### Repeuplement du cache depuis les fichiers validés

```
Total traductions à insérer : 14 826 (2 471 clés × 6 langues)
Entries réellement stockées : 8 826 (1 471 par langue)
Entries écrasées par collision : 6 000
Taux de perte : 40.5%
```

### Couverture effective

| Métrique | Valeur |
|---|---|
| Clés i18n source | 2 471 |
| Entrées de cache après merge | 1 471 |
| Couverture | 59.5% |
| Perte par collision | 40.5% |

## 6. Pourquoi ce n'était pas un bug visible

### Comportement fonctionnel préservé

Le service fonctionne "correctement" en production car :

1. **Cohérence sémantique :** Les clés i18n partageant la même valeur EN reçoivent naturellement la même traduction dans une langue cible. Exemple : `Btn_Home` et `Menu_Home` ("Home" en EN) → tous deux traduits par "Domů" en CZ.

2. **Pas de différence visible :** L'utilisateur final ne voit aucune différence, le rendu UI est identique.

3. **Tests passent :** Les 761 tests unitaires (94% de couverture) vérifient le comportement fonctionnel, pas la granularité du cache.

### Mais des diagnostics faussés

- **Hit rate optimiste :** Un cache HIT pour "Action" est compté 1 fois mais profite à 37 clés i18n
- **Statistiques agrégées trompeuses :** "60% hit rate" cache en réalité un comportement très efficace (chaque HIT sert 1 à 37 clés)
- **Impossible de repeupler depuis les fichiers :** Le merge ne peut pas restaurer les entrées perdues

## 7. Solutions possibles

### Option A — Clé = identifiant i18n

```python
def _make_key(source_lang: str, target_lang: str, text: str, key_id: str = None) -> str:
    return f"{src}:{tgt}:{key_id or text}"
```

**Avantages :**
- 1 entrée par clé i18n
- Pas de collision
- Granularité maximale

**Inconvénients :**
- Le cache ne profite plus de la déduplication naturelle
- Taille du cache ×N pour les valeurs dupliquées (×37 pour "Action")
- Plus d'espace disque nécessaire

### Option B — Clé composite (clé i18n + texte)

```python
def _make_key(source_lang, target_lang, text, key_id):
    return f"{src}:{tgt}:{key_id}:{text}"
```

**Avantages :**
- Cache HIT par clé i18n
- Détection de changement de texte pour invalidation précise
- Permet de vérifier la cohérence texte/clé
- Repeuplement direct 1:1 depuis les fichiers

**Inconvénients :**
- Format de clé incompatible avec l'existant (migration nécessaire)
- Taille du cache légèrement augmentée

### Option C — Cache actuel + index secondaire

Garder `en:{lang}:{text}` pour la déduplication rapide, ajouter un index `en:{lang}:key_id → text` pour le lookup précis.

**Avantages :**
- Rétrocompatible
- Conserve la performance actuelle

**Inconvénients :**
- Complexité accrue
- Deux structures de données à maintenir en cohérence

## 8. Recommandation

**Option B** est la solution la plus propre pour un système i18n :

1. Chaque clé i18n a sa propre entrée de cache
2. Si une clé change de texte en EN, on peut invalider précisément cette entrée
3. Les statistiques de hit rate sont exactes
4. Le repeuplement depuis les fichiers `translation_en_*.json` est direct (1:1)
5. Compatible avec les mécanismes d'invalidation existants (`_dirty`, `flush`)

### Plan de migration suggéré

1. **Phase 1 :** Implémenter `Option B` avec double-écriture (ancien + nouveau format)
2. **Phase 2 :** Sur une période de transition, lire l'ancien format si le nouveau est absent
3. **Phase 3 :** Réécrire entièrement le cache dans le nouveau format
4. **Phase 4 :** Supprimer le code de compatibilité ascendante

## 9. État actuel et acceptation

### Pour la livraison 2026_06_12

Le bug est **acceptable** car :
- Les traductions sont identiques pour les valeurs dupliquées
- Le service fonctionne correctement
- Le cache accélère ~60% des lookups en moyenne
- Aucune régression visible

### Pour les évolutions futures

Le bug devrait être corrigé avant :
- L'ajout de plus de langues (le taux de perte augmenterait)
- L'introduction de traductions spécialisées par contexte (où les doublons pourraient diverger)
- La mise en place de caches distribués (la duplication des données poserait problème)

## 10. Fichiers de référence

| Fichier | Rôle |
|---|---|
| `translator/core/cache.py` | Implémentation du cache (lignes 64-69 : `_make_key`) |
| `translator/core/translator.py` | Utilisation du cache (lignes 96-117 : `translate_text`) |
| `translator/source/2026_06_12_Import/en 7.json` | Source analysée (2 531 clés, 2 471 non vides) |
| `translator/output/.translation_cache.json` | Cache actuel (8 826 entries, 1 471 par langue) |
| `translator/output/2026_06_12_Export/translation_en_*.json` | Fichiers de traduction validés |
| `doc/2026_06_17_Brief_Generate_2026_06_12_Missing_Langs.md` | Brief de génération des traductions |

## 11. Glossaire

| Terme | Définition |
|---|---|
| **Clé i18n** | Identifiant unique d'une chaîne traduisible (ex. `Btn_Home`) |
| **Valeur source** | Texte dans la langue source, ici l'anglais (ex. "Home") |
| **Cache HIT** | Entrée trouvée dans le cache, traduction récupérée instantanément |
| **Cache MISS** | Entrée absente du cache, traduction à calculer |
| **Collision** | Deux clés i18n différentes écrasées dans la même entrée de cache car même valeur source |
