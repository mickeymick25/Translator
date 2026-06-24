"""
Tests for core/config.py — Configuration module.

Covers:
- Config defaults and environment variable overrides
- _is_docker(): Docker environment detection
- _default_output_dir(), _default_source_dir(), _default_excel_dir(), _default_doc_dir():
  environment-aware default paths
- _find_latest_import_folder(): finding the most recent import folder
- _find_source_file_in_import(): finding the source file inside an import folder
- Config.get_source_path(): auto-detection, fallback, and error handling
- Config.batch_langs_list: parsing comma-separated languages
- Config.get_output_path(): generating output file paths
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from core.config import (
    LANGUAGES,
    MODE_ANALYZE,
    MODE_TRANSLATE_DROPDOWNS,
    MODE_TRANSLATE_JSON,
    Config,
    _default_cache_path,
    _default_dir,
    _default_doc_dir,
    _default_excel_dir,
    _default_output_dir,
    _default_rate_limiter_path,
    _default_source_dir,
    _find_latest_import_folder,
    _find_source_file_in_import,
    _is_docker,
    get_config,
)

# ─── Config defaults ───────────────────────────────────────────────


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_default_mode(self):
        """Default mode is translate-json."""
        config = Config()
        assert config.MODE == "translate-json"

    def test_default_source_lang(self):
        """Default source language is 'en'."""
        config = Config()
        assert config.SOURCE_LANG == "en"

    def test_default_target_lang(self):
        """Default target language is 'cs'."""
        config = Config()
        assert config.TARGET_LANG == "cs"

    def test_default_batch_langs(self):
        """Default batch languages include en,fr,cz,sk,de,it,ar."""
        config = Config()
        assert "en" in config.BATCH_LANGS
        assert "fr" in config.BATCH_LANGS
        assert "cz" in config.BATCH_LANGS

    def test_default_output_dir(self):
        """Default output directory depends on execution environment."""
        config = Config()
        if _is_docker():
            assert config.OUTPUT_DIR == "/app/output"
        else:
            assert config.OUTPUT_DIR == str(Path.cwd() / "output")

    def test_default_source_dir(self):
        """Default source directory depends on execution environment."""
        config = Config()
        if _is_docker():
            assert config.SOURCE_DIR == "/app/source"
        else:
            assert config.SOURCE_DIR == str(Path.cwd() / "source")


class TestConfigEnvOverrides:
    """Tests for Config environment variable overrides."""

    @patch.dict(os.environ, {"MODE": "analyze"})
    def test_mode_from_env(self):
        """MODE environment variable overrides the default."""
        config = Config()
        assert config.MODE == "analyze"

    @patch.dict(os.environ, {"SOURCE_LANG": "fr"})
    def test_source_lang_from_env(self):
        """SOURCE_LANG environment variable overrides the default."""
        config = Config()
        assert config.SOURCE_LANG == "fr"

    @patch.dict(os.environ, {"TARGET_LANG": "de"})
    def test_target_lang_from_env(self):
        """TARGET_LANG environment variable overrides the default."""
        config = Config()
        assert config.TARGET_LANG == "de"

    @patch.dict(os.environ, {"BATCH_LANGS": "en,fr,de"})
    def test_batch_langs_from_env(self):
        """BATCH_LANGS environment variable overrides the default."""
        config = Config()
        assert config.BATCH_LANGS == "en,fr,de"

    @patch.dict(os.environ, {"OUTPUT_DIR": "/custom/output"})
    def test_output_dir_from_env(self):
        """OUTPUT_DIR environment variable overrides the default."""
        config = Config()
        assert config.OUTPUT_DIR == "/custom/output"


class TestConfigBatchLangsList:
    """Tests for Config.batch_langs_list property."""

    @patch.dict(os.environ, {"BATCH_LANGS": "en,fr,cz,sk,de,it,ar"})
    def test_parses_comma_separated_list(self):
        """batch_langs_list parses comma-separated languages."""
        config = Config()
        assert config.batch_langs_list == ["en", "fr", "cz", "sk", "de", "it", "ar"]

    @patch.dict(os.environ, {"BATCH_LANGS": "en, fr , cz"})
    def test_strips_whitespace(self):
        """batch_langs_list strips whitespace around language codes."""
        config = Config()
        assert config.batch_langs_list == ["en", "fr", "cz"]

    @patch.dict(os.environ, {"BATCH_LANGS": "en"})
    def test_single_language(self):
        """A single language returns a list with one element."""
        config = Config()
        assert config.batch_langs_list == ["en"]

    @patch.dict(os.environ, {"BATCH_LANGS": "en,,fr"})
    def test_empty_entries_are_filtered(self):
        """Empty entries between commas are filtered out."""
        config = Config()
        assert config.batch_langs_list == ["en", "fr"]


class TestConfigGetOutputPath:
    """Tests for Config.get_output_path()."""

    @patch.dict(
        os.environ,
        {"OUTPUT_DIR": "/tmp/test_output", "SOURCE_LANG": "en", "TARGET_LANG": "fr"},
    )
    def test_generates_correct_filename(self):
        """get_output_path generates the correct filename pattern."""
        config = Config()
        path = config.get_output_path()
        assert path == "/tmp/test_output/translation_en_fr.json"

    @patch.dict(
        os.environ,
        {"OUTPUT_DIR": "/tmp/test_output", "SOURCE_LANG": "en", "TARGET_LANG": "fr"},
    )
    def test_generates_filename_with_suffix(self):
        """get_output_path with suffix includes it in the filename."""
        config = Config()
        path = config.get_output_path(suffix="_dropdown")
        assert path == "/tmp/test_output/translation_en_fr_dropdown.json"


# ─── _find_latest_import_folder ────────────────────────────────────


class TestFindLatestImportFolder:
    """Tests for _find_latest_import_folder()."""

    def test_finds_most_recent_folder(self, temp_dir):
        """Returns the most recent YYYY_MM_DD_Import folder."""
        (temp_dir / "2026_04_13_Import").mkdir()
        (temp_dir / "2026_04_21_Import").mkdir()
        (temp_dir / "2026_05_05_Import").mkdir()

        result = _find_latest_import_folder(str(temp_dir))
        assert result == "2026_05_05_Import"

    def test_returns_none_when_no_import_folders(self, temp_dir):
        """Returns None when no YYYY_MM_DD_Import folder exists."""
        (temp_dir / "other_folder").mkdir()

        result = _find_latest_import_folder(str(temp_dir))
        assert result is None

    def test_returns_none_when_dir_does_not_exist(self):
        """Returns None when the source directory does not exist."""
        result = _find_latest_import_folder("/nonexistent/path")
        assert result is None

    def test_ignores_non_import_folders(self, temp_dir):
        """Only considers folders matching YYYY_MM_DD_Import pattern."""
        (temp_dir / "old_data").mkdir()
        (temp_dir / "2026_05_05_Import").mkdir()
        (temp_dir / "backup_2026").mkdir()

        result = _find_latest_import_folder(str(temp_dir))
        assert result == "2026_05_05_Import"

    def test_ignores_files_not_directories(self, temp_dir):
        """Files matching the pattern name are ignored (only dirs count)."""
        (temp_dir / "2026_05_05_Import").mkdir()
        (temp_dir / "2026_05_06_Import.txt").write_text("not a dir")

        result = _find_latest_import_folder(str(temp_dir))
        assert result == "2026_05_05_Import"

    def test_single_import_folder(self, temp_dir):
        """Works correctly with a single import folder."""
        (temp_dir / "2026_04_13_Import").mkdir()

        result = _find_latest_import_folder(str(temp_dir))
        assert result == "2026_04_13_Import"


# ─── _find_source_file_in_import ────────────────────────────────────


class TestFindSourceFileInImport:
    """Tests for _find_source_file_in_import()."""

    def test_finds_source_file(self, temp_dir):
        """Finds the source file matching the pattern YYYY_MM_DD_translation_{lang}_{lang}.json."""
        import_dir = temp_dir / "2026_05_05_Import"
        import_dir.mkdir()
        (import_dir / "2026_05_05_translation_en_en.json").write_text(
            '{"key": "value"}', encoding="utf-8"
        )

        result = _find_source_file_in_import(str(import_dir), "en")
        assert result is not None
        assert result.endswith("2026_05_05_translation_en_en.json")

    def test_returns_none_when_file_not_found(self, temp_dir):
        """Returns None when the expected source file does not exist."""
        import_dir = temp_dir / "2026_05_05_Import"
        import_dir.mkdir()
        (import_dir / "other_file.json").write_text("{}", encoding="utf-8")

        result = _find_source_file_in_import(str(import_dir), "en")
        assert result is None

    def test_returns_none_when_dir_does_not_exist(self):
        """Returns None when the import directory does not exist."""
        result = _find_source_file_in_import("/nonexistent/path", "en")
        assert result is None

    def test_finds_french_source_file(self, temp_dir):
        """Finds the source file for a different source language."""
        import_dir = temp_dir / "2026_04_21_Import"
        import_dir.mkdir()
        (import_dir / "2026_04_21_translation_fr_fr.json").write_text(
            '{"cle": "valeur"}', encoding="utf-8"
        )

        result = _find_source_file_in_import(str(import_dir), "fr")
        assert result is not None
        assert result.endswith("2026_04_21_translation_fr_fr.json")

    def test_relaxed_fallback_finds_json_with_lang_in_name(self, temp_dir):
        """When the conventional name is absent, falls back to any *.json whose
        stem contains the source language (e.g. 'en8.json')."""
        import_dir = temp_dir / "2026_06_23_Import"
        import_dir.mkdir()
        (import_dir / "en8.json").write_text('{"k": "v"}', encoding="utf-8")

        result = _find_source_file_in_import(str(import_dir), "en")
        assert result is not None
        assert result.endswith("en8.json")

    def test_relaxed_fallback_prefers_largest_lang_match(self, temp_dir):
        """When several *.json mention the source language, the largest wins."""
        import_dir = temp_dir / "2026_06_23_Import"
        import_dir.mkdir()
        (import_dir / "en_small.json").write_text('{"k": "v"}', encoding="utf-8")
        (import_dir / "en_big.json").write_text(
            '{"k": "' + "x" * 200 + '"}', encoding="utf-8"
        )

        result = _find_source_file_in_import(str(import_dir), "en")
        assert result is not None
        assert result.endswith("en_big.json")

    def test_relaxed_fallback_none_when_no_lang_match(self, temp_dir):
        """Returns None when no *.json mentions the source language (conservative)."""
        import_dir = temp_dir / "2026_06_23_Import"
        import_dir.mkdir()
        (import_dir / "metadata.json").write_text("{}", encoding="utf-8")

        result = _find_source_file_in_import(str(import_dir), "en")
        assert result is None


# ─── Config.get_source_path ────────────────────────────────────────


class TestConfigGetSourcePath:
    """Tests for Config.get_source_path() — auto-detection and fallback."""

    @patch.dict(os.environ, {"SOURCE_FILE": "/explicit/path/file.json"}, clear=False)
    def test_explicit_source_file_takes_priority(self):
        """When SOURCE_FILE is set, it is returned directly."""
        config = Config()
        # Reset to pick up env var
        config.SOURCE_FILE = "/explicit/path/file.json"
        result = config.get_source_path()
        assert result == "/explicit/path/file.json"

    def test_auto_detects_latest_import(self, temp_dir):
        """When no SOURCE_FILE, auto-detects the latest import folder."""
        import_dir = temp_dir / "2026_05_05_Import"
        import_dir.mkdir()
        source_file = import_dir / "2026_05_05_translation_en_en.json"
        source_file.write_text('{"key": "value"}', encoding="utf-8")

        config = Config()
        config.SOURCE_DIR = str(temp_dir)
        config.SOURCE_FILE = ""

        result = config.get_source_path()
        assert "2026_05_05_Import" in result
        assert result.endswith("2026_05_05_translation_en_en.json")

    def test_fallback_to_flat_path(self, temp_dir):
        """When no import folder found, falls back to flat path in SOURCE_DIR."""
        source_dir = temp_dir
        fallback_file = source_dir / "translation_en_en.json"
        fallback_file.write_text('{"key": "value"}', encoding="utf-8")

        config = Config()
        config.SOURCE_DIR = str(source_dir)
        config.SOURCE_FILE = ""

        result = config.get_source_path()
        assert result.endswith("translation_en_en.json")

    def test_raises_when_nothing_found(self, temp_dir):
        """Raises FileNotFoundError when no source file can be found."""
        config = Config()
        config.SOURCE_DIR = str(temp_dir)
        config.SOURCE_FILE = ""

        with pytest.raises(FileNotFoundError):
            config.get_source_path()


# ─── LANGUAGES constant ────────────────────────────────────────────


class TestLanguagesConstant:
    """Tests for the LANGUAGES configuration dictionary."""

    def test_all_languages_have_required_keys(self):
        """Each language entry has 'name', 'code', 'target', 'source_col'."""
        for lang_code, lang_info in LANGUAGES.items():
            assert "name" in lang_info, f"{lang_code} missing 'name'"
            assert "code" in lang_info, f"{lang_code} missing 'code'"
            assert "target" in lang_info, f"{lang_code} missing 'target'"
            assert "source_col" in lang_info, f"{lang_code} missing 'source_col'"

    def test_czech_uses_cs_api_code(self):
        """Czech ('cz') uses 'cs' as the Google Translate API code."""
        assert LANGUAGES["cz"]["target"] == "cs"

    def test_en_uses_origin_source_col(self):
        """English uses 'origin' as the source column."""
        assert LANGUAGES["en"]["source_col"] == "origin"

    def test_fr_uses_french_source_col(self):
        """French uses 'french' as the source column."""
        assert LANGUAGES["fr"]["source_col"] == "french"


# ─── Mode constants ────────────────────────────────────────────────


class TestModeConstants:
    """Tests for mode constant values."""

    def test_translate_json_constant(self):
        assert MODE_TRANSLATE_JSON == "translate-json"

    def test_translate_dropdowns_constant(self):
        assert MODE_TRANSLATE_DROPDOWNS == "translate-dropdowns"

    def test_analyze_constant(self):
        assert MODE_ANALYZE == "analyze"


# ─── get_config singleton ──────────────────────────────────────────


class TestGetConfig:
    """Tests for get_config() singleton behavior."""

    def test_returns_config_instance(self):
        """get_config() returns a Config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_singleton_returns_same_instance(self):
        """Repeated calls to get_config() return the same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2


# ─── _is_docker ────────────────────────────────────────────────────


# ─── _default_dir ──────────────────────────────────────────────────


class TestDefaultDir:
    """Tests for _default_dir() — generic environment-aware path resolver."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default_when_no_env_var(self, mock_docker, monkeypatch):
        """In Docker with no env var, returns the Docker default."""
        monkeypatch.delenv("MY_DIR", raising=False)
        result = _default_dir("MY_DIR", "/app/mydir", "/local/mydir")
        assert result == "/app/mydir"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default_when_no_env_var(self, mock_docker, monkeypatch):
        """Outside Docker with no env var, returns the local default."""
        monkeypatch.delenv("MY_DIR", raising=False)
        result = _default_dir("MY_DIR", "/app/mydir", "/local/mydir")
        assert result == "/local/mydir"

    @patch("core.config._is_docker", return_value=True)
    def test_docker_env_var_overrides_default(self, mock_docker):
        """In Docker, env var takes precedence over Docker default."""
        with patch.dict(os.environ, {"MY_DIR": "/custom/dir"}):
            result = _default_dir("MY_DIR", "/app/mydir", "/local/mydir")
            assert result == "/custom/dir"

    @patch("core.config._is_docker", return_value=False)
    def test_local_env_var_overrides_default(self, mock_docker):
        """Outside Docker, env var takes precedence over local default."""
        with patch.dict(os.environ, {"MY_DIR": "/custom/dir"}):
            result = _default_dir("MY_DIR", "/app/mydir", "/local/mydir")
            assert result == "/custom/dir"

    @patch("core.config._is_docker")
    def test_delegates_to_is_docker(self, mock_is_docker):
        """_default_dir calls _is_docker() to determine the environment."""
        mock_is_docker.return_value = True
        _default_dir("TEST_VAR", "/docker/path", "/local/path")
        mock_is_docker.assert_called_once()


