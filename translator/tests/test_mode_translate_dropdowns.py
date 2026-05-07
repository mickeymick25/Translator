"""
Tests for modes/mode_translate_dropdowns.py — Dropdown translation mode.

Covers:
- _detect_input_format(): xlsx/json/unknown detection from file extension
- _extract_entries_from_structured_json(): extracting entries from structured JSON
- _load_source_data(): loading from xlsx or json format (mocked loaders)
- _generate_json_output(): generating JSON output for a single language
- _translate_dropdown_entries_batch(): batch translation with resume support
- _build_contexts_from_translations(): building contexts dict from flat translations
- _get_source_file(): getting source file from config or default
- run(): main entry point with mocked dependencies
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from modes.mode_translate_dropdowns import (
    RATE_LIMIT_SECONDS,
    _build_contexts_from_translations,
    _detect_input_format,
    _extract_entries_from_structured_json,
    _generate_json_output,
    _get_source_file,
    _load_source_data,
    _translate_dropdown_entries_batch,
    run,
)

# ─── _detect_input_format ─────────────────────────────────────────


class TestDetectInputFormat:
    """Tests for _detect_input_format()."""

    def test_xlsx_extension(self):
        """'.xlsx' extension is detected as 'xlsx'."""
        assert _detect_input_format("source.xlsx") == "xlsx"

    def test_xls_extension(self):
        """'.xls' extension is detected as 'xlsx'."""
        assert _detect_input_format("source.xls") == "xlsx"

    def test_json_extension(self):
        """'.json' extension is detected as 'json'."""
        assert _detect_input_format("source.json") == "json"

    def test_uppercase_xlsx(self):
        """Uppercase '.XLSX' is detected correctly (case-insensitive)."""
        assert _detect_input_format("source.XLSX") == "xlsx"

    def test_uppercase_xls(self):
        """Uppercase '.XLS' is detected correctly."""
        assert _detect_input_format("source.XLS") == "xlsx"

    def test_uppercase_json(self):
        """Uppercase '.JSON' is detected correctly."""
        assert _detect_input_format("source.JSON") == "json"

    def test_unknown_txt(self):
        """'.txt' extension returns 'unknown'."""
        assert _detect_input_format("source.txt") == "unknown"

    def test_unknown_csv(self):
        """'.csv' extension returns 'unknown'."""
        assert _detect_input_format("data.csv") == "unknown"

    def test_no_extension(self):
        """A file with no extension returns 'unknown'."""
        assert _detect_input_format("source") == "unknown"

    def test_path_object_xlsx(self):
        """A Path object with .xlsx is detected correctly."""
        assert _detect_input_format(Path("/some/dir/source.xlsx")) == "xlsx"

    def test_path_object_json(self):
        """A Path object with .json is detected correctly."""
        assert _detect_input_format(Path("/some/dir/source.json")) == "json"

    def test_double_extension(self):
        """A double extension like '.xlsx.bak' is detected as 'unknown'."""
        assert _detect_input_format("source.xlsx.bak") == "unknown"


# ─── _extract_entries_from_structured_json ──────────────────────────


class TestExtractEntriesFromStructuredJson:
    """Tests for _extract_entries_from_structured_json()."""

    def test_extracts_entries_from_two_contexts(self, sample_json_structured):
        """Entries are extracted from multiple context sections."""
        entries = _extract_entries_from_structured_json(sample_json_structured)
        assert len(entries) == 4

    def test_entry_has_origin_key(self, sample_json_structured):
        """Each extracted entry has an 'origin' key."""
        entries = _extract_entries_from_structured_json(sample_json_structured)
        origins = {e["origin"] for e in entries}
        assert "Button" in origins
        assert "Cancel" in origins
        assert "File" in origins
        assert "Open" in origins

    def test_entry_has_french_key(self, sample_json_structured):
        """Each extracted entry has a 'french' key with the translation value."""
        entries = _extract_entries_from_structured_json(sample_json_structured)
        french_map = {e["origin"]: e["french"] for e in entries}
        assert french_map["Button"] == "Bouton"
        assert french_map["Cancel"] == "Annuler"
        assert french_map["File"] == "Fichier"
        assert french_map["Open"] == "Ouvrir"

    def test_entry_has_context_key(self, sample_json_structured):
        """Each extracted entry has a 'context' key matching the context name."""
        entries = _extract_entries_from_structured_json(sample_json_structured)
        btn_entries = [e for e in entries if e["context"] == "btn"]
        menu_entries = [e for e in entries if e["context"] == "menu"]
        assert len(btn_entries) == 2
        assert len(menu_entries) == 2

    def test_empty_contexts(self):
        """Empty contexts dict returns an empty list."""
        data = {"metadata": {"language": "EN"}, "contexts": {}}
        entries = _extract_entries_from_structured_json(data)
        assert entries == []

    def test_missing_contexts_key(self):
        """Missing 'contexts' key returns an empty list (uses .get default)."""
        data = {"metadata": {"language": "EN"}}
        entries = _extract_entries_from_structured_json(data)
        assert entries == []

    def test_single_entry_in_single_context(self):
        """A single entry in a single context is extracted correctly."""
        data = {
            "contexts": {
                "ui": {"Save": "Enregistrer"},
            }
        }
        entries = _extract_entries_from_structured_json(data)
        assert len(entries) == 1
        assert entries[0] == {
            "origin": "Save",
            "french": "Enregistrer",
            "context": "ui",
        }

    def test_preserves_unicode_values(self):
        """Unicode characters in translation values are preserved."""
        data = {
            "contexts": {
                "greetings": {"Hello": "مرحبا", "Goodbye": "مع السلامة"},
            }
        }
        entries = _extract_entries_from_structured_json(data)
        assert entries[0]["french"] == "مرحبا"
        assert entries[1]["french"] == "مع السلامة"


# ─── _load_source_data ────────────────────────────────────────────


class TestLoadSourceData:
    """Tests for _load_source_data() with mocked underlying loaders."""

    @patch("modes.mode_translate_dropdowns.load_dropdown_xlsx")
    def test_xlsx_format_calls_load_dropdown_xlsx(self, mock_load_xlsx):
        """XLSX format delegates to load_dropdown_xlsx."""
        mock_load_xlsx.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        entries = _load_source_data("source.xlsx", "xlsx")
        mock_load_xlsx.assert_called_once_with(Path("source.xlsx"))
        assert len(entries) == 1

    @patch("modes.mode_translate_dropdowns.load_dropdown_xlsx")
    def test_xlsx_format_returns_entries(self, mock_load_xlsx):
        """XLSX format returns the entries from load_dropdown_xlsx."""
        expected = [
            {"origin": "Button", "french": "Bouton", "context": "btn"},
            {"origin": "Cancel", "french": "Annuler", "context": "btn"},
        ]
        mock_load_xlsx.return_value = expected

        entries = _load_source_data(Path("/data/source.xlsx"), "xlsx")
        assert entries == expected

    @patch("modes.mode_translate_dropdowns._extract_entries_from_structured_json")
    @patch("modes.mode_translate_dropdowns.load_structured_json")
    def test_json_format_calls_load_structured_json(self, mock_load_json, mock_extract):
        """JSON format delegates to load_structured_json then _extract_entries_from_structured_json."""
        mock_load_json.return_value = {"contexts": {"btn": {"Button": "Bouton"}}}
        mock_extract.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        entries = _load_source_data("source.json", "json")
        mock_load_json.assert_called_once_with(Path("source.json"))
        mock_extract.assert_called_once_with(
            {"contexts": {"btn": {"Button": "Bouton"}}}
        )
        assert len(entries) == 1

    @patch("modes.mode_translate_dropdowns._extract_entries_from_structured_json")
    @patch("modes.mode_translate_dropdowns.load_structured_json")
    def test_json_format_returns_extracted_entries(self, mock_load_json, mock_extract):
        """JSON format returns entries from _extract_entries_from_structured_json."""
        mock_load_json.return_value = {"contexts": {"btn": {"Button": "Bouton"}}}
        mock_extract.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"},
            {"origin": "Cancel", "french": "Annuler", "context": "btn"},
        ]

        entries = _load_source_data("source.json", "json")
        assert len(entries) == 2

    def test_unsupported_format_raises_value_error(self):
        """An unsupported format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported input format"):
            _load_source_data("source.txt", "unknown")

    def test_csv_format_raises_value_error(self):
        """CSV format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported input format"):
            _load_source_data("data.csv", "csv")


# ─── _generate_json_output ─────────────────────────────────────────


class TestGenerateJsonOutput:
    """Tests for _generate_json_output()."""

    @patch("modes.mode_translate_dropdowns.save_structured_json")
    @patch("modes.mode_translate_dropdowns.create_dropdown_metadata")
    def test_en_language_uses_origin_column(
        self, mock_metadata, mock_save, sample_dropdown_entries
    ):
        """English language uses 'origin' column (source_col='origin')."""
        mock_metadata.return_value = {
            "language": "EN",
            "language_name": "Anglais",
            "total_entries": 4,
            "source_file": "test.xlsx",
            "generated_date": "2026-05-08",
        }

        _generate_json_output(
            sample_dropdown_entries, "en", Path("/out/dropdown_en.json"), "test.xlsx"
        )

        # Inspect the output_data passed to save_structured_json
        call_args = mock_save.call_args
        output_data = call_args[0][1]
        # For 'en', source_col is 'origin', so values should match origin
        assert output_data["contexts"]["btn"]["Button"] == "Button"
        assert output_data["contexts"]["btn"]["Cancel"] == "Cancel"
        assert output_data["contexts"]["menu"]["File"] == "File"
        assert output_data["contexts"]["menu"]["Open"] == "Open"

    @patch("modes.mode_translate_dropdowns.save_structured_json")
    @patch("modes.mode_translate_dropdowns.create_dropdown_metadata")
    def test_fr_language_uses_french_column(
        self, mock_metadata, mock_save, sample_dropdown_entries
    ):
        """French language uses 'french' column (source_col='french')."""
        mock_metadata.return_value = {
            "language": "FR",
            "language_name": "Français",
            "total_entries": 4,
            "source_file": "test.xlsx",
            "generated_date": "2026-05-08",
        }

        _generate_json_output(
            sample_dropdown_entries, "fr", Path("/out/dropdown_fr.json"), "test.xlsx"
        )

        call_args = mock_save.call_args
        output_data = call_args[0][1]
        # For 'fr', source_col is 'french', so values should match french translations
        assert output_data["contexts"]["btn"]["Button"] == "Bouton"
        assert output_data["contexts"]["btn"]["Cancel"] == "Annuler"
        assert output_data["contexts"]["menu"]["File"] == "Fichier"
        assert output_data["contexts"]["menu"]["Open"] == "Ouvrir"

    @patch("modes.mode_translate_dropdowns.save_structured_json")
    @patch("modes.mode_translate_dropdowns.create_dropdown_metadata")
    def test_creates_metadata_with_correct_params(
        self, mock_metadata, mock_save, sample_dropdown_entries
    ):
        """create_dropdown_metadata is called with correct parameters."""
        mock_metadata.return_value = {
            "language": "EN",
            "language_name": "Anglais",
            "total_entries": 4,
            "source_file": "test.xlsx",
            "generated_date": "2026-05-08",
        }

        _generate_json_output(
            sample_dropdown_entries, "en", Path("/out/dropdown_en.json"), "test.xlsx"
        )

        mock_metadata.assert_called_once_with(
            language_code="EN",
            language_name="Anglais",
            total_entries=4,
            source_file="test.xlsx",
        )

    @patch("modes.mode_translate_dropdowns.save_structured_json")
    @patch("modes.mode_translate_dropdowns.create_dropdown_metadata")
    def test_save_structured_json_called_with_path_and_data(
        self, mock_metadata, mock_save, sample_dropdown_entries
    ):
        """save_structured_json is called with the output path and data dict."""
        mock_metadata.return_value = {
            "language": "EN",
            "language_name": "Anglais",
            "total_entries": 4,
            "source_file": "test.xlsx",
            "generated_date": "2026-05-08",
        }

        output_path = Path("/out/dropdown_en.json")
        _generate_json_output(sample_dropdown_entries, "en", output_path, "test.xlsx")

        mock_save.assert_called_once()
        actual_path = mock_save.call_args[0][0]
        assert actual_path == output_path

    @patch("modes.mode_translate_dropdowns.save_structured_json")
    @patch("modes.mode_translate_dropdowns.create_dropdown_metadata")
    def test_contexts_preserve_origin_as_key(
        self, mock_metadata, mock_save, sample_dropdown_entries
    ):
        """In the contexts dict, origin text is always the key regardless of language."""
        mock_metadata.return_value = {
            "language": "FR",
            "language_name": "Français",
            "total_entries": 4,
            "source_file": "test.xlsx",
            "generated_date": "2026-05-08",
        }

        _generate_json_output(
            sample_dropdown_entries, "fr", Path("/out/dropdown_fr.json"), "test.xlsx"
        )

        output_data = mock_save.call_args[0][1]
        # Keys in contexts should always be the origin text
        for ctx_name, ctx_dict in output_data["contexts"].items():
            for key in ctx_dict:
                assert key in {"Button", "Cancel", "File", "Open"}

    @patch("modes.mode_translate_dropdowns.save_structured_json")
    @patch("modes.mode_translate_dropdowns.create_dropdown_metadata")
    def test_fallback_when_french_missing(self, mock_metadata, mock_save):
        """When an entry lacks 'french' key and source_col='french', falls back to origin."""
        mock_metadata.return_value = {
            "language": "FR",
            "language_name": "Français",
            "total_entries": 1,
            "source_file": "test.xlsx",
            "generated_date": "2026-05-08",
        }

        entries = [{"origin": "Button", "context": "btn"}]  # no 'french' key

        _generate_json_output(entries, "fr", Path("/out/dropdown_fr.json"), "test.xlsx")

        output_data = mock_save.call_args[0][1]
        # Falls back to origin when french is missing
        assert output_data["contexts"]["btn"]["Button"] == "Button"


# ─── _translate_dropdown_entries_batch ──────────────────────────────


class TestTranslateDropdownEntriesBatch:
    """Tests for _translate_dropdown_entries_batch()."""

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_translates_all_new_entries(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """All entries not in existing_translations are translated."""
        mock_translate_batch.return_value = ["Taste", "Abbrechen", "Datei", "Öffnen"]

        _translate_dropdown_entries_batch(sample_dropdown_entries, "de", {})

        assert mock_translate_batch.call_count == 1
        items_arg = mock_translate_batch.call_args[1]["items"]
        assert len(items_arg) == 4

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_returns_existing_when_all_translated(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """When all entries already exist, no API call is made."""
        existing = {
            "Button": "Taste",
            "Cancel": "Abbrechen",
            "File": "Datei",
            "Open": "Öffnen",
        }

        result = _translate_dropdown_entries_batch(
            sample_dropdown_entries, "de", existing
        )

        mock_translate_batch.assert_not_called()
        assert result == existing

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_resume_translates_only_missing(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """Only entries not in existing_translations are sent to translate_batch."""
        existing = {
            "Button": "Taste",
            "Cancel": "Abbrechen",
        }
        mock_translate_batch.return_value = ["Datei", "Öffnen"]

        _translate_dropdown_entries_batch(sample_dropdown_entries, "de", existing)

        items_arg = mock_translate_batch.call_args[1]["items"]
        assert items_arg == ["File", "Open"]

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_merges_new_translations_with_existing(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """New translations are merged into existing translations."""
        existing = {"Button": "Taste"}
        mock_translate_batch.return_value = ["Abbrechen", "Datei", "Öffnen"]

        result = _translate_dropdown_entries_batch(
            sample_dropdown_entries, "de", existing
        )

        assert result["Button"] == "Taste"  # existing preserved
        assert result["Cancel"] == "Abbrechen"  # newly translated
        assert result["File"] == "Datei"
        assert result["Open"] == "Öffnen"
        assert len(result) == 4

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_passes_rate_limit_to_translate_batch(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """RATE_LIMIT_SECONDS is passed to translate_batch."""
        mock_translate_batch.return_value = ["Taste"]

        single_entry = [sample_dropdown_entries[0]]
        _translate_dropdown_entries_batch(single_entry, "de", {})

        assert (
            mock_translate_batch.call_args[1]["rate_limit_seconds"]
            == RATE_LIMIT_SECONDS
        )

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_passes_correct_language_codes(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """Correct source and target language codes are passed to translate_batch."""
        mock_translate_batch.return_value = ["Tlačítko"]

        single_entry = [sample_dropdown_entries[0]]
        _translate_dropdown_entries_batch(single_entry, "cz", {})

        assert mock_translate_batch.call_args[1]["source_lang"] == "en"
        assert mock_translate_batch.call_args[1]["target_lang"] == "cs"

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_empty_entries_returns_existing(self, mock_translate_batch):
        """With an empty entries list, existing translations are returned unchanged."""
        existing = {"Hello": "Bonjour"}

        result = _translate_dropdown_entries_batch([], "de", existing)

        mock_translate_batch.assert_not_called()
        assert result == existing

    @patch("modes.mode_translate_dropdowns.translate_batch")
    def test_checkpoint_callback_is_provided(
        self, mock_translate_batch, sample_dropdown_entries
    ):
        """A checkpoint callback is passed to translate_batch."""
        mock_translate_batch.return_value = ["Taste", "Abbrechen", "Datei", "Öffnen"]

        _translate_dropdown_entries_batch(sample_dropdown_entries, "de", {})

        assert mock_translate_batch.call_args[1]["checkpoint_callback"] is not None
        assert mock_translate_batch.call_args[1]["checkpoint_every"] == 100


# ─── _build_contexts_from_translations ──────────────────────────────


class TestBuildContextsFromTranslations:
    """Tests for _build_contexts_from_translations()."""

    def test_builds_two_contexts(self, sample_dropdown_entries):
        """Contexts dict is built with correct context names from entries."""
        translations = {
            "Button": "Taste",
            "Cancel": "Abbrechen",
            "File": "Datei",
            "Open": "Öffnen",
        }

        contexts = _build_contexts_from_translations(
            sample_dropdown_entries, translations
        )
        assert "btn" in contexts
        assert "menu" in contexts

    def test_maps_origin_to_translation(self, sample_dropdown_entries):
        """Each origin text maps to its translation in the correct context."""
        translations = {
            "Button": "Taste",
            "Cancel": "Abbrechen",
            "File": "Datei",
            "Open": "Öffnen",
        }

        contexts = _build_contexts_from_translations(
            sample_dropdown_entries, translations
        )
        assert contexts["btn"]["Button"] == "Taste"
        assert contexts["btn"]["Cancel"] == "Abbrechen"
        assert contexts["menu"]["File"] == "Datei"
        assert contexts["menu"]["Open"] == "Öffnen"

    def test_falls_back_to_origin_when_translation_missing(
        self, sample_dropdown_entries
    ):
        """When a translation is missing, origin text is used as fallback."""
        translations = {"Button": "Taste"}  # missing Cancel, File, Open

        contexts = _build_contexts_from_translations(
            sample_dropdown_entries, translations
        )
        assert contexts["btn"]["Cancel"] == "Cancel"  # falls back to origin
        assert contexts["menu"]["File"] == "File"
        assert contexts["menu"]["Open"] == "Open"

    def test_empty_entries_returns_empty_dict(self):
        """With no entries, returns an empty dict."""
        contexts = _build_contexts_from_translations([], {})
        assert contexts == {}

    def test_empty_translations_falls_back_to_origin(self, sample_dropdown_entries):
        """With no translations, all values fall back to origin text."""
        contexts = _build_contexts_from_translations(sample_dropdown_entries, {})
        assert contexts["btn"]["Button"] == "Button"
        assert contexts["menu"]["File"] == "File"

    def test_preserves_unicode_translations(self):
        """Unicode characters in translations are preserved."""
        entries = [
            {"origin": "Hello", "french": "Bonjour", "context": "greetings"},
        ]
        translations = {"Hello": "مرحبا"}

        contexts = _build_contexts_from_translations(entries, translations)
        assert contexts["greetings"]["Hello"] == "مرحبا"

    def test_single_context_single_entry(self):
        """A single entry in a single context works correctly."""
        entries = [{"origin": "Save", "french": "Enregistrer", "context": "ui"}]
        translations = {"Save": "Uložit"}

        contexts = _build_contexts_from_translations(entries, translations)
        assert contexts == {"ui": {"Save": "Uložit"}}


# ─── _get_source_file ─────────────────────────────────────────────


class TestGetSourceFile:
    """Tests for _get_source_file()."""

    @patch("modes.mode_translate_dropdowns.get_config")
    def test_config_source_file_returns_path_and_format(self, mock_get_config):
        """When config.SOURCE_FILE is set, returns it with detected format."""
        mock_config = MagicMock()
        mock_config.SOURCE_FILE = "/data/source.xlsx"
        mock_get_config.return_value = mock_config

        file_path, input_format = _get_source_file()
        assert file_path == "/data/source.xlsx"
        assert input_format == "xlsx"

    @patch("modes.mode_translate_dropdowns.get_config")
    def test_config_source_file_json_format(self, mock_get_config):
        """When config.SOURCE_FILE is a JSON file, format is 'json'."""
        mock_config = MagicMock()
        mock_config.SOURCE_FILE = "/data/source.json"
        mock_get_config.return_value = mock_config

        file_path, input_format = _get_source_file()
        assert file_path == "/data/source.json"
        assert input_format == "json"

    @patch("modes.mode_translate_dropdowns.get_config")
    def test_default_xlsx_when_no_source_file(self, mock_get_config, temp_source_dir):
        """When no SOURCE_FILE, uses default Dropdown_a_traduire.xlsx if it exists."""
        default_file = temp_source_dir / "Dropdown_a_traduire.xlsx"
        default_file.write_text("fake xlsx", encoding="utf-8")

        mock_config = MagicMock()
        mock_config.SOURCE_FILE = ""
        mock_config.EXCEL_DIR = str(temp_source_dir)
        mock_get_config.return_value = mock_config

        file_path, input_format = _get_source_file()
        assert "Dropdown_a_traduire.xlsx" in file_path
        assert input_format == "xlsx"

    @patch("modes.mode_translate_dropdowns.get_config")
    def test_raises_when_default_not_found(self, mock_get_config, temp_source_dir):
        """FileNotFoundError is raised when default source file does not exist."""
        mock_config = MagicMock()
        mock_config.SOURCE_FILE = ""
        mock_config.EXCEL_DIR = str(temp_source_dir)
        mock_get_config.return_value = mock_config

        with pytest.raises(FileNotFoundError, match="Default source file not found"):
            _get_source_file()

    @patch("modes.mode_translate_dropdowns.get_config")
    def test_default_file_format_detected(self, mock_get_config, temp_source_dir):
        """The format of the default file is detected from its extension."""
        default_file = temp_source_dir / "Dropdown_a_traduire.xlsx"
        default_file.write_text("fake xlsx", encoding="utf-8")

        mock_config = MagicMock()
        mock_config.SOURCE_FILE = ""
        mock_config.EXCEL_DIR = str(temp_source_dir)
        mock_get_config.return_value = mock_config

        file_path, input_format = _get_source_file()
        assert input_format == "xlsx"


# ─── run ───────────────────────────────────────────────────────────


class TestRun:
    """Tests for the run() main entry point with mocked dependencies."""

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_json_output_format_calls_generate_all_json(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json
    ):
        """When OUTPUT_FORMAT is 'json', _generate_all_json is called."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en", "fr"]
        mock_config.OUTPUT_FORMAT = "json"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.xlsx", "xlsx")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        mock_gen_json.assert_called_once()

    @patch("modes.mode_translate_dropdowns._generate_all_xlsx")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_xlsx_output_format_calls_generate_all_xlsx(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_xlsx
    ):
        """When OUTPUT_FORMAT is 'xlsx', _generate_all_xlsx is called."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en", "fr"]
        mock_config.OUTPUT_FORMAT = "xlsx"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.xlsx", "xlsx")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        mock_gen_xlsx.assert_called_once()

    @patch("modes.mode_translate_dropdowns._generate_all_xlsx")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_auto_format_xlsx_source_uses_xlsx_output(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_xlsx
    ):
        """When OUTPUT_FORMAT is 'auto' and source is xlsx, xlsx output is used (auto matches input)."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "auto"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.xlsx", "xlsx")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        mock_gen_xlsx.assert_called_once()

    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_source_file_not_found_exits_gracefully(
        self, mock_get_config, mock_get_source, mock_load
    ):
        """When _get_source_file raises FileNotFoundError, run() returns without error."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "json"
        mock_get_config.return_value = mock_config

        mock_get_source.side_effect = FileNotFoundError("Default source file not found")

        # Should not raise
        run()
        mock_load.assert_not_called()

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_load_failure_exits_gracefully(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json
    ):
        """When _load_source_data raises an exception, run() returns without error."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "json"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.xlsx", "xlsx")
        mock_load.side_effect = ValueError("Unsupported format")

        # Should not raise
        run()
        mock_gen_json.assert_not_called()

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_creates_date_based_output_dir(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json, temp_dir
    ):
        """Output directory includes date-based subfolder."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = str(temp_dir)
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "json"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.xlsx", "xlsx")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        # Verify a _Dropdown subdirectory was created inside temp_dir
        subdirs = [d.name for d in temp_dir.iterdir() if d.is_dir()]
        assert any("_Dropdown" in name for name in subdirs)

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_passes_entries_to_generate_all_json(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json
    ):
        """run() passes the loaded entries and source file name to _generate_all_json."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en", "fr"]
        mock_config.OUTPUT_FORMAT = "json"
        mock_get_config.return_value = mock_config

        entries = [
            {"origin": "Button", "french": "Bouton", "context": "btn"},
            {"origin": "File", "french": "Fichier", "context": "menu"},
        ]
        mock_get_source.return_value = ("/data/source.xlsx", "xlsx")
        mock_load.return_value = entries

        run()

        call_args = mock_gen_json.call_args
        assert call_args[0][0] == entries  # entries
        assert call_args[0][1] == ["en", "fr"]  # target_langs
        assert call_args[0][2] == "source.xlsx"  # source_file name

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_unsupported_output_format_returns_early(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json
    ):
        """An unsupported output format (e.g. 'csv') does not call any generator."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "csv"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.xlsx", "xlsx")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        mock_gen_json.assert_not_called()

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_auto_format_json_source_uses_json_output(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json
    ):
        """When OUTPUT_FORMAT is 'auto' and source is json, json output is used."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "auto"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.json", "json")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        mock_gen_json.assert_called_once()

    @patch("modes.mode_translate_dropdowns._generate_all_json")
    @patch("modes.mode_translate_dropdowns._load_source_data")
    @patch("modes.mode_translate_dropdowns._get_source_file")
    @patch("modes.mode_translate_dropdowns.get_config")
    def test_auto_format_unknown_source_uses_json_output(
        self, mock_get_config, mock_get_source, mock_load, mock_gen_json
    ):
        """When OUTPUT_FORMAT is 'auto' and source format is unknown, defaults to json."""
        mock_config = MagicMock()
        mock_config.OUTPUT_DIR = "/tmp/output"
        mock_config.batch_langs_list = ["en"]
        mock_config.OUTPUT_FORMAT = "auto"
        mock_get_config.return_value = mock_config

        mock_get_source.return_value = ("source.dat", "unknown")
        mock_load.return_value = [
            {"origin": "Button", "french": "Bouton", "context": "btn"}
        ]

        run()

        mock_gen_json.assert_called_once()


