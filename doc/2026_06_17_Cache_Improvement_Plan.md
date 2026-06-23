# Plan d'amélioration du cache de traduction

**Date :** 17/06/2026
**Objectif :** Permettre au cache de prendre en charge la **totalité des 2 471 clés par langue** au lieu des 1 471 actuelles
**Statut :** Analyse complète — prêt pour implémentation

---

## 1. Contexte et rappel du problème

Le cache actuel utilise le format de clé `en:{lang}:{text}` où `text` est la **valeur source en anglais**. Avec 1 091 valeurs uniques et 2 471 clés i18n, environ **40% des traductions sont écrasées** par collision (cf. `2026_06_17_Cache_Duplication_Analysis.md`).

**État actuel :**
- Cache : 8 826 entries (1 471 par langue × 6 langues)
- Couverture effective : 59.5% des clés i18n
- Perte par collision : 40.5%

## 2. Analyse du flux de données

### 2.1 Chaîne d'appel complète

```
Fichier source (en 7.json)
   ↓ [chargement]
source_data: dict[str, str]  (clé i18n → valeur EN)
   ↓ [chunking par 50]
chunks: list[dict[str, str]]  (50 clés i18n par chunk)
   ↓ [OllamaProvider.translate_batch(chunk)]
Pour chaque item du chunk:
   key (i18n) → text (EN)
   ↓ [cache.get(source, target, text)]
   Clé actuelle: en:{lang}:{text}  ← collision possible
   ↓ [Ollama] ou [Google fallback]
   translation
   ↓ [cache.put(source, target, text, translation)]
```

### 2.2 Points clés identifiés

**Bonne nouvelle :** La clé i18n est **disponible à chaque étape** :
- `mode_translate_json.py:147` : `provider.translate_batch(chunk, ...)` où `chunk` est `dict[str, str]`
- `ollama_provider.py:135` : `for key, text in items.items():` → la clé i18n est dans `key`
- `ollama_provider.py:186-187` : `chunk_result.items()` → la traduction est associée à la clé i18n

**Le bug est uniquement dans `cache.py:_make_key` qui ignore la clé i18n.**

## 3. Trois solutions analysées en détail

### Solution A — Clé = identifiant i18n seul

```python
def _make_key(source_lang, target_lang, text, key_id=None):
    return f"{src}:{tgt}:{key_id or text}"
```

| Aspect | Évaluation |
|---|---|
| Modifications code | Cache uniquement (1 méthode + signatures appelantes) |
| Couverture | 100% (1 entrée par clé i18n) |
| Régression | ❌ Oui — le cache ne déduplique plus les traductions identiques |
| Espace disque | ×N pour valeurs dupliquées (×37 pour "Action") |
| Migration ancien cache | Lecture ancien format si nouvelle clé absente |
| Tests à adapter | `test_key_format`, `test_different_texts_produce_different_keys` |

**Verdict :** Simple mais **perd l'avantage de la déduplication**. Le cache passe de 8 826 à ~14 826 entries.

### Solution B — Clé composite (clé i18n + texte)

```python
def _make_key(source_lang, target_lang, text, key_id=None):
    if key_id:
        return f"{src}:{tgt}:{key_id}:{text}"
    return f"{src}:{tgt}:{text}"  # rétrocompat
```

| Aspect | Évaluation |
|---|---|
| Modifications code | Cache + ollama_provider + translator (propagation key_id) |
| Couverture | 100% |
| Régression | ❌ Aucune — double format supporté |
| Espace disque | ~14 826 entries (équivalent Solution A) |
| Migration | Lecture des deux formats, réécriture en format B |
| Tests à adapter | Tests cache (nouvelle signature), tests ollama_provider |

**Verdict :** Plus de travail mais **zéro régression**, migration transparente.

### Solution C — Double index (clé i18n → text + text → translation)

```python
# Dans TranslationCache
def put(self, source, target, text, translation, key_id=None):
    base_key = f"{src}:{tgt}:{text}"
    composite_key = f"{src}:{tgt}:{key_id or text}:{text}"
    self._entries[base_key] = translation  # déduplication
    if key_id:
        self._key_index[composite_key] = text  # index secondaire
```

