"""
Tests for modes/mode_analyze.py — XLSX analysis mode.

Covers:
- _print_analysis(): logging of analysis information (stats, sheets, headers, unique values)
- _export_json(): writing analysis dict to a JSON file with correct content
- run(): main entry point with SOURCE_FILE, default path, file-not-found, success, and exception handling
"""

import json
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from modes.mode_analyze import _export_json, _print_analysis, run

# ─── Sample analysis data ─────────────────────────────────────────


def _make_sample_analysis(file_path: str = "/tmp/test.xlsx") -> dict:
    """Build a sample analysis dict matching analyze_xlsx() output structure."""
    return {
        "fichier": file_path,
        "feuilles": [
            {
                "nom": "Dropdowns",
                "dimensions": "A1:C5",
                "lignes": 5,
                "colonnes": 3,
                "en_tetes": ["Origin", "French", "Context"],
                "nombre_lignes_donnees": 4,
                "valeurs_uniques_par_colonne": {
                    "Origin": ["Button", "Cancel", "File", "Open"],
                    "French": ["Annuler", "Bouton", "Fichier", "Ouvrir"],
                    "Context": ["btn", "menu"],
                },
                "premiere_ligne": ["Button", "Bouton", "btn"],
                "dernieres_lignes": [["Open", "Ouvrir", "menu"]],
            }
        ],
        "statistiques": {
            "total_feuilles": 1,
            "total_lignes": 5,
            "total_colonnes": 3,
        },
        "donnees": [],
    }


def _make_multi_sheet_analysis(file_path: str = "/tmp/multi.xlsx") -> dict:
    """Build a sample analysis dict with multiple sheets."""
    return {
        "fichier": file_path,
        "feuilles": [
            {
                "nom": "Dropdowns",
                "dimensions": "A1:C5",
                "lignes": 5,
                "colonnes": 3,
                "en_tetes": ["Origin", "French", "Context"],
                "nombre_lignes_donnees": 4,
                "valeurs_uniques_par_colonne": {
                    "Origin": ["Button", "Cancel"],
                    "Context": ["btn"],
                },
                "premiere_ligne": ["Button", "Bouton", "btn"],
                "dernieres_lignes": [["Cancel", "Annuler", "btn"]],
            },
            {
                "nom": "Labels",
                "dimensions": "A1:B3",
                "lignes": 3,
                "colonnes": 2,
                "en_tetes": ["Key", "Value"],
                "nombre_lignes_donnees": 2,
                "valeurs_uniques_par_colonne": {
                    "Key": ["lbl_home", "lbl_exit"],
                    "Value": ["Exit", "Home"],
                },
                "premiere_ligne": ["lbl_home", "Home"],
                "dernieres_lignes": [["lbl_exit", "Exit"]],
            },
        ],
        "statistiques": {
            "total_feuilles": 2,
            "total_lignes": 8,
            "total_colonnes": 5,
        },
        "donnees": [],
    }


def _make_many_unique_values_analysis() -> dict:
    """Build an analysis dict with more than 10 unique values in a column."""
    values = [f"item_{i:02d}" for i in range(15)]
    return {
        "fichier": "/tmp/many_values.xlsx",
        "feuilles": [
            {
                "nom": "Data",
                "dimensions": "A1:B16",
                "lignes": 16,
                "colonnes": 1,
                "en_tetes": ["Label"],
                "nombre_lignes_donnees": 15,
                "valeurs_uniques_par_colonne": {
                    "Label": values,
                },
                "premiere_ligne": ["item_00"],
                "dernieres_lignes": [["item_14"]],
            }
        ],
        "statistiques": {
            "total_feuilles": 1,
            "total_lignes": 16,
            "total_colonnes": 1,
        },
        "donnees": [],
    }


# ─── _print_analysis ──────────────────────────────────────────────


