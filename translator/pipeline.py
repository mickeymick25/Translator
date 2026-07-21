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
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
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
from pipeline_common import (  # noqa: E402
    BasePipelineContext,
    MAX_REPORT_ENTRIES,
    PREVIEW_LIMIT,
    backup_translation_file,
    confirm,
    json_load,
    json_write,
    load_typos,
    logger,
    parse_languages_arg,
    section_separator,
    short_repr,
    step_banner,
    write_report,
)

from analyze_translation_gap import LangGap, analyze_export  # noqa: E402
from analyze_translation_gap import render as render_gap  # noqa: E402
from compare_sources import Comparison, compare  # noqa: E402
from compare_sources import render as render_comparison  # noqa: E402
from validate_translations import (  # noqa: E402
    ValidationReport,
    validate,
)

# Langues cibles par défaut (toutes configurées sauf 'en' = source)
DEFAULT_TARGET_LANGS = [code for code in LANGUAGES if code != "en"]
# Sprint 2 - tâche 22 : renommage TYPHOS_PATH (coquille de nommage) en TYPOS_PATH.
# Utilisé par step3_detect_typos comme chemin explicite vers source_typos.json
# (le helper load_typos vit dans pipeline_common et utilise sa propre valeur
# par défaut ; passer TYPOS_PATH explicitement permet aux tests de monkeypatcher
# pipeline.TYPOS_PATH).
TYPOS_PATH = TRANSLATOR_DIR / "source_typos.json"


# ─── Dispatcher : détection du type de source ─────────────────────────


def detect_source_kind(source_path: Path | None) -> str:
    """Détecte le type de source : 'json' ou 'dropdown'.

    Basé sur l'extension du fichier (.xlsx/.xls → dropdown, sinon json).
    Retourne 'json' par défaut si le path est None ou l'extension inconnue.
    """
    if source_path is None:
        return "json"
    ext = Path(source_path).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return "dropdown"
    return "json"


# ─── Contexte du pipeline (hérite de la base partagée) ───────────────


@dataclass
class PipelineContext(BasePipelineContext):
    """Contexte du pipeline JSON — étend la base avec les champs spécifiques."""

    # Dossiers (spécifiques JSON)
    new_import_folder: Path | None = None
    prev_import_folder: Path | None = None
    export_dir: Path | None = None  # dernier *_Export

    # Résultats d'étapes (spécifiques JSON)
    comparison: Comparison | None = None
    typos_found: list[dict] = field(default_factory=list)
    typos_corrected: bool = False
    gaps: list[LangGap] = field(default_factory=list)

    # Sprint 2 - tâche 25 : nombre de clés de la nouvelle source, stocké à
    # l'étape 1 pour éviter une relecture dans les rapports (I11).
    source_key_count: int = 0

    # Flags runtime
    no_cache: bool = False


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
    ctx.source_key_count = len(new_data)
    print(f"  Clés nouvelle source   : {ctx.source_key_count}")


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
    typos = load_typos(path=TYPOS_PATH)
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


def _section_source_analysis(ctx: PipelineContext) -> list[str]:
    """Section 1 — Source détectée."""
    L: list[str] = ["## 1. Source détectée\n"]
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
        # Sprint 2 - tâche 25 : utiliser ctx.source_key_count plutôt qu'une
        # relecture du fichier source (I11).
        nkeys = ctx.source_key_count or len(_load_source_for_render(ctx.new_source))
        L.append(f"- Clés nouvelle source : {nkeys}")
    L.append("")
    return L


def _section_comparison_analysis(ctx: PipelineContext) -> list[str]:
    """Section 2 — Comparaison des sources."""
    L: list[str] = ["## 2. Comparaison des sources\n"]
    if ctx.comparison:
        L.append(render_comparison(ctx.comparison))
    else:
        L.append("_Pas de source précédente — comparaison ignorée._\n")
    L.append("")
    return L


def _section_coquilles_analysis(ctx: PipelineContext) -> list[str]:
    """Section 3 — Coquilles source détectées."""
    L: list[str] = ["## 3. Coquilles source détectées\n"]
    if ctx.typos_found:
        L.append("| # | Coquille | Correction | Clés affectées |")
        L.append("|---:|---|---|---|")
        for i, entry in enumerate(ctx.typos_found, 1):
            keys = ", ".join(f"`{k}`" for k in entry["keys"][:PREVIEW_LIMIT])
            extra = (
                f" (+{len(entry['keys']) - PREVIEW_LIMIT})"
                if len(entry["keys"]) > PREVIEW_LIMIT
                else ""
            )
            L.append(
                f"| {i} | `{entry['typo']}` | `{entry['correction']}` | {keys}{extra} |"
            )
        L.append("")
        L.append(
            f"Corrections appliquées : "
            f"{'oui ✅' if ctx.typos_corrected else 'non (voir sortie interactive)'}"
        )
    else:
        L.append("_Aucune coquille connue détectée._")
    L.append("")
    return L


