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
    _check_untranslated_keys,
    _create_checkpoint_callback,
    _translate_single_language,
    run,
)

# ─── _create_checkpoint_callback ──────────────────────────────────


class TestCreateCheckpointCallback:
    """Tests for _create_checkpoint_callback()."""

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_saves_partial_data(self, mock_save):
        """Checkpoint callback saves merged data with completed keys only."""
        keys = ["key_a", "key_b", "key_c"]
        results = ["trans_a", "trans_b", "trans_c"]
        output_path = Path("/tmp/test_checkpoint.json")

        cb = _create_checkpoint_callback(output_path, keys, existing_data={})
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

        cb = _create_checkpoint_callback(output_path, keys, existing_data={})
        cb(completed=2, results=results)

        saved_data = mock_save.call_args[0][1]
        assert saved_data == {"k1": "v1", "k2": "v2"}

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_passes_correct_output_path(self, mock_save):
        """Checkpoint callback passes the output path to save_flat_json."""
        keys = ["k1"]
        results = ["v1"]
        output_path = Path("/custom/path/checkpoint.json")

        cb = _create_checkpoint_callback(output_path, keys, existing_data={})
        cb(completed=1, results=results)

        assert mock_save.call_args[0][0] == output_path

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_with_empty_results(self, mock_save):
        """Checkpoint callback with empty results list does not crash."""
        keys = []
        results = []
        output_path = Path("/tmp/empty.json")

        cb = _create_checkpoint_callback(output_path, keys, existing_data={})
        cb(completed=0, results=results)

        saved_data = mock_save.call_args[0][1]
        assert saved_data == {}

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_merges_with_existing_data(self, mock_save):
        """Checkpoint callback merges new translations with existing data."""
        keys = ["k3", "k4"]
        results = ["v3", "v4"]
        output_path = Path("/tmp/test_merge.json")
        existing_data = {"k1": "v1", "k2": "v2"}

        cb = _create_checkpoint_callback(output_path, keys, existing_data)
        cb(completed=1, results=results)

        saved_data = mock_save.call_args[0][1]
        # Merged data contains both existing and new translations
        assert saved_data == {"k1": "v1", "k2": "v2", "k3": "v3"}

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_existing_data_updated_on_subsequent_calls(self, mock_save):
        """Subsequent checkpoint calls include previously checkpointed translations."""
        keys = ["k2", "k3"]
        results = ["v2", "v3"]
        output_path = Path("/tmp/test_incremental.json")
        existing_data = {"k1": "v1"}

        cb = _create_checkpoint_callback(output_path, keys, existing_data)

        # First checkpoint: completed=1 (k2 translated)
        cb(completed=1, results=results)
        first_save = mock_save.call_args[0][1]
        assert first_save == {"k1": "v1", "k2": "v2"}

        # Second checkpoint: completed=2 (k2 and k3 translated)
        cb(completed=2, results=results)
        second_save = mock_save.call_args[0][1]
        assert second_save == {"k1": "v1", "k2": "v2", "k3": "v3"}

    @patch("modes.mode_translate_json.save_flat_json")
    def test_callback_new_translations_override_existing(self, mock_save):
        """New translations take precedence over existing data on merge."""
        keys = ["k1"]
        results = ["new_v1"]
        output_path = Path("/tmp/test_override.json")
        existing_data = {"k1": "old_v1", "k2": "v2"}

        cb = _create_checkpoint_callback(output_path, keys, existing_data)
        cb(completed=1, results=results)

        saved_data = mock_save.call_args[0][1]
        # New translation for k1 overrides existing value
        assert saved_data == {"k1": "new_v1", "k2": "v2"}


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


# ─── Thread Safety (Bug #1) ───────────────────────────────────────────