# ─── _is_docker ────────────────────────────────────────────────────


class TestIsDocker:
    """Tests for _is_docker() — Docker environment detection."""

    @patch("core.config.os.path.exists")
    def test_returns_true_when_dockerenv_exists(self, mock_exists):
        """Returns True when /.dockerenv exists."""

        def exists_side_effect(path):
            return path == "/.dockerenv"

        mock_exists.side_effect = exists_side_effect

        assert _is_docker() is True

    @patch("core.config.os.path.exists")
    def test_returns_true_when_containerenv_exists(self, mock_exists):
        """Returns True when /run/.containerenv exists (e.g. Podman)."""

        def exists_side_effect(path):
            return path == "/run/.containerenv"

        mock_exists.side_effect = exists_side_effect

        assert _is_docker() is True

    @patch("core.config.os.path.exists")
    def test_returns_true_when_both_exist(self, mock_exists):
        """Returns True when both indicators exist."""
        mock_exists.return_value = True

        assert _is_docker() is True

    @patch("core.config.os.path.exists")
    def test_returns_false_when_neither_exists(self, mock_exists):
        """Returns False when no Docker indicator file exists."""
        mock_exists.return_value = False

        assert _is_docker() is False

    @patch("core.config.os.path.exists")
    def test_checks_dockerenv_first(self, mock_exists):
        """Checks /.dockerenv first (short-circuit if found)."""

        def exists_side_effect(path):
            return path == "/.dockerenv"

        mock_exists.side_effect = exists_side_effect

        _is_docker()
        # /.dockerenv should be the first path checked
        assert mock_exists.call_args_list[0][0][0] == "/.dockerenv"