def _section_gap_analysis(ctx: PipelineContext) -> list[str]:
    """Section 4 — Écart de traduction (vs dernier export)."""
    L: list[str] = ["## 4. Écart de traduction (vs dernier export)\n"]
    if ctx.gaps:
        L.append(render_gap(_load_source_for_render(ctx.new_source), ctx.gaps))
    else:
        L.append(
            "_Aucun export existant ou aucune source précédente — écart non calculé._"
        )
    L.append("")
    return L


def _section_plan_action_analysis(ctx: PipelineContext) -> list[str]:
    """Section 5 — Plan d'action (aperçu)."""
    L: list[str] = ["## 5. Plan d'action (aperçu)\n"]
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
            f"- **Décider** du sort de {overfilled_total} traduction(s) "
            f"sur-remplies (back-fill manuel)."
        )
    else:
        L.append("_Plan d'action indisponible (pas d'écart calculé)._")
    L.append(f"\nProvider sélectionné : **{ctx.provider}**")
    L.append(f"Langues : **{', '.join(ctx.languages)}**")
    L.append("")
    return L


def build_analysis_report(ctx: PipelineContext) -> str:
    """Construit le rapport markdown consolidé des étapes 1-4.

    Assemble les 5 sections `_section_*` (Sprint 2 - tâche 17) en un seul
    document markdown.
    """
    L: list[str] = []
    L.append(
        f"# Rapport d'analyse du pipeline — "
        f"{ctx.new_source.name if ctx.new_source else '?'}\n"
    )
    date_str = (
        ctx.new_import_folder.name.replace("_Import", "")
        if ctx.new_import_folder
        else "?"
    )
    L.append(f"- Date : {date_str}")
    L.append(f"- Source : `{ctx.new_source}`\n")

    L.extend(_section_source_analysis(ctx))
    L.extend(_section_comparison_analysis(ctx))
    L.extend(_section_coquilles_analysis(ctx))
    L.extend(_section_gap_analysis(ctx))
    L.extend(_section_plan_action_analysis(ctx))
    return "\n".join(L)


def step5_report_and_confirm(ctx: PipelineContext) -> bool:
    """Produit le rapport consolidé et demande confirmation pour continuer.

    Retourne True si l'utilisateur confirme (ou en non-interactif), False sinon.
    """
    step_banner(5, "Rapport consolidé + confirmation")
    report_md = build_analysis_report(ctx)

    if ctx.report_path:
        write_report(report_md, ctx.report_path)
        print(f"  Rapport écrit : {ctx.report_path}")
    else:
        print(report_md)

    if ctx.dry_run:
        print("\n  [dry-run] Fin du parcours d'analyse — aucune exécution.")
        return False
    if not ctx.interactive:
        return True

    print("\n" + section_separator("─"))
    print("  ÉTAPE CLÉ — Confirmer pour poursuivre vers la traduction (étapes 6-11).")
    print(section_separator("─"))
    return confirm(ctx, "  Poursuivre ?", default=False)


# ─── Étape 6 : Pré-peuplement + gestion clés modifiées ────────────────


def prepopulate_output(
    last_export_dir: Path | None,
    languages: list[str],
    base_output_dir: Path,
) -> Path:
    """Crée un nouveau dossier daté et y copie les fichiers du dernier export.

    Args:
        last_export_dir: Dossier *_Export source (copie de référence).
            ``None`` ou un chemin inexistant signifie « pas d'export
            précédent » : un dossier daté vide est créé (C12).
        languages: Langues à copier (fichiers translation_en_<lang>.json).
        base_output_dir: Dossier parent des *_Export.

    Returns:
        Le chemin du nouveau dossier daté.

    Si un dossier daté du même jour existe déjà et n'est pas vide, un suffixe
        `_run2`, `_run3`, ... est ajouté pour ne pas écraser silencieusement
        l'export précédent (C6).
    """
    date_str = datetime.now().strftime("%Y_%m_%d")
    new_dir = _next_dated_dir(base_output_dir, f"{date_str}_Export")
    new_dir.mkdir(parents=True, exist_ok=True)
    if last_export_dir is not None and last_export_dir.exists():
        for lang in languages:
            src_file = last_export_dir / f"translation_en_{lang}.json"
            if src_file.exists():
                shutil.copy2(src_file, new_dir / src_file.name)
    return new_dir


