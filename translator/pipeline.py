#!/usr/bin/env python3
"""Pipeline orchestré de traduction COP.

Enchaîne en une seule commande le parcours complet de production des
fichiers traduits à partir d'une nouvelle source EN :

  Étape 1  — Détection auto de la source (dernier *_Import) + précédente
  Étape 2  — Comparaison des deux sources (ajouts/suppressions/modifications)
  Étape 3  — Détection des coquilles source connues + correction interactive
  Étape 4  — Analyse de l'écart entre le dernier export et la nouvelle source
  Étape 5  — Rapport consolidé + confirmation interactive  [ÉTAPE CLÉ]

Les étapes 6-11 (exécution, validation, rapport final) seront ajoutées dans
les phases 2 et 3 (voir doc/2026_07_08_Pipeline_Orchestre_Analyse.md).

Usage:
    # Run complet interactif
    python translator/pipeline.py

    # Dry-run (rapport sans exécution ni confirmation bloquante)
    python translator/pipeline.py --dry-run

    # Langues spécifiques + provider forcé
    python translator/pipeline.py --languages fr,de --provider ollama

    # Override des sources détectées
    python translator/pipeline.py --source path/to/en10.json --prev-source path/to/en9.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ─── sys.path setup ──────────────────────────────────────────────────
# pipeline.py vit dans translator/, mais compare_sources.py et
# analyze_translation_gap.py vivent à la racine du dépôt (un niveau au-dessus).
REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSLATOR_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSLATOR_DIR))

# Imports projet (E402 attendu : suit le sys.path.insert ci-dessus).
from core.config import LANGUAGES, _find_source_file_in_import  # noqa: E402

from analyze_translation_gap import LangGap, analyze_export  # noqa: E402
from analyze_translation_gap import render as render_gap  # noqa: E402
from compare_sources import Comparison, compare  # noqa: E402
from compare_sources import render as render_comparison  # noqa: E402

# Langues cibles par défaut (toutes configurées sauf 'en' = source)
DEFAULT_TARGET_LANGS = [code for code in LANGUAGES if code != "en"]
TYPHOS_PATH = TRANSLATOR_DIR / "source_typos.json"


# ─── Contexte du pipeline ────────────────────────────────────────────


@dataclass
class PipelineContext:
    """Transporte l'état du pipeline d'une étape à l'autre."""

    # Sources
    new_source: Path | None = None
    prev_source: Path | None = None
    new_import_folder: Path | None = None
    prev_import_folder: Path | None = None
    export_dir: Path | None = None  # dernier *_Export

    # Paramètres
    languages: list[str] = field(default_factory=lambda: list(DEFAULT_TARGET_LANGS))
    provider: str = "hybride"  # google | ollama | hybride
    dry_run: bool = False
    interactive: bool = True
    report_path: Path | None = None

    # Résultats d'étapes
    comparison: Comparison | None = None
    typos_found: list[dict] = field(default_factory=list)
    typos_corrected: bool = False
    gaps: list[LangGap] = field(default_factory=list)


# ─── Utilitaires interactifs ─────────────────────────────────────────


def confirm(ctx: PipelineContext, prompt: str, default: bool = False) -> bool:
    """Demande une confirmation oui/non.

    En mode non-interactif (--yes / --dry-run), retourne `default` sans
    demander.
    """
    if not ctx.interactive:
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except EOFError:
        return default
    if answer in ("y", "yes", "o", "oui"):
        return True
    if answer in ("n", "no", "non"):
        return False
    return default


def step_banner(num: int, title: str) -> None:
    print("\n" + "═" * 70)
    print(f"  ÉTAPE {num} — {title}")
    print("═" * 70)


# ─── Étape 1 : Détection source + précédente ──────────────────────────


def _list_import_folders(source_dir: Path) -> list[Path]:
    """Liste les dossiers *_Import triés du plus récent au plus ancien."""
    if not source_dir.exists():
        return []
    pattern = re.compile(r"^\d{4}_\d{2}_\d{2}_Import$")
    folders = [d for d in source_dir.iterdir() if d.is_dir() and pattern.match(d.name)]
    folders.sort(key=lambda p: p.name, reverse=True)
    return folders


