# Analyse de fusion des scripts Python — Service de traduction générique

**Date :** 2026-04-20
**Auteur :** Analyse technique
**Objectif :** Évaluer la faisabilité et les modalités de fusion des scripts Python existants en un service de traduction générique capable de gérer à la fois les fichiers JSON et les dropdowns XLSX.

---

## 1. État des lieux — Inventaire des scripts existants

Le projet contient actuellement **4 scripts Python** répartis dans deux emplacements distincts :

| Script | Emplacement | Rôle |
|--------|-------------|------|
| `translate.py` (v1 — legacy) | `cz/translator/` | Traduction JSON EN → CS, chemins et langues **codés en dur** |
| `translate.py` (v2 — générique) | `translator/` | Traduction JSON avec **variables d'environnement** (`SOURCE_LANG`, `TARGET_LANG`) |
| `generate_dropdowns.py` | `translator/` | Génération des traductions de dropdowns depuis XLSX ou JSON → XLSX ou JSON multilingue |
| `analyze_xlsx.py` | `translator/` | Analyse de la structure du fichier Excel source (outil utilitaire) |

### 1.1 Infrastructure Docker associée

| Dockerfile | docker-compose | Script ciblé |
|-----------|----------------|--------------|
| `cz/translator/Dockerfile` | `cz/translator/docker-compose.yml` | `cz/translator/translate.py` |
| `translator/Dockerfile` | `translator/docker-compose.yml` | `translator/translate.py` |
| `translator/Dockerfile.analyze` | `translator/docker-compose.analyze.yml` | `translator/analyze_xlsx.py` |
| `translator/Dockerfile.generate` | `translator/docker-compose.generate.yml` | `translator/generate_dropdowns.py` |

Au total : **4 Dockerfiles**, **4 docker-compose**, **3 fichiers requirements** distincts (`requirements.txt`, `requirements.analyze.txt`, `requirements.generate.txt`).

---

## 2. Analyse comparative des scripts

### 2.1 `cz/translator/translate.py` (v1 — legacy)

**Caractéristiques :**
- Chemins hardcodés : `output_file = "/app/output/translation_cs_cz.json"`, `source_file = "/app/source/translation_en_en.json"`
- Langue cible hardcodée : `GoogleTranslator(source='en', target='cs')`
- Aucune variable d'environnement
- Code fonctionnellement identique à la v2, mais sans flexibilité

**Verdict :** Version obsolète, totalement redondante avec `translator/translate.py` v2. **À supprimer.**

---

### 2.2 `translator/translate.py` (v2 — générique JSON)

**Caractéristiques :**
- Langues configurables via variables d'environnement : `TARGET_LANG`, `SOURCE_LANG`
- Chemins dynamiques construits depuis les variables d'env
- Gestion des signaux Unix (SIGINT/SIGTERM) pour sauvegarde progressive
- Sauvegarde intermédiaire tous les 100 et 500 entrées
- Rate limiting : `time.sleep(0.1)` entre chaque entrée
- **Format supporté :** JSON à plat `{ "CLE": "valeur" }`

**Limitations identifiées :**
- Ne gère que la structure JSON plate (pas de JSON structuré par contexte)
- Pas de gestion de reprise sur fichier de sortie existant (pas de skip des clés déjà traduites)
- Une seule langue par exécution

---

### 2.3 `translator/generate_dropdowns.py` (dropdowns multilingues)

**Caractéristiques :**
- Détection automatique du format d'entrée (XLSX ou JSON)
- Génération multilingue en une seule exécution (7 langues : EN, FR, CZ, SK, DE, IT, AR)
- Deux formats de sortie : XLSX multi-feuilles **ou** JSON structuré par contexte `{ metadata, contexts }`
- Rate limiting : `time.sleep(0.15)` entre chaque traduction
- Mise à jour automatique du document de documentation `2026_04_17_Dropdown_Xlsx_Analysis.md`
- Configuration des langues centralisée dans le dictionnaire `LANGUAGES`