def _next_dated_dir(base: Path, base_name: str) -> Path:
    """Retourne un chemin unique sous `base` pour éviter d'écraser un dossier.

    Si `base/base_name` n'existe pas ou est vide, le retourne tel quel.
    Sinon, ajoute `_run2`, `_run3`, ... jusqu'à trouver un nom libre.
    """
    candidate = base / base_name
    if not candidate.exists() or not any(candidate.iterdir()):
        return candidate
    # base_name a la forme "YYYY_MM_DD_Export" ; on insère _runN avant le
    # suffixe final ("Export").
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


def manage_modified_keys(
    modified: list[tuple[str, str, str]],
    export_dir: Path,
    languages: list[str],
    interactive: bool = True,
) -> None:
    """Pour chaque clé modifiée, demande l'action (retraduire/garder/saisie).

    Args:
        modified: Liste de (key, old_value, new_value) issues de la comparaison.
        export_dir: Dossier contenant les translation_en_<lang>.json.
        languages: Langues cibles.
        interactive: Si False, conserve toutes les traductions (défaut sûr).
    """
    if not modified:
        return
    for key, old_val, new_val in modified:
        if not interactive:
            continue  # défaut sûr : garder l'existant
        # Afficher le contexte
        print(f"\n  Clé modifiée: {key}")
        print(f"    ancien source: {short_repr(old_val)}")
        print(f"    nouveau source: {short_repr(new_val)}")
        # Langue d'affichage par défaut : le français est la langue pivot
        # historique du projet, indépendante de l'ordre de --languages (C11).
        display_lang = "fr"
        fr_file = export_dir / f"translation_en_{display_lang}.json"
        current = ""
        if fr_file.exists():
            data = json_load(fr_file)
            current = data.get(key, "")
        print(
            f"    traduction actuelle ({display_lang.upper()}): {short_repr(current)}"
        )
        action = _prompt_action(key)
        if action == "1":
            _remove_key_from_all(export_dir, languages, key)
            print(f"    → Clé '{key}' supprimée (sera retraduite).")
        elif action == "3":
            _manual_input_for_all(export_dir, languages, key)
        # action "2" ou annulation : ne rien faire (garder)


def _prompt_action(key: str) -> str:
    """Demande l'action pour une clé modifiée. Retourne '1', '2' ou '3'."""
    while True:
        try:
            answer = input(
                "  Action: [1] Retraduire  [2] Garder l'existant  "
                "[3] Saisir manuellement  "
            ).strip()
        except EOFError:
            return "2"  # défaut sûr : garder
        if answer in ("1", "2", "3"):
            return answer
        print("    Réponse invalide. Tapez 1, 2 ou 3.")


def _remove_key_from_all(export_dir: Path, languages: list[str], key: str) -> None:
    """Supprime une clé de tous les fichiers de traduction."""
    for lang in languages:
        path = export_dir / f"translation_en_{lang}.json"
        if path.exists():
            data = json_load(path)
            data.pop(key, None)
            json_write(path, data)


def _manual_input_for_all(export_dir: Path, languages: list[str], key: str) -> None:
    """Demande une traduction manuelle pour chaque langue et l'écrit."""
    for lang in languages:
        path = export_dir / f"translation_en_{lang}.json"
        try:
            value = input(f"    Traduction {lang.upper()} pour '{key}': ").strip()
        except EOFError:
            continue
        if path.exists():
            data = json_load(path)
        else:
            data = {}
        data[key] = value
        json_write(path, data)
        print(f"    → {lang.upper()}: '{value}' enregistré.")