def _pick_source_in_import(import_folder: Path, source_lang: str = "en") -> Path | None:
    """Retourne le fichier source principal d'un dossier *_Import."""
    found = _find_source_file_in_import(str(import_folder), source_lang)
    return Path(found) if found else None


def _latest_export_dir(output_dir: Path) -> Path | None:
    """Retourne le dossier *_Export le plus récent."""
    if not output_dir.exists():
        return None
    pattern = re.compile(r"^\d{4}_\d{2}_\d{2}_Export$")
    folders = [d for d in output_dir.iterdir() if d.is_dir() and pattern.match(d.name)]
    folders.sort(key=lambda p: p.name, reverse=True)
    return folders[0] if folders else None


def step1_detect_sources(ctx: PipelineContext) -> None:
    """Détecte la nouvelle source, la source précédente et le dernier export."""
    step_banner(1, "Détection des sources")

    source_dir = TRANSLATOR_DIR / "source"
    output_dir = TRANSLATOR_DIR / "output"

    # Nouvelle source (override ou auto-détection)
    if ctx.new_source:
        new_path = Path(ctx.new_source)
        if not new_path.exists():
            raise FileNotFoundError(f"Source --source introuvable : {new_path}")
        ctx.new_source = new_path
        ctx.new_import_folder = new_path.parent
        print(f"  Source (override)      : {new_path}")
    else:
        folders = _list_import_folders(source_dir)
        if not folders:
            raise FileNotFoundError(f"Aucun dossier *_Import trouvé dans {source_dir}")
        new_folder = folders[0]
        new_src = _pick_source_in_import(new_folder)
        if not new_src:
            raise FileNotFoundError(f"Aucun fichier source EN trouvé dans {new_folder}")
        ctx.new_import_folder = new_folder
        ctx.new_source = new_src
        print(f"  Source (dernier import): {new_src.name}")
        print(f"  Dossier import         : {new_folder.name}")

    # Source précédente (override ou 2e dossier le plus récent)
    if ctx.prev_source:
        prev_path = Path(ctx.prev_source)
        if not prev_path.exists():
            raise FileNotFoundError(f"Source --prev-source introuvable : {prev_path}")
        ctx.prev_source = prev_path
        print(f"  Source précédente (ovr): {prev_path}")
    else:
        folders = _list_import_folders(source_dir)
        prev_src = None
        for f in folders:
            if f == ctx.new_import_folder:
                continue
            cand = _pick_source_in_import(f)
            if cand and cand != ctx.new_source:
                prev_src = cand
                ctx.prev_import_folder = f
                break
        if prev_src:
            ctx.prev_source = prev_src
            print(f"  Source précédente      : {prev_src.name}")
            if ctx.prev_import_folder:
                print(f"  Dossier import préc.   : {ctx.prev_import_folder.name}")
        else:
            print(
                "  ⚠️  Aucune source précédente trouvée (pas de comparaison possible)."
            )

    # Dernier export
    ctx.export_dir = _latest_export_dir(output_dir)
    if ctx.export_dir:
        print(f"  Dernier export         : {ctx.export_dir.name}")
    else:
        print("  ⚠️  Aucun dossier *_Export trouvé (pas d'analyse d'écart possible).")

    # Stats de la nouvelle source
    with ctx.new_source.open(encoding="utf-8") as fh:
        new_data = json.load(fh)
    print(f"  Clés nouvelle source   : {len(new_data)}")


# ─── Étape 2 : Comparaison des sources ───────────────────────────────


def step2_compare_sources(ctx: PipelineContext) -> None:
    """Compare la nouvelle source à la précédente."""
    step_banner(2, "Comparaison des sources")
    if not ctx.prev_source:
        print("  ⚠️  Étape ignorée (pas de source précédente).")
        return
    ctx.comparison = compare(ctx.prev_source, ctx.new_source)
    c = ctx.comparison
    print(f"  Ancienne source : {c.old_path.name} ({len(c.old)} clés)")
    print(f"  Nouvelle source : {c.new_path.name} ({len(c.new)} clés)")
    print(f"  Ajoutées        : {len(c.added)}")
    print(f"  Supprimées      : {len(c.removed)}")
    print(f"  Modifiées       : {len(c.modified)}")
    print(f"  Inchangées      : {len(c.unchanged)}")
    ph_mismatch = c.modified_placeholder_mismatch()
    if ph_mismatch:
        print(f"  ⚠️  {len(ph_mismatch)} modifs avec placeholder divergent")


