"""
Mode: analyze — XLSX file structure analysis and reporting.

This module analyzes an XLSX file and provides a detailed report of its
structure, including sheet information, headers, unique values, and sample data.
"""

import json
import logging
from pathlib import Path
from typing import Any

from core.config import get_config
from core.io_xlsx import analyze_xlsx

logger = logging.getLogger(__name__)


def _print_analysis(analysis: dict[str, Any]) -> None:
    """
    Display the XLSX analysis in a human-readable format.

    Args:
        analysis: The analysis dictionary from analyze_xlsx().
    """
    stats = analysis.get("statistiques", {})

    logger.info("=" * 60)
    logger.info("XLSX FILE ANALYSIS")
    logger.info("=" * 60)
    logger.info("File: %s", analysis.get("fichier", "unknown"))
    logger.info("Total sheets: %d", stats.get("total_feuilles", 0))
    logger.info("Total rows: %d", stats.get("total_lignes", 0))
    logger.info("Total columns: %d", stats.get("total_colonnes", 0))
    logger.info("")

    for sheet in analysis.get("feuilles", []):
        logger.info("-" * 60)
        logger.info("SHEET: %s", sheet.get("nom", "unknown"))
        logger.info("-" * 60)
        logger.info("  Dimensions: %s", sheet.get("dimensions", "unknown"))
        logger.info(
            "  Rows: %d (data rows: %d)",
            sheet.get("lignes", 0),
            sheet.get("nombre_lignes_donnees", 0),
        )
        logger.info("  Columns: %d", sheet.get("colonnes", 0))
        logger.info("")

        headers = sheet.get("en_tetes", [])
        logger.info("  Headers: %s", headers)
        logger.info("")

        unique_per_col = sheet.get("valeurs_uniques_par_colonne", {})
        logger.info("  Unique values per column:")
        for col_name, values in unique_per_col.items():
            count = len(values)
            logger.info("    %s: %d unique value(s)", col_name, count)
            if count <= 10:
                for val in values:
                    logger.info("      - %s", val)
            else:
                logger.info("      First 10: %s", values[:10])
                logger.info("      ... and %d more", count - 10)
        logger.info("")

        first_row = sheet.get("premiere_ligne")
        if first_row:
            logger.info("  First data row: %s", first_row)

        logger.info("")


def _export_json(analysis: dict[str, Any], output_path: Path) -> None:
    """
    Export the analysis as JSON for later use.

    Args:
        analysis: The analysis dictionary.
        output_path: Path where to save the JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    logger.info("Analysis JSON exported to: %s", output_path)


def run() -> dict[str, Any]:
    """
    Execute the analyze mode.

    Loads an XLSX file (from SOURCE_FILE or default), analyzes its structure,
    displays the results, and exports the analysis as JSON.

    Returns:
        The analysis dictionary containing all structural information.
    """
    config = get_config()

    # Determine source file path
    if config.SOURCE_FILE:
        file_path = Path(config.SOURCE_FILE)
    else:
        file_path = Path(config.EXCEL_DIR) / "Dropdown_a_traduire.xlsx"

    logger.info("=" * 60)
    logger.info("MODE: analyze")
    logger.info("=" * 60)
    logger.info("Analyzing file: %s", file_path)
    logger.info("=" * 60)

    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        return {}

    # Perform analysis
    try:
        analysis = analyze_xlsx(file_path)
    except Exception as e:
        logger.error("Failed to analyze XLSX file: %s", e)
        return {}

    # Display results
    _print_analysis(analysis)

    # Export JSON
    output_path = Path(config.DOC_DIR) / "xlsx_analysis.json"
    _export_json(analysis, output_path)

    logger.info("=" * 60)
    logger.info("Analysis completed!")
    logger.info("=" * 60)

    return analysis


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run()
