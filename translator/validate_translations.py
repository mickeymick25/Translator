#!/usr/bin/env python3
"""Validate all translation files in the 2026_06_11_Export directory.

Checks:
1. Missing keys (present in source but not in a translation)
2. Empty/null translations
3. Structural inconsistencies across translations
4. Untranslated values (values still in English)
5. Duplicate keys
6. Placeholder preservation (%s, {name}, <b>, ICU)
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

EXPORT_DIR = Path("translator/output/2026_06_11_Export")
SOURCE_DIR = Path("translator/source/2026_06_11_Import")

LANGUAGES = ["ar", "cz", "de", "fr", "it", "sk"]

# Placeholders patterns that should be preserved in translations
PLACEHOLDER_PATTERNS = [
    r"%[sd]",  # %s, %d
    r"\{[\w.]+\}",  # {name}, {count}
    r"<[^>]+>",  # <b>, </b>, <br/>
    r"\\n",  # \n
    r"\{\d+\}",  # {0}, {1} ICU format
]


def load_json(filepath):
    """Load a JSON file and return as dict."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_placeholders(text):
    """Extract all placeholders from a text string."""
    found = []
    for pattern in PLACEHOLDER_PATTERNS:
        found.extend(re.findall(pattern, text))
    return found


def main():
    print("=" * 70)
    print("COP Translation Validation Report - 2026_06_11_Export")
    print("=" * 70)

    # Find source file
    source_files = list(SOURCE_DIR.glob("*.json"))
    if not source_files:
        print(f"\n❌ No source JSON files found in {SOURCE_DIR}")
        sys.exit(1)

    source_file = source_files[0]
    print(f"\n📄 Source file: {source_file.name}")

    try:
        source_data = load_json(source_file)
    except Exception as e:
        print(f"❌ Error loading source: {e}")
        sys.exit(1)

    source_keys = set(source_data.keys())
    print(f"   Source keys: {len(source_keys)}")

    # Load all translation files
    translations = {}
    all_translation_keys = {}
    for lang in LANGUAGES:
        filepath = EXPORT_DIR / f"translation_en_{lang}.json"
        try:
            data = load_json(filepath)
            translations[lang] = data
            all_translation_keys[lang] = set(data.keys())
            print(f"   {lang.upper()}: {len(data)} keys")
        except Exception as e:
            print(f"   {lang.upper()}: ❌ Error loading: {e}")
            translations[lang] = {}
            all_translation_keys[lang] = set()

    # ─── 1. Missing keys ───────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("1️⃣  MISSING KEYS (present in source but not in translation)")
    print("─" * 70)

    total_missing = 0
    for lang in LANGUAGES:
        missing = source_keys - all_translation_keys[lang]
        if missing:
            total_missing += len(missing)
            print(f"\n   {lang.upper()}: {len(missing)} missing keys")
            # Show first 20
            for i, key in enumerate(sorted(missing)[:20]):
                print(f"      - {key}")
            if len(missing) > 20:
                print(f"      ... and {len(missing) - 20} more")
        else:
            print(f"\n   {lang.upper()}: ✅ No missing keys")

    if total_missing == 0:
        print("\n   ✅ All translations have all source keys!")

    # ─── 2. Extra keys ────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("2️⃣  EXTRA KEYS (present in translation but not in source)")
    print("─" * 70)

    total_extra = 0
    for lang in LANGUAGES:
        extra = all_translation_keys[lang] - source_keys
        if extra:
            total_extra += len(extra)
            print(f"\n   {lang.upper()}: {len(extra)} extra keys")
            for i, key in enumerate(sorted(extra)[:20]):
                print(f"      - {key}")
            if len(extra) > 20:
                print(f"      ... and {len(extra) - 20} more")
        else:
            print(f"\n   {lang.upper()}: ✅ No extra keys")

    if total_extra == 0:
        print("\n   ✅ No extra keys in any translation!")

    # ─── 3. Empty/null translations ───────────────────────────────────
    print("\n" + "─" * 70)
    print("3️⃣  EMPTY OR NULL TRANSLATIONS")
    print("─" * 70)

    total_empty = 0
    for lang in LANGUAGES:
        empty_keys = []
        for key, value in translations[lang].items():
            if value is None or (isinstance(value, str) and value.strip() == ""):
                empty_keys.append(key)
        if empty_keys:
            total_empty += len(empty_keys)
            print(f"\n   {lang.upper()}: {len(empty_keys)} empty/null values")
            for i, key in enumerate(sorted(empty_keys)[:20]):
                print(f"      - {key}")
            if len(empty_keys) > 20:
                print(f"      ... and {len(empty_keys) - 20} more")
        else:
            print(f"\n   {lang.upper()}: ✅ No empty translations")

    if total_empty == 0:
        print("\n   ✅ All translations have non-empty values!")

    # ─── 4. Untranslated values (same as English source) ──────────────
    print("\n" + "─" * 70)
    print("4️⃣  POTENTIALLY UNTRANSLATED VALUES (identical to English source)")
    print("─" * 70)

    total_untranslated = 0
    for lang in LANGUAGES:
        untranslated = []
        for key in source_keys & all_translation_keys[lang]:
            src_val = source_data.get(key, "")
            trans_val = translations[lang].get(key, "")
            # Skip short values (buttons, labels that might be same across languages)
            if isinstance(src_val, str) and isinstance(trans_val, str):
                if src_val == trans_val and len(src_val) > 3:
                    untranslated.append(key)
        if untranslated:
            total_untranslated += len(untranslated)
            print(
                f"\n   {lang.upper()}: {len(untranslated)} values identical to source (len > 3)"
            )
            for i, key in enumerate(sorted(untranslated)[:30]):
                src_val = source_data[key][:80]
                print(
                    f'      - {key}: "{src_val}{"..." if len(source_data[key]) > 80 else ""}"'
                )
            if len(untranslated) > 30:
                print(f"      ... and {len(untranslated) - 30} more")
        else:
            print(f"\n   {lang.upper()}: ✅ No untranslated values detected")

    if total_untranslated > 0:
        print(f"\n   ⚠️  Total potentially untranslated values: {total_untranslated}")

    # ─── 5. Placeholder preservation ──────────────────────────────────
    print("\n" + "─" * 70)
    print("5️⃣  PLACEHOLDER PRESERVATION (%s, {name}, <b>, ICU)")
    print("─" * 70)

    total_placeholder_issues = 0
    for lang in LANGUAGES:
        placeholder_issues = []
        for key in source_keys & all_translation_keys[lang]:
            src_val = source_data.get(key, "")
            trans_val = translations[lang].get(key, "")
            if not isinstance(src_val, str) or not isinstance(trans_val, str):
                continue
            src_ph = extract_placeholders(src_val)
            trans_ph = extract_placeholders(trans_val)
            if src_ph and sorted(src_ph) != sorted(trans_ph):
                placeholder_issues.append((key, src_ph, trans_ph))
        if placeholder_issues:
            total_placeholder_issues += len(placeholder_issues)
            print(
                f"\n   {lang.upper()}: {len(placeholder_issues)} keys with placeholder mismatches"
            )
            for i, (key, src_ph, trans_ph) in enumerate(placeholder_issues[:20]):
                print(f"      - {key}: source={src_ph}, translation={trans_ph}")
            if len(placeholder_issues) > 20:
                print(f"      ... and {len(placeholder_issues) - 20} more")
        else:
            print(f"\n   {lang.upper()}: ✅ All placeholders preserved")

    if total_placeholder_issues == 0:
        print("\n   ✅ All placeholders correctly preserved!")

    # ─── 6. Duplicate keys ──────────────────────────────────────────
    print("\n" + "─" * 70)
    print("6️⃣  DUPLICATE KEYS")
    print("─" * 70)

    for lang in LANGUAGES:
        filepath = EXPORT_DIR / f"translation_en_{lang}.json"
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Count occurrences of each key in raw JSON
        key_counts = defaultdict(int)
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith('"') and '":' in line:
                key = line.split('":')[0].strip('"')
                key_counts[key] += 1
        duplicates = {k: v for k, v in key_counts.items() if v > 1}
        if duplicates:
            print(f"\n   {lang.upper()}: {len(duplicates)} duplicate keys")
            for key, count in sorted(duplicates.items())[:10]:
                print(f'      - "{key}" appears {count} times')
        else:
            print(f"\n   {lang.upper()}: ✅ No duplicate keys")

    # ─── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)

    all_ok = (
        total_missing == 0
        and total_extra == 0
        and total_empty == 0
        and total_placeholder_issues == 0
    )

    print(f"   Source keys:           {len(source_keys)}")
    for lang in LANGUAGES:
        filepath = EXPORT_DIR / f"translation_en_{lang}.json"
        data = translations[lang]
        missing = len(source_keys - all_translation_keys[lang])
        extra = len(all_translation_keys[lang] - source_keys)
        empty_count = sum(
            1
            for v in data.values()
            if v is None or (isinstance(v, str) and v.strip() == "")
        )
        print(
            f"   {lang.upper()}:                  {len(data)} keys ({missing} missing, {extra} extra, {empty_count} empty)"
        )

    if all_ok:
        print("\n   ✅ All translations look good!")
    else:
        print(
            f"\n   ⚠️  Issues found: {total_missing} missing, {total_extra} extra, {total_empty} empty, {total_placeholder_issues} placeholder issues"
        )
        if total_untranslated > 0:
            print(
                f"   ⚠️  {total_untranslated} values may be untranslated (identical to source)"
            )

    print("=" * 70)


if __name__ == "__main__":
    main()
