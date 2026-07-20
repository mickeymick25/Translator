#!/usr/bin/env python3
"""Validate translation files against a source JSON.

Checks:
1. Missing keys (present in source but not in a translation)
2. Extra keys (present in translation but not in source)
3. Empty/null translations
4. Potentially untranslated values (identical to English source)
5. Placeholder preservation (%s, {name}, <b>, ICU)
6. Duplicate keys

Usage:
    # Auto-detect the latest *_Export and *_Import folders
    python validate_translations.py

    # Explicit folders / languages
    python validate_translations.py \
        --export-dir translator/output/2026_06_23_Export \
        --source-dir translator/source/2026_06_23_Import \
        --languages ar,cz,de,fr,it,sk

    # Machine-readable JSON output
    python validate_translations.py --json report.json

Programmatic use:
    from validate_translations import validate, render_report
    report = validate(source_path, export_dir, languages)
    print(render_report(report))
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pipeline_common import PLACEHOLDER_PATTERNS  # noqa: E402  (C14)

DEFAULT_LANGUAGES = ["ar", "cz", "de", "fr", "it", "sk", "pt", "es", "hu"]

# Placeholders patterns that should be preserved in translations (C14 :
# partagés via pipeline_common.PLACEHOLDER_PATTERNS — évite la divergence
# avec compare_sources.py).


def _latest_folder(parent: Path, suffix: str) -> Path | None:
    """Return the most recent subfolder of `parent` whose name ends with `suffix`.

    Folders are sorted by name descending (the date prefix orders them
    chronologically, e.g. '2026_06_23_Export').
    """
    if not parent.exists():
        return None
    candidates = sorted(
        (d for d in parent.iterdir() if d.is_dir() and d.name.endswith(suffix)),
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_json(filepath):
    """Load a JSON file and return as dict.

    Raises ValueError si le JSON n'est pas un objet (C13).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"Source {filepath} n'est pas un objet JSON (type: {type(data).__name__})"
        )
    return data


def extract_placeholders(text):
    """Extract all placeholders from a text string."""
    found = []
    for pattern in PLACEHOLDER_PATTERNS:
        found.extend(re.findall(pattern, text))
    return found


def _pick_source_file(source_dir: Path) -> Path | None:
    """Pick the main source JSON in an import folder (largest *.json)."""
    json_files = list(source_dir.glob("*.json"))
    if not json_files:
        return None
    return max(json_files, key=lambda p: p.stat().st_size)


