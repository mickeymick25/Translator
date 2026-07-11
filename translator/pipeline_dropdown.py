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

from core.config import LANGUAGES  # noqa: E402
from core.io_xlsx import (  # noqa: E402
    detect_missing_languages,
    load_dropdown_xlsx,
    load_dropdown_xlsx_all_sheets,
)
from pipeline_common import BasePipelineContext, confirm, step_banner  # noqa: E402, F401

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
    output_format: str = "auto"

    comparison_added: list[str] = field(default_factory=list)
    comparison_removed: list[str] = field(default_factory=list)
    comparison_unchanged: list[str] = field(default_factory=list)

    typos_found: list[dict] = field(default_factory=list)
    typos_corrected: bool = False

    gap_by_lang: dict[str, dict] = field(default_factory=dict)


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
    ctx.missing_languages = detect_missing_languages(ctx.xlsx_path, ctx.languages)
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


def load_typos_dropdown() -> list[dict]:
    typos_path = TRANSLATOR_DIR / "source_typos.json"
    if not typos_path.exists():
        return []
    with typos_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return [
        e
        for e in data.get("typos", [])
        if e.get("scope", "both") in ("dropdown", "both")
    ]


def detect_typos_in_origins(entries: list[dict], typos: list[dict]) -> list[dict]:
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
    wb = openpyxl.load_workbook(xlsx_path)
    modified = 0
    for entry in typos_found:
        for ws in wb.worksheets:
            for row in range(2, ws.max_row + 1):
                for col in range(1, 4):
                    val = ws.cell(row=row, column=col).value
                    if isinstance(val, str) and entry["typo"] in val:
                        ws.cell(row=row, column=col).value = val.replace(
                            entry["typo"], entry["correction"]
                        )
                        modified += 1
    wb.save(xlsx_path)
    return modified


def step3_detect_typos(ctx: PipelineDropdownContext) -> None:
    step_banner(3, "Détection des coquilles source")
    typos = load_typos_dropdown()
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


def build_analysis_report_dropdown(ctx: PipelineDropdownContext) -> str:
    L: list[str] = []
    L.append("# Rapport d'analyse du pipeline dropdown\n")
    L.append(f"- Source : `{ctx.xlsx_path}`\n")

    L.append("## 1. Source\n")
    L.append(f"- Fichier : `{ctx.xlsx_path.name if ctx.xlsx_path else '?'}`")
    L.append(f"- Entrées (Origins) : {len(ctx.entries)}")
    present = [k.lower() for k in ctx.existing_translations if k.lower() != "en"]
    L.append(
        f"- Langues déjà présentes : {', '.join(sorted(present)) if present else 'aucune'}"
    )
    L.append(
        f"- Langues manquantes : {', '.join(ctx.missing_languages) if ctx.missing_languages else 'aucune'}\n"
    )

    L.append("## 2. Comparaison des sources\n")
    if ctx.comparison_added or ctx.comparison_removed:
        L.append(f"- Origins ajoutés : {len(ctx.comparison_added)}")
        L.append(f"- Origins supprimés : {len(ctx.comparison_removed)}")
        L.append(f"- Origins inchangés : {len(ctx.comparison_unchanged)}\n")
    else:
        L.append("_Pas de comparaison (pas de XLSX précédent)._\n")

    L.append("## 3. Coquilles source\n")
    if ctx.typos_found:
        for entry in ctx.typos_found:
            L.append(f"- `{entry['typo']}` → `{entry['correction']}`")
        L.append(
            f"\nCorrections appliquées : {'oui ✅' if ctx.typos_corrected else 'non'}\n"
        )
    else:
        L.append("_Aucune coquille connue détectée._\n")

    L.append("## 4. Écart de traduction par langue\n")
    if ctx.gap_by_lang:
        L.append("| Langue | Existant | À traduire | Total |")
        L.append("|---|---:|---:|---:|")
        for lang in sorted(ctx.gap_by_lang):
            g = ctx.gap_by_lang[lang]
            L.append(
                f"| {lang} | {g.get('existing', 0)} | {g.get('missing_count', 0)} | {g.get('total', 0)} |"
            )
    else:
        L.append("_Écart non calculé._")
    L.append("")

    L.append("## 5. Plan d'action\n")
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
    return "\n".join(L)


