# Audit qualité « Platinum » — Pipeline orchestré COP_translations

Date : 2026-07-13
Périmètre : pipeline JSON, pipeline dropdown, shared kernel, tests, I/O XLSX, validate, compare_sources, analyze_translation_gap.
Méthode : revue de code statique, lecture exhaustive des 9 fichiers listés (~6 700 lignes). Aucune hypothèse non sourcée.

---

## 1. Scores globaux par fichier

| Fichier | Lignes | Score / 10 | Verdict |
|---|---:|---:|---|
| `translator/pipeline_common.py` | 109 | **8.5** | Shared kernel clair et minimal ; sous-exploité. |
| `translator/pipeline.py` | 1 291 | **6.0** | Fonctionnel et testé, mais fonctions longues, duplication, mutation du singleton Config non protégée, `_prompt_action` défini deux fois. |
| `translator/pipeline_dropdown.py` | 798 | **6.5** | Plus court et plus régulier que le JSON, mais étape 8 fantôme, mésalignements sur stale data, docstrings manquantes. |
| `translator/tests/test_pipeline.py` | 1 897 | **7.5** | Couverture large, e2e présent ; peu de `parametrize`, pas de test pour la duplication `_prompt_action`. |
| `translator/tests/test_pipeline_dropdown.py` | 1 158 | **7.0** | Bonne couverture des étapes ; pas d'e2e « vrai fichier », pas de test openpyxl manquant. |
| `translator/core/io_xlsx.py` | 312 | **7.0** | Bonne séparation ; `load_dropdown_xlsx_all_sheets` oublie le garde-fou `openpyxl is None`. |
| `translator/validate_translations.py` | 516 | **6.5** | Dataclean ; `_detect_duplicate_keys` parse le JSON à la regex — fragile. |
| `compare_sources.py` | 302 | **7.5** | Petit, propre, dataclass ; API `compute()` à ne pas oublier. |
| `analyze_translation_gap.py` | 295 | **7.5** | Petit, propre ; pas de vérif que source/old_src sont des dicts. |

**Score global pipeline : 6.9 / 10.** Pour viser « platinum » (≥ 8.5), il faut traiter ~25 points (voir §4 et §5).

---

## 2. Points forts

### Architecture
- **DDD bounded contexts** : `pipeline.py` (JSON) et `pipeline_dropdown.py` (XLSX) sont bien séparés, avec un shared kernel (`pipeline_common.py`) qui centralise `BasePipelineContext`, `confirm`, `step_banner`, `backup_translation_file`, `json_load/json_write`, `short_repr`.
- **Dispatcher propre** : `run_pipeline` fait un dispatch lisible (`--mode` → `detect_source_kind` → dropdown / json) avec import lazy pour éviter les imports circulaires.
- **Dataclasses** pour les contextes (`BasePipelineContext` / `PipelineContext` / `PipelineDropdownContext`) — typés, factories correctes pour les listes.
- **Objets-valeur métier** : `Comparison`, `LangGap`, `ValidationReport`, `LangValidation` — dataclasses avec propriétés calculées (`all_ok`, `total_*`), bonnes sérialisations `to_dict`.

### Qualité de code
- **Typage** quasi complet sur les fonctions publiques (`Path | None`, `list[dict]`, etc.).
- **Docstrings** présentes et utiles sur la majorité des fonctions publiques du pipeline JSON.
- **Style homogène** : `step_banner(n, "…")` + garde `if ctx.dry_run:` en début d'étape — convention lisible et respectée dans les deux pipelines.
- **Bandeaux d'étape** standardisés via `step_banner` → sortie visuellement cohérente sur 11 étapes.

### Tests
- **Couverture large** : une classe `TestXxx` par fonction, contexte factice (`fake_translator_dir`) clair, fixtures XLSX réutilisables.
- **Tests e2e** sur la vraie source `en 10.json` (skippés si absente) — vrai filet de sécurité.
- **Tests dry-run unifié** vérifient qu'aucun fichier/dossier/backup/rapport n'est écrit — excellent.
- **Tests de robustesse** : `FileNotFoundError`, fichiers manquants, dossiers vides, languages manquantes.
- **Tests de mutation du Config singleton** (`test_ollama_provider_sets_config`) — bonne intention.

### Cohérence métier
- **11 étapes identiques** dans les deux pipelines (1 détection → 11 rapport final) — parallélisme facilitant la lecture.
- **Confirmations aux étapes clés** (5 et 6) avec défaut sûr (`EOFError` → garder, `confirm(default=False)`).
- **Respect de l'ordre source** (étape 8 JSON + section 9 du rapport final) — préoccupation métier explicite.

---

## 3. Points faibles par priorité

### 🔴 Critique (bugs potentiels, sécurité, intégrité de données)

#### C1. `_prompt_action` défini DEUX fois dans `pipeline.py` (L561 et L603)
Les deux corps sont identiques, mais la seconde définition **écrase silencieusement** la première. Symptôme de copier-coller ; si l'un des corps diverge un jour, le bug sera invisible. `manage_modified_keys` (L552) appelle `_prompt_action` qui sera toujours la version L603.
- **Fix** : supprimer la seconde définition (L603-615).

