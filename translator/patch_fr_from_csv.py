#!/usr/bin/env python3
"""Patch translation_en_fr.json avec les traductions FR correctes du CSV MessageExcel.

Pour chaque variable presente dans le CSV Export_COP_MessageExcel.csv,
remplace la valeur FR du JSON par la valeur FR du CSV (reference metier).
"""

import csv
import json
import os
import sys


def load_csv_dict(filepath):
    """Charge un CSV separe par ';' en dictionnaire {cle: {label, en, fr}}."""
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


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(base, "source", "2026_06_12_Import")
    output_dir = os.path.join(base, "output", "2026_06_12_Export")

    # Load JSON
    json_path = os.path.join(output_dir, "translation_en_fr.json")
    print(f"Chargement JSON: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        fr_json = json.load(f)
    print(f"  {len(fr_json)} cles")

    # Load CSV
    csv_path = os.path.join(source_dir, "Export_COP_MessageExcel.csv")
    print(f"Chargement CSV: {csv_path}")
    msg_csv = load_csv_dict(csv_path)
    print(f"  {len(msg_csv)} entrees")

    # Build mapping from normalized CSV keys to original CSV keys
    csv_norm_map = {}
    for ck in msg_csv:
        csv_norm_map[normalize_key(ck)] = ck
        csv_norm_map[ck] = ck

    # Patch: replace FR values in JSON with CSV values
    patched = 0
    skipped_empty = 0
    not_found = 0
    already_ok = 0
    changes = []

    for jk in sorted(fr_json.keys()):
        # Find matching CSV key
        if jk in msg_csv:
            msg_key = jk
        elif normalize_key(jk) in csv_norm_map:
            msg_key = csv_norm_map[normalize_key(jk)]
        else:
            not_found += 1
            continue

        msg_fr = msg_csv[msg_key]["fr"]

        # Skip if CSV has no FR value
        if not msg_fr:
            skipped_empty += 1
            continue

        # Check if values differ
        if fr_json[jk] == msg_fr:
            already_ok += 1
            continue

        # Patch!
        old_val = fr_json[jk]
        fr_json[jk] = msg_fr
        patched += 1
        old_short = old_val[:80] + "..." if len(old_val) > 80 else old_val
        new_short = msg_fr[:80] + "..." if len(msg_fr) > 80 else msg_fr
        changes.append(f"  {jk}")
        changes.append(f"    AVANT: {old_short}")
        changes.append(f"    APRES: {new_short}")

    # Save patched JSON
    backup_path = json_path + ".bak"
    print(f"\nSauvegarde original: {backup_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(original_content)

    print(f"Sauvegarde JSON corrige: {json_path}")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(fr_json, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'=' * 70}")
    print(f"RESUME DU PATCH")
    print(f"{'=' * 70}")
    print(f"  Valeurs corrigees (FR CSV -> JSON): {patched}")
    print(f"  Deja correctes:                   {already_ok}")
    print(f"  FR vide dans le CSV (ignorees):    {skipped_empty}")
    print(f"  Absentes du CSV:                   {not_found}")
    print(f"  Total cles JSON:                   {len(fr_json)}")

    if changes:
        print(f"\nDetail des {patched} corrections:")
        for line in changes[:300]:  # Limit output
            print(line)
        if len(changes) > 300:
            print(f"  ... et {(len(changes) - 300) // 3} autres corrections")


if __name__ == "__main__":
    main()