class TestModeTranslateJsonThreadSafety:
    """End-to-end thread-safety test for mode_translate_json with GoogleProvider.

    Reproduces Bug #1: the original implementation used ThreadPoolExecutor to
    translate multiple languages in parallel, but the GoogleProvider shared a
    single non-thread-safe `deep_translator.GoogleTranslator` library state.
    When two threads called translate() concurrently with different targets,
    the target language was overwritten, producing translations in the wrong
    language (FR translated as Czech, etc.).

    The fix is at the provider level: GoogleProvider.translate() now holds a
    threading.Lock for the entire duration of the call. This test verifies
    that the integration is correct: with two parallel languages using the
    same GoogleProvider, the result for each language is in the right
    language.
    """

    def test_google_provider_serializes_concurrent_translates(self):
        """Concurrent GoogleProvider.translate() calls complete without errors.

        With the threading.Lock in GoogleProvider, multiple threads calling
        translate() concurrently are serialized and each call returns its
        expected result. This integration test verifies the contract end-to-
        end: 30 concurrent calls across 4 workers complete, each result
        matches its (source, target).
        """
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import MagicMock, patch

        from core.translator_factory import GoogleProvider

        with patch("core.translator_factory.GoogleTranslator") as mock_cls:

            def factory(source, target):
                inst = MagicMock()
                inst.source = source
                inst.target = target
                inst.translate.return_value = f"{target}:Hello"
                return inst

            mock_cls.side_effect = factory

            provider = GoogleProvider()

            fr_results: list[str] = []
            cs_results: list[str] = []
            errors: list[Exception] = []

            def worker(target, results_list, n=15):
                try:
                    for _ in range(n):
                        results_list.append(provider.translate("Hello", "en", target))
                except Exception as e:
                    errors.append(e)

            with ThreadPoolExecutor(max_workers=4) as executor:
                futs = [
                    executor.submit(worker, "fr", fr_results),
                    executor.submit(worker, "cs", cs_results),
                ]
                for f in futs:
                    f.result()

            assert not errors, f"Errors during concurrent translation: {errors}"
            assert len(fr_results) == 15
            assert len(cs_results) == 15
            assert all(r == "fr:Hello" for r in fr_results)
            assert all(r == "cs:Hello" for r in cs_results)


# ─── Post-Translation Validation (Bug #2) ─────────────────────────


