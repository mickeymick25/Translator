# Brief — Traduction 2026_06_12 Import multi-langues

**Date :** 17/06/2026
**Contexte :** L'export `2026_06_12_Export` ne contient que le FR. Il faut générer les traductions des 5 autres langues (CZ, DE, IT, SK, AR) à partir de la même source.

---

## 1. Source

| Fichier | Chemin | Clés | Valeurs non-vides |
|---------|--------|------|-------------------|
| Source EN | `translator/source/2026_06_12_Import/en 7.json` | **2531** | 2471 |

**Note :** Le nom de fichier contient un espace (`en 7.json`) — il faut spécifier `SOURCE_FILE` explicitement, l'auto-détection ne fonctionne pas.

---

## 2. État actuel de l'export 2026_06_12

| Fichier | Statut | Clés | Notes |
|---------|--------|------|-------|
| `translation_en_fr.json` | ✅ Existe | 2531 | Déjà traduit (cf. `2026_06_12_Translation_FR_Changelog.md`) |
| `translation_en_cz.json` | ❌ **À générer** | 0 | — |
| `translation_en_de.json` | ❌ **À générer** | 0 | — |
| `translation_en_it.json` | ❌ **À générer** | 0 | — |
| `translation_en_sk.json` | ❌ **À générer** | 0 | — |
| `translation_en_ar.json` | ❌ **À générer** | 0 | — |

---

## 3. Référence : export précédent `2026_06_11_Export`

L'export `2026_06_11_Export` (généré le 11/06/2026) contient les **6 langues** avec 2531 clés chacune. C'est une **base de référence** mais attention :

⚠️ **La source a probablement changé** entre `en 6.json` (06_11) et `en 7.json` (06_12). Il faut **re-traduire depuis la nouvelle source** et **ne pas se fier aveuglément** au cache.

### Stratégie recommandée

1. **Activer le cache** (`TRANSLATION_CACHE=true`) — les clés inchangées seront récupérées instantanément
2. **Lancer Ollama** (provider par défaut pour ce projet) — chunking par 50, validation structurelle
3. **Fallback Google** automatique sur les chunks qui échouent
4. **Détection post-traduction** (`_check_untranslated_keys`) — alerte sur les valeurs == source

---

## 4. Plan d'exécution

### Étape 1 — Lancer la traduction multi-langues

```bash
cd translator

# Variables d'environnement à passer
MODE=translate-json
SOURCE_LANG=en
BATCH_LANGS=cz,de,it,sk,ar
SOURCE_FILE=/app/source/2026_06_12_Import/en 7.json
OUTPUT_DIR=/app/output
TRANSLATION_PROVIDER=ollama
TRANSLATION_CACHE=true
OLLAMA_MODEL=minimax-m3:cloud

docker compose -f docker-compose.yml run --rm \
  -e MODE=translate-json \
  -e SOURCE_LANG=en \
  -e BATCH_LANGS=cz,de,it,sk,ar \
  -e "SOURCE_FILE=/app/source/2026_06_12_Import/en 7.json" \
  -e OUTPUT_DIR=/app/output \
  -e TRANSLATION_PROVIDER=ollama \
  -e TRANSLATION_CACHE=true \
  -e OLLAMA_MODEL=minimax-m3:cloud \
  translator
```

