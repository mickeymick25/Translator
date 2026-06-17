#!/usr/bin/env python3
"""Analyse de qualite du fichier translation_en_fr.json (version patchee).

Controles:
1. Cles vides ou null
2. Valeurs identiques a l'anglais (non traduites)
3. Placeholders manquants ou modifies (%s, {name}, <b>, ICU, {{var}})
4. Mots anglais detectes dans les traductions FR
5. Guillemets incoherents
6. Variables utilisant le mot "lieu" au lieu d'"emplacement"
7. Terminologie suspecte
"""

import json
import os
import re
import sys


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# Patterns de placeholders
PLACEHOLDER_PATTERNS = [
    (r"%[sdrifFeEgG]", "printf-style (%s, %d, %f)"),
    (r"\{[a-zA-Z_]\w*\}", "curly-brace ({name}, {count})"),
    (r"\{\{[a-zA-Z_]\w*\}\}", "double-curly ({{name}})"),
    (r"\{\d+\}", "positional ({0}, {1})"),
    (r"<[^>]+>", "HTML-tag (<b>, <br/>)"),
    (r"\\[nt\"\\]", "escape (\\n, \\t)"),
]

# Mots anglais courants qui ne devraient pas etre dans une traduction FR
EN_WORDS_PATTERN = re.compile(
    r"\b(the|and|is|are|was|were|been|have|has|had|will|would|could|should|"
    r"must|shall|may|might|can|does|did|not|this|that|these|those|"
    r"with|from|into|over|under|about|between|through|during|before|after|"
    r"please|enter|select|click|submit|cancel|delete|remove|update|create|"
    r"search|filter|sort|export|import|download|upload|save|close|open|"
    r"enable|disable|required|invalid|valid|error|warning|success|failed|"
    r"already|exists|cannot|must|should|need|only|more|less|"
    r"company|location|organization|unit|role|user|name|label|status|"
    r"date|time|year|month|day|number|code|type|value|field|form|"
    r"button|message|page|screen|section|tab|menu|item|list|"
    r"success|error|information|confirm|cancel)\b",
    re.IGNORECASE,
)


