# Rapport de bugs — Traductions COP

**Date :** 12/06/2026  
**Auteur :** Analyse automatisée  
**Scope :** Exports `2026_04_21` à `2026_06_11`

---

## Table des matières

1. [Bug #1 — Race condition ThreadPoolExecutor (export 05_27)](#bug-1--race-condition-threadpoolexecutor-export-05_27)
2. [Bug #2 — Clés non traduites par Ollama (export 06_11)](#bug-2--clés-non-traduites-par-ollama-export-06_11)
3. [Bug #3 — Incohérence de clé de cache `en:cs:` vs `en:cz:`](#bug-3--incohérence-de-clé-de-cache-encs-vs-encz)
4. [Bug #4 — Langue incorrecte dans les exports historiques (04_21, 05_05, 05_13)](#bug-4--langue-incorrecte-dans-les-exports-historiques-04_21-05_05-05_13)
5. [Annexe — Données de diagnostic](#annexe--données-de-diagnostic)

---

## Bug #1 — Race condition ThreadPoolExecutor (export 05_27)

### Sévérité

🔴 **Critique** — Fichiers de traduction produits dans une mauvaise langue

### Fichiers affectés

- `2026_05_27_Export/translation_en_fr.json` — entièrement en **tchèque** au lieu de français
- `2026_05_27_Export/translation_en_cz.json` — contient du **slovaque** mélangé au tchèque
- `2026_05_27_Export/translation_en_sk.json` — à **97,9 % identique** au fichier CZ (devrait être ~15 %)

### Description

Lors de l'export `2026_05_27`, la traduction batch multi-langues via `ThreadPoolExecutor(max_workers=4)` a produit des fichiers dans une langue incorrecte. Le fichier français contient 1 337 valeurs avec des caractères tchèques exclusifs (`ě`, `ř`, `ů`), et les fichiers CZ/SK sont quasi-identiques (2 469 / 2 523 clés = 97,9 %).

### Cause racine

Le provider `GoogleTranslator` (de la librairie `deep_translator`) est instancié comme un **singleton global** via `get_provider()` dans `translator.py`. Ce singleton est partagé entre tous les threads du `ThreadPoolExecutor`.

Dans `GoogleProvider.translate()` :

```python
# translator/core/translator_factory.py
class GoogleProvider(TranslationProvider):
    def translate(self, text: str, source: str, target: str) -> str:
        result = self._translator_cls(source=source, target=target).translate(text)
```

Bien qu'une nouvelle instance de `GoogleTranslator` soit créée à chaque appel, la librairie `deep_translator` peut avoir un état interne partagé (session HTTP, cache de langue, etc.) qui n'est pas thread-safe.

Dans `_translate_single_language()`, le flux est :

```
Thread 1 (FR):  provider.translate(text, 'en', 'fr')
Thread 2 (CZ):  provider.translate(text, 'en', 'cs')
Thread 3 (SK):  provider.translate(text, 'en', 'sk')
Thread 4 (DE):  provider.translate(text, 'en', 'de')
```

Si les threads s'exécutent simultanément, la langue cible peut être écrasée entre l'initialisation du translator et l'appel `.translate()`, provoquant des résultats dans la mauvaise langue.

### Preuves

| Comparaison | Export 05_27 | Autres exports |
|-------------|-------------|----------------|
| CZ vs SK (identité) | **97,9 %** | ~15 % |
| FR : caractères tchèques | **1 337** | 0 |
| FR : caractères français | **14** | 591–701 |

Seul l'export 05_27 est affecté. L'export 06_11 (Ollama) n'a pas ce problème car Ollama traite chaque langue séquentiellement par chunk.

### Correction appliquée (juin 2026)

**Statut :** ✅ Corrigé — `GoogleProvider` est désormais thread-safe.

**Solution retenue :** Un `threading.Lock` au niveau de l'instance `GoogleProvider` sérialise tous les appels à `translate()`. Le lock est tenu pendant toute la durée de l'appel à `deep_translator.GoogleTranslator(...).translate(text)`, ce qui élimine la fenêtre de course.

**Implémentation :**

```python
# translator/core/translator_factory.py
class GoogleProvider(TranslationProvider):
    def __init__(self):
        self._translator_cls = GoogleTranslator
        self._lock = threading.Lock()

    def translate(self, text: str, source: str, target: str) -> str:
        with self._lock:
            result = self._translator_cls(source=source, target=target).translate(text)
        if result is None or result == "":
            return text
        return result
```

**Conséquence :** Les appels parallèles via `ThreadPoolExecutor` dans `mode_translate_json.run()` sont effectivement sérialisés pour Google (un seul appel à la fois), mais c'est correct : chaque appel est atomique. Les providers batch (Ollama) ne sont pas affectés par ce lock et conservent leur parallélisme.

**Tests ajoutés** (`tests/test_translator_factory.py::TestGoogleProviderThreadSafety`) :
- `test_translate_uses_internal_lock` — Vérifie que `_lock` existe
- `test_translate_acquires_lock_during_call` — Vérifie que le lock est tenu pendant l'appel
- `test_lock_does_not_deadlock_under_load` — 20 threads x 10 appels sans deadlock
- `tests/test_mode_translate_json.py::TestModeTranslateJsonThreadSafety` — Test d'intégration end-to-end avec `ThreadPoolExecutor`

**Branch :** `fix/thread-safety-google-provider`

### Fichiers modifiés

- `translator/core/translator_factory.py` — Ajout `import threading`, `_lock` dans `GoogleProvider.__init__`, `with self._lock:` dans `translate()`
- `translator/tests/test_translator_factory.py` — Classe `TestGoogleProviderThreadSafety` (3 tests)
- `translator/tests/test_mode_translate_json.py` — Classe `TestModeTranslateJsonThreadSafety` (1 test)
- `translator/modes/mode_translate_json.py` — Log informatif lors de l'utilisation d'un provider non-batch

---

## Bug #2 — Clés non traduites par Ollama (export 06_11)

### Sévérité

🟡 **Moyenne** — Poche de clés en anglais dans des fichiers traduits

### Fichiers affectés

Tous les fichiers de l'export `2026_06_11_Export`

### Description

Ollama a renvoyé le texte source anglais sans le traduire pour certaines clés contenant du HTML (`<strong>`) ou des placeholders complexes (`{{selectedContext}}`). Ces clés n'étaient pas dans le cache de traduction, ce qui a forcé un appel Ollama qui a échoué silencieusement.

### Clés affectées

| Clé | Texte anglais non traduit | Langues affectées |
|-----|--------------------------|-------------------|
| `MS_SUCCESS_ERROR_7` | `Preferred Context {{selectedContext}} saved successfully.` | **Toutes** (FR, CZ, DE, IT, AR, SK) |
| `MS_SUCCESS_ERROR_247` | `The {{idType}} <strong> {{tresorId}} </strong> is already linked to the Location...` | FR |
| `MS_SUCCESS_ERROR_248` | `The {{idType}} <strong> {{tresorId}} </strong> is already linked to the Company...` | FR |
| `MS_SUCCESS_ERROR_249` | `The {{idType}} <strong> {{tresorId}} </strong> is already linked to the Organization...` | FR |
| `DA_TL_FL_1777` | `Data integrity alerts` | DE |
| `MS_SUCCESS_ERROR_149` | `Logging in failed` | DE |
| `NE_LO_LO_565` | `Logistic Usecase Transfer List` | SK |
| `PA_US_US_1343` | `Parameter - Access Point` | SK |
| `MS_SUCCESS_ERROR_73` | `Sector OrganizationUnit Created` | SK |

### Cause racine

1. **`MS_SUCCESS_ERROR_7`** — Le texte source a changé entre le source 05_27 et 06_11 :  
   `Preferred Context saved successfully.` → `Preferred Context {{selectedContext}} saved successfully.`  
   L'entrée de cache existait pour l'ancien texte (sans placeholder), mais pas pour le nouveau. Ollama a été appelé pour retraduire, et a renvoyé le texte anglais brut.

2. **`MS_SUCCESS_ERROR_247/248/249`** — Ces textes longs avec du HTML `<strong>` et des placeholders `{{idType}}` n'étaient pas dans le cache pour le français. Ollama n'a pas réussi à les traduire.

3. **`DA_TL_FL_1777`, `MS_SUCCESS_ERROR_149`** — Idem pour l'allemand : absents du cache, Ollama a échoué.

4. **Clés SK** — Textes courts techniques que ni le cache ni Ollama n'ont traduit.

### Mécanisme de l'échec

Dans `OllamaProvider.translate_batch()`, quand un chunk échoue la validation après `max_retries` tentatives :

```python
# translator/core/ollama_provider.py, ligne 208-209
if attempt == self._max_retries:
    results.update({k: v for k, v in chunk.items()})  # Fallback: texte original
```

Le fallback conserve le **texte source anglais** au lieu de signaler l'échec ou de réessayer avec un prompt différent.

### Correction appliquée (juin 2026)

**Statut :** 🟡 Partiellement corrigé — la détection et le fallback par clé sont implémentés et testés. La post-traduction des 9 clés reste à faire manuellement.

**Solution retenue :**

1. **Détection post-traduction** (`_check_untranslated_keys` dans `mode_translate_json.py`) ✅
   - Compare chaque valeur traduite à la valeur source
   - Flag les textes identiques au source de longueur ≥ 15 caractères
   - Logs WARNING avec le code langue et la liste des clés affectées
   - Appelée automatiquement en fin de `_translate_single_language`
   - **Test :** `TestCheckUntranslatedKeys` (10 tests)

2. **Fallback par clé** (`_fallback_per_key` dans `ollama_provider.py`) ✅
   - Quand Ollama échoue sur un chunk après tous les retries, chaque clé est retentée individuellement via Google Translate
   - Si Google échoue ou renvoie le même texte, l'original est conservé
   - Si l'import de GoogleProvider échoue, tous les originaux sont conservés
   - **Test :** `TestFallbackPerKey` (8 tests)

**Garanties :**
- Les traductions longues identiques au source sont flaggées en WARNING (FR, CZ, SK, DE, IT, AR)
- Quand Ollama échoue, Google est tenté clé par clé (limite le scope des fallbacks)
- Pas de régression : la signature publique de `translate_batch` est inchangée

**Tests ajoutés** :
- `tests/test_mode_translate_json.py::TestCheckUntranslatedKeys` — 10 tests
- `tests/test_ollama_provider.py::TestFallbackPerKey` — 8 tests

**Résultat couverture :** `core/ollama_provider.py` 83% → 87%, `modes/mode_translate_json.py` 75% → 76%.

**Reste à faire :**
- Post-traduire manuellement les 9 clés identifiées (cf. tableau des clés affectées) dans les exports finaux
- Envisager de réduire `min_length=15` à une valeur plus permissive (ex. 8) pour attraper les textes courts
- Renforcer le prompt Ollama pour les textes avec HTML/placeholders (peut réduire le taux d'échec à la source)

**Branch :** `test/post-translation-validation`

---

## Bug #3 — Incohérence de clé de cache `en:cs:` vs `en:cz:`

### Sévérité

🟡 **Moyenne** — Re-traductions inutiles du tchèque à chaque exécution Ollama

### Description

Le cache de traduction utilise le code API `cs` comme clé (via `LANGUAGES['cz']['target'] = 'cs'`), mais le fichier de sortie s'appelle `translation_en_cz.json`. Quand Ollama traduit en mode batch, le cache contient des entrées sous `en:cs:` mais la recherche se fait avec `en:cs:` (via `api_target_lang`), ce qui fonctionne. Cependant, le **stockage** Ollama utilise aussi `en:cs:`, donc il n'y a pas de mismatch fonctionnel.

Le problème se manifeste quand :
- Le cache a été peuplé par Google Translate (clé `en:cs:text`)
- Ollama re-traduit et stocke aussi sous `en:cs:text` (correct)
- Mais si une future exécution utilise accidentellement `cz` au lieu de `cs`, le cache ne matchera pas

### État actuel du cache

| Préfixe de clé | Nombre d'entrées |
|----------------|-----------------|
| `en:cs:` | 1 471 |
| `en:cz:` | **0** |
| `en:sk:` | 1 471 |
| `en:de:` | 1 471 |
| `en:fr:` | 1 471 |
| `en:it:` | 1 471 |
| `en:ar:` | 1 471 |

### Correction appliquée (juin 2026)

**Statut :** ✅ Corrigé — les clés de cache sont normalisées et le cache existant est migré automatiquement au chargement.

**Solution retenue :** Une table `_LANG_CODE_NORMALIZE` dans `core/cache.py` mappe les codes API (`cs`) vers les codes utilisateur (`cz`). La fonction `_normalize_lang_code()` est appelée par `_make_key()` à la **construction** de chaque clé, garantissant que les nouvelles entrées utilisent systématiquement le code utilisateur. Au chargement du cache, `migrate_keys()` renomme les anciennes clés `en:cs:` → `en:cz:` en place, de manière idempotente.

**Implémentation :**

```python
# translator/core/cache.py
_LANG_CODE_NORMALIZE = {
    "cs": "cz",  # Czech: API uses 'cs', project uses 'cz'
}

def _normalize_lang_code(lang: str) -> str:
    return _LANG_CODE_NORMALIZE.get(lang, lang)

class TranslationCache:
    @staticmethod
    def _make_key(source_lang, target_lang, text):
        src = _normalize_lang_code(source_lang)
        tgt = _normalize_lang_code(target_lang)
        return f"{src}:{tgt}:{text}"

    def _load(self):
        # ... charge self._entries depuis le fichier
        self.migrate_keys()  # renomme en:cs: → en:cz:

    def migrate_keys(self) -> int:
        migrated = 0
        with self._lock:
            keys_to_rename = []
            for key in list(self._entries.keys()):
                parts = key.split(":", 2)
                if len(parts) == 3:
                    src, tgt, text = parts
                    new_src = _normalize_lang_code(src)
                    new_tgt = _normalize_lang_code(tgt)
                    if new_src != src or new_tgt != tgt:
                        new_key = f"{new_src}:{new_tgt}:{text}"
                        if new_key not in self._entries:
                            keys_to_rename.append((key, new_key))
            for old_key, new_key in keys_to_rename:
                self._entries[new_key] = self._entries.pop(old_key)
                migrated += 1
            if migrated > 0:
                self._dirty = True
        return migrated
```

**Garanties :**
- `put('en', 'cs', text, value)` et `put('en', 'cz', text, value)` stockent dans la même clé `en:cz:text`
- `get('en', 'cs', text)` et `get('en', 'cz', text)` lisent la même entrée
- Migration automatique au chargement : les caches existants (1 471 entrées `en:cs:`) sont migrés à la volée
- Migration idempotente : recharger un cache déjà migré ne change rien
- Pas de perte de données : si les deux clés `en:cs:Hello` et `en:cz:Hello` existent, la migration est sautée pour préserver les deux valeurs

**Tests ajoutés** (`tests/test_cache.py`, 3 nouvelles classes, 16 tests) :
- `TestNormalizeLangCode` (5 tests) — comportement de `_normalize_lang_code()`
- `TestMakeKeyWithNormalization` (4 tests) — équivalence `cs`/`cz` dans `_make_key()`, `get`, `put`
- `TestMigrateKeys` (7 tests) — migration, dirty flag, idempotence, gestion des collisions, textes avec `:`

**Résultat couverture :** `core/cache.py` passe de 89% à **98%**.

**Branch :** `test/cache-key-normalization`

---

## Bug #4 — Langue incorrecte dans les exports historiques (04_21, 05_05, 05_13)

### Sévérité

🟠 **Historique** — Bugs déjà corrigés, mais traces encore présentes dans les exports

### Description

Les exports les plus anciens contiennent des fichiers avec une langue incorrecte. Ces bugs ont été corrigés progressivement.

### Chronologie des corrections

| Export | AR | FR | CZ | SK | DE |
|--------|-----|-----|-----|-----|-----|
| `2026_04_21` | 🔴 Français | ❌ Absent | ✅ Tchèque | 🔴 Tchèque dominant | 🔴 Slovaque mélangé |
| `2026_05_05` | 🔴 Tchèque | 🟡 Slovaque mélangé | ✅ Tchèque | 🔴 Tchèque dominant | 🔴 Peu d'allemand |
| `2026_05_13` | 🔴 Tchèque | 🟡 Slovaque mélangé | ✅ Tchèque | 🔴 Tchèque dominant | 🔴 Partiel (1 365 clés) |
| `2026_05_14` | ✅ Arabe | 🟡 Slovaque mélangé | ✅ Tchèque | 🔴 Tchèque dominant | 🔴 Slovaque mélangé |
| `2026_05_27` | ✅ Arabe | 🔴 **Tchèque** | 🟡 Slovaque mélangé | 🔴 ≈ CZ | ✅ Allemand |
| `2026_06_11` | ✅ Arabe | ✅ Français | ✅ Tchèque | ✅ Slovaque | ✅ Allemand |

### Notes sur la détection

La détection initiale de "caractères tchèques dans le slovaque" et "caractères slovaques dans l'allemand" était **faussée** car les caractères `ť`, `ď`, `š`, `č`, `ž`, `ň` sont communs aux deux langues tchèque et slovaque, et `ä`, `ö` sont des umlauts allemands (pas slovaques). Le recomptage avec les caractères exclusifs donne :

| Langue | Caractères exclusifs | SK(06_11) | DE(06_11) |
|--------|---------------------|-----------|-----------|
| Tchèque | `ě`, `ř`, `ů` | **0** ✅ | **0** ✅ |
| Slovaque | `ľ`, `ŕ` | 118 ✅ | **0** ✅ |
| Allemand | `ä`, `ö`, `ü`, `ß` | — | 679 ✅ |

**Conclusion :** Les fichiers SK et DE de l'export 06_11 sont dans la bonne langue. Seul le FR(05_27) était réellement dans une mauvaise langue (tchèque).

### Correction proposée

Les exports historiques sont à considérer comme **obsolètes**. Seul le dernier export (`2026_06_11`) fait référence. Les 9 clés non traduites du Bug #2 doivent être corrigées dans cet export.

---

## Annexe — Données de diagnostic

### A. Évolution du nombre de clés par export

| Export | AR | CZ | DE | FR | IT | SK |
|--------|-----|-----|-----|-----|-----|-----|
| 04_21 | 2 592 | 2 592 | 2 592 | — | 2 592 | 2 592 |
| 05_05 | 2 629 | 2 629 | 2 629 | 2 629 | 2 629 | 2 629 |
| 05_13 | 2 495 | 2 565 | 1 365 | 2 642 | 2 116 | 1 227 |
| 05_14 | 2 642 | 2 642 | 2 642 | 2 642 | 2 642 | 2 642 |
| 05_27 | 2 523 | 2 523 | 2 523 | 2 523 | 2 523 | 2 523 |
| 06_11 | 2 531 | 2 531 | 2 531 | 2 531 | 2 531 | 2 531 |

### B. Évolution du nombre de valeurs différentes entre exports consécutifs

| Transition | AR | CZ | DE | FR | IT | SK |
|-----------|-----|-----|-----|-----|-----|-----|
| 04_21 → 05_05 | 2 477 | 30 | 1 495 | — | 416 | 1 572 |
| 05_05 → 05_13 | 0 | 13 | 335 | 275 | 0 | 290 |
| 05_13 → 05_14 | 2 495 | 20 | 0 | 273 | 2 | 8 |
| 05_14 → 05_27 | 0 | 2 097 | 2 | 2 350 | 0 | 0 |
| 05_27 → 06_11 | 16 | 2 110 | 21 | 2 359 | 13 | 16 |

> **Note :** Les transitions avec un nombre massif de changements (05_14 → 05_27 pour CZ/FR, 05_27 → 06_11 pour CZ/FR) correspondent aux corrections de langue (tchèque → français, slovaque → tchèque).

### C. Placeholders modifiés dans l'export 06_11

Ollama a modifié des noms de placeholders `{{...}}` par rapport au cache. Ces changements sont probablement corrects (les placeholders doivent correspondre aux noms de variables du code applicatif), mais nécessitent une vérification avec le frontend.

| Clé | Ancien placeholder (cache) | Nouveau placeholder (06_11) | Langues |
|-----|---------------------------|----------------------------|---------|
| `MS_SUCCESS_ERROR_131` | `{{akcia}}` / `{{akce}}` | `{{action}}` | CZ, SK |
| `MS_SUCCESS_ERROR_132` | `{{zpráva}}` / `{{Nachricht}}` / `{{messaggio}}` / `{{رسالة}}` / `{{správa}}` | `{{message}}` | Toutes |
| `CO_AD_HE_1547` | `{{مكتمل}}` | `{{completed}}` | AR |
| `LANGUAGE_PREFERENCE_SUCCESS` | `{{langue}}` / `{{Sprache}}` / `{{lingual}}` | `{{language}}` | FR, DE, IT |
| `MS_SUCCESS_ERROR_156` | `{{selectedlangage}}` / `{{selectedLanguage}}` / `{{selectedlingual}}` | `{{selectedlanguage}}` | FR, CZ, DE, IT, AR, SK |
| `MS A03_US00_02` | `{{identifiant légal}}` / `{{legale Kennung}}` | `{{legal identifier}}` | FR, DE |
| `MS_SUCCESS_ERROR_134/135` | `{{orgUnitLabel}}` | `{{orgaUnitLabel}}` | AR |