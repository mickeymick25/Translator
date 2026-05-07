"""
Tests for modes/mode_translate_json.py — Translation of a flat JSON file.

Covers:
- _create_checkpoint_callback(): checkpoint saves correct partial data
- _translate_single_language(): translate entries, resume, return tuple
- run(): single lang, batch mode, fallback to TARGET_LANG
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from modes.mode_translate_json import (
    _create_checkpoint_callback,
    _translate_single_language,
    run,
)

# ─── _create_checkpoint_callback ──────────────────────────────────


class TestCreateCheckpointCallback:
    """Tests for _create_checkpoint_callback()."""

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_saves_partial_data(self, mock_save):
        """Checkpoint callback saves a dict with completed keys only."""
        keys = ["key_a", "key_b", "key_c"]
        results = ["trans_a", "trans_b", "trans_c"]
        output_path = Path("/tmp/test_checkpoint.json")

        cb = _create_checkpoint_callback(output_path, keys)
        cb(completed=2, results=results)

        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data == {"key_a": "trans_a", "key_b": "trans_b"}

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_saves_all_on_full_completion(self, mock_save):
        """Checkpoint callback with completed=total saves all entries."""
        keys = ["k1", "k2"]
        results = ["v1", "v2"]
        output_path = Path("/tmp/test_full.json")

        cb = _create_checkpoint_callback(output_path, keys)
        cb(completed=2, results=results)

        saved_data = mock_save.call_args[0][1]
        assert saved_data == {"k1": "v1", "k2": "v2"}

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_passes_correct_output_path(self, mock_save):
        """Checkpoint callback passes the output path to save_flat_json."""
        keys = ["k1"]
        results = ["v1"]
        output_path = Path("/custom/path/checkpoint.json")

        cb = _create_checkpoint_callback(output_path, keys)
        cb(completed=1, results=results)

        assert mock_save.call_args[0][0] == output_path

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_with_empty_results(self, mock_save):
        """Checkpoint callback with empty results list does not crash."""
        keys = []
        results = []
        output_path = Path("/tmp/empty.json")

        cb = _create_checkpoint_callback(output_path, keys)
        cb(completed=0, results=results)

        saved_data = mock_save.call_args[0][1]
        assert saved_data == {}


# ─── _translate_single_language ────────────────────────────────────


class TestTranslateSingleLanguage:
    """Tests for _translate_single_language()."""

    @patch("modes.mode_translate_json.save_flat_json")
    @patch("modes.mode_translate_json.translate_batch")
    @patch("modes.mode_translate_json.load_flat_json")
    def test_translates_and_saves(self, mock_load, mock_batch, mock_save, tmp_path):
        """Translates all entries and saves the result."""
        mock_load.return_value = {"k1": "Hello", "k2": "World"}
        mock_batch.return_value = ["Bonjour", "Monde"]

        lang, success, count = _translate_single_language(
            "source.json", {"k1": "Hello", "k2": "World"}, "en", "fr", tmp_path
        )

        assert lang == "fr"
        assert success is True
        assert count == 2
        mock_batch.assert_called_once()
        mock_save.assert_called_once()

    @patch("modes.mode_translate_json.save_flat_json")
    @patch("modes.mode_translate_json.translate_batch")
    @patch("modes.mode_translate_json.load_flat_json")
    def test_skips_already_translated_keys(
        self, mock_load, mock_batch, mock_save, tmp_path
    ):
        """When output exists, already translated keys are skipped."""
        mock_load.return_value = {"k1": "Bonjour"}  # existing translation
        mock_batch.return_value = ["Monde"]

        # Create a fake existing output file in tmp_path
        output_path = tmp_path / "translation_en_fr.json"
        output_path.write_text('{"k1": "Bonjour"}', encoding="utf-8")

        source_data = {"k1": "Hello", "k2": "World"}
        lang, success, count = _translate_single_language(
            "source.json", source_data, "en", "fr", tmp_path
        )

        assert count == 1  # Only k2 needed translation
        # translate_batch should be called with only "World"
        call_args = mock_batch.call_args
        assert call_args[1]["items"] == ["World"]

    @patch("modes.mode_translate_json.save_flat_json")
    @patch("modes.mode_translate_json.translate_batch")
    @patch("modes.mode_translate_json.load_flat_json")
    def test_all_keys_already_translated(
        self, mock_load, mock_batch, mock_save, tmp_path
    ):
        """When all keys already translated, returns 0 entries."""
        mock_load.return_value = {"k1": "Bonjour", "k2": "Monde"}

        output_path = tmp_path / "translation_en_fr.json"
        output_path.write_text('{"k1": "Bonjour", "k2": "Monde"}', encoding="utf-8")

        source_data = {"k1": "Hello", "k2": "World"}
        lang, success, count = _translate_single_language(
            "source.json", source_data, "en", "fr", tmp_path
        )

        assert success is True
        assert count == 0
        mock_batch.assert_not_called()

    @patch("modes.mode_translate_json.save_flat_json")
    @patch("modes.mode_translate_json.translate_batch")
    @patch("modes.mode_translate_json.load_flat_json")
    def test_uses_correct_api_target_for_czech(
        self, mock_load, mock_batch, mock_save, tmp_path
    ):
        """Czech 'cz' uses 'cs' as the API target language code."""
        mock_batch.return_value = ["Dům"]

        _translate_single_language("source.json", {"k1": "Home"}, "en", "cz", tmp_path)

        call_args = mock_batch.call_args
        assert call_args[1]["target_lang"] == "cs"

    @patch("modes.mode_translate_json.save_flat_json")
    @patch("modes.mode_translate_json.translate_batch")
    @patch("modes.mode_translate_json.load_flat_json")
    def test_output_file_naming(self, mock_load, mock_batch, mock_save, tmp_path):
        """Output file is named translation_{source}_{target}.json."""
        mock_batch.return_value = ["Hallo"]

        _translate_single_language("source.json", {"k1": "Hello"}, "en", "de", tmp_path)

        saved_path = mock_save.call_args[0][0]
        assert saved_path.name == "translation_en_de.json"

    @patch("modes.mode_translate_json.save_flat_json")
    @patch("modes.mode_translate_json.translate_batch")
    @patch("modes.mode_translate_json.load_flat_json")
    def test_merges_new_and_existing_translations(
        self, mock_load, mock_batch, mock_save, tmp_path
    ):
        """New translations are merged with existing ones on final save."""
        mock_load.return_value = {"k1": "Bonjour"}
        mock_batch.return_value = ["Monde"]

        output_path = tmp_path / "translation_en_fr.json"
        output_path.write_text('{"k1": "Bonjour"}', encoding="utf-8")

        source_data = {"k1": "Hello", "k2": "World"}
        _translate_single_language("source.json", source_data, "en", "fr", tmp_path)

        saved_data = mock_save.call_args[0][1]
        assert "k1" in saved_data
        assert "k2" in saved_data


# ─── run ────────────────────────────────────────────────────────────


class TestRun:
    """Tests for run() — the main entry point of translate-json mode."""

    @patch("modes.mode_translate_json._translate_single_language")
    @patch("modes.mode_translate_json.load_flat_json")
    @patch("modes.mode_translate_json.get_config")
    def test_single_language_mode(self, mock_get_config, mock_load, mock_translate):
        """With a single batch lang, _translate_single_language is called once."""
        config = MagicMock()
        config.batch_langs_list = ["fr"]
        config.SOURCE_LANG = "en"
        config.OUTPUT_DIR = "/tmp/output_single"
        config.get_source_path.return_value = "/tmp/source.json"
        mock_get_config.return_value = config
        mock_load.return_value = {"k1": "Hello"}
        mock_translate.return_value = ("fr", True, 1)

        run()

        mock_translate.assert_called_once()
        args = mock_translate.call_args[0]
        assert args[2] == "en"  # source_lang
        assert args[3] == "fr"  # target_lang

    @patch("modes.mode_translate_json._translate_single_language")
    @patch("modes.mode_translate_json.load_flat_json")
    @patch("modes.mode_translate_json.get_config")
    def test_batch_mode_multiple_languages(
        self, mock_get_config, mock_load, mock_translate
    ):
        """With multiple batch langs, _translate_single_language is called for each."""
        config = MagicMock()
        config.batch_langs_list = ["fr", "de", "cz"]
        config.SOURCE_LANG = "en"
        config.OUTPUT_DIR = "/tmp/output_batch"
        config.get_source_path.return_value = "/tmp/source.json"
        mock_get_config.return_value = config
        mock_load.return_value = {"k1": "Hello"}
        mock_translate.return_value = ("lang", True, 1)

        run()

        # Called for fr, de, cz (3 langs, excluding source 'en')
        assert mock_translate.call_count == 3

    @patch("modes.mode_translate_json._translate_single_language")
    @patch("modes.mode_translate_json.load_flat_json")
    @patch("modes.mode_translate_json.get_config")
    def test_batch_mode_skips_source_lang(
        self, mock_get_config, mock_load, mock_translate
    ):
        """Source language is skipped in batch mode (can't translate to itself)."""
        config = MagicMock()
        config.batch_langs_list = ["en", "fr", "de"]
        config.SOURCE_LANG = "en"
        config.OUTPUT_DIR = "/tmp/output_skip"
        config.get_source_path.return_value = "/tmp/source.json"
        mock_get_config.return_value = config
        mock_load.return_value = {"k1": "Hello"}
        mock_translate.return_value = ("lang", True, 1)

        run()

        # Called for fr, de only (en skipped)
        assert mock_translate.call_count == 2
        called_langs = [call_args[0][3] for call_args in mock_translate.call_args_list]
        assert "en" not in called_langs

    @patch("modes.mode_translate_json._translate_single_language")
    @patch("modes.mode_translate_json.load_flat_json")
    @patch("modes.mode_translate_json.get_config")
    def test_fallback_to_target_lang(self, mock_get_config, mock_load, mock_translate):
        """When batch_langs is empty, falls back to TARGET_LANG."""
        config = MagicMock()
        config.batch_langs_list = []
        config.SOURCE_LANG = "en"
        config.TARGET_LANG = "sk"
        config.OUTPUT_DIR = "/tmp/output_fallback"
        config.get_source_path.return_value = "/tmp/source.json"
        mock_get_config.return_value = config
        mock_load.return_value = {"k1": "Hello"}
        mock_translate.return_value = ("sk", True, 1)

        run()

        mock_translate.assert_called_once()
        assert mock_translate.call_args[0][3] == "sk"

    @patch("modes.mode_translate_json._translate_single_language")
    @patch("modes.mode_translate_json.load_flat_json")
    @patch("modes.mode_translate_json.get_config")
    def test_creates_date_based_output_folder(
        self, mock_get_config, mock_load, mock_translate
    ):
        """run() passes a date-based output dir ({YYYY_MM_DD}_Export) to _translate_single_language."""
        config = MagicMock()
        config.batch_langs_list = ["fr"]
        config.SOURCE_LANG = "en"
        config.OUTPUT_DIR = "/tmp/output_date_folder"
        config.get_source_path.return_value = "/tmp/source.json"
        mock_get_config.return_value = config
        mock_load.return_value = {"k1": "Hello"}
        mock_translate.return_value = ("fr", True, 1)

        run()

        mock_translate.assert_called_once()
        # The 5th argument (index 4) to _translate_single_language is output_dir
        output_dir = mock_translate.call_args[0][4]
        # output_dir should be a Path ending in {YYYY_MM_DD}_Export
        output_dir_str = str(output_dir)
        assert "_Export" in output_dir_str
        assert "/tmp/output_date_folder" in output_dir_str

    @patch("modes.mode_translate_json._translate_single_language")
    @patch("modes.mode_translate_json.load_flat_json")
    @patch("modes.mode_translate_json.get_config")
    def test_loads_source_data_once(self, mock_get_config, mock_load, mock_translate):
        """Source data is loaded once, not per language."""
        config = MagicMock()
        config.batch_langs_list = ["fr", "de"]
        config.SOURCE_LANG = "en"
        config.OUTPUT_DIR = "/tmp/output_load_once"
        config.get_source_path.return_value = "/tmp/source.json"
        mock_get_config.return_value = config
        mock_load.return_value = {"k1": "Hello"}
        mock_translate.return_value = ("lang", True, 1)

        run()

        # load_flat_json called only once
        assert mock_load.call_count == 1
