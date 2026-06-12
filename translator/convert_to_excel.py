"""Convertit les fichiers JSON de traduction en un fichier Excel exploitable par le métier.

Usage:
    python convert_to_excel.py [--input-dir DIR] [--output FILE]

Par défaut:
    --input-dir = /app/output/2026_05_27_Export
    --output    = /app/excel/translations_en_cz_sk.xlsx
"""

import argparse
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


def derive_section(key: str) -> str:
    """Déduit la section/module à partir du préfixe de la clé."""
    prefix = key.split("_")[0] if "_" in key else key
    sections = {
        "Btn": "Buttons",
        "AL": "Alerts / General",
        "OR": "Organization",
        "CO": "Company",
        "LO": "Location",
        "NE": "News",
        "PA": "Partner",
        "MS": "Messages",
        "LO": "Location",
        "DA": "Dashboard",
        "HE": "Help",
        "HI": "Hierarchy",
        "GR": "Grouping",
        "TR": "Translation",
        "US": "User Settings",
        "CP": "Compliance",
        "LP": "Legal Portal",
        "LL": "Legal Links",
        "DQ": "Data Quality",
        "CR": "Credit",
        "CM": "Common",
        "CO": "Company",
    }
    # Pour les clés spéciales
    if key.startswith("MS A") or key.startswith("MS_"):
        return "Messages"
    if key in ("COP_ID", "500", "400"):
        return "System"
    if key in ("companyLegalIdentifier", "locationLegalIdentifier"):
        return "General"
    if key.startswith("HIERARCHY_NODE_"):
        return "Hierarchy"
    if key in ("Company", "Location", "Organization", "Orga Unit", "Grouping"):
        return "General"
    if (
        key.startswith("INVALID")
        or key.startswith("INTERNAL")
        or key.startswith("PROVIDED")
        or key.startswith("BAD")
    ):
        return "Error Messages"
    if key.startswith("A00_"):
        return "Authentication"
    if (
        key.startswith("SIGN_")
        or key.startswith("LOGIN")
        or key.startswith("LOGOUT")
        or key.startswith("SESSION")
        or key.startswith("LANGUAGE")
        or key.startswith("SNACKBAR")
    ):
        return "Authentication"
    return sections.get(prefix, "Other")


