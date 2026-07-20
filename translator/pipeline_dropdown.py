#!/usr/bin/env python3
"""Pipeline orchestré de traduction COP — mode dropdown (XLSX).

Enchaîne les 11 étapes pour traduire un fichier XLSX dropdown vers les
langues cibles, en réutilisant les traductions déjà présentes dans les
feuilles par langue (cache colonne B).

Architecture DDD : bounded context distinct du pipeline JSON
(`pipeline.py`). Shared kernel dans `pipeline_common.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSLATOR_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSLATOR_DIR))

from typing import Literal  # noqa: E402

from core.config import LANGUAGES  # noqa: E402
from core.io_xlsx import (  # noqa: E402
    detect_missing_languages,
    load_dropdown_xlsx,
    load_dropdown_xlsx_all_sheets,
)
from pipeline_common import (  # noqa: E402, F401
    BasePipelineContext,
    BANNER_WIDTH,
    PREVIEW_LIMIT,
    confirm,
    load_typos,
    logger,
    step_banner,
)

try:
    import openpyxl  # noqa: E402
except ImportError:
    openpyxl = None

DEFAULT_TARGET_LANGS = [code for code in LANGUAGES if code != "en"]


@dataclass
class PipelineDropdownContext(BasePipelineContext):
    """Contexte du pipeline dropdown — étend la base avec les champs XLSX."""

    xlsx_path: Path | None = None
    prev_xlsx_path: Path | None = None
    output_dir: Path | None = None

    existing_translations: dict[str, dict[str, str]] = field(default_factory=dict)
    missing_languages: list[str] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)

    retranslate_all: bool = False
    retranslate_langs: list[str] = field(default_factory=list)
    no_cache: bool = False
    # Sprint 2 - tâche 27 : type Literal pour output_format (validation statique).
    output_format: Literal["json", "xlsx", "auto"] = "auto"

    comparison_added: list[str] = field(default_factory=list)
    comparison_removed: list[str] = field(default_factory=list)
    comparison_unchanged: list[str] = field(default_factory=list)

    typos_found: list[dict] = field(default_factory=list)
    typos_corrected: bool = False

    gap_by_lang: dict[str, dict] = field(default_factory=dict)
    translations_by_lang: dict[str, dict[str, str]] = field(default_factory=dict)


def build_parser_dropdown() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pipeline_dropdown.py",
        description="Pipeline orchestré de traduction COP — mode dropdown (XLSX).",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--languages", type=str, default=None)
    p.add_argument(
        "--provider", choices=["google", "ollama", "hybride"], default="hybride"
    )
    p.add_argument("--source", type=Path, default=None)
    p.add_argument("--prev-source", type=Path, default=None)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--yes", "-y", action="store_true")
    p.add_argument("--mode", choices=["json", "dropdown"], default="dropdown")
    p.add_argument("--format", choices=["json", "xlsx", "auto"], default="auto")
    p.add_argument("--retranslate-all", action="store_true")
    p.add_argument("--retranslate", type=str, default=None)
    p.add_argument("--no-cache", action="store_true")
    return p


def step1_detect_source(ctx: PipelineDropdownContext) -> None:
    """Détecte la source XLSX, charge les feuilles existantes et les langues manquantes.

    Args:
        ctx: Contexte du pipeline dropdown. `ctx.xlsx_path` doit être défini.

    Raises:
        FileNotFoundError: Si `ctx.xlsx_path` est None ou n'existe pas.
    """
    step_banner(1, "Détection source XLSX")
    if not ctx.xlsx_path or not ctx.xlsx_path.exists():
        raise FileNotFoundError(f"Source XLSX introuvable : {ctx.xlsx_path}")
    ctx.existing_translations = load_dropdown_xlsx_all_sheets(ctx.xlsx_path)
    present = sorted(k.lower() for k in ctx.existing_translations if k.lower() != "en")
    print(f"  Source : {ctx.xlsx_path.name}")
    print(f"  Feuilles : {', '.join(ctx.existing_translations.keys())}")
    print(f"  Langues déjà traduites : {', '.join(present) if present else 'aucune'}")
    ctx.entries = load_dropdown_xlsx(ctx.xlsx_path)
    print(f"  Entrées (Origins) : {len(ctx.entries)}")
    # Sprint 2 - tâche 24 : passer existing_translations déjà chargé évite une
    # relecture du XLSX par detect_missing_languages (I10).
    ctx.missing_languages = detect_missing_languages(
        ctx.xlsx_path, ctx.languages, existing_translations=ctx.existing_translations
    )
    if ctx.missing_languages:
        print(f"  Langues manquantes : {', '.join(ctx.missing_languages)}")
    else:
        print("  ✅ Toutes les langues configurées sont déjà présentes.")


def step2_compare_sources(ctx: PipelineDropdownContext) -> None:
    step_banner(2, "Comparaison des sources")
    if not ctx.prev_xlsx_path:
        print("  ⚠️  Étape ignorée (pas de XLSX précédent).")
        return
    if not ctx.prev_xlsx_path.exists():
        print(f"  ⚠️  XLSX précédent introuvable : {ctx.prev_xlsx_path}")
        return
    old = {e["origin"] for e in load_dropdown_xlsx(ctx.prev_xlsx_path) if e["origin"]}
    new = {
        e["origin"]
        for e in (ctx.entries or load_dropdown_xlsx(ctx.xlsx_path))
        if e["origin"]
    }
    ctx.comparison_added = sorted(new - old)
    ctx.comparison_removed = sorted(old - new)
    ctx.comparison_unchanged = sorted(new & old)
    print(f"  Ajoutés : {len(ctx.comparison_added)}")
    for o in ctx.comparison_added[:10]:
        print(f"    + {o}")
    print(f"  Supprimés : {len(ctx.comparison_removed)}")
    for o in ctx.comparison_removed[:10]:
        print(f"    - {o}")
    print(f"  Inchangés : {len(ctx.comparison_unchanged)}")


def detect_typos_in_origins(entries: list[dict], typos: list[dict]) -> list[dict]:
    """Détecte les coquilles connues dans les Origins (colonne A) du XLSX.

    Args:
        entries: Liste d'entrées dropdown ({origin, french, context}).
        typos: Liste d'entrées typo ({typo, correction, scope?}).

    Returns:
        Liste de {typo, correction, origins: [origin, ...]} pour chaque coquille
        trouvée dans au moins un Origin. Les origins sont dédupliquées et triées.
    """
    found: list[dict] = []
    for entry in typos:
        typo = entry["typo"]
        correction = entry["correction"]
        affected = [
            e["origin"]
            for e in entries
            if isinstance(e.get("origin"), str) and typo in e["origin"]
        ]
        if affected:
            found.append(
                {
                    "typo": typo,
                    "correction": correction,
                    "origins": sorted(set(affected)),
                }
            )
    return found


def _apply_typo_corrections_xlsx(xlsx_path: Path, typos_found: list[dict]) -> int:
    """Applique les corrections de coquilles directement dans le XLSX source.

    Parcourt toutes les feuilles et toutes les colonnes utilisées (C9 : plus
    uniquement les 3 premières) et remplace `typo` par `correction`.

    Args:
        xlsx_path: Chemin du fichier XLSX à corriger (modifié in-place).
        typos_found: Liste de {typo, correction, origins} issue de
            `detect_typos_in_origins`.

    Returns:
        Nombre de cellules modifiées.

    Raises:
        ImportError: Si openpyxl n'est pas installé.
    """
    if openpyxl is None:
        raise ImportError("openpyxl is required for XLSX functionality")
    wb = openpyxl.load_workbook(xlsx_path)
    modified = 0
    for entry in typos_found:
        for ws in wb.worksheets:
            for row in range(2, ws.max_row + 1):
                # C9 : parcourir TOUTES les colonnes utilisées (et non plus
                # uniquement les 3 premières).
                for col in range(1, ws.max_column + 1):
                    val = ws.cell(row=row, column=col).value
                    if isinstance(val, str) and entry["typo"] in val:
                        ws.cell(row=row, column=col).value = val.replace(
                            entry["typo"], entry["correction"]
                        )
                        modified += 1
    wb.save(xlsx_path)
    return modified


def step3_detect_typos(ctx: PipelineDropdownContext) -> None:
    """Détecte les coquilles source connues dans les Origins et propose correction.

    Args:
        ctx: Contexte du pipeline dropdown. Utilise `ctx.entries` et
            `ctx.xlsx_path` ; met à jour `ctx.typos_found` et
            `ctx.typos_corrected`.
    """
    step_banner(3, "Détection des coquilles source")
    typos = load_typos(scope="dropdown")
    if not typos:
        print("  Aucun dictionnaire de coquilles trouvé.")
        return
    ctx.typos_found = detect_typos_in_origins(ctx.entries, typos)
    if not ctx.typos_found:
        print("  ✅ Aucune coquille connue détectée dans les Origins.")
        return
    print(f"  {len(ctx.typos_found)} coquille(s) détectée(s) :")
    for i, entry in enumerate(ctx.typos_found, 1):
        print(f"  {i}. « {entry['typo']} » → « {entry['correction']} »")
    if ctx.dry_run:
        print("\n  [dry-run] Aucune correction appliquée.")
        return
    if confirm(ctx, "\n  Corriger le fichier XLSX source ?", default=True):
        count = _apply_typo_corrections_xlsx(ctx.xlsx_path, ctx.typos_found)
        ctx.typos_corrected = True
        print(f"  ✅ {count} cellule(s) corrigée(s).")
    else:
        print("  ⚠️  Corrections non appliquées.")


def step4_analyze_gap(ctx: PipelineDropdownContext) -> None:
    """Analyse l'écart par langue entre les Origins source et les traductions existantes.

    Args:
        ctx: Contexte du pipeline dropdown. Met à jour `ctx.gap_by_lang`
        ({lang: {missing_count, to_translate, total, existing}}).
    """
    step_banner(4, "Analyse de l'écart par langue")
    all_origins = {e["origin"] for e in ctx.entries if e.get("origin")}
    ctx.gap_by_lang = {}
    for lang_upper, translations in ctx.existing_translations.items():
        lang = lang_upper.lower()
        if lang == "en" or lang not in ctx.languages:
            continue
        missing = sorted(all_origins - set(translations.keys()))
        ctx.gap_by_lang[lang] = {
            "missing_count": len(missing),
            "to_translate": missing,
            "total": len(all_origins),
            "existing": len(translations),
        }
    for lang in ctx.missing_languages:
        ctx.gap_by_lang[lang] = {
            "missing_count": len(all_origins),
            "to_translate": sorted(all_origins),
            "total": len(all_origins),
            "existing": 0,
        }
    if not ctx.gap_by_lang:
        print("  Aucune langue à analyser.")
        return
    print("  | Langue | Existant | À traduire | Total |")
    print("  |---|---:|---:|---:|")
    for lang in sorted(ctx.gap_by_lang):
        g = ctx.gap_by_lang[lang]
        print(f"  | {lang} | {g['existing']} | {g['missing_count']} | {g['total']} |")
    total = sum(g["missing_count"] for g in ctx.gap_by_lang.values())
    print(f"\n  Total à traduire : {total} entrée(s) × langues.")


def _section_source_analysis_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 1 — Source (rapport d'analyse dropdown)."""
    L: list[str] = ["## 1. Source\n"]
    L.append(f"- Fichier : `{ctx.xlsx_path.name if ctx.xlsx_path else '?'}`")
    L.append(f"- Entrées (Origins) : {len(ctx.entries)}")
    present = [k.lower() for k in ctx.existing_translations if k.lower() != "en"]
    L.append(
        f"- Langues déjà présentes : "
        f"{', '.join(sorted(present)) if present else 'aucune'}"
    )
    L.append(
        f"- Langues manquantes : "
        f"{', '.join(ctx.missing_languages) if ctx.missing_languages else 'aucune'}\n"
    )
    return L