**Important :** ne pas spécifier `BATCH_LANGS=fr` car le FR est déjà fait (le mode `translate-json` l'écraserait).

### Étape 2 — Surveiller les warnings

Chercher dans les logs :
- `Untranslated key` : valeur identique au source pour textes longs
- `Ollama chunk N/M failed after K attempts` : chunks échoués (fallback Google tenté)
- `Cache HIT` / `Cache MISS` : statistiques du cache

### Étape 3 — Vérification post-traduction

Pour chaque langue générée, vérifier :
- Le nombre de clés = 2531
- Aucun WARNING `Untranslated key` non traité
- Pas de `chunk failed` non récupéré par le fallback

### Étape 4 — Backup de sécurité

Avant d'écraser quoi que ce soit, copier le `translation_en_fr.json` actuel :

```bash
cp translator/output/2026_06_12_Export/translation_en_fr.json \
   translator/output/2026_06_12_Export/translation_en_fr.json.safe
```

(Le fichier `.bak` existe déjà, mais un backup supplémentaire ne fait pas de mal.)

---

## 5. Bugs déjà corrigés (à connaître)

Le service a été amélioré récemment (cf. `doc/2026_06_17_Progress_Report.md`) :

| Bug | Fix | Impact |
|-----|-----|--------|
| #1 — Race condition GoogleProvider | `threading.Lock` dans `GoogleProvider` | Pas de pollution des langues en parallèle |
| #2 — Clés non traduites | `_check_untranslated_keys` + `_fallback_per_key` | Détection + fallback automatique |
| #3 — Cache `en:cs:` vs `en:cz:` | `_LANG_CODE_NORMALIZE` | Cohérence cache ↔ fichiers |

**761 tests passent, couverture 92%.** Le service est dans un état robuste.

---

## 6. Points d'attention

### Cache préchargé

Le cache `translator/output/.translation_cache.json` contient **1471 entrées par langue** (selon le rapport de bugs). Comme la source a changé, une partie sera obsolète, mais une grosse partie sera réutilisable. **Le cache est désactivé par défaut** dans le docker-compose, il faut l'activer explicitement.

### Ollama est-il lancé ?

Vérifier qu'Ollama tourne sur le host avant de lancer la traduction :

```bash
curl http://localhost:11434/api/tags
# Doit retourner la liste des modèles, dont minimax-m3:cloud
```

Le `docker-compose.yml` inclut `extra_hosts: host.docker.internal:host-gateway` pour que le conteneur accède à Ollama sur le host.

### Modèle Ollama

`minimax-m3:cloud` est le modèle recommandé depuis 17/06/2026 :
- Plus rapide que `minimax-m2.7:cloud` (21.8s vs 22.5s FR, 12.3s vs 26.4s CZ)
- 100% de complétude, 100% des placeholders préservés

### Réseau mobile

Le rapport de bugs note que le provider Google utilise `googletrans` qui scrape Google Translate, ce qui sature le réseau mobile. **Préférer Ollama** (local/cloud) pour éviter ce problème.

---

## 7. Commandes utiles

### Vérifier l'état du cache

```bash
docker compose -f translator/docker-compose.yml run --rm \
  -e OUTPUT_DIR=/app/output \
  translator python -c "
import json
with open('output/.translation_cache.json') as f:
    data = json.load(f)
entries = data.get('entries', {})
from collections import Counter
prefixes = Counter(k.split(':')[1] for k in entries if ':' in k)
print('Cache entries by target lang:')
for lang, count in sorted(prefixes.items()):
    print(f'  {lang}: {count}')
print(f'Total: {len(entries)}')
"
```

### Vérifier les traductions générées

```bash
for lang in cz de it sk ar; do
  python3 -c "
import json
d = json.load(open('translator/output/2026_06_12_Export/translation_en_$lang.json'))
print(f'$lang: {len(d)} keys')
"
done
```

### Détecter les non-traduits (post-run)

```bash
python3 -c "
import json
with open('translator/source/2026_06_12_Import/en 7.json') as f:
    source = json.load(f)
for lang in ['cz', 'de', 'it', 'sk', 'ar']:
    path = f'translator/output/2026_06_12_Export/translation_en_{lang}.json'
    try:
        with open(path) as f:
            translated = json.load(f)
    except FileNotFoundError:
        print(f'{lang}: FILE NOT FOUND')
        continue
    untranslated = [
        k for k, v in source.items()
        if v and len(v.strip()) >= 15
        and translated.get(k) == v
    ]
    print(f'{lang}: {len(translated)} keys, {len(untranslated)} untranslated')
    for k in untranslated[:5]:
        print(f'  {k}: {source[k][:60]!r}')
"
```

---

## 8. Estimation de durée

| Étape | Durée estimée |
|-------|---------------|
| Lancement Ollama (démarrage + warmup) | ~30s |
| Traduction CZ (2531 clés) | ~15-20 min (avec cache HIT) |
| Traduction DE | ~15-20 min |
| Traduction IT | ~15-20 min |
| Traduction SK | ~15-20 min |
| Traduction AR | ~15-20 min (peut être plus long) |
| **Total** | **~1h30 - 2h** (en séquentiel, en parallèle avec `BATCH_LANGS` c'est plus rapide) |

Avec le mode `BATCH_LANGS` parallèle (4 workers max), on peut espérer **~30-45 min** pour les 5 langues.

---

## 9. Fichiers de référence

| Fichier | Contenu |
|---------|---------|
| `doc/2026_06_12_Translation_FR_Changelog.md` | Comment le FR a été traité (référence) |
| `doc/2026_06_12_Translation_Bugs_Report.md` | Bugs identifiés (tous corrigés) |
| `doc/2026_06_17_Progress_Report.md` | Résumé des corrections récentes |
| `doc/2026_05_13_Ollama_Provider_Study.md` | Pourquoi et comment Ollama |
| `translator/source/2026_06_12_Import/Export_COP_Excel.csv` | Référence FR validée par le métier |

---

## 10. Résumé exécutif

**Objectif :** Générer les 5 traductions manquantes (CZ, DE, IT, SK, AR) pour l'export 2026_06_12, à partir de la source `en 7.json` (2531 clés).

**Approche :** Ollama avec cache activé + fallback Google sur les chunks échoués + détection post-traduction.

**Risque :** Faible — la mécanique est testée (761 tests, 92% couverture), le Bug #1 (race condition) est corrigé, le cache est cohérent (Bug #3 corrigé).

**Livrables :**
- 5 fichiers `translation_en_{cz,de,it,sk,ar}.json` dans `translator/output/2026_06_12_Export/`
- Backup du FR existant
- Logs de l'exécution pour traçabilité

**Pré-requis :** Ollama lancé sur le host, accès au cache existant (optionnel mais recommandé).
