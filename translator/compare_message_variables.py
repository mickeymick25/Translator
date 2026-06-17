#!/usr/bin/env python3
"""Compare les variables de messages entre 4 sources et génère un fichier Excel.

Sources comparées :
  1. en 7.json (JSON source anglais)
  2. Export_COP_MessageExcel.csv (CSV messages du métier)
  3. translation_en_fr.json (JSON traduit EN→FR)
  4. Export_COP_Excel.csv (CSV Excel de référence)

Génère un fichier Excel avec :
  - Onglet "Comparison" : toutes les variables présentes dans le JSON et le CSV MessageExcel
  - Onglet "Différences" : uniquement les lignes avec des différences de contenu
  - Onglet "Statistiques" : résumé des matchs et différences

Usage:
    python compare_message_variables.py \\
        --source-dir /app/source/2026_06_12_Import \\
        --output-dir /app/output/2026_06_12_Export \\
        --en-json "en 7.json" \\
        --fr-json translation_en_fr.json \\
        --msg-csv Export_COP_MessageExcel.csv \\
        --excel-csv Export_COP_Excel.csv \\
        --output comparison_message_variables.xlsx
"""

import argparse
import csv
import json
import os
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def normalize_key(k: str) -> str:
    """Normalise une clé en remplaçant les espaces par des underscores."""
    return k.replace(" ", "_")


def load_csv_dict(filepath: str) -> dict:
    """Charge un CSV séparé par ';' en dictionnaire {clé: {label, en, fr}}."""
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


def find_match(json_key: str, csv_data: dict) -> tuple[Optional[str], Optional[str]]:
    """Trouve le match d'une clé JSON dans un CSV.

    Returns:
        (csv_key, match_type) ou (None, None) si pas de match.
        match_type: 'exact', 'normalized', ou 'text'.
    """
    # 1. Match exact
    if json_key in csv_data:
        return json_key, "exact"

    # 2. Match normalisé (espaces → underscores)
    norm = normalize_key(json_key)
    if norm in csv_data:
        return norm, "normalized"

    # 3. Match inverse normalisé
    for ck in csv_data:
        if normalize_key(ck) == json_key:
            return ck, "normalized"

    # 4. Match case-insensitive
    lower_keys = {ck.lower(): ck for ck in csv_data}
    if json_key.lower() in lower_keys:
        return lower_keys[json_key.lower()], "case_insensitive"

    return None, None


def normalize_text(text: str) -> str:
    """Normalise le texte pour comparaison."""
    if not text:
        return ""
    return text.replace('""', '"').replace("\\n", "\n").strip()