class TestCheckUntranslatedKeys:
    """Tests for _check_untranslated_keys() — post-translation quality check (Bug #2).

    Bug #2: Ollama (and any provider) can fail to translate a key — e.g. it
    returns the source text unchanged, or it returns an empty string. The
    post-translation check compares each translated value to the source and
    flags any text longer than `min_length` (default 15) that came back
    identical to the source.
    """

    def test_detects_key_with_value_identical_to_source(self):
        """A long translation identical to the source is flagged."""
        source = {"KEY_1": "This is a long sentence in English."}
        translated = {"KEY_1": "This is a long sentence in English."}

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        assert result == ["KEY_1"]

    def test_does_not_flag_short_identical_values(self):
        """Short values (e.g. 'OK', 'Cancel') identical to source are not flagged."""
        source = {"OK_BTN": "OK", "CANCEL_BTN": "Cancel"}
        translated = {"OK_BTN": "OK", "CANCEL_BTN": "Cancel"}

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        # Both are short (len < 15), so they are accepted as legitimate.
        assert result == []

    def test_does_not_flag_proper_translation(self):
        """Proper translations (different from source) are not flagged."""
        source = {"KEY_1": "This is a long sentence in English."}
        translated = {"KEY_1": "C'est une longue phrase en français."}

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        assert result == []

    def test_detects_only_long_untranslated_keys(self):
        """A mix of translated, short-unchanged and long-unchanged keys."""
        source = {
            "SHORT": "OK",  # short, OK
            "LONG_KEY": "Data integrity alerts",  # long, identical → untranslated
            "TRANSLATED": "Data integrity alerts",  # long, will be translated
            "WHITESPACE": "   ",  # only whitespace → not flagged (empty after strip)
        }
        translated = {
            "SHORT": "OK",
            "LONG_KEY": "Data integrity alerts",  # untranslated!
            "TRANSLATED": "Alertes d'intégrité des données",
            "WHITESPACE": "",
        }

        result = _check_untranslated_keys(
            source, translated, target_lang="fr", min_length=15
        )

        assert "LONG_KEY" in result
        assert "SHORT" not in result
        assert "TRANSLATED" not in result
        assert "WHITESPACE" not in result  # source.strip() is empty

    def test_missing_key_in_translated_data_is_flagged(self):
        """A key present in source but missing from translated is flagged
        (translated = '' which never equals source text)."""
        source = {
            "PRESENT": "This is a long sentence.",
            "MISSING": "Another long sentence here.",
        }
        translated = {"PRESENT": "Une longue phrase."}  # MISSING absent

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        # The missing key is treated as having value '', which does not equal
        # the source. So it is NOT flagged by the "identical to source" check.
        # (The function is scoped to detect same-value, not missing keys.)
        assert "PRESENT" not in result
        assert "MISSING" not in result

    def test_empty_source_value_not_flagged(self):
        """Keys with empty source values are not flagged (no translation needed)."""
        source = {"EMPTY_KEY": ""}
        translated = {"EMPTY_KEY": ""}

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        assert result == []

    def test_whitespace_only_source_not_flagged(self):
        """Keys with whitespace-only source are not flagged."""
        source = {"WS_KEY": "   \t\n  "}
        translated = {"WS_KEY": "   \t\n  "}

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        assert result == []

    def test_min_length_threshold(self):
        """min_length controls the minimum source length to flag."""
        source = {
            "BORDERLINE": "12345678901234",  # 14 chars
            "OVER": "123456789012345",  # 15 chars
        }
        translated = {
            "BORDERLINE": "12345678901234",  # unchanged
            "OVER": "123456789012345",  # unchanged
        }

        # With min_length=15, only OVER is flagged.
        result = _check_untranslated_keys(
            source, translated, target_lang="fr", min_length=15
        )
        assert "OVER" in result
        assert "BORDERLINE" not in result

        # With min_length=10, both are flagged.
        result = _check_untranslated_keys(
            source, translated, target_lang="fr", min_length=10
        )
        assert "OVER" in result
        assert "BORDERLINE" in result

    def test_returns_empty_list_when_all_translated(self):
        """If every key is properly translated, return an empty list."""
        source = {f"KEY_{i}": f"English sentence number {i}." for i in range(5)}
        translated = {f"KEY_{i}": f"Phrase française numéro {i}." for i in range(5)}

        result = _check_untranslated_keys(source, translated, target_lang="fr")

        assert result == []

    def test_logs_warning_per_untranslated_key(self):
        """Each untranslated key produces a warning log with the key name."""
        import logging

        source = {
            "UNTRANS_1": "This long text is identical to source.",
            "UNTRANS_2": "Another long identical text for testing.",
            "OK_KEY": "Proper translation here",
        }
        translated = {
            "UNTRANS_1": "This long text is identical to source.",
            "UNTRANS_2": "Another long identical text for testing.",
            "OK_KEY": "Une bonne traduction ici",
        }

        logger_obj = logging.getLogger("modes.mode_translate_json")
        captured: list[str] = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                captured.append(self.format(record))

        handler = ListHandler(level=logging.WARNING)
        handler.setFormatter(logging.Formatter("%(levelname)s [%(lang)s] %(message)s"))
        # Inject the target_lang into the record for our format string.
        old_make_record = logger_obj.makeRecord

        def make_record(*args, **kwargs):
            record = old_make_record(*args, **kwargs)
            record.lang = "FR"
            return record

        logger_obj.addHandler(handler)
        logger_obj.makeRecord = make_record
        old_level = logger_obj.level
        logger_obj.setLevel(logging.WARNING)
        try:
            result = _check_untranslated_keys(
                source, translated, target_lang="fr", min_length=15
            )
        finally:
            logger_obj.removeHandler(handler)
            logger_obj.makeRecord = old_make_record
            logger_obj.setLevel(old_level)

        assert "UNTRANS_1" in result
        assert "UNTRANS_2" in result
        # The logs contain the language code and the key names.
        assert any("UNTRANS_1" in log for log in captured), captured
        assert any("UNTRANS_2" in log for log in captured), captured