def step6_prepopulate_and_manage(ctx: PipelineContext) -> Path | None:
    """Pré-peuple le dossier output, gère les clés modifiées, demande confirmation.

    ÉTAPE CLÉ : confirmation après gestion des clés modifiées.
    Retourne le chemin du nouveau dossier d'export, ou None si annulé/dry-run.
    """
    step_banner(6, "Pré-peuplement + gestion clés modifiées")

    if ctx.dry_run:
        print("  [dry-run] Pré-peuplement et gestion clés ignorés.")
        return None

    if not ctx.export_dir:
        print("  ⚠️  Aucun export précédent — dossier vide créé.")
        # Créer un dossier daté vide pour la traduction (C12 : plus de
        # Path("/dev/null") non portable — on passe None à prepopulate_output
        # qui crée simplement un dossier vide).
        base = TRANSLATOR_DIR / "output"
        new_dir = prepopulate_output(None, ctx.languages, base)
        return new_dir

    # 1. Backup des fichiers du dernier export
    print("  Sauvegarde des fichiers existants...")
    for lang in ctx.languages:
        src_file = ctx.export_dir / f"translation_en_{lang}.json"
        if src_file.exists():
            backup_translation_file(src_file)

    # 2. Pré-peuplement : copie vers un nouveau dossier daté
    base = TRANSLATOR_DIR / "output"
    new_dir = prepopulate_output(ctx.export_dir, ctx.languages, base)
    print(f"  Nouveau dossier d'export : {new_dir.name}")
    copied = sum(
        1
        for lang in ctx.languages
        if (new_dir / f"translation_en_{lang}.json").exists()
    )
    print(f"  {copied} fichier(s) copié(s).")

    # 3. Gestion des clés modifiées
    if ctx.comparison and ctx.comparison.modified:
        modified = ctx.comparison.modified  # list of (key, old, new)
        print(f"\n  {len(modified)} clé(s) modifiée(s) à examiner :")
        manage_modified_keys(
            modified, new_dir, ctx.languages, interactive=ctx.interactive
        )
    else:
        print("  Aucune clé modifiée à examiner.")

    # 4. Confirmation [ÉTAPE CLÉ]
    print("\n" + section_separator("─"))
    print("  ÉTAPE CLÉ — Confirmer avant de lancer la traduction (étapes 7-8).")
    print(section_separator("─"))
    if confirm(ctx, "  Lancer la traduction ?", default=True):
        print("  ✅ Confirmé.")
        return new_dir
    print("  ⛔ Traduction annulée.")
    return None


# ─── Étape 7 : Traduction ───────────────────────────────────────────


def step7_translate(ctx: PipelineContext, export_dir: Path) -> None:
    """Lance la traduction pour chaque langue cible vers `export_dir`.

    Pilote directement `_translate_single_language` du mode translate-json
    (évite le sous-dossier daté créé par `run()`). Le resume est automatique :
    les clés déjà présentes sont gardées, seules les manquantes sont traduites.
    """
    step_banner(7, "Traduction")

    if ctx.dry_run:
        print("  [dry-run] Traduction non lancée.")
        return

    if not ctx.languages:
        print("  Aucune langue à traduire.")
        return

    # Configurer le singleton Config via le context manager `override_config`
    # qui restaure l'ancienne valeur dans un `finally` — y compris si la
    # traduction lève (C2 : singleton non restauré sur exception).
    from pipeline_common import override_config

    provider = ctx.provider if ctx.provider != "hybride" else "google"

    # Charger la source
    with ctx.new_source.open(encoding="utf-8") as fh:
        source_data = json.load(fh)
    source_keys = list(source_data.keys())

    # Import différé : mode_translate_json doit être importé après le sys.path setup
    from modes.mode_translate_json import _translate_single_language  # noqa: E402

    print(f"  Provider : {provider}")
    print(f"  Langues  : {', '.join(ctx.languages)}")
    print(f"  Source   : {ctx.new_source.name} ({len(source_keys)} clés)")

    with override_config(
        source_file=str(ctx.new_source),
        output_dir=str(export_dir),
        provider=provider,
        no_cache=ctx.no_cache,
    ):
        for lang in ctx.languages:
            print(f"\n  → {lang.upper()}...")
            _translate_single_language(
                ctx.new_source, source_data, "en", lang, export_dir
            )
            out_file = export_dir / f"translation_en_{lang}.json"
            if out_file.exists():
                count = len(json.loads(out_file.read_text(encoding="utf-8")))
                print(f"    {count} clés traduites.")


# ─── Étape 8 : Réordonnancement auto ─────────────────────────────────


def reorder_translation_file(path: Path, source_keys: list[str]) -> None:
    """Réécrit un fichier JSON de traduction dans l'ordre des clés source.

    Les clés présentes dans la trad mais absentes de la source sont conservées
    et placées à la fin (pas de perte de données). Les clés source absentes
    de la trad ne sont pas ajoutées.
    """
    data = json_load(path)
    if not data:
        return
    reordered: dict = {}
    for key in source_keys:
        if key in data:
            reordered[key] = data[key]
    # Clés extras (présentes dans la trad, pas dans la source) → à la fin
    for key in data:
        if key not in reordered:
            reordered[key] = data[key]
    json_write(path, reordered)


def step8_reorder(ctx: PipelineContext, export_dir: Path) -> None:
    """Réordonne tous les fichiers de traduction selon l'ordre de la source."""
    step_banner(8, "Réordonnancement auto")

    if ctx.dry_run:
        print("  [dry-run] Réordonnancement non appliqué.")
        return

    if not ctx.new_source:
        print("  ⚠️  Pas de source — étape ignorée.")
        return

    with ctx.new_source.open(encoding="utf-8") as fh:
        source_data = json.load(fh)
    source_keys = list(source_data.keys())

    for lang in ctx.languages:
        path = export_dir / f"translation_en_{lang}.json"
        if not path.exists():
            print(f"  {lang.upper()}: fichier absent — ignoré.")
            continue
        reorder_translation_file(path, source_keys)
        print(f"  {lang.upper()}: réordonné selon la source ({len(source_keys)} clés).")