def main():
    parser = argparse.ArgumentParser(
        description="Compare les variables de messages entre JSON et CSV"
    )
    parser.add_argument(
        "--source-dir",
        default="/app/source/2026_06_12_Import",
        help="Répertoire contenant les fichiers source",
    )
    parser.add_argument(
        "--output-dir",
        default="/app/output/2026_06_12_Export",
        help="Répertoire contenant les fichiers traduits",
    )
    parser.add_argument(
        "--en-json", default="en 7.json", help="Nom du fichier JSON anglais"
    )
    parser.add_argument(
        "--fr-json",
        default="translation_en_fr.json",
        help="Nom du fichier JSON traduit FR",
    )
    parser.add_argument(
        "--msg-csv",
        default="Export_COP_MessageExcel.csv",
        help="Nom du CSV messages métier",
    )
    parser.add_argument(
        "--excel-csv",
        default="Export_COP_Excel.csv",
        help="Nom du CSV Excel de référence",
    )
    parser.add_argument(
        "--output",
        default="comparison_message_variables.xlsx",
        help="Nom du fichier Excel de sortie",
    )
    args = parser.parse_args()

    # --- Chargement des données ---
    en_json_path = os.path.join(args.source_dir, args.en_json)
    fr_json_path = os.path.join(args.output_dir, args.fr_json)
    msg_csv_path = os.path.join(args.source_dir, args.msg_csv)
    excel_csv_path = os.path.join(args.source_dir, args.excel_csv)

    print(f"Chargement EN JSON: {en_json_path}")
    with open(en_json_path, "r", encoding="utf-8") as f:
        en_json = json.load(f)

    print(f"Chargement FR JSON: {fr_json_path}")
    with open(fr_json_path, "r", encoding="utf-8") as f:
        fr_json = json.load(f)

    print(f"Chargement CSV MessageExcel: {msg_csv_path}")
    msg_csv = load_csv_dict(msg_csv_path)

    print(f"Chargement CSV Excel: {excel_csv_path}")
    excel_csv = load_csv_dict(excel_csv_path)

    print(f"\nEN JSON: {len(en_json)} clés")
    print(f"FR JSON: {len(fr_json)} clés")
    print(f"CSV MessageExcel: {len(msg_csv)} entrées")
    print(f"CSV Excel: {len(excel_csv)} entrées")

    # --- Construction des lignes de comparaison ---
    rows = []
    json_keys = sorted(en_json.keys())

    stats = {
        "total": 0,
        "exact": 0,
        "normalized": 0,
        "case_insensitive": 0,
        "text_match": 0,
        "en_diff_msg": 0,
        "en_diff_excel": 0,
        "fr_diff_msg": 0,
        "fr_diff_excel": 0,
    }

    for jk in json_keys:
        # Chercher dans MessageExcel CSV
        msg_key, msg_type = find_match(jk, msg_csv)
        if msg_key is None:
            continue  # Pas dans le CSV MessageExcel

        # Chercher dans Excel CSV
        exc_key, exc_type = find_match(jk, excel_csv)

        stats["total"] += 1
        if msg_type == "exact":
            stats["exact"] += 1
        elif msg_type == "normalized":
            stats["normalized"] += 1
        elif msg_type == "case_insensitive":
            stats["case_insensitive"] += 1

        # Récupérer les valeurs
        en_val = en_json[jk]
        fr_val = fr_json.get(jk, "")

        msg_data = msg_csv[msg_key]
        msg_en = msg_data["en"]
        msg_fr = msg_data["fr"]
        msg_label = msg_data["label"]

        if exc_key and exc_key in excel_csv:
            exc_data = excel_csv[exc_key]
            exc_en = exc_data["en"]
            exc_fr = exc_data["fr"]
        else:
            exc_en = ""
            exc_fr = ""

        # Normaliser pour comparaison
        en_json_norm = normalize_text(en_val)
        msg_en_norm = normalize_text(msg_en)
        exc_en_norm = normalize_text(exc_en)

        # Comparaisons EN
        if msg_en_norm and en_json_norm != msg_en_norm:
            diff_en_msg = "⚠ diff"
            stats["en_diff_msg"] += 1
        elif msg_en_norm:
            diff_en_msg = "✓"
        else:
            diff_en_msg = ""

        if exc_en_norm and en_json_norm != exc_en_norm:
            diff_en_excel = "⚠ diff"
            stats["en_diff_excel"] += 1
        elif exc_en_norm:
            diff_en_excel = "✓"
        else:
            diff_en_excel = ""

        # Comparaisons FR
        if msg_fr and fr_val != msg_fr:
            diff_fr_msg = "⚠ diff"
            stats["fr_diff_msg"] += 1
        elif msg_fr:
            diff_fr_msg = "✓"
        else:
            diff_fr_msg = ""

        if exc_fr and fr_val != exc_fr:
            diff_fr_excel = "⚠ diff"
            stats["fr_diff_excel"] += 1
        elif exc_fr:
            diff_fr_excel = "✓"
        else:
            diff_fr_excel = ""

        # Présence dans Excel CSV
        in_excel = "✓" if (exc_key and exc_key in excel_csv) else ""

        rows.append(
            {
                "json_key": jk,
                "msg_csv_key": msg_key,
                "excel_csv_key": exc_key if exc_key else "",
                "in_excel_csv": in_excel,
                "match_type": msg_type,
                "label": msg_label,
                "en_json": en_val,
                "en_msg_csv": msg_en,
                "en_excel_csv": exc_en,
                "fr_json": fr_val,
                "fr_msg_csv": msg_fr,
                "fr_excel_csv": exc_fr,
                "diff_en_msg": diff_en_msg,
                "diff_en_excel": diff_en_excel,
                "diff_fr_msg": diff_fr_msg,
                "diff_fr_excel": diff_fr_excel,
            }
        )

    # --- Génération Excel ---
    wb = Workbook()

    # Styles
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(
        start_color="2F5496", end_color="2F5496", fill_type="solid"
    )
    diff_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    ok_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    empty_fill = PatternFill(
        start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"
    )
    wrap_align = Alignment(wrap_text=True, vertical="top")
    center_align = Alignment(horizontal="center", vertical="top", wrap_text=True)

    # ====== Onglet 1: Comparison complète ======
    ws_all = wb.active
    ws_all.title = "Comparison"

    headers = [
        "JSON Key",
        "CSV Key (MessageExcel)",
        "CSV Key (Excel)",
        "In Excel CSV",
        "Match Type",
        "Label",
        "EN (JSON)",
        "EN (MessageExcel CSV)",
        "EN (Excel CSV)",
        "Diff EN↔MsgCSV",
        "Diff EN↔ExcelCSV",
        "FR (JSON)",
        "FR (MessageExcel CSV)",
        "FR (Excel CSV)",
        "Diff FR↔MsgCSV",
        "Diff FR↔ExcelCSV",
    ]

    for col, h in enumerate(headers, 1):
        cell = ws_all.cell(row=1, column=col, value=h)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )

    for row_idx, r in enumerate(rows, 2):
        ws_all.cell(row=row_idx, column=1, value=r["json_key"])
        ws_all.cell(row=row_idx, column=2, value=r["msg_csv_key"])
        ws_all.cell(row=row_idx, column=3, value=r["excel_csv_key"])
        ws_all.cell(row=row_idx, column=4, value=r["in_excel_csv"])
        ws_all.cell(row=row_idx, column=5, value=r["match_type"])
        ws_all.cell(row=row_idx, column=6, value=r["label"])
        ws_all.cell(row=row_idx, column=7, value=r["en_json"])
        ws_all.cell(row=row_idx, column=8, value=r["en_msg_csv"])
        ws_all.cell(row=row_idx, column=9, value=r["en_excel_csv"])
        ws_all.cell(row=row_idx, column=10, value=r["diff_en_msg"])
        ws_all.cell(row=row_idx, column=11, value=r["diff_en_excel"])
        ws_all.cell(row=row_idx, column=12, value=r["fr_json"])
        ws_all.cell(row=row_idx, column=13, value=r["fr_msg_csv"])
        ws_all.cell(row=row_idx, column=14, value=r["fr_excel_csv"])
        ws_all.cell(row=row_idx, column=15, value=r["diff_fr_msg"])
        ws_all.cell(row=row_idx, column=16, value=r["diff_fr_excel"])

        # Wrap text pour les colonnes longues
        for col in [7, 8, 9, 12, 13, 14]:
            ws_all.cell(row=row_idx, column=col).alignment = wrap_align

        # Color coding pour les colonnes diff
        for col in [10, 11, 15, 16]:
            cell = ws_all.cell(row=row_idx, column=col)
            cell.alignment = center_align
            if cell.value == "⚠ diff":
                cell.fill = diff_fill
                cell.font = Font(bold=True, color="FF0000")
            elif cell.value == "✓":
                cell.fill = ok_fill
            elif cell.value == "":
                cell.fill = empty_fill

    # Largeurs de colonnes
    col_widths = [35, 35, 35, 14, 14, 25, 60, 60, 60, 16, 16, 60, 60, 60, 16, 16]
    for i, w in enumerate(col_widths, 1):
        ws_all.column_dimensions[get_column_letter(i)].width = w

    ws_all.freeze_panes = "A2"
    ws_all.auto_filter.ref = f"A1:P{len(rows) + 1}"

    # ====== Onglet 2: Différences uniquement ======
    ws_diff = wb.create_sheet("Différences")

    diff_rows = [
        r
        for r in rows
        if any(
            r.get(f) == "⚠ diff"
            for f in ["diff_en_msg", "diff_en_excel", "diff_fr_msg", "diff_fr_excel"]
        )
    ]

    diff_headers = [
        "JSON Key",
        "CSV Key (MessageExcel)",
        "Match Type",
        "Différence",
        "EN (JSON)",
        "EN (MessageExcel CSV)",
        "EN (Excel CSV)",
        "FR (JSON)",
        "FR (MessageExcel CSV)",
        "FR (Excel CSV)",
    ]

    for col, h in enumerate(diff_headers, 1):
        cell = ws_diff.cell(row=1, column=col, value=h)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )

    for row_idx, r in enumerate(diff_rows, 2):
        diffs = []
        if r["diff_en_msg"] == "⚠ diff":
            diffs.append("EN↔MsgCSV")
        if r["diff_en_excel"] == "⚠ diff":
            diffs.append("EN↔ExcelCSV")
        if r["diff_fr_msg"] == "⚠ diff":
            diffs.append("FR↔MsgCSV")
        if r["diff_fr_excel"] == "⚠ diff":
            diffs.append("FR↔ExcelCSV")

        ws_diff.cell(row=row_idx, column=1, value=r["json_key"])
        ws_diff.cell(row=row_idx, column=2, value=r["msg_csv_key"])
        ws_diff.cell(row=row_idx, column=3, value=r["match_type"])
        ws_diff.cell(row=row_idx, column=4, value=", ".join(diffs))
        ws_diff.cell(row=row_idx, column=5, value=r["en_json"])
        ws_diff.cell(row=row_idx, column=6, value=r["en_msg_csv"])
        ws_diff.cell(row=row_idx, column=7, value=r["en_excel_csv"])
        ws_diff.cell(row=row_idx, column=8, value=r["fr_json"])
        ws_diff.cell(row=row_idx, column=9, value=r["fr_msg_csv"])
        ws_diff.cell(row=row_idx, column=10, value=r["fr_excel_csv"])

        for col in [5, 6, 7, 8, 9, 10]:
            ws_diff.cell(row=row_idx, column=col).alignment = wrap_align

    diff_widths = [35, 35, 14, 25, 60, 60, 60, 60, 60, 60]
    for i, w in enumerate(diff_widths, 1):
        ws_diff.column_dimensions[get_column_letter(i)].width = w

    ws_diff.freeze_panes = "A2"
    ws_diff.auto_filter.ref = f"A1:J{len(diff_rows) + 1}"

    # ====== Onglet 3: Statistiques ======
    ws_stats = wb.create_sheet("Statistiques")

    stat_rows = [
        ("Variables JSON présentes dans CSV MessageExcel", stats["total"]),
        ("  - Match exact", stats["exact"]),
        ("  - Match normalisé (espaces)", stats["normalized"]),
        ("  - Match case-insensitive", stats["case_insensitive"]),
        ("", ""),
        ("Différences EN JSON ↔ CSV MessageExcel", stats["en_diff_msg"]),
        ("Différences EN JSON ↔ CSV Excel", stats["en_diff_excel"]),
        ("Différences FR JSON ↔ CSV MessageExcel", stats["fr_diff_msg"]),
        ("Différences FR JSON ↔ CSV Excel", stats["fr_diff_excel"]),
        ("", ""),
        ("Total clés JSON", len(en_json)),
        ("Total entrées CSV MessageExcel", len(msg_csv)),
        ("Total entrées CSV Excel", len(excel_csv)),
    ]

    stat_headers = ["Indicateur", "Valeur"]
    for col, h in enumerate(stat_headers, 1):
        cell = ws_stats.cell(row=1, column=col, value=h)
        cell.font = header_font_white
        cell.fill = header_fill

    for row_idx, (label, value) in enumerate(stat_rows, 2):
        ws_stats.cell(row=row_idx, column=1, value=label)
        ws_stats.cell(row=row_idx, column=2, value=value)

    ws_stats.column_dimensions["A"].width = 45
    ws_stats.column_dimensions["B"].width = 12

    # --- Sauvegarde ---
    output_path = os.path.join(args.output_dir, args.output)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    wb.save(output_path)

    print(f"\n✅ Fichier Excel créé: {output_path}")
    print(f"   - {len(rows)} variables comparées")
    print(f"   - {len(diff_rows)} lignes avec différences")
    print(f"   - {stats['en_diff_msg']} différences EN JSON ↔ MessageExcel CSV")
    print(f"   - {stats['en_diff_excel']} différences EN JSON ↔ Excel CSV")
    print(f"   - {stats['fr_diff_msg']} différences FR JSON ↔ MessageExcel CSV")
    print(f"   - {stats['fr_diff_excel']} différences FR JSON ↔ Excel CSV")


if __name__ == "__main__":
    main()
