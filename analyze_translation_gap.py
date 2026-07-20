#!/usr/bin/env python3
"""Analyse the gap between already-translated export files and a new EN source.

For each target language file in an export folder, compute vs the new source:
- to_add:    keys present in source but missing in the translation file
- to_remove: keys present in the translation file but absent from source
- to_modify: keys whose source VALUE changed between old_source and new_source
             (i.e. the existing target translation is now stale)
- incomplete: keys with an empty translation while the source has non-empty text
- over_filled: keys with a non-empty translation while the source text is empty
               (manual back-fill, not reproducible by the pipeline)

Outputs a markdown report and a machine-readable JSON.

Usage:
    python analyze_translation_gap.py \
        --source translator/source/2026_06_23_Import/en8.json \
        --old-source translator/source/2026_06_12_Import/en 7.json \
        --export-dir translator/output/2026_06_12_Export \
        --languages ar cz de fr it sk \
        --report doc/2026_06_23_Translation_Gap_Analysis.md \
        --json doc/2026_06_23_Translation_Gap_Analysis.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f"Source {path} n'est pas un objet JSON (type: {type(data).__name__})"
        )
    return data


def is_empty(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


@dataclass
class LangGap:
    lang: str
    file: Path
    count: int
    to_add: list[str] = field(default_factory=list)
    to_remove: list[str] = field(default_factory=list)
    to_modify: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)
    over_filled: list[str] = field(default_factory=list)


def analyze(lang: str, tpath: Path, src: dict, old_src: dict) -> LangGap:
    t = load_json(tpath)
    tk, sk, ok = set(t), set(src), set(old_src)
    g = LangGap(lang, tpath, len(t))
    g.to_add = sorted(sk - tk)
    g.to_remove = sorted(tk - sk)
    g.to_modify = sorted(k for k in (ok & sk) if old_src[k] != src[k] and k in t)
    g.incomplete = sorted(
        k for k in (tk & sk) if is_empty(t[k]) and not is_empty(src[k])
    )
    g.over_filled = sorted(
        k for k in (tk & sk) if not is_empty(t[k]) and is_empty(src[k])
    )
    return g


def render(src: dict, gaps: list[LangGap]) -> str:
    L: list[str] = []
    L.append(
        "# Analyse de l'écart de traduction — fichiers existants vs nouvelle source\n"
    )
    L.append(f"- Source (nouvelle) : `{gaps[0].file.parent}` vs source EN courante")
    L.append(f"- Langues analysées : {', '.join(g.lang for g in gaps)}\n")

    L.append("## Synthèse par langue\n")
    L.append(
        "| Langue | Clés présentes | À ajouter | À supprimer | À modifier (source modifiée) | Incomplètes (trad vide, source non vide) | Sur-remplies (trad non vide, source vide) |"
    )
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for g in gaps:
        L.append(
            f"| {g.lang} | {g.count} | {len(g.to_add)} | {len(g.to_remove)} | {len(g.to_modify)} | {len(g.incomplete)} | {len(g.over_filled)} |"
        )
    L.append("")

    # Aggregate add set (should be identical across langs)
    add_sets = [set(g.to_add) for g in gaps]
    common_add = sorted(set.intersection(*add_sets)) if add_sets else []
    L.append(f"## Clés à ajouter (communes à toutes les langues : {len(common_add)})\n")
    if common_add:
        L.append("| Clé | Valeur EN source |")
        L.append("|---|---|")
        for k in common_add:
            L.append(f"| `{k}` | {short(src.get(k))} |")
    else:
        L.append("_Aucune clé commune à ajouter._")
    L.append("")

    # Per-lang add differences (if any)
    for g in gaps:
        diff = set(g.to_add) - set(common_add)
        if diff:
            L.append(f"### Ajouts spécifiques à {g.lang} ({len(diff)})\n")
            for k in sorted(diff):
                L.append(f"- `{k}` : {short(src.get(k))}")
            L.append("")

    # Remove (should be identical)
    rem_sets = [set(g.to_remove) for g in gaps]
    common_rem = sorted(set.intersection(*rem_sets)) if rem_sets else []
    L.append(f"## Clés à supprimer (communes : {len(common_rem)})\n")
    if common_rem:
        L.append("| Clé |")
        L.append("|---|")
        for k in common_rem:
            L.append(f"| `{k}` |")
    else:
        L.append("_Aucune._")
    L.append("")

    # Modify
    mod_sets = [set(g.to_modify) for g in gaps]
    common_mod = sorted(set.intersection(*mod_sets)) if mod_sets else []
    L.append(
        f"## Clés à modifier — source modifiée entre ancienne et nouvelle source (communes : {len(common_mod)})\n"
    )
    if common_mod:
        L.append("| Clé | Nouvelle valeur EN |")
        L.append("|---|---|")
        for k in common_mod:
            L.append(f"| `{k}` | {short(src.get(k))} |")
    else:
        L.append("_Aucune._")
    L.append("")

    # Incomplete
    L.append(
        "## Traductions incomplètes (vide côté cible, texte présent côté source)\n"
    )
    for g in gaps:
        if g.incomplete:
            L.append(f"### {g.lang} ({len(g.incomplete)})\n")
            for k in g.incomplete:
                L.append(f"- `{k}` : {short(src.get(k))}")
            L.append("")
        else:
            L.append(f"### {g.lang} : _aucune_\n")

    # Over-filled
    L.append("## Traductions sur-remplies (valeur côté cible, source vide)\n")
    L.append(
        "> Ces clés ont une source EN vide mais une traduction non vide (back-fill manuel). "
    )
    L.append(
        "Elles ne seront pas régénérées par le pipeline (rien à traduire côté source). "
    )
    L.append("À propager manuellement vers les autres langues si pertinent.\n")
    for g in gaps:
        if g.over_filled:
            L.append(f"### {g.lang} ({len(g.over_filled)})\n")
            L.append("| Clé | Valeur cible actuelle |")
            L.append("|---|---|")
            t = load_json(g.file)
            for k in g.over_filled:
                L.append(f"| `{k}` | {short(t.get(k))} |")
            L.append("")
        else:
            L.append(f"### {g.lang} : _aucune_\n")

    # Action plan
    L.append("## Plan d'action recommandé\n")
    total_add = len(common_add)
    total_rem = len(common_rem)
    total_mod = len(common_mod)
    L.append(
        f"1. **Ajouter** {total_add} nouvelle(s) clé(s) × {len(gaps)} langue(s) = {total_add * len(gaps)} traductions à produire."
    )
    L.append(
        f"2. **Supprimer** {total_rem} clé(s) orpheline(s) des fichiers cibles (commun à toutes les langues)."
    )
    L.append(
        f"3. **Modifier** {total_mod} clé(s) dont la source a changé (retraduire)."
    )
    L.append("4. **Compléter** les traductions incomplètes (voir section dédiée).")
    L.append(
        "5. **Décider** du sort des traductions sur-remplies (back-fill FR) : propager aux autres langues ou laisser."
    )
    L.append("")
    return "\n".join(L)


def short(v) -> str:
    s = str(v).replace("\n", " ")
    if len(s) > 100:
        return s[:97] + "..."
    return s


def analyze_export(
    source_path: Path,
    old_source_path: Path,
    export_dir: Path,
    languages: list[str],
) -> list[LangGap]:
    """Analyse l'écart de traduction pour chaque langue d'un export.

    Helper d'usage programmatique (depuis le pipeline) : charge la source +
    l'ancienne source, puis appelle `analyze()` pour chaque langue.
    """
    src = load_json(source_path)
    old_src = load_json(old_source_path)
    return [
        analyze(lg, export_dir / f"translation_en_{lg}.json", src, old_src)
        for lg in languages
    ]


def gaps_to_dict(
    gaps: list[LangGap],
    source_path: Path,
    old_source_path: Path,
    export_dir: Path,
) -> dict:
    """Sérialise une liste de LangGap en dict (machine-readable)."""
    return {
        "source": str(source_path),
        "old_source": str(old_source_path),
        "export_dir": str(export_dir),
        "languages": [
            {
                "lang": g.lang,
                "file": str(g.file),
                "count": g.count,
                "to_add": g.to_add,
                "to_remove": g.to_remove,
                "to_modify": g.to_modify,
                "incomplete": g.incomplete,
                "over_filled": g.over_filled,
            }
            for g in gaps
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Analyse translation gap vs a new EN source."
    )
    ap.add_argument("--source", type=Path, required=True, help="New EN source JSON")
    ap.add_argument(
        "--old-source",
        type=Path,
        required=True,
        help="Previous EN source JSON (for modify detection)",
    )
    ap.add_argument(
        "--export-dir",
        type=Path,
        required=True,
        help="Folder with translation_en_<lang>.json files",
    )
    ap.add_argument(
        "--languages",
        type=str,
        required=True,
        help="Comma-separated language codes, e.g. ar,cz,de,fr,it,sk",
    )
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    src = load_json(args.source)
    languages = [lg.strip() for lg in args.languages.split(",") if lg.strip()]
    gaps = analyze_export(args.source, args.old_source, args.export_dir, languages)

    md = render(src, gaps)
    if args.report:
        args.report.write_text(md, encoding="utf-8")
        print(f"Report written to {args.report}")
    else:
        print(md)

    if args.json:
        data = gaps_to_dict(gaps, args.source, args.old_source, args.export_dir)
        args.json.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON written to {args.json}")


if __name__ == "__main__":
    main()