# ─── Étape 9 : Validation structurelle ────────────────────────────────


def step9_validate(ctx: PipelineContext, export_dir: Path) -> ValidationReport | None:
    """Valide les fichiers traduits via validate_translations.validate().

    Retourne un ValidationReport (ou None en dry-run).
    """
    step_banner(9, "Validation structurelle")

    if ctx.dry_run:
        print("  [dry-run] Validation non exécutée.")
        return None

    report = validate(ctx.new_source, export_dir, ctx.languages)
    print(f"  Source : {report.source_count} clés")
    for lv in report.languages:
        status = "✅" if not (lv.missing or lv.extra or lv.empty) else "⚠️"
        print(
            f"  {lv.lang.upper()}: {lv.count} clés "
            f"({len(lv.missing)} manquantes, {len(lv.extra)} excédantes, "
            f"{len(lv.empty)} vides) {status}"
        )
    if report.all_ok:
        print("\n  ✅ Toutes les traductions sont valides.")
    else:
        print(
            f"\n  ⚠️  {report.total_missing} manquantes, {report.total_extra} excédantes, "
            f"{report.total_empty} vides, {report.total_placeholder_issues} placeholders."
        )
    return report


# ─── Étape 10 : Détection mésalignements intra-langue ─────────────────


def _tokenize(text: str) -> set[str]:
    """Tokenise une chaîne pour la comparaison (lowercase, alphanumérique).

    Retourne un ensemble de tokens alphanumériques. Si aucun token n'est
    trouvé (texte composé uniquement de ponctuation/emoji), retourne
    `set()` plutôt que `{text.lower()}` — deux textes sans token ne peuvent
    pas être comparés token-à-token et ne doivent pas être signalés comme
    mésalignés (C15 : false positive sur texte ponctué).
    """
    import unicodedata

    # Normaliser (enlever les accents pour la comparaison approximative)
    normalized = unicodedata.normalize("NFKD", text.lower())
    tokens = []
    current = []
    for ch in normalized:
        if ch.isalnum():
            current.append(ch)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return set(tokens)


def detect_misalignments(source: dict, translation: dict, lang: str) -> list[dict]:
    """Détecte les mésalignements intra-langue (heuristique token overlap).

    Pour chaque texte source partagé par plusieurs clés, vérifie que les
    traductions sont cohérentes (au moins un mot en commun). Signale les
    écarts. Heuristique conservatrice : ne signale que les divergences sans
    aucun mot commun (Jaccard = 0).

    Args:
        source: Dict source EN (key → texte).
        translation: Dict traduit (key → texte traduit).
        lang: Code langue (pour le rapport).

    Returns:
        Liste de {source_text, keys, translations} pour chaque mésalignement.
    """
    # Grouper les clés par texte source
    groups: dict[str, list[str]] = {}
    for key, text in source.items():
        if isinstance(text, str) and text:
            groups.setdefault(text, []).append(key)

    misalignments: list[dict] = []
    for source_text, keys in groups.items():
        if len(keys) < 2:
            continue
        # Récupérer les traductions non vides
        trans = {
            k: translation.get(k, "")
            for k in keys
            if isinstance(translation.get(k, ""), str)
            and translation.get(k, "").strip()
        }
        if len(trans) < 2:
            continue
        # Comparer les jeux de tokens par paires
        token_sets = {k: _tokenize(v) for k, v in trans.items()}
        # Skipper la comparaison si l'un des deux sets est vide de tokens
        # (texte sans contenu alphanumérique — C15).
        keys_list = [k for k in trans if token_sets[k]]
        if len(keys_list) < 2:
            continue
        has_divergence = False
        for i in range(len(keys_list)):
            for j in range(i + 1, len(keys_list)):
                if not token_sets[keys_list[i]] & token_sets[keys_list[j]]:
                    has_divergence = True
                    break
            if has_divergence:
                break
        if has_divergence:
            misalignments.append(
                {
                    "source_text": source_text,
                    "keys": sorted(keys_list),
                    "translations": {k: trans[k] for k in sorted(keys_list)},
                }
            )
    return misalignments