def _section_comparison_analysis_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 2 — Comparaison des sources (rapport d'analyse dropdown)."""
    L: list[str] = ["## 2. Comparaison des sources\n"]
    if ctx.comparison_added or ctx.comparison_removed:
        L.append(f"- Origins ajoutés : {len(ctx.comparison_added)}")
        L.append(f"- Origins supprimés : {len(ctx.comparison_removed)}")
        L.append(f"- Origins inchangés : {len(ctx.comparison_unchanged)}\n")
    else:
        L.append("_Pas de comparaison (pas de XLSX précédent)._\n")
    return L


def _section_coquilles_analysis_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 3 — Coquilles source (rapport d'analyse dropdown)."""
    L: list[str] = ["## 3. Coquilles source\n"]
    if ctx.typos_found:
        for entry in ctx.typos_found:
            L.append(f"- `{entry['typo']}` → `{entry['correction']}`")
        L.append(
            f"\nCorrections appliquées : "
            f"{'oui ✅' if ctx.typos_corrected else 'non'}\n"
        )
    else:
        L.append("_Aucune coquille connue détectée._\n")
    return L


def _section_gap_analysis_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 4 — Écart de traduction par langue (rapport d'analyse dropdown)."""
    L: list[str] = ["## 4. Écart de traduction par langue\n"]
    if ctx.gap_by_lang:
        L.append("| Langue | Existant | À traduire | Total |")
        L.append("|---|---:|---:|---:|")
        for lang in sorted(ctx.gap_by_lang):
            g = ctx.gap_by_lang[lang]
            L.append(
                f"| {lang} | {g.get('existing', 0)} | {g.get('missing_count', 0)} | "
                f"{g.get('total', 0)} |"
            )
    else:
        L.append("_Écart non calculé._")
    L.append("")
    return L


def _section_plan_action_analysis_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 5 — Plan d'action (rapport d'analyse dropdown)."""
    L: list[str] = ["## 5. Plan d'action\n"]
    L.append(f"- Provider : **{ctx.provider}**")
    L.append(f"- Langues à traiter : {', '.join(sorted(ctx.gap_by_lang.keys()))}")
    total = sum(g["missing_count"] for g in ctx.gap_by_lang.values())
    L.append(f"- Total à traduire : {total} entrée(s)")
    if ctx.retranslate_all:
        L.append("- ⚠️  Retraduction de toutes les langues (--retranslate-all)")
    if ctx.retranslate_langs:
        L.append(f"- Retraduction de : {', '.join(ctx.retranslate_langs)}")
    if ctx.no_cache:
        L.append("- Cache service désactivé (--no-cache)")
    L.append("")
    return L


def build_analysis_report_dropdown(ctx: PipelineDropdownContext) -> str:
    """Construit le rapport markdown consolidé des étapes 1-4 du pipeline dropdown.

    Assemble les 5 sections `_section_*` (Sprint 2 - tâche 17) en un seul
    document markdown.

    Args:
        ctx: Contexte du pipeline dropdown.

    Returns:
        Le rapport markdown (5 sections : Source, Comparaison, Coquilles,
        Écart, Plan d'action).
    """
    L: list[str] = []
    L.append("# Rapport d'analyse du pipeline dropdown\n")
    L.append(f"- Source : `{ctx.xlsx_path}`\n")

    L.extend(_section_source_analysis_dropdown(ctx))
    L.extend(_section_comparison_analysis_dropdown(ctx))
    L.extend(_section_coquilles_analysis_dropdown(ctx))
    L.extend(_section_gap_analysis_dropdown(ctx))
    L.extend(_section_plan_action_analysis_dropdown(ctx))
    return "\n".join(L)


def step5_report_and_confirm(ctx: PipelineDropdownContext) -> bool:
    """Produit le rapport consolidé et demande confirmation pour continuer.

    Args:
        ctx: Contexte du pipeline dropdown.

    Returns:
        True si l'utilisateur confirme (ou en non-interactif), False sinon
        (ou en dry-run).
    """
    step_banner(5, "Rapport consolidé + confirmation")
    print(build_analysis_report_dropdown(ctx))
    if ctx.dry_run:
        print("\n  [dry-run] Fin du parcours d'analyse — aucune exécution.")
        return False
    if not ctx.interactive:
        return True
    print("\n" + "─" * 70)
    print("  ÉTAPE CLÉ — Confirmer pour poursuivre vers la traduction (étapes 6-11).")
    print("─" * 70)
    return confirm(ctx, "  Poursuivre ?", default=False)


def step6_prepopulate(ctx: PipelineDropdownContext) -> Path | None:
    """Pré-peuple le dossier de sortie daté (sans confirmation redondante).

    Sprint 2 - tâche 23 : la confirmation « Lancer la traduction ? » était
    redondante avec celle de `step5_report_and_confirm` (« Poursuivre vers la
    traduction (étapes 6-11) ? »). Elle a été supprimée : step5 est désormais
    la seule [ÉTAPE CLÉ] avant la traduction.

    Si un dossier daté du même jour existe déjà et n'est pas vide, ajoute un
    suffixe `_run2`, `_run3`, ... pour ne pas écraser silencieusement l'export
    précédent (C6).

    Args:
        ctx: Contexte du pipeline dropdown.

    Returns:
        Le chemin du dossier daté créé, ou None en dry-run.
    """
    step_banner(6, "Pré-peuplement XLSX")
    if ctx.dry_run:
        print("  [dry-run] Pré-peuplement ignoré.")
        return None
    date_str = datetime.now().strftime("%Y_%m_%d")
    output_dir = _next_dated_dir(TRANSLATOR_DIR / "output", f"{date_str}_Dropdown")
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx.output_dir = output_dir
    print(f"  Dossier de sortie : {output_dir.name}")
    return output_dir


def _next_dated_dir(base: Path, base_name: str) -> Path:
    """Retourne un chemin unique sous `base` (suffixe _runN si écrasement)."""
    candidate = base / base_name
    if not candidate.exists() or not any(candidate.iterdir()):
        return candidate
    parts = base_name.rsplit("_", 1)
    head = parts[0] if len(parts) == 2 else base_name
    tail = parts[1] if len(parts) == 2 else ""
    n = 2
    while True:
        name = f"{head}_run{n}" + (f"_{tail}" if tail else "")
        candidate = base / name
        if not candidate.exists() or not any(candidate.iterdir()):
            return candidate
        n += 1


def _translate_dropdown_batch(entries, lang, existing_translations, **kwargs):
    """Traduit les entries via le vrai moteur (mode_translate_dropdowns).

    Args:
        entries: Liste d'entrées dropdown à traduire.
        lang: Code langue cible.
        existing_translations: Dict {origin: traduction} déjà connu (cache col B).
        **kwargs: Accepté pour compatibilité (ignoré).

    Returns:
        Dict {origin: traduction} produit par le moteur de traduction.
    """
    """Traduit les entries via le vrai moteur (mode_translate_dropdowns)."""
    from modes.mode_translate_dropdowns import _translate_dropdown_entries_batch

    return _translate_dropdown_entries_batch(entries, lang, existing_translations)


def step7_translate(ctx: PipelineDropdownContext) -> None:
    """Traduit les Origins manquants en réutilisant le cache colonne B.

    Args:
        ctx: Contexte du pipeline dropdown. Utilise `ctx.gap_by_lang`,
            `ctx.entries`, `ctx.existing_translations` ; met à jour
            `ctx.translations_by_lang` puis appelle `_write_dropdown_output`.
    """
    step_banner(7, "Traduction")
    if ctx.dry_run:
        print("  [dry-run] Traduction non lancée.")
        return
    if not ctx.gap_by_lang:
        print("  Aucune langue à traduire.")
        return

    # Configurer le singleton Config via le context manager `override_config`
    # qui restaure l'ancienne valeur dans un `finally` — y compris si la
    # traduction lève (C2 : singleton non restauré sur exception).
    from pipeline_common import override_config

    provider = ctx.provider if ctx.provider != "hybride" else "google"
    output_dir = ctx.output_dir or (TRANSLATOR_DIR / "output")

    print(f"  Provider : {provider}")
    with override_config(
        source_file=str(ctx.xlsx_path),
        output_dir=str(output_dir),
        provider=provider,
        no_cache=ctx.no_cache,
    ):
        for lang in sorted(ctx.gap_by_lang):
            gap = ctx.gap_by_lang[lang]
            if gap.get("missing_count", 0) == 0 and lang not in ctx.missing_languages:
                if not ctx.retranslate_all and lang not in ctx.retranslate_langs:
                    print(f"  {lang.upper()}: ✅ déjà complète (cache col B)")
                    continue
            print(
                f"  {lang.upper()}: traduction de {gap.get('missing_count', 0)} entrée(s)..."
            )
            if ctx.retranslate_all or lang in ctx.retranslate_langs:
                entries_to_translate = list(ctx.entries)
                existing = {}
            else:
                entries_to_translate = [
                    e
                    for e in ctx.entries
                    if e.get("origin") in gap.get("to_translate", [])
                ]
                existing = ctx.existing_translations.get(lang.upper(), {})
            result = _translate_dropdown_batch(entries_to_translate, lang, existing)
            ctx.translations_by_lang[lang] = result
            print(f"    ✅ {len(entries_to_translate)} traduction(s) produites.")

        # Écriture des fichiers de sortie (JSON/XLSX) dans ctx.output_dir
        _write_dropdown_output(ctx)


def _write_dropdown_output(ctx: PipelineDropdownContext) -> None:
    """Écrit les fichiers de sortie (JSON/XLSX) dans ctx.output_dir.

    Format JSON : un fichier `dropdown_{lang}.json` par langue, groupé par
    contexte, fusionnant traductions produites et cache colonne B.
    Format XLSX : un fichier multi-feuilles via `core.io_xlsx.save_dropdown_xlsx`.
    """
    if ctx.dry_run:
        print("  [dry-run] Écriture des fichiers ignorée.")
        return
    if not ctx.output_dir:
        print("  ⚠️  Pas de dossier de sortie — écriture ignorée.")
        return

    source_file = ctx.xlsx_path.name if ctx.xlsx_path else "dropdown.xlsx"
    fmt = ctx.output_format
    if fmt == "auto":
        # Sprint 2 - tâche 27 : auto déduit le format depuis l'extension du
        # fichier source (.xlsx -> xlsx, sinon json). Auparavant auto résolvait
        # toujours en json (I12).
        src_ext = ctx.xlsx_path.suffix.lower() if ctx.xlsx_path else ""
        fmt = "xlsx" if src_ext in (".xlsx", ".xls") else "json"

    # Indexer le contexte de chaque origin pour regrouper les traductions
    context_by_origin: dict[str, str] = {
        e.get("origin", ""): e.get("context", "") for e in ctx.entries
    }

    if fmt == "json":
        for lang in ctx.languages:
            merged: dict[str, str] = dict(
                ctx.existing_translations.get(lang.upper(), {})
            )
            merged.update(ctx.translations_by_lang.get(lang, {}))
            contexts: dict[str, dict[str, str]] = {}
            for origin, translation in merged.items():
                ctx_name = context_by_origin.get(origin, "")
                contexts.setdefault(ctx_name, {})[origin] = translation
            payload = {
                "metadata": {
                    "language": lang.upper(),
                    "source_file": source_file,
                    "total_entries": len(merged),
                },
                "contexts": contexts,
            }
            out_path = ctx.output_dir / f"dropdown_{lang}.json"
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(
                f"  {lang.upper()}: {out_path.name} écrit " f"({len(merged)} entrées)."
            )
    elif fmt == "xlsx":
        from core.config import LANGUAGES as _LANGS
        from core.io_xlsx import save_dropdown_xlsx

        translations: dict[str, dict[str, str]] = {}
        for lang in ctx.languages:
            merged_lang: dict[str, str] = dict(
                ctx.existing_translations.get(lang.upper(), {})
            )
            merged_lang.update(ctx.translations_by_lang.get(lang, {}))
            translations[lang] = merged_lang
        out_path = ctx.output_dir / "dropdown_translations.xlsx"
        save_dropdown_xlsx(ctx.entries, translations, out_path, _LANGS)
        print(f"  XLSX écrit : {out_path.name}")
    else:
        print(f"  ⚠️  Format de sortie inconnu : {ctx.output_format}")


def step8_reorder(ctx: PipelineDropdownContext) -> None:
    """Réordonne les fichiers de sortie selon l'ordre des Origins source.

    Pour chaque fichier `dropdown_{lang}.json` dans `ctx.output_dir`, recharge
    le JSON, réordonne les entrées de chaque contexte selon l'ordre des
    Origins de `ctx.entries`, et réécrit le fichier (C4 : implementation
    réelle — l'ancienne version n'écrivait rien).
    """
    step_banner(8, "Réordonnancement auto")
    if ctx.dry_run:
        print("  [dry-run] Réordonnancement non appliqué.")
        return
    if not ctx.output_dir:
        print("  ⚠️  Pas de dossier de sortie — étape ignorée.")
        return
    source_origins = [e["origin"] for e in ctx.entries if e.get("origin")]
    print(f"  Ordre source : {len(source_origins)} Origins")
    for lang in ctx.languages:
        out_path = ctx.output_dir / f"dropdown_{lang}.json"
        if not out_path.exists():
            print(f"  {lang.upper()}: fichier absent — ignoré.")
            continue
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"  {lang.upper()}: ⚠️  lecture impossible ({e}).")
            continue
        contexts = payload.get("contexts") if isinstance(payload, dict) else None
        if not isinstance(contexts, dict):
            print(f"  {lang.upper()}: structure inattendue — ignoré.")
            continue
        ordered_contexts: dict[str, dict[str, str]] = {}
        for ctx_name, entries in contexts.items():
            if not isinstance(entries, dict):
                ordered_contexts[ctx_name] = entries
                continue
            ordered: dict[str, str] = {}
            for origin in source_origins:
                if origin in entries:
                    ordered[origin] = entries[origin]
            # Clés extras (présentes dans le fichier, pas dans la source) → à la fin
            for origin, value in entries.items():
                if origin not in ordered:
                    ordered[origin] = value
            ordered_contexts[ctx_name] = ordered
        payload["contexts"] = ordered_contexts
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"  {lang.upper()}: réordonné selon la source "
            f"({len(source_origins)} Origins)."
        )


def validate_dropdown(ctx: PipelineDropdownContext, output_dir: Path) -> dict | None:
    """Valide les fichiers de sortie dropdown.

    Args:
        ctx: Contexte du pipeline dropdown.
        output_dir: Dossier de sortie contenant les fichiers `dropdown_<lang>.json`.
            Conservé pour signature homogène avec le pipeline JSON ; la
            validation se fait sur `ctx.existing_translations` (cache col B).

    Returns:
        Dict {lang: {missing: [], empty: [], untranslated: []}}, ou None en
        dry-run.
    """
    step_banner(9, "Validation dropdown")
    if ctx.dry_run:
        print("  [dry-run] Validation non exécutée.")
        return None

    all_origins = {e["origin"] for e in ctx.entries if e.get("origin")}
    results = {}

    for lang in ctx.languages:
        lang_upper = lang.upper()
        translations = ctx.existing_translations.get(lang_upper, {})

        missing = sorted(all_origins - set(translations.keys()))
        empty = sorted(
            k
            for k, v in translations.items()
            if not v or (isinstance(v, str) and v.strip() == "")
        )
        untranslated = sorted(
            k
            for k in all_origins & set(translations.keys())
            if translations[k] == k and len(k) > 3
        )

        results[lang] = {
            "missing": missing,
            "empty": empty,
            "untranslated": untranslated,
        }

        status = "✅" if not missing and not empty else "⚠️"
        print(
            f"  {lang_upper}: {len(translations)} traductions, "
            f"{len(missing)} manquantes, {len(empty)} vides {status}"
        )

    total_missing = sum(len(r["missing"]) for r in results.values())
    total_empty = sum(len(r["empty"]) for r in results.values())
    if total_missing == 0 and total_empty == 0:
        print("\n  ✅ Toutes les traductions sont valides.")
    else:
        print(f"\n  ⚠️  {total_missing} manquantes, {total_empty} vides.")

    return results


def detect_misalignments_dropdown(
    ctx: PipelineDropdownContext,
) -> dict:
    """Détecte les mésalignements intra-langue restreints au sein d'un même contexte.

    Pour chaque Origin partagé par plusieurs contextes, compare les traductions
    au sein d'un même contexte. Signale les divergences (Jaccard=0 sur les tokens).

    Analyse les traductions **fraîches** produites par `step7_translate` (C3 :
    l'ancienne version lisait `ctx.existing_translations` — cache stale — au
    lieu de fusionner avec `ctx.translations_by_lang`).

    Args:
        ctx: Contexte du pipeline dropdown (entries, existing_translations,
            translations_by_lang).

    Returns:
        Dict {lang: [mésalignement, ...]} où chaque mésalignement est un dict
        `{origin, translations}`. Vide si aucune divergence détectée.
    """
    step_banner(10, "Détection mésalignements intra-langue")
    if ctx.dry_run:
        print("  [dry-run] Mésalignements non détectés.")
        return {}

    from collections import defaultdict

    misalignments = {}
    for lang in ctx.languages:
        # Fusionner cache existant (colonne B) et traductions fraîches (C3).
        merged = {
            **ctx.existing_translations.get(lang.upper(), {}),
            **ctx.translations_by_lang.get(lang, {}),
        }
        lang_mis = []

        # Grouper par origin pour trouver les divergences
        origin_translations = defaultdict(set)
        for e in ctx.entries:
            origin = e.get("origin")
            context = e.get("context")
            if origin and context:
                trans = merged.get(origin, "")
                if trans:
                    origin_translations[origin].add(trans)

        # Un même Origin avec des traductions divergentes (tokens disjoints)
        for origin, trans_set in origin_translations.items():
            if len(trans_set) < 2:
                continue
            trans_list = list(trans_set)
            has_divergence = False
            for i in range(len(trans_list)):
                for j in range(i + 1, len(trans_list)):
                    tokens_i = set(trans_list[i].lower().split())
                    tokens_j = set(trans_list[j].lower().split())
                    if not tokens_i & tokens_j:
                        has_divergence = True
                        break
                if has_divergence:
                    break
            if has_divergence:
                lang_mis.append({"origin": origin, "translations": list(trans_set)})

        if lang_mis:
            misalignments[lang] = lang_mis
            print(f"  {lang.upper()}: {len(lang_mis)} mésalignement(s) potentiel(s).")
        else:
            print(f"  {lang.upper()}: ✅ aucun mésalignement.")

    return misalignments


def _section_source_final_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 1 — Source (rapport final dropdown)."""
    return [
        "## 1. Source\n",
        f"- Fichier : `{ctx.xlsx_path.name if ctx.xlsx_path else '?'}`",
        f"- Entrées : {len(ctx.entries)}",
        f"- Langues traitées : {', '.join(ctx.languages)}\n",
    ]


def _section_comparison_final_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 2 — Comparaison (rapport final dropdown)."""
    L: list[str] = ["## 2. Comparaison\n"]
    if ctx.comparison_added or ctx.comparison_removed:
        L.append(f"- Ajoutés : {len(ctx.comparison_added)}")
        L.append(f"- Supprimés : {len(ctx.comparison_removed)}")
    else:
        L.append("_Pas de comparaison._")
    L.append("")
    return L


def _section_coquilles_final_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 3 — Coquilles (rapport final dropdown)."""
    L: list[str] = ["## 3. Coquilles\n"]
    if ctx.typos_found:
        L.append(f"- {len(ctx.typos_found)} coquille(s) détectée(s)")
        L.append(
            f"- Corrections appliquées : {'oui' if ctx.typos_corrected else 'non'}"
        )
    else:
        L.append("_Aucune._")
    L.append("")
    return L


def _section_gap_final_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 4 — Écart (rapport final dropdown)."""
    L: list[str] = ["## 4. Écart\n"]
    if ctx.gap_by_lang:
        L.append("| Langue | Existant | À traduire | Total |")
        L.append("|---|---:|---:|---:|")
        for lang in sorted(ctx.gap_by_lang):
            g = ctx.gap_by_lang[lang]
            L.append(
                f"| {lang} | {g.get('existing', 0)} | {g.get('missing_count', 0)} | "
                f"{g.get('total', 0)} |"
            )
    L.append("")
    return L


def _section_plan_final_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 5 — Plan d'action (rapport final dropdown)."""
    total = sum(g.get("missing_count", 0) for g in ctx.gap_by_lang.values())
    return [
        "## 5. Plan d'action\n",
        f"- Provider : {ctx.provider}",
        f"- Total traduit : {total}",
        "",
    ]


def _section_translation_final_dropdown(
    ctx: PipelineDropdownContext, output_dir: Path
) -> list[str]:
    """Section 6 — Traduction (rapport final dropdown)."""
    return [
        "## 6. Traduction\n",
        f"- Dossier de sortie : `{output_dir.name if output_dir else 'N/A'}`",
        "",
    ]


def _section_validation_final_dropdown(
    ctx: PipelineDropdownContext, validation_results: dict
) -> list[str]:
    """Section 7 — Validation (rapport final dropdown)."""
    L: list[str] = ["## 7. Validation\n"]
    if validation_results:
        L.append("| Langue | Manquantes | Vides | Non traduites |")
        L.append("|---|---:|---:|---:|")
        for lang in sorted(validation_results):
            r = validation_results[lang]
            L.append(
                f"| {lang} | {len(r['missing'])} | {len(r['empty'])} | "
                f"{len(r['untranslated'])} |"
            )
    else:
        L.append("_Validation non exécutée._")
    L.append("")
    return L


def _section_misalignments_final_dropdown(
    ctx: PipelineDropdownContext, misalignments: dict
) -> list[str]:
    """Section 8 — Mésalignements (rapport final dropdown)."""
    total_mis = sum(len(v) for v in misalignments.values()) if misalignments else 0
    return [
        "## 8. Mésalignements\n",
        f"**{total_mis} mésalignement(s)** détecté(s).\n",
        "",
    ]


def _section_order_final_dropdown(ctx: PipelineDropdownContext) -> list[str]:
    """Section 9 — Ordre (rapport final dropdown)."""
    return [
        "## 9. Ordre\n",
        "Ordre des Origins source respecté (étape 8).",
        "",
    ]


def build_final_report_dropdown(
    ctx: PipelineDropdownContext,
    output_dir: Path,
    validation_results: dict,
    misalignments: dict,
) -> str:
    """Construit le rapport markdown final du pipeline dropdown.

    Assemble les 9 sections `_section_*` (Sprint 2 - tâche 17) en un seul
    document markdown.

    Args:
        ctx: Contexte du pipeline dropdown.
        output_dir: Dossier de sortie des fichiers traduits.
        validation_results: Résultat de `validate_dropdown` (ou None).
        misalignments: Résultat de `detect_misalignments_dropdown` (ou {}).

    Returns:
        Le rapport markdown assemblé (9 sections).
    """
    L: list[str] = []
    L.append("# Rapport final du pipeline dropdown COP\n")
    L.append(f"- Source : `{ctx.xlsx_path}`\n")

    L.extend(_section_source_final_dropdown(ctx))
    L.extend(_section_comparison_final_dropdown(ctx))
    L.extend(_section_coquilles_final_dropdown(ctx))
    L.extend(_section_gap_final_dropdown(ctx))
    L.extend(_section_plan_final_dropdown(ctx))
    L.extend(_section_translation_final_dropdown(ctx, output_dir))
    L.extend(_section_validation_final_dropdown(ctx, validation_results))
    L.extend(_section_misalignments_final_dropdown(ctx, misalignments))
    L.extend(_section_order_final_dropdown(ctx))
    return "\n".join(L)


def step11_final_report_dropdown(
    ctx: PipelineDropdownContext,
    output_dir: Path,
    validation_results: dict,
    misalignments: dict,
) -> Path | None:
    """Génère le rapport final consolidé et l'écrit dans `doc/`.

    Args:
        ctx: Contexte du pipeline dropdown.
        output_dir: Dossier de sortie des fichiers traduits.
        validation_results: Résultat de `validate_dropdown` (ou None).
        misalignments: Résultat de `detect_misalignments_dropdown` (ou {}).

    Returns:
        Chemin du fichier markdown écrit, ou None en dry-run.
    """
    step_banner(11, "Rapport consolidé final")
    if ctx.dry_run:
        print("  [dry-run] Rapport final non écrit.")
        return None

    report = build_final_report_dropdown(
        ctx, output_dir, validation_results, misalignments
    )
    date_str = datetime.now().strftime("%Y_%m_%d")
    doc_dir = REPO_ROOT / "doc"
    doc_dir.mkdir(exist_ok=True)
    path = doc_dir / f"{date_str}_Pipeline_Dropdown_Report.md"
    path.write_text(report, encoding="utf-8")
    print(f"  Rapport final écrit : {path}")
    return path


def run_pipeline_dropdown(args: argparse.Namespace) -> int:
    """Point d'entrée du pipeline dropdown : enchaîne les étapes 1-11.

    Args:
        args: Namespace argparse (source, prev_source, languages, provider,
            dry_run, yes, format, retranslate_all, retranslate, no_cache).

    Returns:
        Code de sortie : 0 (succès ou arrêt utilisateur), 2 (FileNotFoundError),
        3 (erreur durant la traduction).
    """
    ctx = PipelineDropdownContext(
        dry_run=getattr(args, "dry_run", False),
        provider=getattr(args, "provider", "hybride"),
        interactive=not getattr(args, "yes", False)
        and not getattr(args, "dry_run", False),
        report_path=getattr(args, "report", None),
        output_format=getattr(args, "format", "auto"),
        retranslate_all=getattr(args, "retranslate_all", False),
        no_cache=getattr(args, "no_cache", False),
    )
    if getattr(args, "source", None):
        ctx.xlsx_path = Path(args.source)
    if getattr(args, "prev_source", None):
        ctx.prev_xlsx_path = Path(args.prev_source)
    if getattr(args, "languages", None):
        ctx.languages = [lg.strip() for lg in args.languages.split(",") if lg.strip()]
    if getattr(args, "retranslate", None):
        ctx.retranslate_langs = [
            lg.strip() for lg in args.retranslate.split(",") if lg.strip()
        ]

    print("🚀 Pipeline dropdown — COP Translation")
    logger.info(
        "   Provider : %s | Langues : %s",
        ctx.provider,
        ", ".join(ctx.languages),
    )
    if ctx.dry_run:
        logger.info("   Mode : dry-run")
    if ctx.retranslate_all:
        logger.info("   Retraduction : toutes les langues (--retranslate-all)")
    if ctx.retranslate_langs:
        logger.info("   Retraduction : %s", ", ".join(ctx.retranslate_langs))
    if ctx.no_cache:
        logger.info("   Cache service : désactivé (--no-cache)")

    try:
        step1_detect_source(ctx)
        step2_compare_sources(ctx)
        step3_detect_typos(ctx)
        step4_analyze_gap(ctx)
        confirmed = step5_report_and_confirm(ctx)
    except FileNotFoundError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 2

    if ctx.dry_run:
        # Dry-run unifié : simuler les étapes 6-11 sans rien exécuter.
        # Chaque étape a sa propre garde `dry_run` qui affiche un message et skippe.
        # C12 : plus de Path("/dev/null") — on utilise le dossier output/ existant
        # (les étapes dry-run n'accèdent pas au chemin).
        simulated_output = ctx.output_dir or (TRANSLATOR_DIR / "output")
        step6_prepopulate(ctx)  # skippé (retourne None)
        step7_translate(ctx)  # skippé
        step8_reorder(ctx)  # skippé
        validate_dropdown(ctx, simulated_output)  # skippé
        detect_misalignments_dropdown(ctx)  # skippé
        step11_final_report_dropdown(ctx, simulated_output, None, {})  # skippé
        print("\n⏹  [dry-run] Simulation complète — aucune exécution.")
        return 0

    if not confirmed:
        print("\n⏹  Parcours arrêté (confirmation refusée).")
        return 0

    output_dir = step6_prepopulate(ctx)
    if not output_dir:
        print("\n⏹  Traduction annulée à l'étape 6.")
        return 0

    try:
        step7_translate(ctx)
        step8_reorder(ctx)
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ Erreur durant la traduction : {e}", file=sys.stderr)
        return 3

    # Phase 3 — Validation + mésalignements + rapport final
    validation_results = validate_dropdown(ctx, output_dir)
    misalignments = detect_misalignments_dropdown(ctx)
    step11_final_report_dropdown(ctx, output_dir, validation_results, misalignments)

    print("\n✅ Pipeline dropdown terminé.")
    return 0


def main() -> None:
    args = build_parser_dropdown().parse_args()
    sys.exit(run_pipeline_dropdown(args))


if __name__ == "__main__":
    main()
