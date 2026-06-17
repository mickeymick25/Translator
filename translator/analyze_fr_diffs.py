#!/usr/bin/env python3
"""Analyse les differences entre translation_en_fr.json et Export_COP_MessageExcel.csv.

Genere un rapport et un fichier Excel de comparaison.
"""

import csv
import json
import os
import re


def load_csv_dict(filepath):
    """Charge un CSV separes par ';' en dictionnaire {cle: {label, en, fr}}."""
    data = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        next(reader)  # skip header
        for row in reader:
            if row and row[0].strip():
                key = row[0].strip()
                label = row[1].strip() if len(row) > 1 else ""
                en = row[2].strip() if len(row) > 2 else ""
                fr = row[3].strip() if len(row) > 3 else ""
                data[key] = {"label": label, "en": en, "fr": fr}
    return data


def normalize_key(k):
    """Normalise une cle en remplacant les espaces par des underscores."""
    return k.replace(" ", "_")


def classify_diff(json_val, csv_val):
    """Classifie le type de difference entre la valeur JSON et la valeur CSV."""
    j = json_val.strip()
    c = csv_val.strip()

    # Emoji manquant
    if "\u26a0\ufe0f" in c and "\u26a0\ufe0f" not in j:
        return "emoji_manquant"

    # Placeholder change
    json_placeholders = set(re.findall(r"\{\{[^}]+\}\}", j))
    csv_placeholders = set(re.findall(r"\{\{[^}]+\}\}", c))
    if json_placeholders != csv_placeholders and json_placeholders and csv_placeholders:
        return "placeholder"

    # Difference de contenu reel (apres normalisation des espaces/quotes)
    j_norm = (
        j.replace("\u00a0", " ")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00ab", '"')
        .replace("\u00bb", '"')
    )
    c_norm = (
        c.replace("\u00a0", " ")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00ab", '"')
        .replace("\u00bb", '"')
    )
    if j_norm != c_norm:
        return "contenu"

    return "format"


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(base, "source", "2026_06_12_Import")
    output_dir = os.path.join(base, "output", "2026_06_12_Export")

    # Load data
    with open(os.path.join(source_dir, "en 7.json"), "r", encoding="utf-8") as f:
        en_json = json.load(f)
    with open(
        os.path.join(output_dir, "translation_en_fr.json"), "r", encoding="utf-8"
    ) as f:
        fr_json = json.load(f)

    msg_csv = load_csv_dict(os.path.join(source_dir, "Export_COP_MessageExcel.csv"))

    # Build mapping
    csv_norm_map = {}
    for ck in msg_csv:
        csv_norm_map[normalize_key(ck)] = ck
        csv_norm_map[ck] = ck

    # Compare
    fr_diff = []
    fr_match = []
    fr_empty_csv = []
    not_in_csv = []

    for jk in sorted(en_json.keys()):
        if jk in msg_csv:
            msg_key = jk
        elif normalize_key(jk) in csv_norm_map:
            msg_key = csv_norm_map[normalize_key(jk)]
        else:
            not_in_csv.append(jk)
            continue

        fr_val = fr_json.get(jk, "")
        msg_data = msg_csv[msg_key]
        msg_en = msg_data["en"]
        msg_fr = msg_data["fr"]

        if not msg_fr:
            fr_empty_csv.append((jk, msg_key, fr_val))
        elif fr_val != msg_fr:
            diff_type = classify_diff(fr_val, msg_fr)
            fr_diff.append((jk, msg_key, fr_val, msg_fr, msg_en, diff_type))
        else:
            fr_match.append(jk)

    # Stats
    print("=" * 70)
    print("ANALYSE DES DIFFERENCES FR: JSON vs CSV MessageExcel")
    print("=" * 70)
    print(f"EN JSON: {len(en_json)} cles")
    print(f"FR JSON: {len(fr_json)} cles")
    print(f"CSV MessageExcel: {len(msg_csv)} entrees")
    print(
        f"Variables comparees (JSON + CSV): {len(fr_match) + len(fr_diff) + len(fr_empty_csv)}"
    )
    print(f"  FR identique au CSV: {len(fr_match)}")
    print(f"  FR different du CSV: {len(fr_diff)}")
    print(f"  FR vide dans le CSV: {len(fr_empty_csv)}")
    print(f"  Absentes du CSV: {len(not_in_csv)}")

    # Classification
    cat_emoji = [d for d in fr_diff if d[5] == "emoji_manquant"]
    cat_placeholder = [d for d in fr_diff if d[5] == "placeholder"]
    cat_contenu = [d for d in fr_diff if d[5] == "contenu"]
    cat_format = [d for d in fr_diff if d[5] == "format"]

    print(f"\nClassification des {len(fr_diff)} differences:")
    print(f"  - Emoji manquant (⚠️): {len(cat_emoji)}")
    print(f"  - Placeholders differents: {len(cat_placeholder)}")
    print(f"  - Contenu reel different: {len(cat_contenu)}")
    print(f"  - Format/ponctuation seulement: {len(cat_format)}")

    # Detail: emoji manquants
    print(f"\n{'=' * 70}")
    print(f"EMOJI MANQUANT ({len(cat_emoji)} variables)")
    print("=" * 70)
    for jk, mk, fv, mf, me, dt in cat_emoji:
        print(f"  {jk}")
        print(f"    JSON: {fv[:120]}{'...' if len(fv) > 120 else ''}")
        print(f"    CSV : {mf[:120]}{'...' if len(mf) > 120 else ''}")
        print()

    # Detail: contenu different
    print(f"\n{'=' * 70}")
    print(f"CONTENU DIFFERENT ({len(cat_contenu)} variables)")
    print("=" * 70)
    for jk, mk, fv, mf, me, dt in cat_contenu:
        print(f"  {jk}")
        print(f"    JSON: {fv[:150]}{'...' if len(fv) > 150 else ''}")
        print(f"    CSV : {mf[:150]}{'...' if len(mf) > 150 else ''}")
        print()

    # Detail: placeholders differents
    print(f"\n{'=' * 70}")
    print(f"PLACEHOLDERS DIFFERENTS ({len(cat_placeholder)} variables)")
    print("=" * 70)
    for jk, mk, fv, mf, me, dt in cat_placeholder:
        print(f"  {jk}")
        print(f"    JSON: {fv[:150]}{'...' if len(fv) > 150 else ''}")
        print(f"    CSV : {mf[:150]}{'...' if len(mf) > 150 else ''}")
        print()

    # Detail: format seulement
    print(f"\n{'=' * 70}")
    print(f"FORMAT/PONCTUATION DIFFERENT ({len(cat_format)} variables)")
    print("=" * 70)
    for jk, mk, fv, mf, me, dt in cat_format:
        print(f"  {jk}")
        print(f"    JSON: {fv[:150]}{'...' if len(fv) > 150 else ''}")
        print(f"    CSV : {mf[:150]}{'...' if len(mf) > 150 else ''}")
        print()

    # Variables avec FR vide dans le CSV
    print(f"\n{'=' * 70}")
    print(f"FR VIDE DANS CSV ({len(fr_empty_csv)} variables)")
    print("=" * 70)
    for jk, mk, fv in fr_empty_csv:
        print(f"  {jk}: JSON='{fv[:80]}{'...' if len(fv) > 80 else ''}'")

    # Write results to JSON for further processing
    results = {
        "summary": {
            "en_json_keys": len(en_json),
            "fr_json_keys": len(fr_json),
            "csv_entries": len(msg_csv),
            "compared": len(fr_match) + len(fr_diff) + len(fr_empty_csv),
            "fr_identical": len(fr_match),
            "fr_different": len(fr_diff),
            "fr_empty_csv": len(fr_empty_csv),
            "not_in_csv": len(not_in_csv),
            "cat_emoji": len(cat_emoji),
            "cat_placeholder": len(cat_placeholder),
            "cat_contenu": len(cat_contenu),
            "cat_format": len(cat_format),
        },
        "diffs": [
            {
                "json_key": jk,
                "csv_key": mk,
                "fr_json": fv,
                "fr_csv": mf,
                "en_csv": me,
                "diff_type": dt,
            }
            for jk, mk, fv, mf, me, dt in fr_diff
        ],
        "empty_csv": [
            {"json_key": jk, "csv_key": mk, "fr_json": fv}
            for jk, mk, fv in fr_empty_csv
        ],
    }

    output_path = os.path.join(output_dir, "fr_diff_analysis.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResultats sauvegardes dans: {output_path}")


if __name__ == "__main__":
    main()