def step10_detect_misalignments(
    ctx: PipelineContext, export_dir: Path
) -> dict[str, list[dict]]:
    """Détecte les mésalignements pour toutes les langues.

    Retourne un dict {lang: [mésalignement, ...]}. Signale, ne corrige pas.
    """
    step_banner(10, "Détection mésalignements intra-langue")

    if ctx.dry_run:
        print("  [dry-run] Mésalignements non détectés.")
        return {}

    source = json_load(ctx.new_source)
    result: dict[str, list[dict]] = {}
    for lang in ctx.languages:
        path = export_dir / f"translation_en_{lang}.json"
        if not path.exists():
            continue
        translation = json_load(path)
        mism = detect_misalignments(source, translation, lang)
        result[lang] = mism
        if mism:
            print(f"  {lang.upper()}: {len(mism)} mésalignement(s) potentiel(s).")
            for m in mism[:5]:
                print(
                    f"    « {short_repr(m['source_text'])} » → {', '.join(m['keys'])}"
                )
        else:
            print(f"  {lang.upper()}: ✅ aucun mésalignement.")
    total = sum(len(v) for v in result.values())
    if total:
        print(f"\n  ⚠️  {total} mésalignement(s) au total (à vérifier manuellement).")
    return result


# ─── Étape 11 : Rapport consolidé final ────────────────────────────────


def _section_source_final(ctx: PipelineContext) -> list[str]:
    """Section 1 — Source (rapport final)."""
    L: list[str] = ["## 1. Source\n"]
    if ctx.new_source:
        nkeys = ctx.source_key_count or len(_load_source_for_render(ctx.new_source))
        L.append(f"- Fichier : `{ctx.new_source.name}`")
        L.append(f"- Clés : {nkeys}")
    if ctx.prev_source:
        L.append(f"- Source précédente : `{ctx.prev_source.name}`")
    L.append("")
    return L


def _section_comparison_final(ctx: PipelineContext) -> list[str]:
    """Section 2 — Comparaison des sources (rapport final)."""
    L: list[str] = ["## 2. Comparaison des sources\n"]
    if ctx.comparison:
        c = ctx.comparison
        L.append(f"- Ajoutées : {len(c.added)}")
        L.append(f"- Supprimées : {len(c.removed)}")
        L.append(f"- Modifiées : {len(c.modified)}")
    else:
        L.append("_Pas de comparaison (pas de source précédente)._")
    L.append("")
    return L


def _section_coquilles_final(ctx: PipelineContext) -> list[str]:
    """Section 3 — Coquilles source (rapport final)."""
    L: list[str] = ["## 3. Coquilles source\n"]
    if ctx.typos_found:
        L.append("| Coquille | Correction | Clés |")
        L.append("|---|---|---|")
        for entry in ctx.typos_found:
            L.append(
                f"| `{entry['typo']}` | `{entry['correction']}` | "
                f"{', '.join(entry['keys'][:PREVIEW_LIMIT])} |"
            )
    else:
        L.append("_Aucune coquille connue détectée._")
    L.append(
        f"\nCorrections appliquées : {'oui ✅' if ctx.typos_corrected else 'non'}\n"
    )
    return L


def _section_gap_final(ctx: PipelineContext) -> list[str]:
    """Section 4 — Écart de traduction (rapport final)."""
    L: list[str] = ["## 4. Écart de traduction\n"]
    if ctx.gaps:
        L.append(
            "| Langue | Présentes | À ajouter | À supprimer | À modifier | "
            "Incomplètes | Sur-remplies |"
        )
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        for g in ctx.gaps:
            L.append(
                f"| {g.lang} | {g.count} | {len(g.to_add)} | {len(g.to_remove)} | "
                f"{len(g.to_modify)} | {len(g.incomplete)} | {len(g.over_filled)} |"
            )
    else:
        L.append("_Écart non calculé._")
    L.append("")
    return L


def _section_plan_final(ctx: PipelineContext) -> list[str]:
    """Section 5 — Plan d'action (rapport final)."""
    return [
        "## 5. Plan d'action\n",
        f"- Provider utilisé : **{ctx.provider}**",
        f"- Langues traitées : {', '.join(ctx.languages)}",
        "",
    ]


def _section_translation_final(ctx: PipelineContext, export_dir: Path) -> list[str]:
    """Section 6 — Traduction (rapport final)."""
    L: list[str] = ["## 6. Traduction\n"]
    L.append(f"- Dossier d'export : `{export_dir.name if export_dir else 'N/A'}`")
    if export_dir and export_dir.exists():
        files = list(export_dir.glob("translation_en_*.json"))
        L.append(f"- Fichiers produits : {len(files)}")
        for f in sorted(files):
            count = len(json.loads(f.read_text(encoding="utf-8")))
            L.append(f"  - `{f.name}` : {count} clés")
    L.append("")
    return L