# ─── _default_output_dir ──────────────────────────────────────────


class TestDefaultOutputDir:
    """Tests for _default_output_dir() — environment-aware output path."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default(self, mock_docker):
        """In Docker, default is /app/output."""
        result = _default_output_dir()
        assert result == "/app/output"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default(self, mock_docker, monkeypatch):
        """Outside Docker, default is CWD/output."""
        monkeypatch.delenv("OUTPUT_DIR", raising=False)
        result = _default_output_dir()
        assert result == str(Path.cwd() / "output")

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"OUTPUT_DIR": "/custom/output"})
    def test_docker_env_var_overrides_default(self, mock_docker):
        """In Docker, OUTPUT_DIR env var overrides the Docker default."""
        result = _default_output_dir()
        assert result == "/custom/output"

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"OUTPUT_DIR": "/custom/output"})
    def test_local_env_var_overrides_default(self, mock_docker):
        """Outside Docker, OUTPUT_DIR env var overrides the local default."""
        result = _default_output_dir()
        assert result == "/custom/output"


# ─── _default_source_dir ──────────────────────────────────────────


class TestDefaultSourceDir:
    """Tests for _default_source_dir() — environment-aware source path."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default(self, mock_docker):
        """In Docker, default is /app/source."""
        result = _default_source_dir()
        assert result == "/app/source"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default(self, mock_docker, monkeypatch):
        """Outside Docker, default is CWD/source."""
        monkeypatch.delenv("SOURCE_DIR", raising=False)
        result = _default_source_dir()
        assert result == str(Path.cwd() / "source")

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"SOURCE_DIR": "/custom/source"})
    def test_docker_env_var_overrides_default(self, mock_docker):
        """In Docker, SOURCE_DIR env var overrides the Docker default."""
        result = _default_source_dir()
        assert result == "/custom/source"

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"SOURCE_DIR": "/custom/source"})
    def test_local_env_var_overrides_default(self, mock_docker):
        """Outside Docker, SOURCE_DIR env var overrides the local default."""
        result = _default_source_dir()
        assert result == "/custom/source"


