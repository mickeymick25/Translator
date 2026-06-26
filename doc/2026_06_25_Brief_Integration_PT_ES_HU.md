# Brief — Intégration de 3 nouvelles langues (PT, ES, HU)

- **Date** : 2026-06-25
- **Demande** : intégrer 3 nouveaux pays cibles — Portugal, Espagne, Hongrie.
- **Source courante** : `translator/source/2026_06_25_Import/en 9.json` (2542 clés, corrigée : `Pairing Error`, `In progress`).
- **Dernier export** : `translator/output/2026_06_25_Export/` (6 langues existantes : ar, cz, de, fr, it, sk — 2542 clés chacune).

## Objectif

Étendre le périmètre de traduction de 6 à **9 langues cibles** en ajoutant :

| Pays | Code projet | Code API (Google/Ollama) | Nom (FR) |
|---|---|---|---|
| Portugal | `pt` | `pt` | Portugais |
| Espagne | `es` | `es` | Espagnol |
| Hongrie | `hu` | `hu` | Hongrois |

Produire les fichiers `translation_en_pt.json`, `translation_en_es.json`, `translation_en_hu.json` (2542 clés chacun) dans `output/2026_06_25_Export/`, sans modifier les 6 fichiers existants.

## Périmètre code

| Fichier | Changement |
|---|---|
| `translator/core/config.py` | Ajout de `pt`/`es`/`hu` dans `LANGUAGES` (target, code, source_col=`origin`) + dans le default `BATCH_LANGS`. |
| `translator/core/ollama_provider.py` | Ajout dans `LANG_NAMES` (Portuguese/Spanish/Hungarian) pour le prompt Ollama. |
| `translator/docker-compose.yml` | `BATCH_LANGS` default étendu. |
| `translator/validate_translations.py` | `DEFAULT_LANGUAGES` étendu. |
| `translator/tests/test_config.py` | Tests des codes API `pt`/`es`/`hu`. |

## Choix d'exécution

- **Provider** : **Ollama** avec `minimax-m3:cloud` (cloud via Ollama).
  - Raison : run complet 2542×3 → Ollama en chunking 50 entrées = ~153 requêtes LLM vs ~5000 appels Google ; validation structurelle 5 contrôles ; retry intelligent ; fallback Google per-key ; pas de risque de plafond Google 429 sur un run long. Chemin batch recommandé par le projet (IMP3).
- **Exécution** : **séquentielle** (une langue à la fois), pas de parallélisme.
- **Service** : via **Docker** (`docker compose`), cohérent avec l'architecture du projet et les hooks pre-commit.
- **Conservation** : les 6 fichiers de langues existants **ne doivent pas être modifiés** (on ne lance que `pt`, puis `es`, puis `hu`).

## Commandes prévues (séquentiel, via Docker)

```bash
cd translator

# 1) Portugais
BATCH_LANGS=pt TRANSLATION_PROVIDER=ollama OLLAMA_MODEL=minimax-m3:cloud \
  docker compose -f docker-compose.yml up --build

# 2) Espagnol
BATCH_LANGS=es TRANSLATION_PROVIDER=ollama OLLAMA_MODEL=minimax-m3:cloud \
  docker compose -f docker-compose.yml up --build

# 3) Hongrois
BATCH_LANGS=hu TRANSLATION_PROVIDER=ollama OLLAMA_MODEL=minimax-m3:cloud \
  docker compose -f docker-compose.yml up --build
```

Paramètres clé :
- `BATCH_LANGS=<une langue>` → ne traite qu'une langue à la fois (les 6 autres non touchées).
- `TRANSLATION_PROVIDER=ollama` + `OLLAMA_MODEL=minimax-m3:cloud`.
- `OLLAMA_URL` par défaut du compose : `http://host.docker.internal:11434` (conteneur → Ollama sur le host).
- Source auto-détectée : `2026_06_25_Import/en 9.json` (fallback relaxé, pas de `-i`).
- Sortie : `translator/output/2026_06_25_Export/` (dossier déjà pré-peuplé avec les 6 langues existantes).

## Mécanisme

- Pour `pt`/`es`/`hu` : fichier de sortie **absent** → **traduction complète** des 2542 clés (chunking 50 entrées, validation structurelle, retry).
- Pour les 6 langues existantes : **non concernées** par le `BATCH_LANGS` → aucun chargement/écriture.
- Cache : enrichi des entrées `en:pt:*`, `en:es:*`, `en:hu:*` (clés composite `src:tgt:key_id:text`). Les entrées des autres langues (dont `en:fr:Monitoring`) **non touchées**.
- Fallback : si un chunk Ollama échoue après `max_retries`, `_fallback_per_key` traduit chaque clé via Google.

## Prérequis à vérifier avant lancement

- Daemon Docker actif.
- `ollama serve` lancé sur le host.
- Modèle `minimax-m3:cloud` accessible (`ollama list`).

## Validation attendue

- 3 nouveaux fichiers × 2542 clés.
- `validate_translations.py --languages ar,cz,de,fr,it,sk,pt,es,hu` : 0 missing / 0 extra / 0 placeholder issue pour pt/es/hu.
- Aucune modification des 6 fichiers existants (vérification : hash ou key-count + spot-check des valeurs conservées FR « Monitoring », Option A).

## Documentation associée à mettre à jour

- `README.md` (FR) + `README.en.md` (EN) : table « Langues supportées », `BATCH_LANGS`, historique des versions (v3.2.0).
- Ce brief archivé dans `doc/`.

## Risques / points d'attention

- **Durée** : ~25–35 min par langue (chunking séquentiel), soit ~75–105 min au total en séquentiel. Accepté par choix (séquentiel + Ollama).
- **Qualité Ollama** : surveiller les fallbacks Google dans les logs (`_fallback_per_key`) — un nombre élevé indiquerait des chunks en échec.
- **Disponibilité modèle cloud** : `minimax-m3:cloud` dépend du service cloud Ollama ; si indisponible, basculer sur Google ou un modèle local (`qwen3` ≥8 GB RAM).
- **Non-modification des fichiers existants** : garantie par `BATCH_LANGS` restreint à une langue + reprise (les fichiers existants ne sont ni chargés ni écrits quand la langue n'est pas dans la liste).