def main():
    parser = argparse.ArgumentParser(
        description="Convertit les JSON de traduction en Excel"
    )
    parser.add_argument(
        "--input-dir",
        default="/app/output/2026_05_27_Export",
        help="Répertoire contenant les fichiers JSON traduits",
    )
    parser.add_argument(
        "--source-dir",
        default="/app/source/2026_05_27_Import",
        help="Répertoire contenant le fichier source anglais",
    )
    parser.add_argument(
        "--source-file", default="en 5.json", help="Nom du fichier source anglais"
    )
    parser.add_argument(
        "--output",
        default="/app/excel/translations_en_cz_sk.xlsx",
        help="Fichier Excel de sortie",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    source_dir = args.source_dir
    source_file = args.source_file
    output_file = args.output

    # Chargement des fichiers JSON traduits
    cz_file = os.path.join(input_dir, "translation_en_cz.json")
    sk_file = os.path.join(input_dir, "translation_en_sk.json")

    with open(cz_file, "r", encoding="utf-8") as f:
        cz_data = json.load(f)
    with open(sk_file, "r", encoding="utf-8") as f:
        sk_data = json.load(f)

    # Chargement du fichier source anglais
    en_file = os.path.join(source_dir, source_file)
    with open(en_file, "r", encoding="utf-8") as f:
        en_data = json.load(f)

    # Vérification que les clés correspondent
    cz_keys = set(cz_data.keys())
    sk_keys = set(sk_data.keys())
    en_keys = set(en_data.keys())
    all_keys = sorted(set(list(cz_keys) + list(sk_keys) + list(en_keys)))

    only_cz = cz_keys - sk_keys - en_keys
    only_sk = sk_keys - cz_keys - en_keys
    only_en = en_keys - cz_keys - sk_keys
    if only_cz:
        print(f"⚠ Clés uniquement dans CZ ({len(only_cz)}): {list(only_cz)[:10]}...")
    if only_sk:
        print(f"⚠ Clés uniquement dans SK ({len(only_sk)}): {list(only_sk)[:10]}...")
    if only_en:
        print(f"⚠ Clés uniquement dans EN ({len(only_en)}): {list(only_en)[:10]}...")

    # Création du workbook
    wb = Workbook()

    # --- Feuille 1: Tableau complet ---
    ws_all = wb.active
    ws_all.title = "Traductions"

    # Styles
    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(
        start_color="2F5496", end_color="2F5496", fill_type="solid"
    )
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_alignment = Alignment(vertical="top", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    empty_fill = PatternFill(
        start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"
    )

    # En-têtes
    headers = [
        "Section",
        "Clé",
        "Anglais (EN)",
        "Tchèque (CZ)",
        "Slovaque (SK)",
        "EN vide ?",
        "CZ vide ?",
        "SK vide ?",
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws_all.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Données
    for row_idx, key in enumerate(all_keys, 2):
        en_val = en_data.get(key, "")
        cz_val = cz_data.get(key, "")
        sk_val = sk_data.get(key, "")
        section = derive_section(key)

        ws_all.cell(row=row_idx, column=1, value=section).border = thin_border
        ws_all.cell(row=row_idx, column=2, value=key).border = thin_border

        cell_en = ws_all.cell(row=row_idx, column=3, value=en_val)
        cell_en.border = thin_border
        cell_en.alignment = cell_alignment
        if en_val == "":
            cell_en.fill = empty_fill

        cell_cz = ws_all.cell(row=row_idx, column=4, value=cz_val)
        cell_cz.border = thin_border
        cell_cz.alignment = cell_alignment
        if cz_val == "":
            cell_cz.fill = empty_fill

        cell_sk = ws_all.cell(row=row_idx, column=5, value=sk_val)
        cell_sk.border = thin_border
        cell_sk.alignment = cell_alignment
        if sk_val == "":
            cell_sk.fill = empty_fill

        cell_en_empty = ws_all.cell(
            row=row_idx, column=6, value="✓" if en_val == "" else ""
        )
        cell_en_empty.border = thin_border
        cell_en_empty.alignment = Alignment(horizontal="center")
        if en_val == "":
            cell_en_empty.fill = empty_fill

        cell_cz_empty = ws_all.cell(
            row=row_idx, column=7, value="✓" if cz_val == "" else ""
        )
        cell_cz_empty.border = thin_border
        cell_cz_empty.alignment = Alignment(horizontal="center")
        if cz_val == "":
            cell_cz_empty.fill = empty_fill

        cell_sk_empty = ws_all.cell(
            row=row_idx, column=8, value="✓" if sk_val == "" else ""
        )
        cell_sk_empty.border = thin_border
        cell_sk_empty.alignment = Alignment(horizontal="center")
        if sk_val == "":
            cell_sk_empty.fill = empty_fill

    # Largeurs de colonnes
    ws_all.column_dimensions["A"].width = 18
    ws_all.column_dimensions["B"].width = 35
    ws_all.column_dimensions["C"].width = 50
    ws_all.column_dimensions["D"].width = 50
    ws_all.column_dimensions["E"].width = 50
    ws_all.column_dimensions["F"].width = 10
    ws_all.column_dimensions["G"].width = 10
    ws_all.column_dimensions["H"].width = 10

    # Filtres automatiques
    ws_all.auto_filter.ref = f"A1:H{len(all_keys) + 1}"

    # Freeze top row
    ws_all.freeze_panes = "A2"

    # --- Feuille 2: Statistiques par section ---
    ws_stats = wb.create_sheet("Statistiques")
    stats = {}
    empty_en_count = 0
    empty_cz_count = 0
    empty_sk_count = 0
    for key in all_keys:
        section = derive_section(key)
        en_val = en_data.get(key, "")
        cz_val = cz_data.get(key, "")
        sk_val = sk_data.get(key, "")
        if section not in stats:
            stats[section] = {"total": 0, "en_empty": 0, "cz_empty": 0, "sk_empty": 0}
        stats[section]["total"] += 1
        if en_val == "":
            stats[section]["en_empty"] += 1
            empty_en_count += 1
        if cz_val == "":
            stats[section]["cz_empty"] += 1
            empty_cz_count += 1
        if sk_val == "":
            stats[section]["sk_empty"] += 1
            empty_sk_count += 1

    stats_headers = [
        "Section",
        "Nombre de clés",
        "EN vides",
        "CZ vides",
        "SK vides",
        "% traduit EN",
        "% traduit CZ",
        "% traduit SK",
    ]
    for col_idx, header in enumerate(stats_headers, 1):
        cell = ws_stats.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    for row_idx, (section, data) in enumerate(sorted(stats.items()), 2):
        ws_stats.cell(row=row_idx, column=1, value=section).border = thin_border
        ws_stats.cell(row=row_idx, column=2, value=data["total"]).border = thin_border
        ws_stats.cell(
            row=row_idx, column=3, value=data["en_empty"]
        ).border = thin_border
        ws_stats.cell(
            row=row_idx, column=4, value=data["cz_empty"]
        ).border = thin_border
        ws_stats.cell(
            row=row_idx, column=5, value=data["sk_empty"]
        ).border = thin_border
        pct_en = (
            round((1 - data["en_empty"] / data["total"]) * 100, 1)
            if data["total"] > 0
            else 0
        )
        pct_cz = (
            round((1 - data["cz_empty"] / data["total"]) * 100, 1)
            if data["total"] > 0
            else 0
        )
        pct_sk = (
            round((1 - data["sk_empty"] / data["total"]) * 100, 1)
            if data["total"] > 0
            else 0
        )
        ws_stats.cell(row=row_idx, column=6, value=f"{pct_en}%").border = thin_border
        ws_stats.cell(row=row_idx, column=7, value=f"{pct_cz}%").border = thin_border
        ws_stats.cell(row=row_idx, column=8, value=f"{pct_sk}%").border = thin_border

    # Total
    total_row = len(stats) + 2
    ws_stats.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
    ws_stats.cell(row=total_row, column=2, value=len(all_keys)).font = Font(bold=True)
    ws_stats.cell(row=total_row, column=3, value=empty_en_count).font = Font(bold=True)
    ws_stats.cell(row=total_row, column=4, value=empty_cz_count).font = Font(bold=True)
    ws_stats.cell(row=total_row, column=5, value=empty_sk_count).font = Font(bold=True)
    pct_en_total = (
        round((1 - empty_en_count / len(all_keys)) * 100, 1) if len(all_keys) > 0 else 0
    )
    pct_cz_total = (
        round((1 - empty_cz_count / len(all_keys)) * 100, 1) if len(all_keys) > 0 else 0
    )
    pct_sk_total = (
        round((1 - empty_sk_count / len(all_keys)) * 100, 1) if len(all_keys) > 0 else 0
    )
    ws_stats.cell(row=total_row, column=6, value=f"{pct_en_total}%").font = Font(
        bold=True
    )
    ws_stats.cell(row=total_row, column=7, value=f"{pct_cz_total}%").font = Font(
        bold=True
    )
    ws_stats.cell(row=total_row, column=8, value=f"{pct_sk_total}%").font = Font(
        bold=True
    )

    ws_stats.column_dimensions["A"].width = 20
    ws_stats.column_dimensions["B"].width = 18
    ws_stats.column_dimensions["C"].width = 12
    ws_stats.column_dimensions["D"].width = 12
    ws_stats.column_dimensions["E"].width = 12
    ws_stats.column_dimensions["F"].width = 15
    ws_stats.column_dimensions["G"].width = 15
    ws_stats.column_dimensions["H"].width = 15

    # --- Feuille 3: Clés avec traductions manquantes ---
    ws_missing = wb.create_sheet("Traductions manquantes")
    missing_headers = ["Clé", "Section", "EN vide", "CZ vide", "SK vide"]
    for col_idx, header in enumerate(missing_headers, 1):
        cell = ws_missing.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    missing_row = 2
    for key in all_keys:
        en_val = en_data.get(key, "")
        cz_val = cz_data.get(key, "")
        sk_val = sk_data.get(key, "")
        if en_val == "" or cz_val == "" or sk_val == "":
            section = derive_section(key)
            ws_missing.cell(row=missing_row, column=1, value=key).border = thin_border
            ws_missing.cell(
                row=missing_row, column=2, value=section
            ).border = thin_border
            ws_missing.cell(
                row=missing_row, column=3, value="✓" if en_val == "" else ""
            ).border = thin_border
            ws_missing.cell(
                row=missing_row, column=4, value="✓" if cz_val == "" else ""
            ).border = thin_border
            ws_missing.cell(
                row=missing_row, column=5, value="✓" if sk_val == "" else ""
            ).border = thin_border
            missing_row += 1

    ws_missing.column_dimensions["A"].width = 35
    ws_missing.column_dimensions["B"].width = 18
    ws_missing.column_dimensions["C"].width = 10
    ws_missing.column_dimensions["D"].width = 10
    ws_missing.column_dimensions["E"].width = 10

    # Création du répertoire de sortie si nécessaire
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Sauvegarde
    wb.save(output_file)
    print(f"\n✅ Fichier Excel créé: {output_file}")
    print(f"   - {len(all_keys)} clés de traduction")
    print(
        f"   - {empty_en_count} traductions EN manquantes ({pct_en_total}% renseigné)"
    )
    print(f"   - {empty_cz_count} traductions CZ manquantes ({pct_cz_total}% traduit)")
    print(f"   - {empty_sk_count} traductions SK manquantes ({pct_sk_total}% traduit)")
    print(
        f"   - {len(all_keys) - max(empty_en_count, empty_cz_count, empty_sk_count)} clés complètement renseignées dans les 3 langues"
    )


if __name__ == "__main__":
    main()