# ─── Étape 3 : Détection des coquilles source ────────────────────────


def load_typos(path: Path = TYPHOS_PATH) -> list[dict]:
    """Charge le dictionnaire des coquilles connues."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("typos", [])


def detect_typos_in_source(source_path: Path, typos: list[dict]) -> list[dict]:
    """Détecte les coquilles connues dans les valeurs de la source.

    Retourne une liste d'entrées : {typo, correction, keys: [clé i18n, ...]}
    """
    with source_path.open(encoding="utf-8") as fh:
        source_data = json.load(fh)
    found: list[dict] = []
    for entry in typos:
        typo = entry["typo"]
        correction = entry["correction"]
        affected = [
            key
            for key, value in source_data.items()
            if isinstance(value, str) and typo in value
        ]
        if affected:
            found.append(
                {
                    "typo": typo,
                    "correction": correction,
                    "keys": sorted(affected),
                    "first_seen_key": entry.get("first_seen_key", ""),
                }
            )
    return found


def apply_typo_corrections(source_path: Path, typos_found: list[dict]) -> int:
    """Applique les corrections au fichier source. Retourne le nombre de clés modifiées."""
    with source_path.open(encoding="utf-8") as fh:
        source_data = json.load(fh)
    modified = 0
    for entry in typos_found:
        typo = entry["typo"]
        correction = entry["correction"]
        for key, value in source_data.items():
            if isinstance(value, str) and typo in value:
                source_data[key] = value.replace(typo, correction)
                modified += 1
    with source_path.open("w", encoding="utf-8") as fh:
        json.dump(source_data, fh, ensure_ascii=False, indent=2)
    return modified


def step3_detect_typos(ctx: PipelineContext) -> None:
    """Détecte les coquilles source connues et propose correction."""
    step_banner(3, "Détection des coquilles source")
    typos = load_typos()
    if not typos:
        print("  Aucun dictionnaire de coquilles trouvé (source_typos.json absent).")
        return
    ctx.typos_found = detect_typos_in_source(ctx.new_source, typos)
    if not ctx.typos_found:
        print("  ✅ Aucune coquille connue détectée dans la source.")
        return
    print(f"  {len(ctx.typos_found)} coquille(s) détectée(s) :\n")
    for i, entry in enumerate(ctx.typos_found, 1):
        keys_preview = ", ".join(entry["keys"][:5])
        extra = f" (+{len(entry['keys']) - 5})" if len(entry["keys"]) > 5 else ""
        print(f"  {i}. « {entry['typo']} » → « {entry['correction']} »")
        print(f"     Clés affectées : {keys_preview}{extra}")
    if ctx.dry_run:
        print("\n  [dry-run] Aucune correction appliquée.")
        return
    if confirm(ctx, "\n  Corriger le fichier source maintenant ?", default=True):
        count = apply_typo_corrections(ctx.new_source, ctx.typos_found)
        ctx.typos_corrected = True
        print(f"  ✅ {count} clé(s) corrigée(s) dans {ctx.new_source.name}")
    else:
        print("  ⚠️  Corrections non appliquées (la source contient des coquilles).")


# ─── Étape 4 : Analyse de l'écart de traduction ───────────────────────


def step4_analyze_gap(ctx: PipelineContext) -> None:
    """Analyse l'écart entre le dernier export et la nouvelle source."""
    step_banner(4, "Analyse de l'écart de traduction")
    if not ctx.export_dir:
        print("  ⚠️  Étape ignorée (aucun export existant).")
        return
    if not ctx.prev_source:
        print(
            "  ⚠️  Étape ignorée (pas de source précédente pour le calcul des 'modify')."
        )
        return
    ctx.gaps = analyze_export(
        ctx.new_source, ctx.prev_source, ctx.export_dir, ctx.languages
    )
    print(f"  Export analysé   : {ctx.export_dir.name}")
    print(f"  Langues          : {', '.join(ctx.languages)}\n")
    print(
        "  | Langue | Présentes | À ajouter | À supprimer | À modifier | Incomplètes | Sur-remplies |"
    )
    print("  |---|---:|---:|---:|---:|---:|---:|")
    for g in ctx.gaps:
        print(
            f"  | {g.lang} | {g.count} | {len(g.to_add)} | {len(g.to_remove)} | "
            f"{len(g.to_modify)} | {len(g.incomplete)} | {len(g.over_filled)} |"
        )
    common_add = (
        set.intersection(*(set(g.to_add) for g in ctx.gaps)) if ctx.gaps else set()
    )
    common_rem = (
        set.intersection(*(set(g.to_remove) for g in ctx.gaps)) if ctx.gaps else set()
    )
    common_mod = (
        set.intersection(*(set(g.to_modify) for g in ctx.gaps)) if ctx.gaps else set()
    )
    print(
        f"\n  Synthèse : {len(common_add)} ajout(s) × {len(ctx.languages)} langues, "
        f"{len(common_rem)} suppression(s), {len(common_mod)} modification(s) à retraduire."
    )