def extract_placeholders(text):
    """Extrait tous les placeholders d'un texte."""
    found = []
    icu_pattern = re.compile(r"\{[^}]+,\s*\w+,")

    for match in icu_pattern.finditer(text):
        start = match.start()
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > start:
            found.append(text[start:end])

    for idx, (pattern, _) in enumerate(PLACEHOLDER_PATTERNS):
        if idx == 4:  # ICU already handled
            continue
        for m in re.finditer(pattern, text):
            if any(
                s <= m.start() < e
                for s, e in [(p.start(), p.end()) for p in icu_pattern.finditer(text)]
            ):
                continue
            found.append(m.group())

    return sorted(found)


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(base, "source", "2026_06_12_Import")
    output_dir = os.path.join(base, "output", "2026_06_12_Export")

    en_path = os.path.join(source_dir, "en 7.json")
    fr_path = os.path.join(output_dir, "translation_en_fr.json")

    print("=" * 80)
    print("ANALYSE DE QUALITE: translation_en_fr.json")
    print("=" * 80)

    en_data = load_json(en_path)
    fr_data = load_json(fr_path)

    en_keys = set(en_data.keys())
    fr_keys = set(fr_data.keys())

    print(f"\nCles EN: {len(en_keys)} | Cles FR: {len(fr_keys)}")
    if en_keys != fr_keys:
        missing_in_fr = en_keys - fr_keys
        extra_in_fr = fr_keys - en_keys
        if missing_in_fr:
            print(f"  Cles manquantes dans FR: {len(missing_in_fr)}")
        if extra_in_fr:
            print(f"  Cles en trop dans FR: {len(extra_in_fr)}")

    # --- 1. Valeurs vides ---
    empty_values = [
        (k, fr_data[k])
        for k in sorted(fr_data)
        if not fr_data[k] or fr_data[k].strip() == ""
    ]
    print(f"\n{'=' * 80}")
    print(f"1. VALEURS VIDES ({len(empty_values)})")
    print("=" * 80)
    for k, v in empty_values[:30]:
        print(f"  {k}")
    if len(empty_values) > 30:
        print(f"  ... et {len(empty_values) - 30} autres")

    # --- 2. Valeurs identiques a l'anglais (non traduites) ---
    identical = []
    for k in sorted(en_keys & fr_keys):
        if en_data[k] == fr_data[k] and en_data[k].strip():
            # Skip short values and technical terms
            if len(en_data[k]) <= 3:
                continue
            identical.append((k, en_data[k]))

    print(f"\n{'=' * 80}")
    print(f"2. VALEURS NON TRUITES (identiques EN=FR, longueur > 3) ({len(identical)})")
    print("=" * 80)
    for k, v in identical[:40]:
        v_short = v[:80] + "..." if len(v) > 80 else v
        print(f"  {k}: {v_short}")
    if len(identical) > 40:
        print(f"  ... et {len(identical) - 40} autres")

    # --- 3. Placeholders manquants ou modifies ---
    placeholder_issues = []
    for k in sorted(en_keys & fr_keys):
        en_val = en_data[k]
        fr_val = fr_data[k]
        if not en_val or not fr_val:
            continue
        en_ph = extract_placeholders(en_val)
        fr_ph = extract_placeholders(fr_val)
        if en_ph and sorted(en_ph) != sorted(fr_ph):
            placeholder_issues.append((k, en_val, fr_val, en_ph, fr_ph))

    print(f"\n{'=' * 80}")
    print(f"3. PLACEHOLDERS MANQUANTS OU MODIFIES ({len(placeholder_issues)})")
    print("=" * 80)
    for k, ev, fv, eph, fph in placeholder_issues[:30]:
        print(f"  {k}")
        print(f"    EN placeholders: {eph}")
        print(f"    FR placeholders: {fph}")
    if len(placeholder_issues) > 30:
        print(f"  ... et {len(placeholder_issues) - 30} autres")

    # --- 4. Mots anglais detectes dans les traductions FR ---
    english_words = []
    for k in sorted(en_keys & fr_keys):
        fr_val = fr_data[k]
        if not fr_val:
            continue
        en_val = en_data[k]
        # Skip if FR == EN (already flagged)
        if fr_val == en_val:
            continue
        # Find English words in FR that are NOT in EN
        en_words_set = set(EN_WORDS_PATTERN.findall(en_val))
        fr_words = EN_WORDS_PATTERN.findall(fr_val)
        suspicious = [
            w for w in fr_words if w.lower() not in {ew.lower() for ew in en_words_set}
        ]
        if suspicious:
            english_words.append((k, fr_val, suspicious))

    print(f"\n{'=' * 80}")
    print(f"4. MOTS ANGLAIS SUSPECTS DANS LES TRADUCTIONS FR ({len(english_words)})")
    print("=" * 80)
    for k, fv, words in english_words[:40]:
        fv_short = fv[:100] + "..." if len(fv) > 100 else fv
        print(f"  {k}: {fv_short}")
        print(f"    Mots suspects: {', '.join(words[:5])}")
    if len(english_words) > 40:
        print(f"  ... et {len(english_words) - 40} autres")

    # --- 5. Guillemets incoherents ---
    quote_issues = []
    for k in sorted(en_keys & fr_keys):
        fr_val = fr_data[k]
        if not fr_val:
            continue
        # Mix of curly quotes and straight quotes
        has_curly = (
            "\u00ab" in fr_val
            or "\u00bb" in fr_val
            or "\u201c" in fr_val
            or "\u201d" in fr_val
        )
        has_straight = '"' in fr_val
        if has_curly and has_straight:
            quote_issues.append((k, fr_val))

    print(f"\n{'=' * 80}")
    print(
        f"5. GUILLEMETS INCOHERENTS (mix quotes droites + courbes) ({len(quote_issues)})"
    )
    print("=" * 80)
    for k, fv in quote_issues[:20]:
        fv_short = fv[:100] + "..." if len(fv) > 100 else fv
        print(f"  {k}: {fv_short}")
    if len(quote_issues) > 20:
        print(f"  ... et {len(quote_issues) - 20} autres")

    # --- 6. Variables utilisant "lieu" au lieu d'"emplacement" ---
    lieu_issues = []
    for k in sorted(fr_data):
        fr_val = fr_data[k]
        if not fr_val:
            continue
        if re.search(r"\blieu[x]?\b", fr_val, re.IGNORECASE):
            lieu_issues.append((k, fr_val))

    print(f"\n{'=' * 80}")
    print(f'6. UTILISATION DU MOT "lieu" AU LIEU D\'"emplacement" ({len(lieu_issues)})')
    print("=" * 80)
    for k, fv in lieu_issues:
        fv_short = fv[:120] + "..." if len(fv) > 120 else fv
        print(f"  {k}: {fv_short}")

    # --- 7. Terminologie suspecte ---
    suspect_terms = {
        "unité orga": "organisation",
        "unité organisationnelle": "organisation",
        "site": "emplacement (si contexte COP)",
        "Enter a": "Saisissez un",
        "Select a": "Sélectionnez un",
        "Select an": "Sélectionnez un",
    }
    terminology_issues = []
    for k in sorted(fr_data):
        fr_val = fr_data[k]
        if not fr_val:
            continue
        found_terms = []
        for term, suggestion in suspect_terms.items():
            if term.lower() in fr_val.lower():
                found_terms.append((term, suggestion))
        if found_terms:
            terminology_issues.append((k, fr_val, found_terms))

    print(f"\n{'=' * 80}")
    print(f"7. TERMINOLOGIE SUSPECTE ({len(terminology_issues)})")
    print("=" * 80)
    for k, fv, terms in terminology_issues[:40]:
        fv_short = fv[:100] + "..." if len(fv) > 100 else fv
        term_str = ", ".join([f'"{t}" -> "{s}"' for t, s in terms])
        print(f"  {k}: {fv_short}")
        print(f"    {term_str}")
    if len(terminology_issues) > 40:
        print(f"  ... et {len(terminology_issues) - 40} autres")

    # --- Resume ---
    print(f"\n{'=' * 80}")
    print("RESUME")
    print("=" * 80)
    print(f"  Valeurs vides:                   {len(empty_values)}")
    print(f"  Non traduites (EN=FR):           {len(identical)}")
    print(f"  Placeholders modifies/manquants: {len(placeholder_issues)}")
    print(f"  Mots anglais suspects:           {len(english_words)}")
    print(f"  Guillemets incoherents:          {len(quote_issues)}")
    print(f'  Utilisation de "lieu":            {len(lieu_issues)}')
    print(f"  Terminologie suspecte:           {len(terminology_issues)}")

    total_issues = (
        len(empty_values)
        + len(identical)
        + len(placeholder_issues)
        + len(english_words)
        + len(quote_issues)
        + len(lieu_issues)
        + len(terminology_issues)
    )
    print(f"\n  TOTAL PROBLEMES:                {total_issues}")

    # Save results
    results = {
        "empty_values": [{"key": k, "value": v} for k, v in empty_values],
        "identical_en_fr": [{"key": k, "value": v} for k, v in identical],
        "placeholder_issues": [
            {"key": k, "en": ev, "fr": fv, "en_ph": eph, "fr_ph": fph}
            for k, ev, fv, eph, fph in placeholder_issues
        ],
        "english_words": [
            {"key": k, "value": fv, "words": w} for k, fv, w in english_words
        ],
        "quote_issues": [{"key": k, "value": fv} for k, fv in quote_issues],
        "lieu_issues": [{"key": k, "value": fv} for k, fv in lieu_issues],
        "terminology_issues": [
            {"key": k, "value": fv, "terms": t} for k, fv, t in terminology_issues
        ],
    }

    output_file = os.path.join(output_dir, "fr_quality_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResultats sauvegardes dans: {output_file}")


if __name__ == "__main__":
    main()