| Aspect | Évaluation |
|---|---|
| Modifications code | Cache (ajout index secondaire) |
| Couverture | 100% avec lookup précis |
| Régression | ❌ Aucune |
| Espace disque | ~8 826 entries + ~14 826 index |
| Complexité | Élevée (2 structures synchronisées) |

**Verdict :** Le plus puissant mais **trop complexe** pour le gain réel.

## 4. Recommandation : **Solution B — clé composite**

### Justification

1. **Zéro régression** : l'ancien format reste lisible, le nouveau format coexiste
2. **Migration douce** : on peut basculer progressivement sans casser les déploiements
3. **Repérage précis** : chaque clé i18n a sa propre entrée de cache
4. **Détection de changement** : si le texte EN d'une clé change, on peut invalider précisément
5. **Test futur possible** : permet des traductions différenciées par contexte si besoin

## 5. Plan d'implémentation

### Phase 1 — Préparation (sans modification fonctionnelle)

**Durée estimée :** 1-2h

1. **Ajouter une méthode de test** dans `cache.py` :
   ```python
   @staticmethod
   def _make_composite_key(source_lang, target_lang, key_id, text):
       return f"{src}:{tgt}:{key_id}:{text}"
   ```

2. **Modifier `_make_key` pour accepter un `key_id` optionnel** :
   ```python
   @staticmethod
   def _make_key(source_lang, target_lang, text, key_id=None):
       src = _normalize_lang_code(source_lang)
       tgt = _normalize_lang_code(target_lang)
       if key_id:
           return f"{src}:{tgt}:{key_id}:{text}"
       return f"{src}:{tgt}:{text}"
   ```

3. **Modifier `get()` et `put()` pour accepter `key_id`** :
   ```python
   def get(self, source_lang, target_lang, text, key_id=None) -> str | None:
       key = self._make_key(source_lang, target_lang, text, key_id)
       ...

   def put(self, source_lang, target_lang, text, translation, key_id=None) -> None:
       key = self._make_key(source_lang, target_lang, text, key_id)
       ...
   ```

### Phase 2 — Propagation aux appelants

**Durée estimée :** 2-3h

1. **`core/translator.py:translate_text`** :
   ```python
   def translate_text(text, source_lang, target_lang, max_retries=3, key_id=None):
       ...
       cached = cache.get(source_lang, target_lang, text, key_id=key_id)
       ...
       cache.put(source_lang, target_lang, text, result, key_id=key_id)
   ```

2. **`core/ollama_provider.py:translate_batch`** :
   ```python
   for key, text in items.items():
       cached_result = cache.get(source, target, text, key_id=key)
       ...
       cache.put(source, target, original_text, v, key_id=k)
   ```

3. **`modes/mode_translate_json.py`** : propager `key_id` aux appels batch

### Phase 3 — Migration du cache existant

**Durée estimée :** 1h

Script de migration `migrate_cache_v2.py` :
```python
"""Convertit le cache existant du format simple au format composite."""
import json

with open(cache_path) as f:
    cache = json.load(f)

# Les anciennes clés "en:lang:text" sont l'anciennes traductions
# On ne peut PAS les migrer car on n'a pas les clés i18n
# Solution : repartir des fichiers de traduction validés

new_entries = {}
for lang in ['fr', 'cz', 'de', 'it', 'sk', 'ar']:
    translation_file = f'translation_en_{lang}.json'
    with open(translation_file) as f:
        translations = json.load(f)
    for key_id, source_value in en_source.items():
        if not source_value.strip():
            continue
        tr_value = translations.get(key_id, '')
        if not tr_value.strip():
            continue
        cache_key = f'en:{lang}:{key_id}:{source_value}'
        new_entries[cache_key] = tr_value

# Réécrire le cache dans le nouveau format
cache['entries'] = new_entries
cache['metadata']['version'] = 2
cache['metadata']['format'] = 'composite'
```

### Phase 4 — Tests et validation

**Durée estimée :** 2-3h