#### C2. Singleton `Config` muté sans `try/finally` (les deux `step7_translate`)
`config_module._config = config` est positionné, puis l'appel de traduction peut lever. Le `except Exception` dans `run_pipeline` (L1272) retourne `rc=3` **sans restaurer** `config_module._config = None`. Le singleton reste pollué → tout appel ultérieur à `get_config()` dans le même process retourne la config du pipeline (source/OUTPUT_DIR faux). Concrètement :
- Les tests qui enchaînent plusieurs `run_pipeline` peuvent voir un test contaminé par le précédent.
- Un usage programmatique en boucle peut corrompre l'état global.
- **Fix** : encapsuler dans un gestionnaire de contexte `override_config(**overrides)` (dans `pipeline_common`) qui fait `try/finally` et restaure l'ancienne valeur (pas `None`, l'ancienne).

#### C3. `detect_misalignments_dropdown` analyse les **stale data** (L538-593)
La fonction lit `ctx.existing_translations.get(lang_upper, {})` — le cache colonne B initial — et **non** `ctx.translations_by_lang[lang]` qui vient d'être produit par `step7_translate`. Après traduction, les nouvelles traductions ne sont jamais examinées. L'étape 10 dropdown est donc **inefficace** sur les origins nouvellement traduits.
- **Fix** : fusionner `existing_translations` et `translations_by_lang` avant comparaison (comme le fait déjà `_write_dropdown_output`).

#### C4. `step8_reorder` (dropdown) est un **no-op** qui prétend travailler (L472-484)
La fonction affiche `"réordonné selon la source"` pour chaque langue mais **n'écrit rien**. Or le JSON produit par `_write_dropdown_output` itère `merged.items()` dont l'ordre dépend du cache XLSX, pas de la source. L'étape 8 dropdown ne respecte donc pas l'ordre source — contradiction avec la section 9 du rapport final.
- **Fix** : soit réécrire les fichiers `dropdown_{lang}.json` en suivant `source_origins`, soit supprimer l'étape 8 dropdown et assumer l'absence de réordonnancement (et corriger le rapport).

#### C5. `pipeline.py --mode dropdown --retranslate-all` → erreur argparse
`build_parser` (JSON, L1120-1178) ne déclare **pas** `--retranslate-all`, `--retranslate`, `--format`. Si l'utilisateur passe `--mode dropdown` avec un flag dropdown-only via l'entrypoint `pipeline.py`, argparse rejette le flag. Le dispatcher ne propage pas ces options.
- **Fix** : fusionner les parsers (ajouter les flags dropdown-only à `build_parser` avec `default=None`) ou documenter que le mode dropdown doit être invoqué via `pipeline_dropdown.py` directement.

#### C6. Re-run same-day écrase silencieusement l'export du jour
`prepopulate_output` fait `new_dir.mkdir(parents=True, exist_ok=True)` puis `shutil.copy2(...)` sans backup préalable des fichiers déjà présents dans `new_dir`. Un second run le même jour écrase les traductions produites par le premier run, sans warning ni backup.
- **Fix** : si `new_dir` existe déjà et n'est pas vide, backuper ou suffixer (`2026_07_13_Export_run2`).

#### C7. `_detect_duplicate_keys` (validate_translations.py L184-196) parse le JSON à la regex
L'implémentation découpe par lignes et cherche `line.startswith('"')` et `'":'` — incorrect pour :
- JSON minifié (une seule ligne) ;
- JSON avec objets imbriqués (les clés internes sont comptées comme clés de top-level) ;
- clés contenant `":"` (split naïf) ;
- clés échappées en `\uXXXX`.
- **Fix** : utiliser un parser JSON qui signale les doublons (`json.JSONDecoder.object_pairs_hook`), ou `json5`/une lecture manuelle d'un tokenizer.

#### C8. `load_dropdown_xlsx_all_sheets` ne vérifie pas `openpyxl is None`
Contrairement à `load_dropdown_xlsx` (L56-57) qui lève `ImportError("openpyxl is required…")`, `load_dropdown_xlsx_all_sheets` (L274) appelle `openpyxl.load_workbook(...)` directement → `AttributeError: 'NoneType' object has no attribute 'load_workbook'` en l'absence d'openpyxl. Incohérent et message opaque.
- **Fix** : ajouter le même garde-fou `if openpyxl is None: raise ImportError(...)`.

#### C9. `_apply_typo_corrections_xlsx` (dropdown) parcourt les colonnes 1 à 3 en dur (L178)
`for col in range(1, 4)` — ne corrige pas les éventuelles colonnes 4+ (ex. notes, contexte étendu). Magic number non nommé. De plus, la fonction ne valide pas `openpyxl is None`.
- **Fix** : `for col in range(1, ws.max_column + 1)` ou constantes nommées `ORIGIN_COL=1, TRAD_COL=2, CONTEXT_COL=3` et itérer sur toutes les colonnes utilisées.

#### C10. `save_dropdown_xlsx` crée une feuille par langue **configurée** (pas seulement traduite)
Si `LANGUAGES` contient 9 langues mais que seules 3 ont été traduites, la feuille des 6 autres est remplie avec `value = origin` (passthrough anglais). Résultat : un XLSX qui **prétend** être traduit en 9 langues alors qu'il ne l'est pas. Faux-positif côté consumer.
- **Fix** : ne créer des feuilles que pour les langues présentes dans `translations`, ou mettre une cellule marqueur `[NOT TRANSLATED]`/vider la colonne Traduction.