# ─── _default_excel_dir ────────────────────────────────────────────


class TestDefaultExcelDir:
    """Tests for _default_excel_dir() — environment-aware excel path."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default(self, mock_docker):
        """In Docker, default is /app/excel."""
        result = _default_excel_dir()
        assert result == "/app/excel"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default(self, mock_docker, monkeypatch):
        """Outside Docker, default is CWD/excel."""
        monkeypatch.delenv("EXCEL_DIR", raising=False)
        result = _default_excel_dir()
        assert result == str(Path.cwd() / "excel")

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"EXCEL_DIR": "/custom/excel"})
    def test_docker_env_var_overrides_default(self, mock_docker):
        """In Docker, EXCEL_DIR env var overrides the Docker default."""
        result = _default_excel_dir()
        assert result == "/custom/excel"

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"EXCEL_DIR": "/custom/excel"})
    def test_local_env_var_overrides_default(self, mock_docker):
        """Outside Docker, EXCEL_DIR env var overrides the local default."""
        result = _default_excel_dir()
        assert result == "/custom/excel"


# ─── _default_doc_dir ──────────────────────────────────────────────


class TestDefaultDocDir:
    """Tests for _default_doc_dir() — environment-aware doc path."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default(self, mock_docker):
        """In Docker, default is /app/doc."""
        result = _default_doc_dir()
        assert result == "/app/doc"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default(self, mock_docker, monkeypatch):
        """Outside Docker, default is CWD/Doc."""
        monkeypatch.delenv("DOC_DIR", raising=False)
        result = _default_doc_dir()
        assert result == str(Path.cwd() / "Doc")

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"DOC_DIR": "/custom/doc"})
    def test_docker_env_var_overrides_default(self, mock_docker):
        """In Docker, DOC_DIR env var overrides the Docker default."""
        result = _default_doc_dir()
        assert result == "/custom/doc"

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"DOC_DIR": "/custom/doc"})
    def test_local_env_var_overrides_default(self, mock_docker):
        """Outside Docker, DOC_DIR env var overrides the local default."""
        result = _default_doc_dir()
        assert result == "/custom/doc"