# ─── Étape 5 : Rapport consolidé + confirmation ──────────────────────


def _load_source_for_render(source_path: Path) -> dict:
    """Helper : charge la source pour render_gap() (qui attend le dict source)."""
    with source_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def build_analysis_report(ctx: PipelineContext) -> str:
    """Construit le rapport markdown consolidé des étapes 1-4."""
    L: list[str] = []
    L.append(
        f"# Rapport d'analyse du pipeline — {ctx.new_source.name if ctx.new_source else '?'}\n"
    )
    date_str = (
        ctx.new_import_folder.name.replace("_Import", "")
        if ctx.new_import_folder
        else "?"
    )
    L.append(f"- Date : {date_str}")
    L.append(f"- Source : `{ctx.new_source}`\n")

    # Section 1 — Source
    L.append("## 1. Source détectée\n")
    L.append(f"- Nouvelle source : `{ctx.new_source}`")
    if ctx.new_import_folder:
        L.append(f"- Dossier import : `{ctx.new_import_folder.name}`")
    if ctx.prev_source:
        L.append(f"- Source précédente : `{ctx.prev_source}`")
    if ctx.prev_import_folder:
        L.append(f"- Dossier import préc. : `{ctx.prev_import_folder.name}`")
    if ctx.export_dir:
        L.append(f"- Dernier export : `{ctx.export_dir.name}`")
    if ctx.new_source:
        with ctx.new_source.open(encoding="utf-8") as fh:
            nkeys = len(json.load(fh))
        L.append(f"- Clés nouvelle source : {nkeys}")
    L.append("")

    # Section 2 — Comparaison
    L.append("## 2. Comparaison des sources\n")
    if ctx.comparison:
        L.append(render_comparison(ctx.comparison))
    else:
        L.append("_Pas de source précédente — comparaison ignorée._\n")
    L.append("")

    # Section 3 — Coquilles source
    L.append("## 3. Coquilles source détectées\n")
    if ctx.typos_found:
        L.append("| # | Coquille | Correction | Clés affectées |")
        L.append("|---:|---|---|---|")
        for i, entry in enumerate(ctx.typos_found, 1):
            keys = ", ".join(f"`{k}`" for k in entry["keys"][:5])
            extra = f" (+{len(entry['keys']) - 5})" if len(entry["keys"]) > 5 else ""
            L.append(
                f"| {i} | `{entry['typo']}` | `{entry['correction']}` | {keys}{extra} |"
            )
        L.append("")
        L.append(
            f"Corrections appliquées : {'oui ✅' if ctx.typos_corrected else 'non (voir sortie interactive)'}"
        )
    else:
        L.append("_Aucune coquille connue détectée._")
    L.append("")

    # Section 4 — Écart de traduction
    L.append("## 4. Écart de traduction (vs dernier export)\n")
    if ctx.gaps:
        L.append(render_gap(_load_source_for_render(ctx.new_source), ctx.gaps))
    else:
        L.append(
            "_Aucun export existant ou aucune source précédente — écart non calculé._"
        )
    L.append("")

    # Section 5 — Plan d'action (aperçu)
    L.append("## 5. Plan d'action (aperçu)\n")
    if ctx.gaps:
        common_add = set.intersection(*(set(g.to_add) for g in ctx.gaps))
        common_rem = set.intersection(*(set(g.to_remove) for g in ctx.gaps))
        common_mod = set.intersection(*(set(g.to_modify) for g in ctx.gaps))
        L.append(
            f"- **Ajouter** {len(common_add)} clé(s) × {len(ctx.languages)} langue(s) = "
            f"{len(common_add) * len(ctx.languages)} traductions à produire."
        )
        L.append(f"- **Supprimer** {len(common_rem)} clé(s) orpheline(s).")
        L.append(f"- **Retraduire** {len(common_mod)} clé(s) dont la source a changé.")
        incomplete_total = sum(len(g.incomplete) for g in ctx.gaps)
        overfilled_total = sum(len(g.over_filled) for g in ctx.gaps)
        L.append(f"- **Compléter** {incomplete_total} traduction(s) incomplète(s).")
        L.append(
            f"- **Décider** du sort de {overfilled_total} traduction(s) sur-remplies (back-fill manuel)."
        )
    else:
        L.append("_Plan d'action indisponible (pas d'écart calculé)._")
    L.append(f"\nProvider sélectionné : **{ctx.provider}**")
    L.append(f"Langues : **{', '.join(ctx.languages)}**")
    L.append("")
    return "\n".join(L)