def _section_validation_final(
    ctx: PipelineContext, validation_report: ValidationReport | None
) -> list[str]:
    """Section 7 — Validation (rapport final)."""
    L: list[str] = ["## 7. Validation\n"]
    if validation_report:
        L.append("| Langue | Clés | Manquantes | Excédantes | Vides | Placeholders |")
        L.append("|---|---:|---:|---:|---:|---:|")
        for lv in validation_report.languages:
            L.append(
                f"| {lv.lang} | {lv.count} | {len(lv.missing)} | {len(lv.extra)} | "
                f"{len(lv.empty)} | {len(lv.placeholder_issues)} |"
            )
        L.append(
            f"\n**Total** : {validation_report.total_missing} manquantes, "
            f"{validation_report.total_extra} excédantes, "
            f"{validation_report.total_empty} vides, "
            f"{validation_report.total_placeholder_issues} placeholders."
        )
    else:
        L.append("_Validation non exécutée._")
    L.append("")
    return L


def _section_misalignments_final(
    ctx: PipelineContext, misalignments: dict[str, list[dict]]
) -> list[str]:
    """Section 8 — Mésalignements (rapport final)."""
    L: list[str] = ["## 8. Mésalignements\n"]
    total_misalign = sum(len(v) for v in misalignments.values()) if misalignments else 0
    L.append(
        f"**{total_misalign} mésalignement(s) potentiel(s)** détecté(s) "
        f"(heuristique, à vérifier manuellement).\n"
    )
    if misalignments:
        for lang, mism_list in misalignments.items():
            if mism_list:
                L.append(f"### {lang.upper()} ({len(mism_list)})\n")
                L.append("| Texte source | Clés | Traductions |")
                L.append("|---|---|---|")
                for m in mism_list[:MAX_REPORT_ENTRIES]:
                    keys = ", ".join(m["keys"])
                    trans = " / ".join(
                        f"{k}={short_repr(v)}"
                        for k, v in m.get("translations", {}).items()
                    )
                    L.append(f"| {short_repr(m['source_text'])} | {keys} | {trans} |")
    L.append("")
    return L


def _section_order_final(ctx: PipelineContext, export_dir: Path) -> list[str]:
    """Section 9 — Ordre (rapport final)."""
    L: list[str] = ["## 9. Ordre\n"]
    if export_dir and export_dir.exists() and ctx.new_source:
        source_keys = list(json_load(ctx.new_source).keys())
        all_aligned = True
        for lang in ctx.languages:
            path = export_dir / f"translation_en_{lang}.json"
            if not path.exists():
                continue
            trans_keys = list(json_load(path).keys())
            # Vérifier que les clés source sont dans l'ordre
            source_in_trans = [k for k in source_keys if k in trans_keys]
            aligned = source_in_trans == [k for k in trans_keys if k in source_keys]
            status = "✅" if aligned else "❌"
            L.append(f"- {lang.upper()}: {status}")
            if not aligned:
                all_aligned = False
        aligned_msg = (
            "Tous les fichiers sont alignés sur l'ordre source ✅"
            if all_aligned
            else "Des fichiers ne sont pas alignés ❌"
        )
        L.append(f"\n**{aligned_msg}**")
    else:
        L.append("_Vérification de l'ordre non disponible._")
    L.append("")
    return L


def build_final_report(
    ctx: PipelineContext,
    export_dir: Path,
    validation_report: ValidationReport | None,
    misalignments: dict[str, list[dict]],
) -> str:
    """Construit le rapport markdown final consolidé (9 sections).

    Assemble les 9 sections `_section_*` (Sprint 2 - tâche 17) en un seul
    document markdown.
    """
    L: list[str] = []
    L.append("# Rapport final du pipeline de traduction COP\n")
    date_str = (
        ctx.new_import_folder.name.replace("_Import", "")
        if ctx.new_import_folder
        else "?"
    )
    L.append(f"- Date : {date_str}")
    L.append(f"- Source : `{ctx.new_source}`\n")

    L.extend(_section_source_final(ctx))
    L.extend(_section_comparison_final(ctx))
    L.extend(_section_coquilles_final(ctx))
    L.extend(_section_gap_final(ctx))
    L.extend(_section_plan_final(ctx))
    L.extend(_section_translation_final(ctx, export_dir))
    L.extend(_section_validation_final(ctx, validation_report))
    L.extend(_section_misalignments_final(ctx, misalignments))
    L.extend(_section_order_final(ctx, export_dir))
    return "\n".join(L)