# ─── Config with environment-aware defaults ────────────────────────


class TestConfigEnvironmentAwareDefaults:
    """Tests for Config defaults using _default_*_dir() functions."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_defaults(self, mock_docker):
        """In Docker, all directory defaults use /app/* paths."""
        config = Config()
        assert config.OUTPUT_DIR == "/app/output"
        assert config.SOURCE_DIR == "/app/source"
        assert config.EXCEL_DIR == "/app/excel"
        assert config.DOC_DIR == "/app/doc"

    @patch("core.config._is_docker", return_value=False)
    def test_local_defaults(self, mock_docker, monkeypatch):
        """Outside Docker, all directory defaults use CWD-relative paths."""
        for key in ("OUTPUT_DIR", "SOURCE_DIR", "EXCEL_DIR", "DOC_DIR"):
            monkeypatch.delenv(key, raising=False)
        config = Config()
        assert config.OUTPUT_DIR == str(Path.cwd() / "output")
        assert config.SOURCE_DIR == str(Path.cwd() / "source")
        assert config.EXCEL_DIR == str(Path.cwd() / "excel")
        assert config.DOC_DIR == str(Path.cwd() / "Doc")

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"OUTPUT_DIR": "/my/output", "SOURCE_DIR": "/my/source"})
    def test_env_vars_override_local_defaults(self, mock_docker):
        """Env vars take precedence over local defaults."""
        config = Config()
        assert config.OUTPUT_DIR == "/my/output"
        assert config.SOURCE_DIR == "/my/source"

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"OUTPUT_DIR": "/my/output", "SOURCE_DIR": "/my/source"})
    def test_env_vars_override_docker_defaults(self, mock_docker):
        """Env vars take precedence over Docker defaults."""
        config = Config()
        assert config.OUTPUT_DIR == "/my/output"
        assert config.SOURCE_DIR == "/my/source"


# ─── _default_cache_path ──────────────────────────────────────────


class TestDefaultCachePath:
    """Tests for _default_cache_path() — environment-aware cache file path."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default(self, mock_docker):
        """In Docker, default cache path is /app/output/.translation_cache.json."""
        result = _default_cache_path()
        assert result == "/app/output/.translation_cache.json"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default(self, mock_docker, monkeypatch):
        """Outside Docker, default cache path is CWD/output/.translation_cache.json."""
        monkeypatch.delenv("TRANSLATION_CACHE_PATH", raising=False)
        result = _default_cache_path()
        assert result == str(Path.cwd() / "output" / ".translation_cache.json")

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"TRANSLATION_CACHE_PATH": "/custom/cache.json"})
    def test_docker_env_var_overrides_default(self, mock_docker):
        """In Docker, TRANSLATION_CACHE_PATH env var overrides the Docker default."""
        result = _default_cache_path()
        assert result == "/custom/cache.json"

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"TRANSLATION_CACHE_PATH": "/custom/cache.json"})
    def test_local_env_var_overrides_default(self, mock_docker):
        """Outside Docker, TRANSLATION_CACHE_PATH env var overrides the local default."""
        result = _default_cache_path()
        assert result == "/custom/cache.json"


# ─── Config cache settings ────────────────────────────────────────


class TestConfigCacheSettings:
    """Tests for Config TRANSLATION_CACHE, TRANSLATION_CACHE_PATH, and cache_enabled."""

    def test_default_translation_cache_is_true(self):
        """Default TRANSLATION_CACHE is 'true'."""
        config = Config()
        assert config.TRANSLATION_CACHE == "true"

    def test_cache_enabled_is_true_by_default(self):
        """cache_enabled property returns True by default."""
        config = Config()
        assert config.cache_enabled is True

    @patch.dict(os.environ, {"TRANSLATION_CACHE": "false"})
    def test_cache_enabled_false(self):
        """TRANSLATION_CACHE=false disables the cache."""
        config = Config()
        assert config.cache_enabled is False

    @patch.dict(os.environ, {"TRANSLATION_CACHE": "0"})
    def test_cache_enabled_zero(self):
        """TRANSLATION_CACHE=0 disables the cache."""
        config = Config()
        assert config.cache_enabled is False

    @patch.dict(os.environ, {"TRANSLATION_CACHE": "yes"})
    def test_cache_enabled_yes(self):
        """TRANSLATION_CACHE=yes enables the cache."""
        config = Config()
        assert config.cache_enabled is True

    @patch.dict(os.environ, {"TRANSLATION_CACHE": "1"})
    def test_cache_enabled_one(self):
        """TRANSLATION_CACHE=1 enables the cache."""
        config = Config()
        assert config.cache_enabled is True

    @patch.dict(os.environ, {"TRANSLATION_CACHE": "TRUE"})
    def test_cache_enabled_case_insensitive(self):
        """TRANSLATION_CACHE is case-insensitive."""
        config = Config()
        assert config.cache_enabled is True

    @patch("core.config._is_docker", return_value=True)
    def test_default_cache_path_in_docker(self, mock_docker):
        """In Docker, default cache path is /app/output/.translation_cache.json."""
        config = Config()
        assert config.TRANSLATION_CACHE_PATH == "/app/output/.translation_cache.json"

    @patch("core.config._is_docker", return_value=False)
    def test_default_cache_path_local(self, mock_docker, monkeypatch):
        """Outside Docker, default cache path uses CWD."""
        monkeypatch.delenv("TRANSLATION_CACHE_PATH", raising=False)
        config = Config()
        assert config.TRANSLATION_CACHE_PATH == str(
            Path.cwd() / "output" / ".translation_cache.json"
        )

    @patch.dict(os.environ, {"TRANSLATION_CACHE_PATH": "/my/cache.json"})
    def test_cache_path_env_var_override(self):
        """TRANSLATION_CACHE_PATH env var overrides the default."""
        config = Config()
        assert config.TRANSLATION_CACHE_PATH == "/my/cache.json"


class TestDefaultRateLimiterPath:
    """Tests for _default_rate_limiter_path()."""

    @patch("core.config._is_docker", return_value=True)
    def test_docker_default(self, mock_docker):
        """In Docker, default rate limiter path is /app/output/.rate_limiter_state.json."""
        result = _default_rate_limiter_path()
        assert result == "/app/output/.rate_limiter_state.json"

    @patch("core.config._is_docker", return_value=False)
    def test_local_default(self, mock_docker):
        """Outside Docker, default rate limiter path uses CWD."""
        result = _default_rate_limiter_path()
        assert "output" in result
        assert ".rate_limiter_state.json" in result

    @patch("core.config._is_docker", return_value=True)
    @patch.dict(os.environ, {"RATE_LIMITER_STATE_PATH": "/custom/state.json"})
    def test_docker_env_var_overrides_default(self, mock_docker):
        """RATE_LIMITER_STATE_PATH env var overrides Docker default."""
        result = _default_rate_limiter_path()
        assert result == "/custom/state.json"

    @patch("core.config._is_docker", return_value=False)
    @patch.dict(os.environ, {"RATE_LIMITER_STATE_PATH": "/local/state.json"})
    def test_local_env_var_overrides_default(self, mock_docker):
        """RATE_LIMITER_STATE_PATH env var overrides local default."""
        result = _default_rate_limiter_path()
        assert result == "/local/state.json"


class TestConfigRateLimiterSettings:
    """Tests for Config rate limiter settings."""

    def test_default_rate_limiter_state_path_exists(self):
        """Config has a RATE_LIMITER_STATE_PATH field."""
        config = Config()
        assert hasattr(config, "RATE_LIMITER_STATE_PATH")
        assert isinstance(config.RATE_LIMITER_STATE_PATH, str)

    @patch("core.config._is_docker", return_value=True)
    def test_default_rate_limiter_path_in_docker(self, mock_docker):
        """In Docker, RATE_LIMITER_STATE_PATH defaults to /app/output."""
        config = Config()
        assert config.RATE_LIMITER_STATE_PATH == "/app/output/.rate_limiter_state.json"

    @patch("core.config._is_docker", return_value=False)
    def test_default_rate_limiter_path_local(self, mock_docker):
        """Outside Docker, RATE_LIMITER_STATE_PATH uses CWD."""
        config = Config()
        assert "output" in config.RATE_LIMITER_STATE_PATH
        assert ".rate_limiter_state.json" in config.RATE_LIMITER_STATE_PATH

    @patch.dict(os.environ, {"RATE_LIMITER_STATE_PATH": "/my/state.json"})
    def test_rate_limiter_path_env_var_override(self):
        """RATE_LIMITER_STATE_PATH env var overrides the default."""
        config = Config()
        assert config.RATE_LIMITER_STATE_PATH == "/my/state.json"


class TestConfigCLIFlags:
    """Tests for Config CLI flag fields (dry_run, verbose, quiet)."""

    def test_dry_run_default_false(self):
        """dry_run defaults to False."""
        config = Config()
        assert config.dry_run is False

    def test_dry_run_can_be_set_true(self):
        """dry_run can be set to True."""
        config = Config(dry_run=True)
        assert config.dry_run is True

    def test_verbose_default_false(self):
        """verbose defaults to False."""
        config = Config()
        assert config.verbose is False

    def test_verbose_can_be_set_true(self):
        """verbose can be set to True."""
        config = Config(verbose=True)
        assert config.verbose is True

    def test_quiet_default_false(self):
        """quiet defaults to False."""
        config = Config()
        assert config.quiet is False

    def test_quiet_can_be_set_true(self):
        """quiet can be set to True."""
        config = Config(quiet=True)
        assert config.quiet is True

    def test_all_cli_flags_default_false(self):
        """All CLI flags default to False simultaneously."""
        config = Config()
        assert config.dry_run is False
        assert config.verbose is False
        assert config.quiet is False

    def test_all_cli_flags_can_be_set(self):
        """All CLI flags can be set simultaneously."""
        config = Config(dry_run=True, verbose=True, quiet=True)
        assert config.dry_run is True
        assert config.verbose is True
        assert config.quiet is True


# ─── IMP-T004: Multi-provider config ──────────────────────────────


class TestConfigProviderDefaults:
    """Tests for multi-provider configuration defaults (IMP-T004)."""

    def test_default_translation_provider(self):
        """Default translation provider is 'google'."""
        config = Config()
        assert config.TRANSLATION_PROVIDER == "google"

    def test_default_deepl_api_key_empty(self):
        """Default DeepL API key is empty string."""
        config = Config()
        assert config.DEEPL_API_KEY == ""

    def test_default_deepl_use_free_api(self):
        """Default DEEPL_USE_FREE_API is 'true'."""
        config = Config()
        assert config.DEEPL_USE_FREE_API == "true"

    def test_default_translation_fallback(self):
        """Default TRANSLATION_FALLBACK is 'false'."""
        config = Config()
        assert config.TRANSLATION_FALLBACK == "false"


class TestConfigProviderEnvOverrides:
    """Tests for multi-provider environment variable overrides (IMP-T004)."""

    @patch.dict(os.environ, {"TRANSLATION_PROVIDER": "deepl"})
    def test_translation_provider_from_env(self):
        """TRANSLATION_PROVIDER environment variable overrides the default."""
        config = Config()
        assert config.TRANSLATION_PROVIDER == "deepl"

    @patch.dict(os.environ, {"DEEPL_API_KEY": "my-secret-key"})
    def test_deepl_api_key_from_env(self):
        """DEEPL_API_KEY environment variable is loaded."""
        config = Config()
        assert config.DEEPL_API_KEY == "my-secret-key"

    @patch.dict(os.environ, {"DEEPL_USE_FREE_API": "false"})
    def test_deepl_use_free_api_from_env(self):
        """DEEPL_USE_FREE_API environment variable overrides the default."""
        config = Config()
        assert config.DEEPL_USE_FREE_API == "false"

    @patch.dict(os.environ, {"TRANSLATION_FALLBACK": "true"})
    def test_translation_fallback_from_env(self):
        """TRANSLATION_FALLBACK environment variable overrides the default."""
        config = Config()
        assert config.TRANSLATION_FALLBACK == "true"


class TestConfigProviderProperties:
    """Tests for multi-provider derived properties (IMP-T004)."""

    def test_deepl_use_free_api_enabled_default(self):
        """deepl_use_free_api_enabled is True by default."""
        config = Config()
        assert config.deepl_use_free_api_enabled is True

    @patch.dict(os.environ, {"DEEPL_USE_FREE_API": "false"})
    def test_deepl_use_free_api_disabled(self):
        """deepl_use_free_api_enabled is False when DEEPL_USE_FREE_API='false'."""
        config = Config()
        assert config.deepl_use_free_api_enabled is False

    def test_deepl_use_free_api_one_means_true(self):
        """deepl_use_free_api_enabled is True when DEEPL_USE_FREE_API='1'."""
        config = Config(DEEPL_USE_FREE_API="1")
        assert config.deepl_use_free_api_enabled is True

    def test_fallback_enabled_default_false(self):
        """fallback_enabled is False by default."""
        config = Config()
        assert config.fallback_enabled is False

    @patch.dict(os.environ, {"TRANSLATION_FALLBACK": "true"})
    def test_fallback_enabled_true(self):
        """fallback_enabled is True when TRANSLATION_FALLBACK='true'."""
        config = Config()
        assert config.fallback_enabled is True

    def test_fallback_enabled_yes_means_true(self):
        """fallback_enabled is True when TRANSLATION_FALLBACK='yes'."""
        config = Config(TRANSLATION_FALLBACK="yes")
        assert config.fallback_enabled is True