1. **Tests unitaires à adapter** dans `tests/test_cache.py` :
   - `test_key_format` : accepter les deux formats
   - `test_composite_key_format` : nouveau test
   - `test_get_put_with_key_id` : nouveau test
   - `test_backward_compatibility` : nouveau test (ancien format reste lisible)

2. **Tests d'intégration** :
   - Lancer une traduction avec cache v2 → vérifier les logs
   - Relancer la même traduction → vérifier 100% de cache HIT
   - Comparer cache v1 vs cache v2 en taille et couverture

3. **Validation non-régression** :
   - Tous les tests existants doivent passer (761 tests)
   - Vérifier que les traductions générées sont identiques
   - Vérifier que le FR corrigé reste correct

## 6. Estimation de l'impact

### Espace disque

| Métrique | v1 (actuel) | v2 (proposé) |
|---|---|---|
| Format de clé | `en:lang:text` | `en:lang:key:text` |
| Entries par langue | 1 471 | 2 471 |
| Total (6 langues) | 8 826 | 14 826 |
| Taille fichier | 791 KB | ~1.5 MB estimé |

### Performance

| Métrique | v1 | v2 |
|---|---|---|
| Hit rate par run | ~60% | **~100%** |
| Temps moyen run | ~25 min | **<1 min** |
| Cache lookup | O(1) | O(1) |
| Migration one-shot | — | ~30s |

### Couverture

| Métrique | v1 | v2 |
|---|---|---|
| Clés effectivement cachées | 1 471/2 471 | **2 471/2 471** |
| Perte par collision | 40.5% | **0%** |

## 7. Risques identifiés

### Risque 1 — Incompatibilité ancien cache

**Mitigation :** La Phase 1 conserve la rétrocompatibilité. Le cache v2 peut lire les deux formats.

### Risque 2 — Tests cassés

**Mitigation :** Adapter les tests existants (5-10 tests) + ajouter tests de rétrocompatibilité.

### Risque 3 — Migration incorrecte

**Mitigation :** Backup `.translation_cache.json.full_backup.bak` existe déjà. Migration script idempotente.

### Risque 4 — Régression sur les traductions

**Mitigation :** Les traductions sont stockées identiques. Seule la clé change.

## 8. Checklist de validation

- [ ] Tous les tests `test_cache.py` passent (76 tests)
- [ ] Tous les tests `test_translator.py` passent
- [ ] Tous les tests `test_ollama_provider.py` passent
- [ ] Run de test sur 1 langue (CZ) → 100% cache HIT au 2e run
- [ ] Comparaison traductions v1 vs v2 → identiques
- [ ] Taille cache v2 dans les limites attendues (~1.5 MB)
- [ ] Documentation mise à jour (README + ce document)

## 9. Décisions à prendre avant implémentation

| Question | Options |
|---|---|
| Faut-il conserver l'ancien format en lecture ? | ✅ Oui (rétrocompat) |
| Faut-il une période de transition ? | ❌ Non (peut coexister) |
| Faut-il un flag de configuration ? | ❌ Non (transparent) |
| Migration auto au démarrage ? | ⚠️ À discuter |

## 10. Fichiers à modifier

| Fichier | Modifications |
|---|---|
| `translator/core/cache.py` | Ajouter key_id dans _make_key, get, put |
| `translator/core/translator.py` | Propager key_id dans translate_text |
| `translator/core/ollama_provider.py` | Propager key_id dans translate_batch |
| `translator/modes/mode_translate_json.py` | Propager key_id (si nécessaire) |
| `translator/tests/test_cache.py` | Adapter tests + ajouter rétrocompat |
| `translator/output/.translation_cache.json` | Migration au nouveau format |
| `doc/2026_06_17_Cache_Improvement_Plan.md` | Ce document (mise à jour post-implémentation) |

## 11. Estimation globale

| Phase | Effort |
|---|---|
| Phase 1 — Préparation | 1-2h |
| Phase 2 — Propagation | 2-3h |
| Phase 3 — Migration | 1h |
| Phase 4 — Tests | 2-3h |
| **Total** | **6-9h** |

**Recommandation :** Implémenter en une session dédiée, avec tests complets avant déploiement.