#### C11. `manage_modified_keys` affiche la traduction courante via `languages[0]` (L544)
Si l'utilisateur passe `--languages de,fr`, `languages[0] == "de"` alors que le projet est historiquement piloté en français → affichage contre-intuitif. Pire, l'utilisateur peut croire que c'est la traduction de référence.
- **Fix** : utiliser une langue d'affichage explicitement configurable (default `"fr"`) indépendante de l'ordre de `--languages`.

#### C12. `prepopulate_output(Path("/dev/null"), ...)` (L634, JSON étape 6)
Passe `/dev/null` comme dossier source. Fonctionne « par accident » (le `src_file.exists()` vaut False), mais :
- Non portable (Windows n'a pas `/dev/null`) ;
- Sémantiquement trompeur (le message dit « dossier vide créé » alors qu'on a passé un fichier spécial).
- **Fix** : introduire un sentinel explicite ou appeler une branche dédiée « pas d'export précédent ».

#### C13. `validate` / `analyze` n'ont pas de garde-fou « le JSON n'est pas un dict »
`source_data.keys()` lève si le JSON est une liste ou un scalaire. Une source corrompue produit une `AttributeError` opaque.
- **Fix** : `if not isinstance(source_data, dict): raise ValueError(f"Source {path} n'est pas un objet JSON")`.

#### C14. `extract_placeholders` (validate) vs `PLACEHOLDER_RE` (compare_sources) — regex divergentes
`validate_translations.py` compile 5 patterns séparés (incluant `\\n` littéral), `compare_sources.py` en combine un seul (`%[sd]|\{[^}]+\}|<[^>]+>|\{[0-9]+\}`). Les placeholders détectés diffèrent entre validation et comparaison → faux-négatifs possibles côté validation, faux-positifs côté comparaison.
- **Fix** : extraire une constante `PLACEHOLDER_PATTERNS` partagée (dans `pipeline_common` ou un module `placeholders.py`).

#### C15. `_tokenize` (pipeline.py L837) — fallback qui retourne le texte entier
Si aucune token alnum n'est trouvé (texte ponctué/emoji), retourne `{text.lower()}`. Deux chaînes distinctes composées uniquement de ponctuation ne partageront jamais de token → signalées comme mésalignées (false positive). À l'inverse, ce n'est pas un mésalignement réel.
- **Fix** : retourner `set()` pour les textes sans token, et skipper la comparaison si l'un des deux est vide de tokens.

### 🟡 Important (design, maintabilité, dette technique)

#### I1. Duplication structurelle forte entre les deux pipelines
~70 % du squelette est parallèle : `stepN_*`, `load_typos*`, `detect_typos_in_*`, `_apply_typo_corrections_*`, `build_analysis_report*`, `build_final_report*`, `step11_final_report_*`, `run_pipeline_*`, mutation du singleton Config, etc. Le shared kernel n'exploite pas ces similarités.
- **Fix** : extraire dans `pipeline_common` :
  - `load_typos(scope)` unifié (filtre `"both|json|dropdown"`) ;
  - `override_config(...)` context manager ;
  - `dry_run_guard(ctx, msg)` ;
  - `write_markdown_report(content, kind)` ;
  - `report_section(header, lines)` helper.

#### I2. Fonctions trop longues / complexité cyclomatique élevée
| Fonction | Lignes | Note |
|---|---:|---|
| `build_final_report` (pipeline.py) | 155 | > 50 ; 9 sections markdown concaténées à la main. |
| `build_analysis_report` (pipeline.py) | 91 | Idem, 5 sections. |
| `build_final_report_dropdown` | 87 | Idem, 9 sections. |
| `step1_detect_sources` | 66 | 3 responsabilités (new / prev / export). |
| `_write_dropdown_output` | 66 | Deux branches format (json/xlsx) à séparer. |
| `build_analysis_report_dropdown` | 60 | 5 sections. |
| `step7_translate` (dropdown) | 51 | Mixe Config + trad + écriture. |

- **Fix** : une fonction = une section markdown. Extraire `_section_source(ctx)`, `_section_comparison(ctx)`, etc.

#### I3. Pas de logging — uniquement `print`
Toutes les diagnostics passent par `print` (et `print(..., file=sys.stderr)` pour les erreurs). Pas de niveaux, pas de redirection facile, pas de silenciation en usage programmatique. Tests utilisent `capsys` — fragile.
- **Fix** : `logger = logging.getLogger("pipeline")` ; remplacer les `print` d'info par `logger.info`, garder `print` uniquement pour les rapports markdown affichés (étape 5).

#### I4. `output_dir` non typé dans plusieurs fonctions dropdown
`validate_dropdown(ctx, output_dir)`, `build_final_report_dropdown(ctx, output_dir, ...)`, `step11_final_report_dropdown(ctx, output_dir, ...)` — paramètre sans annotation `Path`. Incohérent avec le reste du pipeline.
- **Fix** : ajouter `output_dir: Path` partout.

#### I5. Docstrings manquantes ou trop courtes (dropdown)
Absentes ou mono-ligne sur : `step1_detect_source`, `load_typos_dropdown`, `detect_typos_in_origins`, `_apply_typo_corrections_xlsx`, `_translate_dropdown_batch`, `_write_dropdown_output` (présente mais courte), `validate_dropdown`, `detect_misalignments_dropdown`, `build_final_report_dropdown`, `step11_final_report_dropdown`, `run_pipeline_dropdown`.
- **Fix** : standardiser « Args / Returns / Raises » comme dans `pipeline.py`.

#### I6. Magic numbers non nommés
| Expression | Emplacement | Sens |
|---|---|---|
| `5` (preview de clés) | `step3_detect_typos`, `build_analysis_report`, `compare_sources.render` | Limite d'aperçu |
| `80` / `100` / `117` / `120` | `short_repr`, `short` (×2), `short` | Seuils de troncation → 4 valeurs différentes |
| `3` (`len(k) > 3`) | `validate_translations.validate_lang`, `detect_misalignments_dropdown` | Seuil « non-traduit » |
| `70` | `step_banner`, séparateurs | Largeur de bandeau |
| `range(1, 4)` | `_apply_typo_corrections_xlsx` | Colonnes A-C |
| `120` | `compare_sources.render` | Sample de modifications |
| `20` | `build_final_report` (mésalignements) | Sample de mésalignements |

- **Fix** : `PREVIEW_LIMIT = 5`, `BANNER_WIDTH = 70`, `TRUNCATE = 100`, `UNTRANSLATED_MIN_LEN = 3`, `TYPHOS_PATH` → `TYPOS_PATH`.

#### I7. `TYPHOS_PATH` — typo de nom de constante (L74 pipeline.py)
`TYPHOS` au lieu de `TYPOS`. Le fichier référencé est `source_typos.json`. Un relecteur cherchera « typos » et ne trouvera pas la constante.
- **Fix** : renommer en `TYPOS_PATH`.

#### I8. Deux confirmations consécutives (dropdown étapes 5 et 6)
`step5_report_and_confirm` demande « Poursuivre ? » (default False). Si oui, `step6_prepopulate` redemande « Lancer la traduction ? » (default True). UX dupliquée, risque d'incohérence (un "non" à l'étape 5 sort, un "non" à l'étape 6 annule avec message différent).
- **Fix** : fusionner en une seule confirmation après l'étape 5 (supprimer la confirmation interne à `step6_prepopulate`).

#### I9. `PipelineDropdownContext.comparison_added/removed/unchanged: list[str]` ne réutilise pas `Comparison`
Le pipeline JSON utilise `Comparison` (dataclass structurée avec `added_by_prefix`, `modified_placeholder_mismatch`, etc.). Le dropdown stocke 3 listes plates → perte de richesse, pas de helper de préfixe.
- **Fix** : produire un `Comparison` (ou un `OriginComparison` adapté) réutilisable dans les deux pipelines.

#### I10. `detect_missing_languages` recharge le XLSX complet (L305)
`step1_detect_source` a déjà appelé `load_dropdown_xlsx_all_sheets` et stocké dans `ctx.existing_translations`. `detect_missing_languages` recharge depuis le disque. Double I/O.
- **Fix** : surcharger `detect_missing_languages(xlsx_path=None, configured_langs, existing_translations=None)` ; si `existing_translations` fourni, ne pas recharger.

#### I11. `build_analysis_report` et `build_final_report` rechargent `ctx.new_source` (L399, L956)
Comptage des clés source fait 3 fois (étape 1, rapport intermédiaire, rapport final).
- **Fix** : stocker `ctx.source_key_count: int` à l'étape 1 et le réutiliser.

#### I12. `_write_dropdown_output` — `auto` résout toujours en `json` (L419-421)
Le flag `--format auto` n'a aucune valeur ajoutée (pas de détection du format d'entrée). Soit le rendre fonctionnel (auto = suivre l'extension de `xlsx_path`), soit le supprimer.
- **Fix** : `auto` → regarder `ctx.xlsx_path.suffix` ; si `.xlsx`, sortir xlsx ; sinon json. Ou supprimer `auto`.

#### I13. `detect_misalignments_dropdown(ctx, validation_results)` — paramètre mort
`validation_results` n'est jamais utilisé dans le corps. Bug de signature ou dead code.
- **Fix** : supprimer le paramètre ou l'utiliser (e.g., ne signaler que les origins non-missing).

#### I14. `save_dropdown_xlsx` — paramètre `languages: dict` mal nommé et `lang_info` unused
Le nom suggère une liste de codes ; c'est en fait `LANGUAGES` (dict de config). La variable `lang_info` est itérée mais non utilisée.
- **Fix** : renommer en `lang_config: dict[str, Any]` et `for lang_code, _ in lang_config.items()`.

#### I15. Pas de tests pour la duplication `_prompt_action` ni pour le non-restauration du singleton
- Pas de test vérifiant `_prompt_action` est défini une seule fois (inspection statique via `inspect.getmembers`).
- Pas de test vérifiant qu'après une exception dans `step7_translate`, `core.config._config` vaut `None`.
- Pas de test pour la perte de l'ordre source en dropdown (étape 8 no-op).
- Pas de test pour `save_dropdown_xlsx` quand la langue n'est pas traduite (passthrough anglais).
- Pas de test pour `--mode dropdown --retranslate-all` via `pipeline.py` (qui plante argparse).

#### I16. Peu de tests paramétrés
Seulement 3 occurrences de `@pytest.mark.parametrize` (sur `confirm` et `detect_source_kind`). Les tests de typos, mésalignements, validation, format de sortie gagneraient à être paramétrés (gains de lisibilité et de couverture).

#### I17. `pipeline_common.py` sous-exploité
109 lignes seulement. Manquent :
- `override_config(...)` context manager (C2) ;
- `load_typos(scope)` unifié (I1) ;
- `dry_run_guard(ctx, step_name)` ;
- `truncate(text, n=100)` unifié (remplacerait les 3 `short`/`short_repr`) ;
- `write_report(content, kind, doc_dir)` ;
- `parse_languages_arg(s)` (présent en double dans les deux `run_pipeline`).

#### I18. `output_format: str = "auto"` non validé
Le dataclass accepte n'importe quelle string. La validation se fait tardivement dans `_write_dropdown_output` (branche `else` affichant un warning). Mieux vaut une `Literal["json", "xlsx", "auto"]` ou une énumération.

#### I19. `Compare(...).compute()` à ne pas oublier
L'API de `compare_sources` exige un appel manuel à `.compute()` après construction. Le helper `compare()` le fait pour l'usage programmatique, mais un utilisateur direct de `Comparison(...)` oublie le calcul.
- **Fix** : soit `__post_init__` qui appelle `compute`, soit renommer `Comparison` en `ComparisonBuilder` et exposer uniquement `compare()`.

#### I20. `step7_translate` (JSON) charge `source_data` en local (L713-714) puis passe `ctx.new_source` ET `source_data` à `_translate_single_language`
Redondance. Soit passer uniquement le path et laisser le mode charger, soit passer uniquement les données et éviter la relecture.
- **Fix** : uniformiser la signature du mode.

### 🟢 Mineur (style, cosmétique, consistance)

- **M1.** `from pipeline_common import BasePipelineContext, confirm, step_banner  # noqa: E402, F401` — le `F401` est trompeur (`confirm` et `step_banner` sont utilisés). Retirer le noqa.
- **M2.** `_LANGS` alias inutile dans `_write_dropdown_output` (L455) — `LANGUAGES` direct suffit.
- **M3.** Variable `merged` (json) / `merged_lang` (xlsx) — nommage inconsistant dans une même fonction.
- **M4.** `print(f"  {lang.upper()}: {out_path.name} écrit " f"({len(merged)} entrées).")` — f-string coupée artificiellement ; fusionner.
- **M5.** Docstring pipeline.py L13-14 mentionne encore « Les étapes 6-11 seront ajoutées dans les phases 2 et 3 » — obsolète (phases livrées).
- **M6.** `def fake_translate(src_file, src_data, src_lang, tgt_lang, out_dir)` (test e2e) — `src_file` et `src_lang` unused. Préfixer `_`.
- **M7.** README.md (translator/) est obsolète : ne mentionne ni `pipeline.py`, ni `pipeline_dropdown.py`, ni `pipeline_common.py`, ni le workflow orchestré. Indique « 723 tests (94% couverture) » — à vérifier.
- **M8.** `_REPO_ROOT` (test) vs `REPO_ROOT` (pipeline) — même concept, deux noms.
- **M9.** `step5_report_and_confirm` (JSON) écrit le rapport sur `ctx.report_path` même en `--dry-run` (L475-477) — comportement correct mais non documenté dans la docstring.
- **M10.** Aucun `__init__.py` dans `translator/tests/` — discovery via `pytest.ini`, mais dépend de la config.
- **M11.** `Path("/dev/null")` apparaît à 2 endroits (pipeline.py L1245, pipeline_dropdown.py L757) — magic path.
- **M12.** Plusieurs `print("\n" + "─" * 70)` et `print("═" * 70)` — extraire `section_separator(char="─", width=70)` dans `pipeline_common`.
- **M13.** `PipelineContext.no_cache` est défini au niveau du dataclass JSON mais pas dans `BasePipelineContext` — or `run_pipeline_dropdown` lit aussi `args.no_cache`. Devrait être dans la base.
- **M14.** `manage_modified_keys(... interactive: bool = True)` accepte un booléen, mais `confirm()` dans le pipeline lit `ctx.interactive`. Deux sources de vérité.
- **M15.** `_manual_input_for_all` accepte une valeur vide sans warning (le test aussi). Ajouter une garde `if not value: print("  ⚠️ vide — ignoré"); continue`.
- **M16.** `detect_typos_in_source` utilise `typo in value` (substring) — risque de faux-positifs (`"cat"` dans `"category"`). Documenter la limitation ou utiliser des word-boundaries.
- **M17.** `_apply_typo_corrections_xlsx` itère `wb.worksheets` (toutes feuilles) pour chaque typo — O(typos × sheets × rows × cols). Acceptable pour peu de typos, mais à documenter.
- **M18.** `step11_final_report_dropdown` ne return pas `Path` (return `None` au lieu du path écrit) dans la signature — annotation manquante.
- **M19.** `build_final_report_dropdown` section 4 (Écart) : si `gap_by_lang` est vide, seul un `""` final est ajouté — pas de placeholder `_Écart non calculé._` comme dans la version JSON. Inconsistance.
- **M20.** `compare_sources.short` tronque à 120 ; `analyze_translation_gap.short` à 100 ; `pipeline_common.short_repr` à 80. Trois seuils pour la même fonction. Unifier.
- **M21.** `validate_translations.py` définit `load_json` (L66-69) — duplique `pipeline_common.json_load` et `compare_sources.load_json` et `analyze_translation_gap.load_json`. Quatre copies.
- **M22.** `PLACEHOLDER_PATTERNS` (validate) list de strings vs `PLACEHOLDER_RE` (compare) une regex compilée — deux styles pour le même concept.
- **M23.** Imports en tête de `pipeline.py` (L52-70) avec `# noqa: E402` — normal mais verbeux. Un `conftest.py` qui ajuste `sys.path` rendrait les noqa inutiles.
- **M24.** `step10_detect_misalignments` (JSON) n'ajoute pas une entrée pour les langues dont le fichier est absent (L914 `continue`). Inconsistant avec `step9_validate` qui signale toujours toutes les langues.
- **M25.** `detect_misalignments` argument `lang` est pris en compte pour la signature mais jamais utilisé dans le corps.
- **M26.** `PipelineDropdownContext.output_format` est un `str` libre ; devrait être `Literal["json", "xlsx", "auto"]`.

---

## 4. Recommandations de refactoring (spécifiques et actionnables)

### R1. Créer un context manager `override_config` dans `pipeline_common`
```python
@contextmanager
def override_config(*, source_file: str, output_dir: str, provider: str,
                    no_cache: bool = False) -> Iterator[None]:
    import core.config as cfg
    from core.config import Config
    prev = cfg._config
    c = Config(SOURCE_LANG="en", SOURCE_FILE=source_file, OUTPUT_DIR=output_dir,
               TRANSLATION_PROVIDER=provider)
    if no_cache:
        c.TRANSLATION_CACHE = "false"
    cfg._config = c
    try:
        yield
    finally:
        cfg._config = prev
```
Remplace les blocs dupliqués dans `step7_translate` (JSON + dropdown). Corrige **C2**.

### R2. Unifier `load_typos` et la détection de typos
```python
def load_typos(path: Path, scope: str = "both") -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return [e for e in data.get("typos", [])
            if e.get("scope", "both") in (scope, "both")]
```
`pipeline.py` et `pipeline_dropdown.py` deviennent des minces wrappers.

### R3. Extraire les sections de rapport
Pour chaque rapport (`build_analysis_report`, `build_final_report`, `build_analysis_report_dropdown`, `build_final_report_dropdown`) :
- une fonction `_section_<name>(ctx) -> list[str]` par section ;
- un `build_report(ctx, sections: list[Callable[[PipelineContext], list[str]]]) -> str` qui concatène.
Divise les fonctions de 90-155 lignes en 5-9 fonctions de 10-20 lignes. Corrige **I2**.

### R4. Supprimer la seconde définition de `_prompt_action`
Et déplacer la fonction (utilisée uniquement par `manage_modified_keys`) juste au-dessus de celle-ci, ou en faire une méthode privée d'un helper `ModifiedKeysManager`. Corrige **C1**.

### R5. Réparer `step8_reorder` dropdown
Soit réécrire les fichiers `dropdown_{lang}.json` selon l'ordre source (construire `contexts` en itérant `ctx.entries`), soit supprimer l'étape et mettre à jour le rapport. Corrige **C4**.

### R6. Fusionner les parsers CLI
`build_parser` (JSON) doit accepter tous les flags dropdown-only avec `default=None`, et `run_pipeline_dropdown` ne lire que les flags présents. Permet `pipeline.py --mode dropdown --retranslate-all`. Corrige **C5**.

### R7. Généraliser `detect_misalignments_dropdown` pour analyser les traductions fraîches
```python
def _merged_translations(ctx, lang: str) -> dict[str, str]:
    merged = dict(ctx.existing_translations.get(lang.upper(), {}))
    merged.update(ctx.translations_by_lang.get(lang, {}))
    return merged
```
Utiliser dans `detect_misalignments_dropdown` et `_write_dropdown_output`. Corrige **C3**.

### R8. Ajouter garde-fou openpyxl manquant
Ajouter `if openpyxl is None: raise ImportError("openpyxl is required for XLSX operations")` à `load_dropdown_xlsx_all_sheets`. Corrige **C8**.

### R9. Réimplémenter `_detect_duplicate_keys` avec `object_pairs_hook`
```python
def _detect_duplicate_keys(filepath: Path) -> dict[str, int]:
    if not filepath.exists():
        return {}
    counts: dict[str, int] = defaultdict(int)
    def _hook(pairs):
        d = {}
        for k, v in pairs:
            counts[k] += 1
            d[k] = v
        return d
    with open(filepath, encoding="utf-8") as fh:
        json.load(fh, object_pairs_hook=_hook)
    return {k: v for k, v in counts.items() if v > 1}
```
Corrige **C7**.

### R10. Centraliser les constantes
Créer `translator/pipeline_common.py` (ou `translator/core/constants.py`) :
```python
BANNER_WIDTH = 70
PREVIEW_LIMIT = 5
TRUNCATE_TEXT = 100
UNTRANSLATED_MIN_LEN = 3
TYPOS_FILENAME = "source_typos.json"
```
Corrige **I6, M20**.

### R11. Introduire le logging
```python
import logging
logger = logging.getLogger("pipeline")
```
Remplacer les `print` d'info par `logger.info`. Garder `print` pour les rapports markdown interactifs. Corrige **I3**.

### R12. Sauvegarde de l'export du jour avant écrasement
Dans `prepopulate_output` :
```python
if new_dir.exists() and any(new_dir.iterdir()):
    backup = new_dir.with_name(f"{new_dir.name}_bak_{datetime.now():%H%M%S}")
    shutil.move(new_dir, backup)
new_dir.mkdir(parents=True, exist_ok=True)
```
Corrige **C6**.

### R13. Étendre les tests pour les bugs identifiés
- `test_prompt_action_defined_once` (via `inspect.getsource` ou comparaison `id`).
- `test_config_singleton_restored_after_exception`.
- `test_step8_dropdown_preserves_source_order` (échouera tant que R5 n'est pas fait — red/green).
- `test_save_dropdown_xlsx_only_translated_langs`.
- `test_pipeline_dropdown_flags_via_json_entrypoint` (vérifie R6).
- `test_load_dropdown_xlsx_all_sheets_raises_importerror_without_openpyxl`.
- `test_detect_duplicate_keys_nested_json` (vérifie R9).

### R14. Migrer `output_format` vers `Literal["json", "xlsx", "auto"]`
Et rendre `auto` fonctionnel : `auto` → xlsx si `ctx.xlsx_path.suffix == ".xlsx"` et > seuil de taille, sinon json. Corrige **I12, M26**.

### R15. Couper `build_final_report` (JSON) en 9 fonctions `_section_*`
Voir R3. La fonction la plus longue du projet (155 lignes) doit passer sous 30 lignes (orchestration seule).

### R16. Réparer README.md
- Ajouter une section « Pipeline orchestré » qui documente `pipeline.py`, `pipeline_dropdown.py`, `pipeline_common.py` et le workflow 11 étapes.
- Mettre à jour le compteur de tests et la structure du projet (ajouter les 3 fichiers + `source_typos.json`).
- Documenter `--mode dropdown`, `--retranslate-all`, `--format`.
- Corrige **M7, M5**.

---

## 5. Plan d'action priorisé

### Sprint 1 — Bugs critiques (estimé 1 jour)
| # | Tâche | Fichier(s) | Effort | Référence |
|---|---|---|---|---|
| 1 | Supprimer la 2e définition `_prompt_action` | pipeline.py | 5 min | C1 |
| 2 | `override_config` context manager + migration des 2 `step7_translate` | pipeline_common + 2 pipelines | 1 h | C2 / R1 |
| 3 | `detect_misalignments_dropdown` lit `translations_by_lang` | pipeline_dropdown.py | 30 min | C3 / R7 |
| 4 | Réparer `step8_reorder` dropdown (réordonner ou supprimer) | pipeline_dropdown.py | 1 h | C4 / R5 |
| 5 | Fusionner `build_parser` (flags dropdown-only) | pipeline.py | 30 min | C5 / R6 |
| 6 | Backup de l'export du jour avant écrasement | pipeline.py | 30 min | C6 / R12 |
| 7 | Réimplémenter `_detect_duplicate_keys` via `object_pairs_hook` | validate_translations.py | 30 min | C7 / R9 |
| 8 | Garde-fou `openpyxl is None` dans `load_dropdown_xlsx_all_sheets` | io_xlsx.py | 5 min | C8 |
| 9 | `_apply_typo_corrections_xlsx` itère `ws.max_column` | pipeline_dropdown.py | 10 min | C9 |
| 10 | `save_dropdown_xlsx` ne crée des feuilles que pour les langs traduites | io_xlsx.py | 30 min | C10 |
| 11 | `manage_modified_keys` : langue d'affichage explicite | pipeline.py | 15 min | C11 |
| 12 | Supprimer `Path("/dev/null")` → sentinel dédié | pipeline.py | 15 min | C12 |
| 13 | Garde-fou « source n'est pas un dict » dans `validate` et `analyze` | 2 fichiers | 10 min | C13 |
| 14 | `extract_placeholders` partagé | pipeline_common + 2 fichiers | 30 min | C14 |
| 15 | `_tokenize` retourne `set()` si aucun token | pipeline.py | 5 min | C15 |

### Sprint 2 — Refactoring & dette (estimé 1.5 jour)
| # | Tâche | Fichier(s) | Effort |
|---|---|---|---|
| 16 | Unifier `load_typos(scope)` dans `pipeline_common` | pipeline_common + 2 pipelines | 30 min |
| 17 | Extraire `_section_*` pour les 4 fonctions de rapport | 2 pipelines | 3 h |
| 18 | Introduire `logging` à la place de `print` | 2 pipelines | 2 h |
| 19 | Annoter `output_dir: Path` partout (dropdown) | pipeline_dropdown.py | 10 min |
| 20 | Compléter docstrings dropdown | pipeline_dropdown.py | 1 h |
| 21 | Constantes nommées (`BANNER_WIDTH`, `PREVIEW_LIMIT`, etc.) | pipeline_common + usages | 30 min |
| 22 | Renommer `TYPHOS_PATH` → `TYPOS_PATH` | pipeline.py + tests | 10 min |
| 23 | Supprimer la confirmation redondante de `step6_prepopulate` | pipeline_dropdown.py | 15 min |
| 24 | `detect_missing_languages` accepte `existing_translations` | io_xlsx.py + caller | 20 min |
| 25 | Stocker `ctx.source_key_count` à l'étape 1 | pipeline.py | 20 min |
| 26 | Supprimer paramètre mort `validation_results` de `detect_misalignments_dropdown` | pipeline_dropdown.py | 5 min |
| 27 | `output_format: Literal[...]` + `auto` fonctionnel | pipeline_dropdown.py | 30 min |
| 28 | `save_dropdown_xlsx` : renommer `languages` → `lang_config` | io_xlsx.py | 10 min |

### Sprint 3 — Tests & documentation (estimé 0.5 jour)
| # | Tâche | Effort |
|---|---|---|
| 29 | 7 tests ciblés (R13) | 2 h |
| 30 | Paramétrer les tests typos / mésalignements / validation | 1 h |
| 31 | Mise à jour README.md (R16) | 1 h |
| 32 | Vérifier couverture réelle avec `pytest --cov` | 15 min |

### Sprint 4 — Polish (optionnel, estimé 0.5 jour)
- Extraire `parse_languages_arg`, `truncate`, `write_report` dans `pipeline_common`.
- `Comparison.__post_init__` qui appelle `compute()` (ou renommer en `ComparisonBuilder`).
- Supprimer les `noqa: E402` via `conftest.py` qui ajuste `sys.path`.
- Migrer `print("─" * 70)` vers `section_separator()`.
- Centraliser les 4 `load_json` en une seule dans `pipeline_common`.

---

## 6. Synthèse

Le pipeline orchestré est **fonctionnel, testé, et architecturalement sain** (DDD, shared kernel, dispatcher propre). Il atteint un niveau **6.9 / 10** — bon mais pas « platinum ».

Pour franchir le cap **8.5 / 10**, deux familles d'actions sont prioritaires :
1. **15 bugs critiques** identifiés en §3 (dont 4 sont des bugs silencieux : `_prompt_action` dupliquée, singleton Config non restauré, `step8_reorder` dropdown no-op, `detect_misalignments_dropdown` sur stale data).
2. **Refactoring de duplication** (§4 R1-R3) : `override_config`, `load_typos(scope)`, et l'extraction des sections de rapport feront passer les fonctions longues sous 30 lignes et faciliteront l'ajout de tests.

Le reste (logging, constantes, docstrings dropdown, README) est du polish qui fait la différence entre « propre » et « platinum ».

**Aucune des modifications proposées ne doit casser les tests existants** si elles sont faites dans l'ordre (d'abord les tests rouges pour C1-C15, puis le refactoring). Le filet de sécurité e2e (`TestPipelineEndToEndEn10`) est précieux et doit être préservé.
---

## 7. Suivi d'avancement

### Sprint 1 — Bugs critiques : ✅ Terminé (2026-07-13)

Les 15 bugs critiques (C1-C15) ont été corrigés en TDD. Score estimé après corrections : **~8/10**.

| # | Bug | Statut |
|---|---|:---:|
| C1 | _prompt_action doublon | ✅ |
| C2 | Singleton Config non restauré | ✅ |
| C3 | Mésalignements sur stale data | ✅ |
| C4 | step8_reorder dropdown no-op | ✅ |
| C5 | --retranslate-all casse argparse | ✅ |
| C6 | Re-run écrase silencieusement | ✅ |
| C7 | _detect_duplicate_keys à la regex | ✅ |
| C8 | load_dropdown_xlsx_all_sheets sans garde openpyxl | ✅ |
| C9 | Colonnes 1-3 en dur | ✅ |
| C10 | Feuilles XLSX pour langues non traduites | ✅ |
| C11 | Affichage languages[0] | ✅ |
| C12 | Path("/dev/null") | ✅ |
| C13 | Pas de garde "JSON pas un dict" | ✅ |
| C14 | Regex placeholders divergentes | ✅ |
| C15 | _tokenize faux positifs | ✅ |

Validation : 1008 tests OK, ruff propre, 7 fichiers modifiés (348 insertions, 130 suppressions).

### Sprint 2 — Refactoring & dette : ⬜ À faire
### Sprint 3 — Tests & documentation : ⬜ À faire
### Sprint 4 — Polish : ⬜ À faire

### Sprint 3 — Tests & documentation : ✅ Terminé (2026-07-20)

4/4 tâches complétées. Score estimé après Sprint 3 : **~9/10**.

| # | Tâche | Statut |
|---|---|:---:|
| 29 | 7 tests ciblés (R13) | ✅ |
| 30 | Paramétrer les tests typos / mésalignements / validation | ✅ |
| 31 | Mise à jour README.md et README.en.md (R16) | ✅ |
| 32 | Vérifier couverture réelle avec pytest --cov | ✅ |

Validation : 1037 tests OK (1008 initiaux + 29 nouveaux), ruff propre, couverture 93% (pipeline.py 94%, pipeline_common.py 99%, pipeline_dropdown.py 90%).

### Sprint 2 — Refactoring & dette : ✅ Terminé (2026-07-13)

12/13 tâches complétées. Score estimé après Sprint 2 : **~8.5/10**.

| # | Tâche | Statut |
|---|---|:---:|
| 16 | Unifier load_typos(scope) | ✅ |
| 17 | Extraire _section_* (4 rapports) | ✅ |
| 18 | Introduire logging | 🟡 Partiel (logger ajouté, prints d'étapes conservés pour capsys) |
| 19 | Annoter output_dir: Path | ✅ |
| 20 | Compléter docstrings dropdown | ✅ |
| 21 | Constantes nommées | ✅ |
| 22 | Renommer TYPHOS_PATH → TYPOS_PATH | ✅ |
| 23 | Supprimer confirmation redondante step6 | ✅ |
| 24 | detect_missing_languages(existing_translations=) | ✅ |
| 25 | Stocker ctx.source_key_count | ✅ |
| 26 | Supprimer paramètre mort validation_results | ✅ |
| 27 | output_format: Literal + auto fonctionnel | ✅ |
| 28 | save_dropdown_xlsx: languages → lang_config | ✅ |

Validation : 1008 tests OK, ruff propre, 6 fichiers modifiés.