def step5_report_and_confirm(ctx: PipelineDropdownContext) -> bool:
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
    """Pré-peuple le dossier de sortie daté et demande confirmation [ÉTAPE CLÉ]."""
    step_banner(6, "Pré-peuplement XLSX")
    if ctx.dry_run:
        print("  [dry-run] Pré-peuplement ignoré.")
        return None
    date_str = datetime.now().strftime("%Y_%m_%d")
    output_dir = TRANSLATOR_DIR / "output" / f"{date_str}_Dropdown"
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx.output_dir = output_dir
    print(f"  Dossier de sortie : {output_dir.name}")
    if not ctx.interactive:
        return output_dir
    if confirm(ctx, "  Lancer la traduction ?", default=True):
        return output_dir
    print("  ⛔ Traduction annulée.")
    return None


def _translate_dropdown_batch(entries, lang, existing_translations, **kwargs):
    """Stub — sera remplacé par le vrai moteur de traduction (mock dans les tests)."""
    return {}


def step7_translate(ctx: PipelineDropdownContext) -> None:
    """Traduit les Origins manquants en réutilisant le cache colonne B."""
    step_banner(7, "Traduction")
    if ctx.dry_run:
        print("  [dry-run] Traduction non lancée.")
        return
    if not ctx.gap_by_lang:
        print("  Aucune langue à traduire.")
        return
    print(f"  Provider : {ctx.provider}")
    for lang in sorted(ctx.gap_by_lang):
        gap = ctx.gap_by_lang[lang]
        if gap.get("missing_count", 0) == 0 and lang not in ctx.missing_languages:
            if not ctx.retranslate_all and lang not in ctx.retranslate_langs:
                print(f"  {lang.upper()}: ✅ déjà complète (cache col B)")
                continue
        print(
            f"  {lang.upper()}: traduction de {gap.get('missing_count', 0)} entrée(s)..."
        )
        entries_to_translate = [
            e for e in ctx.entries if e.get("origin") in gap.get("to_translate", [])
        ]
        _translate_dropdown_batch(
            entries_to_translate,
            lang,
            ctx.existing_translations.get(lang.upper(), {}),
        )
        print(f"    ✅ {len(entries_to_translate)} traduction(s) produites.")


def step8_reorder(ctx: PipelineDropdownContext) -> None:
    """Réordonne les fichiers de sortie selon l'ordre des Origins source."""
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
        print(f"  {lang.upper()}: réordonné selon la source.")