# ─── _translate_dropdown_entry (via _translate_dropdown_entries_batch path) ──


class TestRateLimitSeconds:
    """Tests for the RATE_LIMIT_SECONDS constant."""

    def test_rate_limit_value(self):
        """RATE_LIMIT_SECONDS should be 0.15."""
        assert RATE_LIMIT_SECONDS == 0.15


# ─── Integration-style tests with multiple mocks ──────────────────


class TestGenerateJsonOutputIntegration:
    """Integration-style tests for _generate_json_output with real file I/O."""

    def test_en_language_writes_valid_json_file(
        self, temp_dir, sample_dropdown_entries
    ):
        """_generate_json_output for 'en' writes a valid JSON file to disk."""
        from core.io_json import load_structured_json

        output_path = temp_dir / "dropdown_en.json"

        _generate_json_output(sample_dropdown_entries, "en", output_path, "test.xlsx")

        assert output_path.exists()
        data = load_structured_json(output_path)
        assert "metadata" in data
        assert "contexts" in data
        assert data["contexts"]["btn"]["Button"] == "Button"

    def test_fr_language_writes_valid_json_file(
        self, temp_dir, sample_dropdown_entries
    ):
        """_generate_json_output for 'fr' writes a valid JSON file with French values."""
        from core.io_json import load_structured_json

        output_path = temp_dir / "dropdown_fr.json"

        _generate_json_output(sample_dropdown_entries, "fr", output_path, "test.xlsx")

        data = load_structured_json(output_path)
        assert data["contexts"]["btn"]["Button"] == "Bouton"
        assert data["contexts"]["menu"]["File"] == "Fichier"

    def test_de_language_writes_valid_json_file(
        self, temp_dir, sample_dropdown_entries
    ):
        """_generate_json_output for 'de' (source_col=origin) writes origin values."""
        from core.io_json import load_structured_json

        output_path = temp_dir / "dropdown_de.json"

        _generate_json_output(sample_dropdown_entries, "de", output_path, "test.xlsx")

        data = load_structured_json(output_path)
        # For 'de', source_col is 'origin', so values match origin
        assert data["contexts"]["btn"]["Button"] == "Button"
        assert data["contexts"]["menu"]["File"] == "File"
