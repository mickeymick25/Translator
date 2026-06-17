# Brief — Génération des traductions manquantes (2026_06_12_Export)

**Date :** 17/06/2026
**Contexte :** L'export `2026_06_12_Export` ne contient que le FR. Il faut générer les 5 autres langues (CZ, DE, IT, SK, AR) à partir de la même source.

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

⚠️ **Ne pas toucher au FR existant** : ne pas inclure `fr` dans `BATCH_LANGS`.

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

## 4. Nouveau modèle par défaut : `minimax-m3:cloud`

Depuis le 17/06/2026, le modèle Ollama par défaut a changé :
- **Ancien** : `minimax-m2.7:cloud`
- **Nouveau** : **`minimax-m3:cloud`** ⭐

**Résultats du benchmark** (30 entrées FR + CZ) :

| Modèle | FR | CZ | Succès |
|--------|----|----|--------|
| `minimax-m3:cloud` | 21.8s | **12.3s** | 2/2 |
| `minimax-m2.7:cloud` | 17-22s | 20-44s | 4/5 |
| `glm-5.1:cloud` | 70-105s | 60-87s | 4/4 |
| `glm-5.2:cloud` | 8-73s | 7-74s | 2/6 |

**`minimax-m3:cloud`** est 2x plus rapide que `minimax-m2.7` sur le tchèque (12.3s vs 20-44s), 100% de complétude, 100% des placeholders préservés.

⚠️ **Pour forcer un modèle spécifique** (par exemple si le nouveau défaut pose problème), utiliser `--ollama-model <model>` ou `OLLAMA_MODEL=<model>`.

---

## 5. Plan d'exécution

### Étape 0 — Backup de sécurité

```bash
cp translator/output/2026_06_12_Export/translation_en_fr.json \
   translator/output/2026_06_12_Export/translation_en_fr.json.safe
```

(Le fichier `.bak` existe déjà, mais un backup supplémentaire ne fait pas de mal.)

### Étape 1 — Vérifier qu'Ollama tourne

```bash
curl http://localhost:11434/api/tags
# Doit retourner la liste des modèles, dont minimax-m3:cloud
```

Si Ollama n'est pas lancé : `ollama serve` dans un terminal séparé.

### Étape 2 — Lancer la traduction multi-langues

```bash
cd translator

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

**Note :** on ne met **PAS** `fr` dans `BATCH_LANGS` (déjà fait). Si on veut l'inclure, le mode `translate-json` écraserait le FR existant.

**Si on veut utiliser l'ancien modèle** (par précaution, vu que c'est le 1er run avec `minimax-m3`) :

```bash
docker compose -f docker-compose.yml run --rm \
  -e MODE=translate-json \
  -e SOURCE_LANG=en \
  -e BATCH_LANGS=cz,de,it,sk,ar \
  -e "SOURCE_FILE=/app/source/2026_06_12_Import/en 7.json" \
  -e OUTPUT_DIR=/app/output \
  -e TRANSLATION_PROVIDER=ollama \
  -e TRANSLATION_CACHE=true \
  -e OLLAMA_MODEL=minimax-m2.7:cloud \
  translator
```

### Étape 3 — Surveiller les logs

Pendant l'exécution, chercher dans les logs :
- `Untranslated key` : valeur identique au source pour textes longs
- `Ollama chunk N/M failed after K attempts` : chunks échoués (fallback Google tenté)
- `Cache HIT` / `Cache MISS` : statistiques du cache
- `Falling back to Google Translate for N items` : fallback Google activé

### Étape 4 — Vérification post-traduction

Pour chaque langue générée, vérifier :
- Le nombre de clés = 2531
- Aucun WARNING `Untranslated key` non traité
- Pas de `chunk failed` non récupéré par le fallback

Commande de vérification :

```bash
docker compose -f translator/docker-compose.yml run --rm \
  --entrypoint python3 \
  -v /Users/michaelboitin/Documents/02_Dev/COP_translations/translator/source:/app/source \
  -v /Users/michaelboitin/Documents/02_Dev/COP_translations/translator/output:/app/output \
  translator python3 -c "
import json
import os
out_dir = '/app/output/2026_06_12_Export'
with open('/app/source/2026_06_12_Import/en 7.json') as f:
    source = json.load(f)
for lang in ['cz', 'de', 'it', 'sk', 'ar']:
    path = os.path.join(out_dir, f'translation_en_{lang}.json')
    if not os.path.exists(path):
        print(f'{lang}: MISSING')
        continue
    with open(path) as f:
        translated = json.load(f)
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

## 6. Bugs déjà corrigés (à connaître)

Le service a été amélioré récemment (cf. `doc/2026_06_17_Progress_Report.md`) :

| Bug | Fix | Impact |
|-----|-----|--------|
| #1 — Race condition GoogleProvider | `threading.Lock` dans `GoogleProvider` | Pas de pollution des langues en parallèle |
| #2 — Clés non traduites | `_check_untranslated_keys` + `_fallback_per_key` | Détection + fallback automatique |
| #3 — Cache `en:cs:` vs `en:cz:` | `_LANG_CODE_NORMALIZE` | Cohérence cache ↔ fichiers |