class TestPrintAnalysis:
    """Tests for _print_analysis() — logging of analysis results."""

    def test_logs_file_name(self, caplog):
        """Logs the file path from the analysis dict."""
        analysis = _make_sample_analysis("/tmp/my_file.xlsx")
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "my_file.xlsx" in caplog.text

    def test_logs_total_sheets(self, caplog):
        """Logs the total number of sheets."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Total sheets: 1" in caplog.text

    def test_logs_total_rows(self, caplog):
        """Logs the total number of rows."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Total rows: 5" in caplog.text

    def test_logs_total_columns(self, caplog):
        """Logs the total number of columns."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Total columns: 3" in caplog.text

    def test_logs_sheet_name(self, caplog):
        """Logs each sheet name."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "SHEET: Dropdowns" in caplog.text

    def test_logs_sheet_dimensions(self, caplog):
        """Logs sheet dimensions."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "A1:C5" in caplog.text

    def test_logs_sheet_row_counts(self, caplog):
        """Logs total rows and data rows for a sheet."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Rows: 5 (data rows: 4)" in caplog.text

    def test_logs_sheet_column_count(self, caplog):
        """Logs column count for a sheet."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Columns: 3" in caplog.text

    def test_logs_headers(self, caplog):
        """Logs the headers for each sheet."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Origin" in caplog.text
        assert "French" in caplog.text
        assert "Context" in caplog.text

    def test_logs_unique_value_counts(self, caplog):
        """Logs the number of unique values per column."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Origin: 4 unique value(s)" in caplog.text
        assert "Context: 2 unique value(s)" in caplog.text

    def test_logs_individual_unique_values_when_few(self, caplog):
        """When a column has <=10 unique values, each value is logged individually."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "Button" in caplog.text
        assert "Cancel" in caplog.text

    def test_logs_first_10_unique_values_when_many(self, caplog):
        """When a column has >10 unique values, only the first 10 are shown with a count."""
        analysis = _make_many_unique_values_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "First 10:" in caplog.text
        assert "and 5 more" in caplog.text

    def test_logs_first_data_row(self, caplog):
        """Logs the first data row when present."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "First data row" in caplog.text

    def test_logs_multiple_sheets(self, caplog):
        """Logs information for each sheet when there are multiple."""
        analysis = _make_multi_sheet_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "SHEET: Dropdowns" in caplog.text
        assert "SHEET: Labels" in caplog.text

    def test_handles_empty_analysis(self, caplog):
        """Handles an empty/minimal analysis dict without errors."""
        analysis = {"fichier": "unknown", "feuilles": [], "statistiques": {}}
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "XLSX FILE ANALYSIS" in caplog.text
        assert "Total sheets: 0" in caplog.text

    def test_handles_sheet_without_first_row(self, caplog):
        """Handles a sheet that has no first data row (empty sheet)."""
        analysis = {
            "fichier": "/tmp/empty_sheet.xlsx",
            "feuilles": [
                {
                    "nom": "Empty",
                    "dimensions": "A1:A1",
                    "lignes": 1,
                    "colonnes": 1,
                    "en_tetes": ["Col1"],
                    "nombre_lignes_donnees": 0,
                    "valeurs_uniques_par_colonne": {},
                    "premiere_ligne": None,
                    "dernieres_lignes": [],
                }
            ],
            "statistiques": {
                "total_feuilles": 1,
                "total_lignes": 1,
                "total_colonnes": 1,
            },
            "donnees": [],
        }
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "SHEET: Empty" in caplog.text

    def test_logs_xlsx_analysis_header(self, caplog):
        """Logs the 'XLSX FILE ANALYSIS' banner."""
        analysis = _make_sample_analysis()
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _print_analysis(analysis)
        assert "XLSX FILE ANALYSIS" in caplog.text


# ─── _export_json ──────────────────────────────────────────────────


class TestExportJson:
    """Tests for _export_json() — exporting analysis as JSON."""

    def test_creates_json_file(self, temp_dir):
        """Creates a JSON file at the specified output path."""
        analysis = _make_sample_analysis()
        output_path = temp_dir / "output" / "analysis.json"
        _export_json(analysis, output_path)
        assert output_path.exists()

    def test_writes_valid_json(self, temp_dir):
        """The written file contains valid JSON."""
        analysis = _make_sample_analysis()
        output_path = temp_dir / "analysis.json"
        _export_json(analysis, output_path)
        with output_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_content_matches_input(self, temp_dir):
        """The JSON content matches the input analysis dict exactly."""
        analysis = _make_sample_analysis("/tmp/my_file.xlsx")
        output_path = temp_dir / "analysis.json"
        _export_json(analysis, output_path)
        with output_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["fichier"] == "/tmp/my_file.xlsx"
        assert data["statistiques"]["total_feuilles"] == 1
        assert len(data["feuilles"]) == 1
        assert data["feuilles"][0]["nom"] == "Dropdowns"

    def test_creates_parent_directories(self, temp_dir):
        """Creates parent directories if they do not exist."""
        analysis = _make_sample_analysis()
        output_path = temp_dir / "deep" / "nested" / "dir" / "analysis.json"
        _export_json(analysis, output_path)
        assert output_path.exists()

    def test_preserves_unicode_characters(self, temp_dir):
        """Unicode characters in the analysis are preserved in the JSON."""
        analysis = {
            "fichier": "/tmp/unicode.xlsx",
            "feuilles": [
                {
                    "nom": "Données",
                    "valeurs_uniques_par_colonne": {
                        "Texte": ["Français", "Résumé", "À propos"],
                    },
                    "en_tetes": ["Texte"],
                    "premiere_ligne": ["Français"],
                }
            ],
            "statistiques": {
                "total_feuilles": 1,
                "total_lignes": 1,
                "total_colonnes": 1,
            },
            "donnees": [],
        }
        output_path = temp_dir / "unicode_analysis.json"
        _export_json(analysis, output_path)
        with output_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["feuilles"][0]["nom"] == "Données"
        assert "Français" in data["feuilles"][0]["valeurs_uniques_par_colonne"]["Texte"]

    def test_writes_human_readable_unicode(self, temp_dir):
        """JSON is written with ensure_ascii=False so Unicode is human-readable."""
        analysis = {
            "fichier": "/tmp/test.xlsx",
            "feuilles": [
                {
                    "nom": "Résumé",
                    "en_tetes": ["Texte"],
                    "valeurs_uniques_par_colonne": {},
                    "premiere_ligne": ["Écriture"],
                }
            ],
            "statistiques": {},
            "donnees": [],
        }
        output_path = temp_dir / "test.json"
        _export_json(analysis, output_path)
        content = output_path.read_text(encoding="utf-8")
        # ensure_ascii=False means Unicode chars are NOT escaped as \uXXXX
        assert "Résumé" in content
        assert "Écriture" in content

    def test_logs_export_path(self, caplog, temp_dir):
        """Logs the path where the JSON was exported."""
        analysis = _make_sample_analysis()
        output_path = temp_dir / "analysis.json"
        with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
            _export_json(analysis, output_path)
        assert "Analysis JSON exported" in caplog.text
        assert str(output_path) in caplog.text

    def test_overwrites_existing_file(self, temp_dir):
        """Overwrites an existing file with new content."""
        analysis1 = {
            "fichier": "/tmp/first.xlsx",
            "feuilles": [],
            "statistiques": {},
            "donnees": [],
        }
        analysis2 = {
            "fichier": "/tmp/second.xlsx",
            "feuilles": [],
            "statistiques": {},
            "donnees": [],
        }
        output_path = temp_dir / "analysis.json"

        _export_json(analysis1, output_path)
        _export_json(analysis2, output_path)

        with output_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["fichier"] == "/tmp/second.xlsx"


# ─── run ───────────────────────────────────────────────────────────


class TestRunWithSourceFile:
    """Tests for run() when SOURCE_FILE is explicitly set."""

    @patch("pathlib.Path.exists", return_value=True)
    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    @patch.dict(
        os.environ, {"SOURCE_FILE": "/explicit/path/dropdown.xlsx"}, clear=False
    )
    def test_uses_source_file_when_set(
        self, mock_analyze, mock_print, mock_export, mock_exists
    ):
        """When SOURCE_FILE is set, run() analyzes that file."""
        mock_analyze.return_value = _make_sample_analysis(
            "/explicit/path/dropdown.xlsx"
        )
        result = run()
        mock_analyze.assert_called_once()
        called_path = mock_analyze.call_args[0][0]
        assert str(called_path) == "/explicit/path/dropdown.xlsx"

    @patch("pathlib.Path.exists", return_value=True)
    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    @patch.dict(
        os.environ, {"SOURCE_FILE": "/explicit/path/dropdown.xlsx"}, clear=False
    )
    def test_returns_analysis_dict(
        self, mock_analyze, mock_print, mock_export, mock_exists
    ):
        """When analysis succeeds, run() returns the analysis dict."""
        expected = _make_sample_analysis("/explicit/path/dropdown.xlsx")
        mock_analyze.return_value = expected
        result = run()
        assert result == expected

    @patch("pathlib.Path.exists", return_value=True)
    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    @patch.dict(
        os.environ, {"SOURCE_FILE": "/explicit/path/dropdown.xlsx"}, clear=False
    )
    def test_calls_print_analysis(
        self, mock_analyze, mock_print, mock_export, mock_exists
    ):
        """run() calls _print_analysis with the analysis result."""
        analysis = _make_sample_analysis("/explicit/path/dropdown.xlsx")
        mock_analyze.return_value = analysis
        run()
        mock_print.assert_called_once_with(analysis)

    @patch("pathlib.Path.exists", return_value=True)
    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    @patch.dict(
        os.environ, {"SOURCE_FILE": "/explicit/path/dropdown.xlsx"}, clear=False
    )
    def test_calls_export_json(
        self, mock_analyze, mock_print, mock_export, mock_exists
    ):
        """run() calls _export_json to save the analysis."""
        analysis = _make_sample_analysis("/explicit/path/dropdown.xlsx")
        mock_analyze.return_value = analysis
        run()
        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args[0][0] == analysis
        # Second arg should be a Path ending in xlsx_analysis.json
        assert str(call_args[0][1]).endswith("xlsx_analysis.json")


class TestRunWithoutSourceFile:
    """Tests for run() when SOURCE_FILE is not set (default path used)."""

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    @patch("pathlib.Path.exists", return_value=True)
    @patch.dict(os.environ, {"SOURCE_FILE": "", "EXCEL_DIR": "/app/excel"}, clear=False)
    def test_uses_default_path(
        self, mock_exists, mock_analyze, mock_print, mock_export
    ):
        """Without SOURCE_FILE, uses EXCEL_DIR/Dropdown_a_traduire.xlsx."""
        mock_analyze.return_value = _make_sample_analysis()
        run()
        called_path = mock_analyze.call_args[0][0]
        assert str(called_path) == str(Path("/app/excel") / "Dropdown_a_traduire.xlsx")

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    @patch("pathlib.Path.exists", return_value=True)
    @patch.dict(
        os.environ, {"SOURCE_FILE": "", "EXCEL_DIR": "/custom/excel"}, clear=False
    )
    def test_custom_excel_dir(self, mock_exists, mock_analyze, mock_print, mock_export):
        """EXCEL_DIR environment variable changes the default file path."""
        mock_analyze.return_value = _make_sample_analysis()
        run()
        called_path = mock_analyze.call_args[0][0]
        assert str(called_path) == str(
            Path("/custom/excel") / "Dropdown_a_traduire.xlsx"
        )


class TestRunFileNotFound:
    """Tests for run() when the file does not exist."""

    def test_returns_empty_dict(self, temp_dir, caplog):
        """When the file is not found, returns an empty dict."""
        nonexistent = temp_dir / "nonexistent.xlsx"
        with patch.dict(os.environ, {"SOURCE_FILE": str(nonexistent)}, clear=False):
            with caplog.at_level(logging.ERROR, logger="modes.mode_analyze"):
                result = run()
        assert result == {}

    def test_logs_error_message(self, temp_dir, caplog):
        """When the file is not found, logs an error with the file path."""
        nonexistent = temp_dir / "missing.xlsx"
        with patch.dict(os.environ, {"SOURCE_FILE": str(nonexistent)}, clear=False):
            with caplog.at_level(logging.ERROR, logger="modes.mode_analyze"):
                run()
        assert "File not found" in caplog.text
        assert "missing.xlsx" in caplog.text

    @patch("modes.mode_analyze.analyze_xlsx")
    @patch.dict(
        os.environ, {"SOURCE_FILE": "", "EXCEL_DIR": "/nonexistent/dir"}, clear=False
    )
    def test_default_file_not_found_returns_empty(self, mock_analyze, caplog):
        """When default path file does not exist, returns empty dict without calling analyze_xlsx."""
        with caplog.at_level(logging.ERROR, logger="modes.mode_analyze"):
            result = run()
        assert result == {}
        mock_analyze.assert_not_called()


class TestRunAnalyzeException:
    """Tests for run() when analyze_xlsx raises an exception."""

    def test_returns_empty_dict_on_exception(self, temp_dir, caplog):
        """When analyze_xlsx raises, run() returns an empty dict."""
        xlsx_file = temp_dir / "test.xlsx"
        xlsx_file.touch()  # Create the file so it "exists"
        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with patch("modes.mode_analyze.analyze_xlsx") as mock_analyze:
                mock_analyze.side_effect = Exception("Corrupt file")
                with caplog.at_level(logging.ERROR, logger="modes.mode_analyze"):
                    result = run()
        assert result == {}

    def test_logs_error_on_exception(self, temp_dir, caplog):
        """When analyze_xlsx raises, run() logs the error message."""
        xlsx_file = temp_dir / "corrupt.xlsx"
        xlsx_file.touch()
        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with patch("modes.mode_analyze.analyze_xlsx") as mock_analyze:
                mock_analyze.side_effect = Exception("Corrupt file")
                with caplog.at_level(logging.ERROR, logger="modes.mode_analyze"):
                    run()
        assert "Failed to analyze XLSX file" in caplog.text
        assert "Corrupt file" in caplog.text

    def test_does_not_export_json_on_exception(self, temp_dir):
        """When analyze_xlsx raises, _export_json is NOT called."""
        xlsx_file = temp_dir / "bad.xlsx"
        xlsx_file.touch()
        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with patch("modes.mode_analyze.analyze_xlsx") as mock_analyze:
                with patch("modes.mode_analyze._export_json") as mock_export:
                    mock_analyze.side_effect = Exception("Parse error")
                    run()
        mock_export.assert_not_called()

    def test_does_not_print_analysis_on_exception(self, temp_dir):
        """When analyze_xlsx raises, _print_analysis is NOT called."""
        xlsx_file = temp_dir / "bad.xlsx"
        xlsx_file.touch()
        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with patch("modes.mode_analyze.analyze_xlsx") as mock_analyze:
                with patch("modes.mode_analyze._print_analysis") as mock_print:
                    mock_analyze.side_effect = Exception("Parse error")
                    run()
        mock_print.assert_not_called()


class TestRunSuccess:
    """Tests for run() on successful analysis."""

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    def test_returns_full_analysis(
        self, mock_analyze, mock_print, mock_export, temp_dir
    ):
        """On success, returns the full analysis dict from analyze_xlsx."""
        xlsx_file = temp_dir / "Dropdown_a_traduire.xlsx"
        xlsx_file.touch()
        expected = _make_sample_analysis(str(xlsx_file))
        mock_analyze.return_value = expected

        with patch.dict(
            os.environ,
            {"SOURCE_FILE": str(xlsx_file), "DOC_DIR": str(temp_dir)},
            clear=False,
        ):
            result = run()

        assert result == expected
        assert result["fichier"] == str(xlsx_file)
        assert result["statistiques"]["total_feuilles"] == 1

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    def test_export_uses_doc_dir(self, mock_analyze, mock_print, mock_export, temp_dir):
        """On success, exports JSON to DOC_DIR/xlsx_analysis.json."""
        xlsx_file = temp_dir / "data.xlsx"
        xlsx_file.touch()
        analysis = _make_sample_analysis(str(xlsx_file))
        mock_analyze.return_value = analysis

        with patch.dict(
            os.environ,
            {"SOURCE_FILE": str(xlsx_file), "DOC_DIR": str(temp_dir / "docs")},
            clear=False,
        ):
            run()

        call_args = mock_export.call_args[0]
        output_path = call_args[1]
        assert str(output_path).endswith("xlsx_analysis.json")
        assert str(temp_dir / "docs") in str(output_path)

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    def test_logs_analyze_mode(
        self, mock_analyze, mock_print, mock_export, temp_dir, caplog
    ):
        """run() logs that it is running in 'analyze' mode."""
        xlsx_file = temp_dir / "data.xlsx"
        xlsx_file.touch()
        mock_analyze.return_value = _make_sample_analysis(str(xlsx_file))

        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
                run()

        assert "MODE: analyze" in caplog.text

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    def test_logs_analyzing_file(
        self, mock_analyze, mock_print, mock_export, temp_dir, caplog
    ):
        """run() logs which file it is analyzing."""
        xlsx_file = temp_dir / "data.xlsx"
        xlsx_file.touch()
        mock_analyze.return_value = _make_sample_analysis(str(xlsx_file))

        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
                run()

        assert "Analyzing file" in caplog.text
        assert "data.xlsx" in caplog.text

    @patch("modes.mode_analyze._export_json")
    @patch("modes.mode_analyze._print_analysis")
    @patch("modes.mode_analyze.analyze_xlsx")
    def test_logs_completion(
        self, mock_analyze, mock_print, mock_export, temp_dir, caplog
    ):
        """run() logs a completion message."""
        xlsx_file = temp_dir / "data.xlsx"
        xlsx_file.touch()
        mock_analyze.return_value = _make_sample_analysis(str(xlsx_file))

        with patch.dict(os.environ, {"SOURCE_FILE": str(xlsx_file)}, clear=False):
            with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
                run()

        assert "Analysis completed" in caplog.text


class TestRunIntegrationWithRealFile:
    """Tests for run() using a real temp XLSX file (analyze_xlsx NOT mocked)."""

    def test_analyzes_real_xlsx_file(self, temp_xlsx_file, temp_dir, caplog):
        """run() correctly analyzes a real XLSX file end-to-end."""
        with patch.dict(
            os.environ,
            {
                "SOURCE_FILE": str(temp_xlsx_file),
                "DOC_DIR": str(temp_dir / "doc_output"),
            },
            clear=False,
        ):
            with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
                result = run()

        # Verify analysis dict
        assert result != {}
        assert "fichier" in result
        assert "feuilles" in result
        assert "statistiques" in result
        assert result["statistiques"]["total_feuilles"] >= 1

        # Verify JSON was exported
        json_path = temp_dir / "doc_output" / "xlsx_analysis.json"
        assert json_path.exists()
        with json_path.open("r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["fichier"] == str(temp_xlsx_file)

        # Verify logging
        assert "Analysis completed" in caplog.text

    def test_default_path_with_real_xlsx(self, temp_xlsx_file, temp_dir, caplog):
        """run() with no SOURCE_FILE uses EXCEL_DIR/Dropdown_a_traduire.xlsx."""
        # Place the file at the default location
        import shutil

        excel_dir = temp_dir / "excel"
        excel_dir.mkdir()
        default_file = excel_dir / "Dropdown_a_traduire.xlsx"
        shutil.copy(str(temp_xlsx_file), str(default_file))

        with patch.dict(
            os.environ,
            {
                "SOURCE_FILE": "",
                "EXCEL_DIR": str(excel_dir),
                "DOC_DIR": str(temp_dir / "doc_output"),
            },
            clear=False,
        ):
            with caplog.at_level(logging.INFO, logger="modes.mode_analyze"):
                result = run()

        assert result != {}
        assert "fichier" in result

        # Verify it analyzed the default file
        json_path = temp_dir / "doc_output" / "xlsx_analysis.json"
        assert json_path.exists()