def step5_report_and_confirm(ctx: PipelineContext) -> bool:
    """Produit le rapport consolidé et demande confirmation pour continuer.

    Retourne True si l'utilisateur confirme (ou en non-interactif), False sinon.
    """
    step_banner(5, "Rapport consolidé + confirmation")
    report_md = build_analysis_report(ctx)

    if ctx.report_path:
        ctx.report_path.write_text(report_md, encoding="utf-8")
        print(f"  Rapport écrit : {ctx.report_path}")
    else:
        print(report_md)

    if ctx.dry_run:
        print("\n  [dry-run] Fin du parcours d'analyse — aucune exécution.")
        return False
    if not ctx.interactive:
        return True

    print("\n" + "─" * 70)
    print("  ÉTAPE CLÉ — Confirmer pour poursuivre vers la traduction (étapes 6-11).")
    print("  (Phase 2 + 3 seront implémentées ultérieurement ; pour l'instant")
    print("   la confirmation valide le rapport d'analyse.)")
    print("─" * 70)
    return confirm(ctx, "  Poursuivre ?", default=False)


# ─── CLI ─────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pipeline.py",
        description="Pipeline orchestré de traduction COP.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Rapport d'analyse sans exécution ni confirmation bloquante.",
    )
    p.add_argument(
        "--languages",
        type=str,
        default=None,
        help="Langues cibles séparées par virgules (défaut : toutes). Ex : fr,de",
    )
    p.add_argument(
        "--provider",
        choices=["google", "ollama", "hybride"],
        default="hybride",
        help="Provider de traduction (défaut : hybride). Utilisé en Phase 2.",
    )
    p.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Override la détection de la nouvelle source.",
    )
    p.add_argument(
        "--prev-source",
        type=Path,
        default=None,
        help="Override la détection de la source précédente.",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Chemin de sortie du rapport markdown d'analyse.",
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Mode non-interactif : valide toutes les étapes clés sans demander.",
    )
    return p


def run_pipeline(args: argparse.Namespace) -> int:
    """Point d'entrée : exécute les étapes 1-5 de la Phase 1."""
    ctx = PipelineContext(
        dry_run=args.dry_run,
        provider=args.provider,
        interactive=not args.yes and not args.dry_run,
        report_path=args.report,
    )
    if args.source:
        ctx.new_source = args.source
    if args.prev_source:
        ctx.prev_source = args.prev_source
    if args.languages:
        ctx.languages = [lg.strip() for lg in args.languages.split(",") if lg.strip()]

    print("🚀 Pipeline de traduction COP — Phase 1 (analyse)")
    print(f"   Provider : {ctx.provider} | Langues : {', '.join(ctx.languages)}")
    if ctx.dry_run:
        print("   Mode : dry-run (analyse seule, pas d'exécution)")

    try:
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        step3_detect_typos(ctx)
        step4_analyze_gap(ctx)
        confirmed = step5_report_and_confirm(ctx)
    except FileNotFoundError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 2

    if confirmed:
        print("\n✅ Rapport d'analyse validé. Phase 2 (exécution) à implémenter.")
    else:
        print("\n⏹  Parcours arrêté (confirmation refusée ou dry-run).")
    return 0


def main() -> None:
    args = build_parser().parse_args()
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
