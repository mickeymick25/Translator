#!/usr/bin/env python3
"""Compare two COP source JSON exports (en7 vs en8) and emit a structured report.

Usage:
    python compare_sources.py <old.json> <new.json> [--report <path>]

Produces:
- counts (old, new, common)
- added keys (in new, not in old)
- removed keys (in old, not in new)
- modified values (same key, different value) with diff snippet
- unchanged keys count
- value-length stats for modified entries
- placeholder/format check (%s, {name}, <b>, ICU {n, plural, ...})
- prefix-group breakdown of added/removed keys (e.g. PA_, LO_, CO_, MS ...)
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"%[sd]|\{[^}]+\}|<[^>]+>|\{[0-9]+\}")
ICU_RE = re.compile(r"\{[^}]+,\s*(plural|select|selectordinal)", re.I)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def prefix_of(key: str) -> str:
    """Group key by its leading token before the first '_' (or whole key)."""
    if "_" in key:
        return key.split("_", 1)[0]
    if " " in key:
        return key.split(" ", 1)[0]
    return key


@dataclass
class Comparison:
    old_path: Path
    new_path: Path
    old: dict
    new: dict
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[tuple[str, str, str]] = field(default_factory=list)  # key, old, new
    unchanged: list[str] = field(default_factory=list)

    def compute(self) -> "Comparison":
        old_keys = set(self.old)
        new_keys = set(self.new)
        self.added = sorted(new_keys - old_keys, key=lambda k: (prefix_of(k), k))
        self.removed = sorted(old_keys - new_keys, key=lambda k: (prefix_of(k), k))
        common = old_keys & new_keys
        for k in sorted(common, key=lambda k: (prefix_of(k), k)):
            ov, nv = self.old[k], self.new[k]
            if ov != nv:
                self.modified.append((k, ov, nv))
            else:
                self.unchanged.append(k)
        return self

    @property
    def added_by_prefix(self) -> dict[str, list[str]]:
        d: dict[str, list[str]] = defaultdict(list)
        for k in self.added:
            d[prefix_of(k)].append(k)
        return dict(sorted(d.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    @property
    def removed_by_prefix(self) -> dict[str, list[str]]:
        d: dict[str, list[str]] = defaultdict(list)
        for k in self.removed:
            d[prefix_of(k)].append(k)
        return dict(sorted(d.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    def modified_with_placeholder_delta(
        self,
    ) -> list[tuple[str, str, str, list[str], list[str]]]:
        out = []
        for k, ov, nv in self.modified:
            o_ph = sorted(set(PLACEHOLDER_RE.findall(str(ov))))
            n_ph = sorted(set(PLACEHOLDER_RE.findall(str(nv))))
            out.append((k, ov, nv, o_ph, n_ph))
        return out

    def modified_placeholder_mismatch(
        self,
    ) -> list[tuple[str, str, str, list[str], list[str]]]:
        return [
            (k, ov, nv, o_ph, n_ph)
            for k, ov, nv, o_ph, n_ph in self.modified_with_placeholder_delta()
            if o_ph != n_ph
        ]


def value_diff(key: str, ov: str, nv: str) -> str:
    ov_l = str(ov).splitlines() or [str(ov)]
    nv_l = str(nv).splitlines() or [str(nv)]
    diff = list(
        unified_diff(
            ov_l, nv_l, fromfile=f"{key} (old)", tofile=f"{key} (new)", lineterm=""
        )
    )
    return "\n".join(diff) if diff else "(single-line change)"


def render(c: Comparison) -> str:
    lines: list[str] = []
    lines.append(
        f"# Comparaison des sources COP : {c.old_path.name} -> {c.new_path.name}\n"
    )
    lines.append(f"- Ancienne source : `{c.old_path}`")
    lines.append(f"- Nouvelle source : `{c.new_path}`\n")
    lines.append("## Synthèse\n")
    lines.append("| Métrique | Valeur |")
    lines.append("|---|---|")
    lines.append(f"| Clés (ancienne) | {len(c.old)} |")
    lines.append(f"| Clés (nouvelle) | {len(c.new)} |")
    lines.append(f"| Communes | {len(c.unchanged) + len(c.modified)} |")
    lines.append(f"| Inchangées | {len(c.unchanged)} |")
    lines.append(f"| Modifiées (valeur) | {len(c.modified)} |")
    lines.append(f"| Ajoutées | {len(c.added)} |")
    lines.append(f"| Supprimées | {len(c.removed)} |")
    ph_mismatch = c.modified_placeholder_mismatch()
    lines.append(f"| Modifs avec placeholder divergent | {len(ph_mismatch)} |")
    lines.append("")

    # Added
    lines.append("## Clés ajoutées (" + str(len(c.added)) + ")\n")
    if c.added:
        lines.append("### Par préfixe\n")
        lines.append("| Préfixe | Nombre | Exemples |")
        lines.append("|---|---:|---|")
        for pfx, keys in c.added_by_prefix.items():
            sample = ", ".join(f"`{k}`" for k in keys[:5])
            extra = f" (+{len(keys) - 5})" if len(keys) > 5 else ""
            lines.append(f"| {pfx} | {len(keys)} | {sample}{extra} |")
        lines.append("")
        lines.append("### Liste complète\n")
        for k in c.added:
            v = c.new[k]
            lines.append(f"- `{k}` : {short(v)}")
    else:
        lines.append("_Aucune_\n")
    lines.append("")

    # Removed
    lines.append("## Clés supprimées (" + str(len(c.removed)) + ")\n")
    if c.removed:
        lines.append("### Par préfixe\n")
        lines.append("| Préfixe | Nombre | Exemples |")
        lines.append("|---|---:|---|")
        for pfx, keys in c.removed_by_prefix.items():
            sample = ", ".join(f"`{k}`" for k in keys[:5])
            extra = f" (+{len(keys) - 5})" if len(keys) > 5 else ""
            lines.append(f"| {pfx} | {len(keys)} | {sample}{extra} |")
        lines.append("")
        lines.append("### Liste complète\n")
        for k in c.removed:
            v = c.old[k]
            lines.append(f"- `{k}` : {short(v)}")
    else:
        lines.append("_Aucune_\n")
    lines.append("")

    # Modified
    lines.append("## Clés modifiées (" + str(len(c.modified)) + ")\n")
    if c.modified:
        lines.append(
            "### Modifs avec divergences de placeholders ("
            + str(len(ph_mismatch))
            + ")\n"
        )
        if ph_mismatch:
            lines.append("| Clé | Placeholders old | Placeholders new |")
            lines.append("|---|---|---|")
            for k, ov, nv, o_ph, n_ph in ph_mismatch:
                lines.append(f"| `{k}` | {o_ph} | {n_ph} |")
            lines.append("")
            lines.append("### Détail de ces divergences\n")
            for k, ov, nv, o_ph, n_ph in ph_mismatch:
                lines.append(f"#### `{k}`\n")
                lines.append(f"- old: {short(ov)}")
                lines.append(f"- new: {short(nv)}\n")
        else:
            lines.append("_Aucune divergence de placeholders détectée._\n")

        lines.append("### Détail des valeurs modifiées (échantillon <= 120)\n")
        sample = c.modified if len(c.modified) <= 120 else c.modified[:120]
        for k, ov, nv in sample:
            lines.append(f"#### `{k}`\n")
            lines.append("```diff")
            lines.append(value_diff(k, ov, nv))
            lines.append("```\n")
        if len(c.modified) > 120:
            lines.append(
                f"_... et {len(c.modified) - 120} autres modifications non affichées._\n"
            )
    else:
        lines.append("_Aucune valeur modifiée._\n")
    lines.append("")

    # Prefix movement summary
    lines.append("## Mouvement par préfixe (ajouts - suppressions)\n")
    all_prefixes = set(c.added_by_prefix) | set(c.removed_by_prefix)
    lines.append("| Préfixe | Ajouts | Suppressions | Solde |")
    lines.append("|---|---:|---:|---:|")
    for pfx in sorted(
        all_prefixes,
        key=lambda p: (
            -(len(c.added_by_prefix.get(p, [])) - len(c.removed_by_prefix.get(p, [])))
        ),
    ):
        a = len(c.added_by_prefix.get(pfx, []))
        r = len(c.removed_by_prefix.get(pfx, []))
        lines.append(f"| {pfx} | {a} | {r} | {a - r} |")
    lines.append("")
    return "\n".join(lines)


def short(v) -> str:
    s = str(v).replace("\n", " ")
    if len(s) > 120:
        return s[:117] + "..."
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare two COP source JSON exports.")
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument(
        "--report", type=Path, default=None, help="Optional output .md path"
    )
    ap.add_argument(
        "--json", type=Path, default=None, help="Optional machine-readable .json path"
    )
    args = ap.parse_args()

    c = Comparison(
        args.old, args.new, load_json(args.old), load_json(args.new)
    ).compute()

    md = render(c)
    if args.report:
        args.report.write_text(md, encoding="utf-8")
        print(f"Report written to {args.report}")
    else:
        print(md)

    if args.json:
        data = {
            "old_path": str(args.old),
            "new_path": str(args.new),
            "counts": {
                "old": len(c.old),
                "new": len(c.new),
                "unchanged": len(c.unchanged),
                "modified": len(c.modified),
                "added": len(c.added),
                "removed": len(c.removed),
            },
            "added": c.added,
            "removed": c.removed,
            "modified": [{"key": k, "old": ov, "new": nv} for k, ov, nv in c.modified],
            "added_by_prefix": {p: ks for p, ks in c.added_by_prefix.items()},
            "removed_by_prefix": {p: ks for p, ks in c.removed_by_prefix.items()},
            "placeholder_mismatch": [
                {"key": k, "old": ov, "new": nv, "old_ph": o_ph, "new_ph": n_ph}
                for k, ov, nv, o_ph, n_ph in c.modified_placeholder_mismatch()
            ],
        }
        args.json.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON written to {args.json}")


if __name__ == "__main__":
    main()