**761 tests passent, couverture 92%.** Le service est dans un état robuste.

---

## 7. Points d'attention

### Cache préchargé

Le cache `translator/output/.translation_cache.json` contient **1471 entrées par langue** (selon le rapport de bugs). Comme la source a changé, une partie sera obsolète, mais une grosse partie sera réutilisable. **Le cache est désactivé par défaut** dans le docker-compose, il faut l'activer explicitement.

### Nouveau modèle = nouveau comportement

`minimax-m3:cloud` est utilisé pour la 1re fois en production (avant aujourd'hui, c'était `minimax-m2.7:cloud`). Si tu observes des comportements étranges :
- Erreurs 503 sporadiques : Ollama cloud est parfois surchargé, le fallback Google prend le relais
- Traductions bizarres : réduire `OLLAMA_CHUNK_SIZE` à 25 pour des chunks plus petits
- Timeout : augmenter `OLLAMA_TIMEOUT` à 600

En cas de doute, on peut **revenir temporairement à `minimax-m2.7:cloud`** avec `-e OLLAMA_MODEL=minimax-m2.7:cloud` (voir étape 2).

### Ollama est-il lancé ?

Vérifier qu'Ollama tourne sur le host avant de lancer la traduction :

```bash
curl http://localhost:11434/api/tags
# Doit retourner la liste des modèles, dont minimax-m3:cloud
```

Le `docker-compose.yml` inclut `extra_hosts: host.docker.internal:host-gateway` pour que le conteneur accède à Ollama sur le host.

### Réseau mobile

Le rapport de bugs note que le provider Google utilise `googletrans` qui scrape Google Translate, ce qui sature le réseau mobile. **Préférer Ollama** (local/cloud) pour éviter ce problème.

---

## 8. Commandes utiles

### Vérifier l'état du cache

```bash
docker compose -f translator/docker-compose.yml run --rm \
  --entrypoint python3 \
  -v /Users/michaelboitin/Documents/02_Dev/COP_translations/translator/output:/app/output \
  translator python3 -c "
import json
from collections import Counter
with open('/app/output/.translation_cache.json') as f:
    data = json.load(f)
entries = data.get('entries', {})
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
  echo -n "$lang: "
  ls -la "translator/output/2026_06_12_Export/translation_en_$lang.json" 2>/dev/null || echo "MISSING"
done
```

### Détecter les non-traduits (post-run)

Voir commande dans l'étape 4 ci-dessus.

---

## 9. Estimation de durée

Avec `minimax-m3:cloud` (le nouveau défaut) :

| Étape | Durée estimée |
|-------|---------------|
| Lancement Ollama (démarrage + warmup) | ~30s |
| Traduction CZ (2531 clés) | ~20-30 min (avec cache HIT) |
| Traduction DE | ~20-30 min |
| Traduction IT | ~20-30 min |
| Traduction SK | ~20-30 min |
| Traduction AR | ~25-35 min (peut être plus long) |
| **Total** | **~1h30 - 2h30** (séquentiel) |

Avec le mode `BATCH_LANGS` parallèle (4 workers max) :
- **~45 min - 1h15** pour les 5 langues

---

## 10. Fichiers de référence

| Fichier | Contenu |
|---------|---------|
| `doc/2026_06_12_Translation_FR_Changelog.md` | Comment le FR a été traité (référence) |
| `doc/2026_06_12_Translation_Bugs_Report.md` | Bugs identifiés (tous corrigés) |
| `doc/2026_06_17_Progress_Report.md` | Résumé des corrections récentes |
| `doc/2026_05_13_Ollama_Provider_Study.md` | Pourquoi et comment Ollama |
| `translator/source/2026_06_12_Import/Export_COP_Excel.csv` | Référence FR validée par le métier |
| `translator/benchmark_glm_5.2.py` | Script de benchmark (utilisé pour valider m3) |

---

## 11. Résumé exécutif

**Objectif :** Générer les 5 traductions manquantes (CZ, DE, IT, SK, AR) pour l'export 2026_06_12, à partir de la source `en 7.json` (2531 clés).

**Approche :** Ollama `minimax-m3:cloud` (nouveau défaut, plus rapide) + cache activé + fallback Google sur les chunks échoués + détection post-traduction.

**Risque :** Faible — la mécanique est testée (761 tests, 92% couverture), les 3 bugs sont corrigés. Le seul point d'attention est le nouveau modèle (1er usage en prod), avec fallback possible vers `minimax-m2.7:cloud` si besoin.

**Livrables :**
- 5 fichiers `translation_en_{cz,de,it,sk,ar}.json` dans `translator/output/2026_06_12_Export/`
- Backup du FR existant
- Logs de l'exécution pour traçabilité

**Pré-requis :** Ollama lancé sur le host (`ollama serve`), accès au cache existant (optionnel mais recommandé).
