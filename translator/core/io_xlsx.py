"""
XLSX I/O module for the translation service.
Handles reading, writing, and analysis of Excel files for dropdown translations.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

try:
    import openpyxl
    from openpyxl import Workbook
except ImportError:
    openpyxl = None
    Workbook = None
    logging.warning("openpyxl not installed. XLSX functionality will be limited.")

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and trimming.

    Args:
        text: The text to clean.

    Returns:
        Cleaned text with normalized whitespace.
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def load_dropdown_xlsx(file_path: str | Path) -> list[dict[str, str]]:
    """
    Load dropdown data from an XLSX source file.

    Expected XLSX structure:
        - Column A: Origin (source text)
        - Column B: French (French translation)
        - Column C: Context (translation context category)

    Args:
        file_path: Path to the XLSX file.

    Returns:
        List of dictionaries with keys: origin, french, context.

    Raises:
        FileNotFoundError: If the file does not exist.
        ImportError: If openpyxl is not installed.
    """
    if openpyxl is None:
        raise ImportError("openpyxl is required for XLSX operations")

    path = Path(file_path)
    logger.debug("Loading dropdown XLSX from: %s", path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    wb = openpyxl.load_workbook(path)
    ws = wb.active

    data: list[dict[str, str]] = []
    for row in range(2, ws.max_row + 1):
        origin = clean_text(ws.cell(row=row, column=1).value or "")
        french = clean_text(ws.cell(row=row, column=2).value or "")
        context = clean_text(ws.cell(row=row, column=3).value or "")

        if origin:
            data.append(
                {
                    "origin": origin,
                    "french": french,
                    "context": context or "unknown",
                }
            )

    logger.info("Loaded %d entries from dropdown XLSX: %s", len(data), path.name)
    return data


def analyze_xlsx(file_path: str | Path) -> dict[str, Any]:
    """
    Analyze an XLSX file and return detailed structure information.

    Provides comprehensive analysis including:
        - Sheet names and dimensions
        - Headers for each sheet
        - Unique values per column
        - Sample data rows

    Args:
        file_path: Path to the XLSX file to analyze.

    Returns:
        Dictionary containing:
            - fichier: Original file path
            - feuilles: List of sheet information dicts
            - statistiques: Overall statistics (total sheets, rows, columns)

    Raises:
        FileNotFoundError: If the file does not exist.
        ImportError: If openpyxl is not installed.
    """
    if openpyxl is None:
        raise ImportError("openpyxl is required for XLSX operations")

    path = Path(file_path)
    logger.debug("Analyzing XLSX file: %s", path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    wb = openpyxl.load_workbook(path)

    analysis: dict[str, Any] = {
        "fichier": str(path),
        "feuilles": [],
        "statistiques": {
            "total_feuilles": len(wb.sheetnames),
            "total_lignes": 0,
            "total_colonnes": 0,
        },
        "donnees": [],
    }

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]

        # Get headers
        headers: list[str | None] = []
        for col in range(1, ws.max_column + 1):
            headers.append(ws.cell(row=1, column=col).value)

        # Get all data rows
        rows_data: list[list[Any]] = []
        for row in range(2, ws.max_row + 1):
            row_data: list[Any] = []
            for col in range(1, ws.max_column + 1):
                row_data.append(ws.cell(row=row, column=col).value)
            rows_data.append(row_data)

        # Analyze unique values per column
        unique_values_per_column: dict[str, list[Any]] = {}
        for col_idx, header in enumerate(headers):
            if header:
                unique_vals: set[Any] = set()
                for row_data in rows_data:
                    if col_idx < len(row_data) and row_data[col_idx]:
                        unique_vals.add(row_data[col_idx])
                unique_values_per_column[header] = sorted(list(unique_vals))

        sheet_info: dict[str, Any] = {
            "nom": sheet_name,
            "dimensions": ws.dimensions,
            "lignes": ws.max_row,
            "colonnes": ws.max_column,
            "en_tetes": headers,
            "nombre_lignes_donnees": ws.max_row - 1,
            "valeurs_uniques_par_colonne": unique_values_per_column,
            "premiere_ligne": rows_data[0] if rows_data else None,
            "dernieres_lignes": rows_data[-5:] if len(rows_data) >= 5 else rows_data,
        }

        analysis["feuilles"].append(sheet_info)
        analysis["statistiques"]["total_lignes"] += ws.max_row
        analysis["statistiques"]["total_colonnes"] += ws.max_column
        analysis["donnees"].append({"feuille": sheet_name, "lignes": rows_data})

    logger.info(
        "XLSX analysis completed: %d sheets, %d total rows",
        analysis["statistiques"]["total_feuilles"],
        analysis["statistiques"]["total_lignes"],
    )

    return analysis


def save_dropdown_xlsx(
    data: list[dict[str, str]],
    translations: dict[str, dict[str, str]],
    output_file: str | Path,
    languages: dict[str, dict[str, str]],
) -> None:
    """
    Generate a multi-sheet XLSX file with translations for each language.

    Creates one sheet per language with columns: Origin, Traduction, Contexte

    Args:
        data: List of source entries with origin, french, context keys.
        translations: Dictionary mapping language code to translation dict.
            Format: {lang_code: {origin_text: translated_text, ...}}
        output_file: Output file path.
        languages: Language configuration dictionary.

    Raises:
        ImportError: If openpyxl is not installed.
    """
    if openpyxl is None or Workbook is None:
        raise ImportError("openpyxl is required for XLSX operations")

    path = Path(output_file)
    logger.debug("Saving dropdown XLSX to: %s", path)

    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # Create a sheet for each language
    for lang_code, lang_info in languages.items():
        ws = wb.create_sheet(title=lang_code.upper())
        ws.append(["Origin", "Traduction", "Contexte"])

    logger.info("Created %d language sheets", len(languages))

    # Write data to each sheet
    for entry in data:
        origin = entry["origin"]
        context = entry["context"]

        for lang_code, lang_info in languages.items():
            ws = wb[lang_code.upper()]

            if lang_code == "en":
                value = origin
            elif lang_code == "fr":
                value = entry.get("french", "")
            else:
                lang_translations = translations.get(lang_code, {})
                value = lang_translations.get(origin, origin)

            ws.append([origin, value, context])

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)

    logger.info(
        "Saved dropdown XLSX with %d entries across %d languages: %s",
        len(data),
        len(languages),
        path.name,
    )