**Limitations identifiées :**
- Chemins source/output codés en dur dans les constantes (pas de variables d'environnement)
- Logs de debug (`print(f"DEBUG: ...")`) non nettoyés laissés en production
- La mise à jour de la documentation présente des problèmes de format (tableau Markdown corrompu observé)
- Pas de gestion de reprise : si le script s'interrompt, toute la génération recommence

---

### 2.4 `translator/analyze_xlsx.py` (outil utilitaire)

**Caractéristiques :**
- Outil d'inspection uniquement, sans logique de traduction
- Export JSON de l'analyse vers `Doc/xlsx_analysis.json`
- Autonome et bien encapsulé

**Verdict :** Script utilitaire indépendant. Peut être intégré comme **sous-commande** du service générique.

---

## 3. Identification des fonctionnalités communes

En croisant les quatre scripts, les blocs de code **communs ou similaires** sont :

| Fonctionnalité | `translate.py` v1 | `translate.py` v2 | `generate_dropdowns.py` | `analyze_xlsx.py` |
|----------------|:-----------------:|:-----------------:|:-----------------------:|:-----------------:|
| Chargement JSON | ✅ | ✅ | ✅ | ❌ |
| Sauvegarde JSON | ✅ | ✅ | ✅ | ❌ |
| Appel GoogleTranslator | ✅ | ✅ | ✅ | ❌ |
| Retry logic (3 essais) | ✅ | ✅ | ❌ (1 essai) | ❌ |
| Rate limiting | ✅ | ✅ | ✅ | ❌ |
| Gestion signaux SIGINT | ✅ | ✅ | ❌ | ❌ |
| Sauvegarde progressive | ✅ | ✅ | ❌ | ❌ |
| Chargement XLSX | ❌ | ❌ | ✅ | ✅ |
| Multi-langues en batch | ❌ | ❌ | ✅ | ❌ |
| Config via env vars | ❌ | ✅ | ❌ | ❌ |

**Observation clé :** La logique de traduction (appel API, retry, rate limiting) est **dupliquée** entre `translate.py` v2 et `generate_dropdowns.py`, mais avec des niveaux de robustesse différents.

---

## 4. Analyse des dépendances

### 4.1 Dépendances Python actuelles

| Package | `translate.py` | `generate_dropdowns.py` | `analyze_xlsx.py` |
|---------|:--------------:|:-----------------------:|:-----------------:|
| `deep-translator` | ✅ | ✅ | ❌ |
| `openpyxl` | ❌ | ✅ | ✅ |

Un service générique fusionné nécessiterait un **requirements.txt unique** :
```
deep-translator
openpyxl
```

### 4.2 Modules Python standard utilisés

- `json`, `time`, `signal`, `sys`, `os` — communs
- `pathlib.Path` — uniquement dans `generate_dropdowns.py` et `analyze_xlsx.py`
- `collections.defaultdict`, `datetime`, `re` — uniquement dans `generate_dropdowns.py`

---

## 5. Architecture proposée pour le service générique

### 5.1 Principe de conception

Le service générique doit être piloté par **variables d'environnement** et/ou **arguments CLI**, et exposer trois **modes d'opération** :

| Mode | Variable d'env / Argument | Description |
|------|--------------------------|-------------|
| `translate-json` | `MODE=translate-json` | Traduction d'un fichier JSON plat (actuel `translate.py` v2) |
| `translate-dropdowns` | `MODE=translate-dropdowns` | Génération multi-langues depuis XLSX/JSON dropdowns |
| `analyze` | `MODE=analyze` | Analyse et rapport de structure d'un fichier XLSX |

### 5.2 Structure de fichiers cible proposée

```
translator/
├── service.py                   ← Point d'entrée unique (remplace les 3 scripts)
├── core/
│   ├── __init__.py
│   ├── translator.py            ← Logique de traduction (GoogleTranslator + retry + rate limiting)
│   ├── io_json.py               ← Lecture/écriture JSON (plat et structuré par contexte)
│   ├── io_xlsx.py               ← Lecture/écriture XLSX (fusionne analyze + generate)
│   └── config.py                ← Configuration centralisée (langues, chemins, env vars)
├── modes/
│   ├── __init__.py
│   ├── mode_translate_json.py   ← Logique du translate.py v2
│   ├── mode_translate_dropdowns.py ← Logique du generate_dropdowns.py
│   └── mode_analyze.py          ← Logique du analyze_xlsx.py
├── Dockerfile                   ← Dockerfile unique
├── docker-compose.yml           ← docker-compose unique avec variable MODE
└── requirements.txt             ← requirements unifié
```

### 5.3 Variables d'environnement du service générique

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `MODE` | `translate-json` | Mode d'opération |
| `SOURCE_LANG` | `en` | Langue source (pour mode `translate-json`) |
| `TARGET_LANG` | `cs` | Langue cible (pour mode `translate-json`) |
| `SOURCE_FILE` | *(selon le mode)* | Fichier source à traiter |
| `OUTPUT_DIR` | `/app/output` | Répertoire de sortie |
| `EXCEL_DIR` | `/app/excel` | Répertoire des fichiers Excel |
| `DOC_DIR` | `/app/doc` | Répertoire de documentation |
| `BATCH_LANGS` | `en,fr,cz,sk,de,it,ar` | Langues pour le mode `translate-dropdowns` |
| `OUTPUT_FORMAT` | `auto` | Format de sortie : `json`, `xlsx`, `auto` |

### 5.4 Schéma d'architecture du service

```
service.py
    │
    ├── Lecture de MODE (env var)
    │
    ├── MODE=translate-json
    │       └── core/translator.py
    │           └── core/io_json.py (JSON plat)
    │
    ├── MODE=translate-dropdowns
    │       ├── core/io_xlsx.py  OU  core/io_json.py (selon SOURCE_FILE)
    │       ├── core/translator.py
    │       └── core/io_json.py  OU  core/io_xlsx.py (selon OUTPUT_FORMAT)
    │
    └── MODE=analyze
            └── core/io_xlsx.py
```

---

## 6. Points de vigilance pour la fusion

### 6.1 Divergences à harmoniser

| Problème | Localisation | Solution proposée |
|----------|-------------|-------------------|
| Retry logic absente dans `generate_dropdowns.py` | `translate_entry()` | Extraire la fonction `translate_text()` de `translate.py` v2 comme référence unique dans `core/translator.py` |
| Gestion de signaux absente dans `generate_dropdowns.py` | — | Centraliser le handler dans `service.py` |
| Sauvegarde progressive absente dans `generate_dropdowns.py` | — | Implémenter un callback de checkpoint dans `core/translator.py` |
| Logs DEBUG non nettoyés | `generate_dropdowns.py` | Remplacer tous les `print(f"DEBUG:...")` par le module `logging` Python |
| Mise à jour doc Markdown fragile | `update_documentation()` dans `generate_dropdowns.py` | Réécrire avec un parser Markdown plus robuste ou générer la section entière |
| Chemins hardcodés | `generate_dropdowns.py` | Tout migrer vers les variables d'environnement listées en §5.3 |

### 6.2 Comportements à préserver

- ✅ La sauvegarde intermédiaire tous les 100 entrées (mode `translate-json`)
- ✅ L'arrêt propre sur SIGINT/SIGTERM avec sauvegarde de l'état
- ✅ La préservation des traductions FR existantes du fichier XLSX (ne pas re-traduire)
- ✅ La structure JSON `{ metadata, contexts }` des fichiers dropdown
- ✅ Le rate limiting entre les appels API

### 6.3 Régression à éviter

Le mode `translate-json` du service générique doit produire des fichiers de sortie **identiques** aux fichiers actuellement générés dans `cz/`, `fr/`, `en/` pour ne pas casser les intégrations existantes.

---

## 7. Plan de migration

### Phase 1 — Préparation (sans disruption)
- [ ] Créer la structure `core/` avec les modules communs extraits des scripts existants
- [ ] Écrire les tests unitaires pour `core/translator.py` (retry, rate limiting)
- [ ] Valider que `mode_translate_json.py` produit les mêmes sorties que l'actuel `translate.py` v2

### Phase 2 — Intégration
- [ ] Implémenter `service.py` avec la résolution du `MODE`
- [ ] Créer le `Dockerfile` et `docker-compose.yml` unifiés
- [ ] Créer le `requirements.txt` unifié (`deep-translator` + `openpyxl`)
- [ ] Tester le mode `translate-dropdowns` sur le fichier `Dropdown_a_traduire.xlsx`

### Phase 3 — Nettoyage
- [ ] Archiver ou supprimer `cz/translator/` (legacy)
- [ ] Supprimer `Dockerfile.analyze`, `Dockerfile.generate`, `docker-compose.analyze.yml`, `docker-compose.generate.yml`
- [ ] Supprimer `requirements.analyze.txt`, `requirements.generate.txt`
- [ ] Mettre à jour le README (si existant) ou créer une documentation d'utilisation

---

## 8. Estimation de l'effort

| Tâche | Complexité | Estimation |
|-------|-----------|------------|
| Extraction de `core/translator.py` | Faible | ~1h |
| Extraction de `core/io_json.py` | Faible | ~30min |
| Extraction de `core/io_xlsx.py` | Moyenne | ~1h30 |
| Écriture de `service.py` (routing) | Faible | ~30min |
| Réécriture de `update_documentation()` | Moyenne | ~1h |
| Migration vers `logging` | Faible | ~30min |
| Dockerfile + docker-compose unifiés | Faible | ~30min |
| Tests de non-régression | Moyenne | ~2h |
| **Total estimé** | | **~7-8h** |

---

## 9. Bénéfices attendus de la fusion

| Axe | Situation actuelle | Après fusion |
|-----|--------------------|--------------|
| Nombre de scripts Python | 4 (dont 1 obsolète) | 1 point d'entrée + modules |
| Nombre de Dockerfiles | 4 | 1 |
| Nombre de docker-compose | 4 | 1 |
| Nombre de requirements.txt | 3 | 1 |
| Logique de traduction dupliquée | Oui (2 implémentations) | Non (1 seule source) |
| Robustesse retry/checkpoint | Hétérogène | Uniforme |
| Configuration | Mixte (hardcodé + env vars) | Tout via env vars |
| Extensibilité (nouvelle langue) | Modifier plusieurs fichiers | Modifier `config.py` uniquement |

---

## 10. Conclusion et recommandation

La fusion est **fortement recommandée**. Le projet dispose déjà d'une bonne base avec la v2 de `translate.py` (configuration par variables d'environnement, gestion des signaux) et la structure avancée de `generate_dropdowns.py` (multi-langues, multi-formats). Les deux scripts partagent suffisamment de logique pour justifier une factorisation en modules communs.

L'effort est **maîtrisé (~7-8h)** et le gain en maintenabilité, lisibilité et robustesse est significatif. La priorité absolue est de **supprimer le script legacy `cz/translator/translate.py`** qui n'apporte aucune valeur ajoutée par rapport à la v2 existante.

**Recommandation de priorité :**
1. 🔴 **Immédiat** — Supprimer `cz/translator/translate.py` (legacy obsolète)
2. 🟠 **Court terme** — Fusionner `translate.py` v2 et `generate_dropdowns.py` via l'architecture modulaire proposée
3. 🟡 **Moyen terme** — Intégrer `analyze_xlsx.py` comme sous-commande du service générique

---

*Document généré le 2026-04-20*