@dataclass
class LangValidation:
    """Résultat de validation pour une seule langue."""

    lang: str
    file: Path
    count: int = 0
    loaded: bool = False
    load_error: str | None = None
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    untranslated: list[tuple[str, str]] = field(
        default_factory=list
    )  # (key, src_value)
    placeholder_issues: list[tuple[str, list[str], list[str]]] = field(
        default_factory=list
    )
    duplicates: dict[str, int] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Rapport de validation consolidé sur toutes les langues."""

    source_file: Path
    source_keys: set[str]
    source_count: int
    languages: list[LangValidation]

    @property
    def total_missing(self) -> int:
        return sum(len(lv.missing) for lv in self.languages)

    @property
    def total_extra(self) -> int:
        return sum(len(lv.extra) for lv in self.languages)

    @property
    def total_empty(self) -> int:
        return sum(len(lv.empty) for lv in self.languages)

    @property
    def total_untranslated(self) -> int:
        return sum(len(lv.untranslated) for lv in self.languages)

    @property
    def total_placeholder_issues(self) -> int:
        return sum(len(lv.placeholder_issues) for lv in self.languages)

    @property
    def all_ok(self) -> bool:
        return (
            self.total_missing == 0
            and self.total_extra == 0
            and self.total_empty == 0
            and self.total_placeholder_issues == 0
        )

    def to_dict(self) -> dict:
        """Sérialise en dict (machine-readable)."""
        return {
            "source_file": str(self.source_file),
            "source_count": self.source_count,
            "languages": [
                {
                    "lang": lv.lang,
                    "file": str(lv.file),
                    "count": lv.count,
                    "loaded": lv.loaded,
                    "load_error": lv.load_error,
                    "missing": lv.missing,
                    "extra": lv.extra,
                    "empty": lv.empty,
                    "untranslated": [
                        {"key": k, "source": v} for k, v in lv.untranslated
                    ],
                    "placeholder_issues": [
                        {"key": k, "source": s, "translation": t}
                        for k, s, t in lv.placeholder_issues
                    ],
                    "duplicates": lv.duplicates,
                }
                for lv in self.languages
            ],
            "totals": {
                "missing": self.total_missing,
                "extra": self.total_extra,
                "empty": self.total_empty,
                "untranslated": self.total_untranslated,
                "placeholder_issues": self.total_placeholder_issues,
            },
            "all_ok": self.all_ok,
        }


def _detect_duplicate_keys(filepath: Path) -> dict[str, int]:
    r"""Détecte les clés JSON en doublon pendant le parsing (C7).

    Utilise `json.JSONDecoder.object_pairs_hook` pour signaler les doublons
    au moment du parsing, au lieu de découper le fichier à la regex (approche
    cassée pour JSON minifié, objets imbriqués, clés contenant `":"` ou
    échappées en `\uXXXX`). Ne retourne que les clés apparaissant plus d'une
    fois au sein d'un même objet.
    """
    if not filepath.exists():
        return {}
    counts: dict[str, int] = defaultdict(int)

    def _hook(pairs):
        d = {}
        for k, v in pairs:
            counts[k] += 1
            d[k] = v
        return d

    with open(filepath, "r", encoding="utf-8") as f:
        json.load(f, object_pairs_hook=_hook)
    return {k: v for k, v in counts.items() if v > 1}


def validate_lang(
    lang: str,
    translation_path: Path,
    source_data: dict,
    source_keys: set[str],
) -> LangValidation:
    """Exécute les 6 contrôles pour un fichier de langue contre la source."""
    lv = LangValidation(lang=lang, file=translation_path)

    try:
        data = load_json(translation_path)
        lv.loaded = True
        lv.count = len(data)
    except Exception as e:  # noqa: BLE001 — reporter toute erreur de load
        lv.loaded = False
        lv.load_error = str(e)
        return lv

    trans_keys = set(data.keys())

    # 1. Missing keys
    lv.missing = sorted(source_keys - trans_keys)

    # 2. Extra keys
    lv.extra = sorted(trans_keys - source_keys)

    # 3. Empty/null translations
    lv.empty = sorted(
        key
        for key, value in data.items()
        if value is None or (isinstance(value, str) and value.strip() == "")
    )

    # 4. Potentially untranslated values (identical to source, len > 3)
    lv.untranslated = []
    for key in source_keys & trans_keys:
        src_val = source_data.get(key, "")
        trans_val = data.get(key, "")
        if isinstance(src_val, str) and isinstance(trans_val, str):
            if src_val == trans_val and len(src_val) > 3:
                lv.untranslated.append((key, src_val))
    lv.untranslated.sort(key=lambda kv: kv[0])

    # 5. Placeholder preservation
    lv.placeholder_issues = []
    for key in source_keys & trans_keys:
        src_val = source_data.get(key, "")
        trans_val = data.get(key, "")
        if not isinstance(src_val, str) or not isinstance(trans_val, str):
            continue
        src_ph = extract_placeholders(src_val)
        trans_ph = extract_placeholders(trans_val)
        if src_ph and sorted(src_ph) != sorted(trans_ph):
            lv.placeholder_issues.append((key, src_ph, trans_ph))

    # 6. Duplicate keys
    lv.duplicates = _detect_duplicate_keys(translation_path)

    return lv


def validate(
    source_path: Path,
    export_dir: Path,
    languages: list[str],
) -> ValidationReport:
    """Valide tous les fichiers `translation_en_<lang>.json` contre la source.

    Args:
        source_path: Chemin du fichier source JSON.
        export_dir: Dossier contenant les `translation_en_<lang>.json`.
        languages: Codes de langues cibles (ex : ['ar', 'cz', 'fr']).

    Returns:
        Un ValidationReport avec les résultats par langue.
    """
    source_data = load_json(source_path)
    source_keys = set(source_data.keys())

    results = [
        validate_lang(
            lang,
            export_dir / f"translation_en_{lang}.json",
            source_data,
            source_keys,
        )
        for lang in languages
    ]

    return ValidationReport(
        source_file=source_path,
        source_keys=source_keys,
        source_count=len(source_keys),
        languages=results,
    )


def render_report(report: ValidationReport) -> str:
    """Génère le rapport textuel (compatible avec la sortie CLI historique)."""
    L: list[str] = []
    L.append("=" * 70)
    L.append(f"COP Translation Validation Report - {report.source_file.parent.name}")
    L.append("=" * 70)
    L.append(
        f"\n📄 Source file: {report.source_file.name}  "
        f"(in {report.source_file.parent.name})"
    )
    L.append(f"   Source keys: {report.source_count}")

    for lv in report.languages:
        if lv.loaded:
            L.append(f"   {lv.lang.upper()}: {lv.count} keys")
        else:
            L.append(f"   {lv.lang.upper()}: ❌ Error loading: {lv.load_error}")

    # ─── 1. Missing keys ───────────────────────────────────────────────
    L.append("\n" + "─" * 70)
    L.append("1️⃣  MISSING KEYS (present in source but not in translation)")
    L.append("─" * 70)
    if report.total_missing == 0:
        L.append("\n   ✅ All translations have all source keys!")
    else:
        for lv in report.languages:
            if lv.missing:
                L.append(f"\n   {lv.lang.upper()}: {len(lv.missing)} missing keys")
                for key in lv.missing[:20]:
                    L.append(f"      - {key}")
                if len(lv.missing) > 20:
                    L.append(f"      ... and {len(lv.missing) - 20} more")
            else:
                L.append(f"\n   {lv.lang.upper()}: ✅ No missing keys")

    # ─── 2. Extra keys ────────────────────────────────────────────────
    L.append("\n" + "─" * 70)
    L.append("2️⃣  EXTRA KEYS (present in translation but not in source)")
    L.append("─" * 70)
    if report.total_extra == 0:
        L.append("\n   ✅ No extra keys in any translation!")
    else:
        for lv in report.languages:
            if lv.extra:
                L.append(f"\n   {lv.lang.upper()}: {len(lv.extra)} extra keys")
                for key in lv.extra[:20]:
                    L.append(f"      - {key}")
                if len(lv.extra) > 20:
                    L.append(f"      ... and {len(lv.extra) - 20} more")
            else:
                L.append(f"\n   {lv.lang.upper()}: ✅ No extra keys")

    # ─── 3. Empty/null translations ───────────────────────────────────
    L.append("\n" + "─" * 70)
    L.append("3️⃣  EMPTY OR NULL TRANSLATIONS")
    L.append("─" * 70)
    if report.total_empty == 0:
        L.append("\n   ✅ All translations have non-empty values!")
    else:
        for lv in report.languages:
            if lv.empty:
                L.append(f"\n   {lv.lang.upper()}: {len(lv.empty)} empty/null values")
                for key in lv.empty[:20]:
                    L.append(f"      - {key}")
                if len(lv.empty) > 20:
                    L.append(f"      ... and {len(lv.empty) - 20} more")
            else:
                L.append(f"\n   {lv.lang.upper()}: ✅ No empty translations")

    # ─── 4. Untranslated values (same as English source) ──────────────
    L.append("\n" + "─" * 70)
    L.append("4️⃣  POTENTIALLY UNTRANSLATED VALUES (identical to English source)")
    L.append("─" * 70)
    if report.total_untranslated > 0:
        L.append(
            f"\n   ⚠️  Total potentially untranslated values: {report.total_untranslated}"
        )
    for lv in report.languages:
        if lv.untranslated:
            L.append(
                f"\n   {lv.lang.upper()}: {len(lv.untranslated)} values identical to source (len > 3)"
            )
            for key, src_val in lv.untranslated[:30]:
                src_preview = src_val[:80]
                ellipsis = "..." if len(src_val) > 80 else ""
                L.append(f'      - {key}: "{src_preview}{ellipsis}"')
            if len(lv.untranslated) > 30:
                L.append(f"      ... and {len(lv.untranslated) - 30} more")
        else:
            L.append(f"\n   {lv.lang.upper()}: ✅ No untranslated values detected")

    # ─── 5. Placeholder preservation ──────────────────────────────────
    L.append("\n" + "─" * 70)
    L.append("5️⃣  PLACEHOLDER PRESERVATION (%s, {name}, <b>, ICU)")
    L.append("─" * 70)
    if report.total_placeholder_issues == 0:
        L.append("\n   ✅ All placeholders correctly preserved!")
    else:
        for lv in report.languages:
            if lv.placeholder_issues:
                L.append(
                    f"\n   {lv.lang.upper()}: {len(lv.placeholder_issues)} keys with placeholder mismatches"
                )
                for key, src_ph, trans_ph in lv.placeholder_issues[:20]:
                    L.append(f"      - {key}: source={src_ph}, translation={trans_ph}")
                if len(lv.placeholder_issues) > 20:
                    L.append(f"      ... and {len(lv.placeholder_issues) - 20} more")
            else:
                L.append(f"\n   {lv.lang.upper()}: ✅ All placeholders preserved")

    # ─── 6. Duplicate keys ──────────────────────────────────────────
    L.append("\n" + "─" * 70)
    L.append("6️⃣  DUPLICATE KEYS")
    L.append("─" * 70)
    for lv in report.languages:
        if lv.duplicates:
            L.append(f"\n   {lv.lang.upper()}: {len(lv.duplicates)} duplicate keys")
            for key, count in sorted(lv.duplicates.items())[:10]:
                L.append(f'      - "{key}" appears {count} times')
        else:
            L.append(f"\n   {lv.lang.upper()}: ✅ No duplicate keys")

    # ─── Summary ──────────────────────────────────────────────────────
    L.append("\n" + "=" * 70)
    L.append("📊 SUMMARY")
    L.append("=" * 70)
    L.append(f"   Source:               {report.source_file.name}")
    L.append(f"   Source keys:          {report.source_count}")
    for lv in report.languages:
        if lv.loaded:
            L.append(
                f"   {lv.lang.upper():<6}                 {lv.count} keys "
                f"({len(lv.missing)} missing, {len(lv.extra)} extra, {len(lv.empty)} empty)"
            )

    if report.all_ok:
        L.append("\n   ✅ All translations look good!")
    else:
        L.append(
            f"\n   ⚠️  Issues found: {report.total_missing} missing, {report.total_extra} extra, "
            f"{report.total_empty} empty, {report.total_placeholder_issues} placeholder issues"
        )
        if report.total_untranslated > 0:
            L.append(
                f"   ⚠️  {report.total_untranslated} values may be untranslated (identical to source)"
            )
    L.append("=" * 70)
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--export-dir",
        default=None,
        help="Folder containing translation_en_<lang>.json files "
        "(default: latest *_Export under translator/output).",
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help="Folder containing the source JSON "
        "(default: latest *_Import under translator/source).",
    )
    parser.add_argument(
        "--languages",
        default=",".join(DEFAULT_LANGUAGES),
        help="Comma-separated target language codes (default: ar,cz,de,fr,it,sk).",
    )
    parser.add_argument(
        "--json",
        default=None,
        help="Optional machine-readable JSON output path.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent  # translator/
    export_dir = (
        Path(args.export_dir)
        if args.export_dir
        else _latest_folder(repo_root / "output", "_Export")
    )
    source_dir = (
        Path(args.source_dir)
        if args.source_dir
        else _latest_folder(repo_root / "source", "_Import")
    )
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    if not export_dir or not export_dir.exists():
        print(f"\n❌ Export dir not found: {export_dir}")
        sys.exit(1)
    if not source_dir or not source_dir.exists():
        print(f"\n❌ Source dir not found: {source_dir}")
        sys.exit(1)

    source_file = _pick_source_file(source_dir)
    if not source_file:
        print(f"\n❌ No source JSON files found in {source_dir}")
        sys.exit(1)

    try:
        load_json(source_file)
    except Exception as e:
        print(f"❌ Error loading source: {e}")
        sys.exit(1)

    # Run the structured validation and render the full report
    report = validate(source_file, export_dir, languages)
    print(render_report(report))

    if args.json:
        Path(args.json).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON written to {args.json}")


if __name__ == "__main__":
    main()
