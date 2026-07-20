"""
XLSX I/O module for the translation service.
Handles reading, writing, and analysis of Excel files for dropdown translations.
"""

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

    # C10 : ne créer une feuille que pour les langues réellement traduites.
    # `en` (source) et `fr` (issue de la colonne `french` du XLSX source)
    # sont toujours créées car leurs valeurs proviennent du fichier source,
    # pas d'un dict de traduction. Pour les autres langues, on exige un dict
    # de traduction non vide ; sinon on insère un marqueur `[NOT TRANSLATED]`
    # pour éviter un XLSX qui prétend être traduit à tort.
    sheets_created: list[str] = []
    for lang_code, lang_info in languages.items():
        if lang_code in ("en", "fr"):
            create_sheet = True
        else:
            lang_translations = translations.get(lang_code, {})
            create_sheet = bool(lang_translations)
        if create_sheet:
            ws = wb.create_sheet(title=lang_code.upper())
            ws.append(["Origin", "Traduction", "Contexte"])
            sheets_created.append(lang_code)
        else:
            ws = wb.create_sheet(title=f"{lang_code.upper()}_NOT_TRANSLATED")
            ws.append(["[NOT TRANSLATED]"])
            sheets_created.append(f"{lang_code}_not_translated")

    logger.info("Created %d language sheets", len(sheets_created))

    # Write data to each sheet
    for entry in data:
        origin = entry["origin"]
        context = entry["context"]

        for lang_code, lang_info in languages.items():
            sheet_title = lang_code.upper()
            if lang_code not in ("en", "fr") and not translations.get(lang_code):
                # Feuille marqueur — pas de données par entrée
                continue
            ws = wb[sheet_title]

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


# ─── Pipeline dropdown : lecture multi-feuilles ──────────────────────


def load_dropdown_xlsx_all_sheets(path: Path) -> dict[str, dict[str, str]]:
    """Lit TOUTES les feuilles d'un XLSX dropdown (une feuille par langue).

    Contrairement à `load_dropdown_xlsx` qui ne lit que la feuille active,
    cette fonction parcourt toutes les feuilles et construit un dict :
      {LANG_CODE: {origin: traduction}}

    Args:
        path: Chemin du fichier XLSX.

    Returns:
        Dict {nom_feuille_upper: {origin: traduction}}.
        Les lignes dont l'Origin est vide sont ignorées.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ImportError: Si openpyxl n'est pas installé (C8).
    """
    if openpyxl is None:
        raise ImportError("openpyxl is required for XLSX functionality")
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    wb = openpyxl.load_workbook(path, data_only=True)
    result: dict[str, dict[str, str]] = {}
    for ws in wb.worksheets:
        lang = ws.title.upper()
        translations: dict[str, str] = {}
        for row in range(2, ws.max_row + 1):
            origin = clean_text(ws.cell(row=row, column=1).value or "")
            traduction = clean_text(ws.cell(row=row, column=2).value or "")
            if origin:  # ignorer les lignes vides
                translations[origin] = traduction
        result[lang] = translations
    return result


def detect_missing_languages(
    xlsx_path: Path,
    configured_langs: list[str],
) -> list[str]:
    """Détecte les langues configurées absentes du XLSX source.

    Compare les noms de feuilles du XLSX (en majuscules) avec les langues
    configurées (en minuscules). 'en' (source) n'est jamais considéré
    comme manquant.

    Args:
        xlsx_path: Chemin du fichier XLSX à inspecter.
        configured_langs: Liste des codes langues configurés (ex : ['fr','cz','sk',...]).

    Returns:
        Liste triée des codes langues manquants (en minuscules).
    """
    all_sheets = load_dropdown_xlsx_all_sheets(xlsx_path)
    present = {lang.lower() for lang in all_sheets}
    missing = [
        lang
        for lang in configured_langs
        if lang.lower() != "en" and lang.lower() not in present
    ]
    return sorted(missing)
