#!/usr/bin/env python3
"""Pipeline orchestré de traduction COP — mode dropdown (XLSX).

Enchaîne les 11 étapes pour traduire un fichier XLSX dropdown vers les
langues cibles, en réutilisant les traductions déjà présentes dans les
feuilles par langue (cache colonne B).

Architecture DDD : bounded context distinct du pipeline JSON
(`pipeline.py`). Shared kernel dans `pipeline_common.py`.

Usage:
    python translator/pipeline_dropdown.py --source dropdown.xlsx --languages pt,es,hu
    python translator/pipeline_dropdown.py --dry-run --source dropdown.xlsx
    python translator/pipeline_dropdown.py --source dropdown.xlsx --retranslate-all
    python translator/pipeline_dropdown.py --source dropdown.xlsx --no-cache
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# sys.path setup (identique à pipeline.py)
REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSLATOR_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSLATOR_DIR))

from core.config import LANGUAGES  # noqa: E402
from pipeline_common import BasePipelineContext, confirm, step_banner  # noqa: E402, F401

DEFAULT_TARGET_LANGS = [code for code in LANGUAGES if code != "en"]


# ─── Contexte du pipeline dropdown ───────────────────────────────────


@dataclass
class PipelineDropdownContext(BasePipelineContext):
    """Contexte du pipeline dropdown — étend la base avec les champs XLSX."""

    # Sources XLSX
    xlsx_path: Path | None = None
    prev_xlsx_path: Path | None = None  # XLSX précédent (comparaison étape 2)
    output_dir: Path | None = None  # dossier {date}_Dropdown

    # Données
    existing_translations: dict[str, dict[str, str]] = field(default_factory=dict)
    missing_languages: list[str] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)  # [{origin, french, context}]

    # Flags spécifiques dropdown
    retranslate_all: bool = False
    retranslate_langs: list[str] = field(default_factory=list)
    no_cache: bool = False
    output_format: str = "auto"  # json | xlsx | auto


# ─── CLI ─────────────────────────────────────────────────────────────


def build_parser_dropdown() -> argparse.ArgumentParser:
    """Construit le parser CLI du pipeline dropdown."""
    p = argparse.ArgumentParser(
        prog="pipeline_dropdown.py",
        description="Pipeline orchestré de traduction COP — mode dropdown (XLSX).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Rapport d'analyse sans exécution.",
    )
    p.add_argument(
        "--languages",
        type=str,
        default=None,
        help="Langues cibles séparées par virgules (défaut : toutes). Ex : pt,es,hu",
    )
    p.add_argument(
        "--provider",
        choices=["google", "ollama", "hybride"],
        default="hybride",
        help="Provider de traduction (défaut : hybride).",
    )
    p.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Fichier XLSX source (override auto-détection).",
    )
    p.add_argument(
        "--prev-source",
        type=Path,
        default=None,
        help="Fichier XLSX précédent (pour comparaison).",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Chemin de sortie du rapport markdown.",
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Mode non-interactif : valide toutes les étapes clés.",
    )
    p.add_argument(
        "--mode",
        choices=["json", "dropdown"],
        default="dropdown",
        help="Force le type de pipeline (défaut : dropdown).",
    )
    p.add_argument(
        "--format",
        choices=["json", "xlsx", "auto"],
        default="auto",
        help="Format de sortie (défaut : auto = format d'entrée).",
    )
    # Flags spécifiques dropdown — options de retraduction
    p.add_argument(
        "--retranslate-all",
        action="store_true",
        help="Ignore le cache colonne B → re-traduit toutes les langues.",
    )
    p.add_argument(
        "--retranslate",
        type=str,
        default=None,
        help="Retraduit les langues listées (ex : fr,de), garde le cache pour les autres.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Désactive le cache du service (.translation_cache.json).",
    )
    return p


# ─── Point d'entrée (squelette — étapes à venir en D5+) ─────────────


def run_pipeline_dropdown(args: argparse.Namespace) -> int:
    """Point d'entrée du pipeline dropdown.

    Squelette pour D4 — les étapes 1-11 seront implémentées en D5-D14.
    """
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

    # TODO D5-D14 : implémenter les étapes 1-11
    print("\n⏳ Les étapes 1-11 du pipeline dropdown seront implémentées (D5-D14).")
    return 0


def main() -> None:
    args = build_parser_dropdown().parse_args()
    sys.exit(run_pipeline_dropdown(args))


if __name__ == "__main__":
    main()