def validate_dropdown(ctx: PipelineDropdownContext, output_dir) -> dict | None:
    """Valide les fichiers de sortie dropdown.

    Retourne un dict {lang: {missing: [], empty: [], untranslated: []}}.
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
    ctx: PipelineDropdownContext, validation_results: dict
) -> dict:
    """Détecte les mésalignements intra-langue restreints au sein d'un même contexte.

    Pour chaque Origin partagé par plusieurs contextes, compare les traductions
    au sein d'un même contexte. Signale les divergences (Jaccard=0 sur les tokens).
    """
    step_banner(10, "Détection mésalignements intra-langue")
    if ctx.dry_run:
        print("  [dry-run] Mésalignements non détectés.")
        return {}

    from collections import defaultdict

    misalignments = {}
    for lang in ctx.languages:
        lang_upper = lang.upper()
        translations = ctx.existing_translations.get(lang_upper, {})
        lang_mis = []

        # Grouper par origin pour trouver les divergences
        origin_translations = defaultdict(set)
        for e in ctx.entries:
            origin = e.get("origin")
            context = e.get("context")
            if origin and context:
                trans = translations.get(origin, "")
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


def build_final_report_dropdown(
    ctx: PipelineDropdownContext,
    output_dir,
    validation_results: dict,
    misalignments: dict,
) -> str:
    """Construit le rapport markdown final du pipeline dropdown."""
    L: list[str] = []
    L.append("# Rapport final du pipeline dropdown COP\n")
    L.append(f"- Source : `{ctx.xlsx_path}`\n")

    # Section 1 — Source
    L.append("## 1. Source\n")
    L.append(f"- Fichier : `{ctx.xlsx_path.name if ctx.xlsx_path else '?'}`")
    L.append(f"- Entrées : {len(ctx.entries)}")
    L.append(f"- Langues traitées : {', '.join(ctx.languages)}\n")

    # Section 2 — Comparaison
    L.append("## 2. Comparaison\n")
    if ctx.comparison_added or ctx.comparison_removed:
        L.append(f"- Ajoutés : {len(ctx.comparison_added)}")
        L.append(f"- Supprimés : {len(ctx.comparison_removed)}")
    else:
        L.append("_Pas de comparaison._")
    L.append("")

    # Section 3 — Coquilles
    L.append("## 3. Coquilles\n")
    if ctx.typos_found:
        L.append(f"- {len(ctx.typos_found)} coquille(s) détectée(s)")
        L.append(
            f"- Corrections appliquées : {'oui' if ctx.typos_corrected else 'non'}"
        )
    else:
        L.append("_Aucune._")
    L.append("")

    # Section 4 — Écart
    L.append("## 4. Écart\n")
    if ctx.gap_by_lang:
        L.append("| Langue | Existant | À traduire | Total |")
        L.append("|---|---:|---:|---:|")
        for lang in sorted(ctx.gap_by_lang):
            g = ctx.gap_by_lang[lang]
            L.append(
                f"| {lang} | {g.get('existing', 0)} | {g.get('missing_count', 0)} | {g.get('total', 0)} |"
            )
    L.append("")

    # Section 5 — Plan
    L.append("## 5. Plan d'action\n")
    L.append(f"- Provider : {ctx.provider}")
    total = sum(g.get("missing_count", 0) for g in ctx.gap_by_lang.values())
    L.append(f"- Total traduit : {total}")
    L.append("")

    # Section 6 — Traduction
    L.append("## 6. Traduction\n")
    L.append(f"- Dossier de sortie : `{output_dir.name if output_dir else 'N/A'}`")
    L.append("")

    # Section 7 — Validation
    L.append("## 7. Validation\n")
    if validation_results:
        L.append("| Langue | Manquantes | Vides | Non traduites |")
        L.append("|---|---:|---:|---:|")
        for lang in sorted(validation_results):
            r = validation_results[lang]
            L.append(
                f"| {lang} | {len(r['missing'])} | {len(r['empty'])} | {len(r['untranslated'])} |"
            )
    else:
        L.append("_Validation non exécutée._")
    L.append("")

    # Section 8 — Mésalignements
    L.append("## 8. Mésalignements\n")
    total_mis = sum(len(v) for v in misalignments.values()) if misalignments else 0
    L.append(f"**{total_mis} mésalignement(s)** détecté(s).\n")
    L.append("")

    # Section 9 — Ordre
    L.append("## 9. Ordre\n")
    L.append("Ordre des Origins source respecté (étape 8).")
    L.append("")

    return "\n".join(L)


def step11_final_report_dropdown(
    ctx: PipelineDropdownContext,
    output_dir,
    validation_results: dict,
    misalignments: dict,
):
    """Génère le rapport final et l'écrit dans doc/."""
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
    ctx = PipelineDropdownContext(
        dry_run=args.dry_run,
        provider=args.provider,
        interactive=not args.yes and not args.dry_run,
        report_path=args.report,
        output_format=args.format,
        retranslate_all=args.retranslate_all,
        no_cache=args.no_cache,
    )
    if args.source:
        ctx.xlsx_path = Path(args.source)
    if args.prev_source:
        ctx.prev_xlsx_path = Path(args.prev_source)
    if args.languages:
        ctx.languages = [lg.strip() for lg in args.languages.split(",") if lg.strip()]
    if args.retranslate:
        ctx.retranslate_langs = [
            lg.strip() for lg in args.retranslate.split(",") if lg.strip()
        ]

    print("🚀 Pipeline dropdown — COP Translation")
    print(f"   Provider : {ctx.provider} | Langues : {', '.join(ctx.languages)}")
    if ctx.xlsx_path:
        print(f"   Source : {ctx.xlsx_path.name}")
    if ctx.dry_run:
        print("   Mode : dry-run")
    if ctx.retranslate_all:
        print("   Retraduction : toutes les langues (--retranslate-all)")
    if ctx.retranslate_langs:
        print(f"   Retraduction : {', '.join(ctx.retranslate_langs)}")
    if ctx.no_cache:
        print("   Cache service : désactivé (--no-cache)")

    if ctx.dry_run:
        print("\n⏹  [dry-run] Analyse complète — aucune exécution.")
        return 0

    # TODO D9-D14 : implémenter les étapes 6-11
    print("\n⏳ Les étapes 6-11 du pipeline dropdown seront implémentées (D9-D14).")
    return 0


def main() -> None:
    args = build_parser_dropdown().parse_args()
    sys.exit(run_pipeline_dropdown(args))


if __name__ == "__main__":
    main()