def step11_final_report(
    ctx: PipelineContext,
    export_dir: Path,
    validation_report: ValidationReport | None,
    misalignments: dict[str, list[dict]],
) -> Path | None:
    """Génère le rapport consolidé final et l'écrit dans doc/."""
    step_banner(11, "Rapport consolidé final")

    if ctx.dry_run:
        print("  [dry-run] Rapport final non écrit.")
        return None

    report_md = build_final_report(ctx, export_dir, validation_report, misalignments)
    date_str = datetime.now().strftime("%Y_%m_%d")
    doc_dir = REPO_ROOT / "doc"
    path = doc_dir / f"{date_str}_Pipeline_Report.md"
    write_report(report_md, path)
    print(f"  Rapport final écrit : {path}")
    return path


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
    p.add_argument(
        "--mode",
        choices=["json", "dropdown"],
        default=None,
        help="Force le type de pipeline (json ou dropdown). "
        "Détection auto par extension si non spécifié.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Désactive le cache du service (.translation_cache.json).",
    )
    # Flags spécifiques au mode dropdown (C5) — acceptés par le parser JSON
    # pour permettre `--mode dropdown --retranslate-all` via pipeline.py.
    # `default=None`/`False` pour ne pas perturber le mode JSON.
    p.add_argument("--retranslate-all", action="store_true", default=False)
    p.add_argument("--retranslate", type=str, default=None)
    p.add_argument("--format", choices=["json", "xlsx", "auto"], default=None)
    return p


def run_pipeline(args: argparse.Namespace) -> int:
    """Point d'entrée : dispatch vers le pipeline JSON ou dropdown.

    Détection du type de source :
      1. Flag `--mode` explicite (prioritaire)
      2. Auto-détection par extension de `--source` (si fourni)
      3. Défaut : JSON (comportement historique)
    """
    # Déterminer le mode
    if args.mode:
        mode = args.mode
    elif args.source:
        mode = detect_source_kind(args.source)
    else:
        mode = "json"  # défaut historique

    if mode == "dropdown":
        from pipeline_dropdown import run_pipeline_dropdown

        return run_pipeline_dropdown(args)

    return _run_pipeline_json(args)


def _run_pipeline_json(args: argparse.Namespace) -> int:
    """Exécute le pipeline JSON (étapes 1-11, Phases 1-3)."""
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
        ctx.languages = parse_languages_arg(args.languages)
    if getattr(args, "no_cache", False):
        ctx.no_cache = True

    logger.info(
        "🚀 Pipeline de traduction COP — Phases 1-3 (analyse + exécution + validation)"
    )
    logger.info(
        "   Provider : %s | Langues : %s", ctx.provider, ", ".join(ctx.languages)
    )
    if ctx.dry_run:
        logger.info("   Mode : dry-run (analyse seule, pas d'exécution)")
    if ctx.no_cache:
        logger.info("   Cache service : désactivé (--no-cache)")

    try:
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        step3_detect_typos(ctx)
        step4_analyze_gap(ctx)
        confirmed = step5_report_and_confirm(ctx)
    except FileNotFoundError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 2

    if ctx.dry_run:
        # Dry-run unifié : simuler les étapes 6-11 sans rien exécuter.
        # Chaque étape a sa propre garde `dry_run` qui affiche un message et
        # skippe. On utilise le dernier export existant comme dossier factice ;
        # sinon le dossier de base output/ (C12 : plus de Path("/dev/null")
        # non portable — les étapes dry-run n'accèdent pas au chemin).
        simulated_export = ctx.export_dir or (TRANSLATOR_DIR / "output")
        step6_prepopulate_and_manage(ctx)  # skippé (retourne None)
        step7_translate(ctx, simulated_export)  # skippé
        step8_reorder(ctx, simulated_export)  # skippé
        step9_validate(ctx, simulated_export)  # skippé
        step10_detect_misalignments(ctx, simulated_export)  # skippé
        step11_final_report(ctx, simulated_export, None, {})  # skippé
        print("\n⏹  [dry-run] Simulation complète — aucune exécution.")
        return 0

    if not confirmed:
        print("\n⏹  Parcours arrêté (confirmation refusée).")
        return 0

    try:
        export_dir = step6_prepopulate_and_manage(ctx)
    except FileNotFoundError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        return 2

    if not export_dir:
        print("\n⏹  Traduction annulée à l'étape 6.")
        return 0

    try:
        step7_translate(ctx, export_dir)
        step8_reorder(ctx, export_dir)
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ Erreur durant la traduction : {e}", file=sys.stderr)
        return 3

    # Phase 3 — Validation + mésalignements + rapport final
    validation_report = step9_validate(ctx, export_dir)
    misalignments = step10_detect_misalignments(ctx, export_dir)
    step11_final_report(ctx, export_dir, validation_report, misalignments)

    print("\n✅ Pipeline terminé (Phases 1-3).")
    return 0


def main() -> None:
    args = build_parser().parse_args()
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
