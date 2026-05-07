"""
Tests for the CLI interface — service.py build_parser() and build_config_from_args().

Covers:
- build_parser(): subcommands, arguments, defaults
- build_config_from_args(): CLI > env > default resolution
- --verbose / --quiet logging levels
- --dry-run flag
- --version flag
- Each subcommand: translate-json, translate-dropdowns, analyze
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# ─── build_parser ─────────────────────────────────────────────────


class TestBuildParser:
    """Tests for build_parser() — argument parser creation."""

    def test_parser_is_argument_parser(self):
        """build_parser() returns an argparse.ArgumentParser."""
        from service import build_parser

        parser = build_parser()
        import argparse

        assert isinstance(parser, argparse.ArgumentParser)

    def test_parser_prog_name(self):
        """Parser prog name is 'service.py'."""
        from service import build_parser

        parser = build_parser()
        assert parser.prog == "service.py"

    def test_parser_has_translate_json_subcommand(self):
        """Parser recognizes 'translate-json' subcommand."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.mode == "translate-json"

    def test_parser_has_translate_dropdowns_subcommand(self):
        """Parser recognizes 'translate-dropdowns' subcommand."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns"])
        assert args.mode == "translate-dropdowns"

    def test_parser_has_analyze_subcommand(self):
        """Parser recognizes 'analyze' subcommand."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze"])
        assert args.mode == "analyze"

    def test_parser_no_subcommand_sets_mode_none(self):
        """Without a subcommand, mode is None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args([])
        assert args.mode is None

    def test_parser_verbose_short_flag(self):
        """Parser accepts -v for verbose."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["-v", "translate-json"])
        assert args.verbose is True

    def test_parser_verbose_long_flag(self):
        """Parser accepts --verbose for verbose."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["--verbose", "translate-json"])
        assert args.verbose is True

    def test_parser_verbose_default_false(self):
        """Verbose defaults to False."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.verbose is False

    def test_parser_quiet_short_flag(self):
        """Parser accepts -q for quiet."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["-q", "translate-json"])
        assert args.quiet is True

    def test_parser_quiet_long_flag(self):
        """Parser accepts --quiet for quiet."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["--quiet", "translate-json"])
        assert args.quiet is True

    def test_parser_quiet_default_false(self):
        """Quiet defaults to False."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.quiet is False

    def test_parser_dry_run_flag(self):
        """Parser accepts --dry-run flag on subcommands."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--dry-run"])
        assert args.dry_run is True

    def test_parser_dry_run_default_false(self):
        """--dry-run defaults to False."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.dry_run is False


# ─── translate-json subcommand ─────────────────────────────────────


class TestTranslateJsonSubcommand:
    """Tests for the translate-json subcommand arguments."""

    def test_source_lang_long_flag(self):
        """--source-lang sets source language."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--source-lang", "fr"])
        assert args.source_lang == "fr"

    def test_source_lang_short_flag(self):
        """-s sets source language."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "-s", "de"])
        assert args.source_lang == "de"

    def test_source_lang_default_none(self):
        """Source language defaults to None (falls back to env/default)."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.source_lang is None

    def test_target_lang_long_flag(self):
        """--target-lang sets target language."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--target-lang", "cs"])
        assert args.target_lang == "cs"

    def test_target_lang_short_flag(self):
        """-t sets target language."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "-t", "sk"])
        assert args.target_lang == "sk"

    def test_target_lang_default_none(self):
        """Target language defaults to None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.target_lang is None

    def test_input_long_flag(self):
        """--input sets source file path."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--input", "my_file.json"])
        assert args.input == "my_file.json"

    def test_input_short_flag(self):
        """-i sets source file path."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "-i", "data.json"])
        assert args.input == "data.json"

    def test_input_default_none(self):
        """Input defaults to None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.input is None

    def test_output_dir_flag(self):
        """--output-dir sets output directory."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--output-dir", "/tmp/out"])
        assert args.output_dir == "/tmp/out"

    def test_output_dir_default_none(self):
        """Output dir defaults to None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.output_dir is None

    def test_batch_langs_flag(self):
        """--batch-langs sets batch languages."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--batch-langs", "en,fr,cz"])
        assert args.batch_langs == "en,fr,cz"

    def test_batch_langs_default_none(self):
        """Batch langs defaults to None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])
        assert args.batch_langs is None

    def test_dry_run_on_translate_json(self):
        """--dry-run is available on translate-json subcommand."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--dry-run"])
        assert args.dry_run is True

    def test_combined_flags(self):
        """Multiple flags can be combined."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "translate-json",
                "-s",
                "en",
                "-t",
                "fr",
                "-i",
                "test.json",
                "--dry-run",
            ]
        )
        assert args.mode == "translate-json"
        assert args.source_lang == "en"
        assert args.target_lang == "fr"
        assert args.input == "test.json"
        assert args.dry_run is True


# ─── translate-dropdowns subcommand ────────────────────────────────


class TestTranslateDropdownsSubcommand:
    """Tests for the translate-dropdowns subcommand arguments."""

    def test_mode_is_translate_dropdowns(self):
        """Parser recognizes translate-dropdowns mode."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns"])
        assert args.mode == "translate-dropdowns"

    def test_input_flag(self):
        """--input sets the source file for dropdowns."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--input", "dropdowns.xlsx"])
        assert args.input == "dropdowns.xlsx"

    def test_batch_langs_flag(self):
        """--batch-langs sets batch languages for dropdowns."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--batch-langs", "fr,cz,sk"])
        assert args.batch_langs == "fr,cz,sk"

    def test_format_json(self):
        """--format json sets output format."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--format", "json"])
        assert args.format == "json"

    def test_format_xlsx(self):
        """--format xlsx sets output format."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--format", "xlsx"])
        assert args.format == "xlsx"

    def test_format_auto(self):
        """--format auto sets output format."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--format", "auto"])
        assert args.format == "auto"

    def test_format_default_none(self):
        """Format defaults to None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns"])
        assert args.format is None

    def test_output_dir_flag(self):
        """--output-dir sets output directory for dropdowns."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--output-dir", "/tmp/out"])
        assert args.output_dir == "/tmp/out"

    def test_dry_run_on_translate_dropdowns(self):
        """--dry-run is available on translate-dropdowns subcommand."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--dry-run"])
        assert args.dry_run is True

    def test_source_lang_on_translate_dropdowns(self):
        """--source-lang is available on translate-dropdowns."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--source-lang", "en"])
        assert args.source_lang == "en"


# ─── analyze subcommand ────────────────────────────────────────────


class TestAnalyzeSubcommand:
    """Tests for the analyze subcommand arguments."""

    def test_mode_is_analyze(self):
        """Parser recognizes analyze mode."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze"])
        assert args.mode == "analyze"

    def test_input_flag(self):
        """--input sets the XLSX file to analyze."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze", "--input", "data.xlsx"])
        assert args.input == "data.xlsx"

    def test_input_default_none(self):
        """Input defaults to None."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze"])
        assert args.input is None

    def test_output_dir_flag(self):
        """--output-dir sets output directory for analyze."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze", "--output-dir", "/tmp/out"])
        assert args.output_dir == "/tmp/out"

    def test_output_dir_default_none(self):
        """Output dir defaults to None for analyze."""
        from service import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze"])
        assert args.output_dir is None


# ─── build_config_from_args — resolution priority ──────────────────


class TestBuildConfigFromArgsPriority:
    """Tests for CLI > env > default resolution in build_config_from_args()."""

    def test_cli_overrides_env_for_source_lang(self):
        """CLI --source-lang takes priority over SOURCE_LANG env var."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--source-lang", "de"])

        with patch.dict(os.environ, {"SOURCE_LANG": "fr"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.SOURCE_LANG == "de"
            config_module._config = None

    def test_env_used_when_no_cli_for_source_lang(self):
        """SOURCE_LANG env var is used when CLI --source-lang is not provided."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        with patch.dict(os.environ, {"SOURCE_LANG": "it"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.SOURCE_LANG == "it"
            config_module._config = None

    def test_default_used_when_no_cli_no_env_for_source_lang(self):
        """Default 'en' is used when neither CLI nor env var is set."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        with patch.dict(os.environ, {}, clear=False):
            # Remove the env var if it exists
            os.environ.pop("SOURCE_LANG", None)
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.SOURCE_LANG == "en"
            config_module._config = None

    def test_cli_overrides_env_for_target_lang(self):
        """CLI --target-lang takes priority over TARGET_LANG env var."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--target-lang", "sk"])

        with patch.dict(os.environ, {"TARGET_LANG": "fr"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.TARGET_LANG == "sk"
            config_module._config = None

    def test_cli_overrides_env_for_input(self):
        """CLI --input takes priority over SOURCE_FILE env var."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--input", "/custom/file.json"])

        with patch.dict(os.environ, {"SOURCE_FILE": "/env/file.json"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.SOURCE_FILE == "/custom/file.json"
            config_module._config = None

    def test_cli_overrides_env_for_output_dir(self):
        """CLI --output-dir takes priority over OUTPUT_DIR env var."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--output-dir", "/custom/output"])

        with patch.dict(os.environ, {"OUTPUT_DIR": "/env/output"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.OUTPUT_DIR == "/custom/output"
            config_module._config = None

    def test_cli_overrides_env_for_batch_langs(self):
        """CLI --batch-langs takes priority over BATCH_LANGS env var."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--batch-langs", "en,fr,de"])

        with patch.dict(os.environ, {"BATCH_LANGS": "en,fr,cz,sk"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.BATCH_LANGS == "en,fr,de"
            config_module._config = None

    def test_cli_overrides_env_for_format(self):
        """CLI --format takes priority over OUTPUT_FORMAT env var."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--format", "xlsx"])

        with patch.dict(os.environ, {"OUTPUT_FORMAT": "json"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.OUTPUT_FORMAT == "xlsx"
            config_module._config = None


# ─── build_config_from_args — mode from subcommand ────────────────


class TestBuildConfigFromArgsMode:
    """Tests that the mode is correctly set from the subcommand."""

    def test_translate_json_mode(self):
        """translate-json subcommand sets MODE to 'translate-json'."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.MODE == "translate-json"
        config_module._config = None

    def test_translate_dropdowns_mode(self):
        """translate-dropdowns subcommand sets MODE to 'translate-dropdowns'."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.MODE == "translate-dropdowns"
        config_module._config = None

    def test_analyze_mode(self):
        """analyze subcommand sets MODE to 'analyze'."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.MODE == "analyze"
        config_module._config = None


# ─── build_config_from_args — dry-run flag ────────────────────────


class TestBuildConfigFromArgsDryRun:
    """Tests for --dry-run flag propagation."""

    def test_dry_run_flag_true(self):
        """--dry-run sets dry_run attribute to True."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json", "--dry-run"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.dry_run is True
        config_module._config = None

    def test_dry_run_flag_false_by_default(self):
        """Without --dry-run, dry_run attribute is False."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.dry_run is False
        config_module._config = None

    def test_dry_run_on_dropdowns(self):
        """--dry-run works on translate-dropdowns subcommand."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-dropdowns", "--dry-run"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.dry_run is True
        config_module._config = None


# ─── build_config_from_args — verbose/quiet ────────────────────────


class TestBuildConfigFromArgsVerbosity:
    """Tests for --verbose and --quiet flag propagation."""

    def test_verbose_flag(self):
        """--verbose sets verbose attribute to True."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["--verbose", "translate-json"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.verbose is True
        config_module._config = None

    def test_verbose_default_false(self):
        """Without --verbose, verbose attribute is False."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.verbose is False
        config_module._config = None

    def test_quiet_flag(self):
        """--quiet sets quiet attribute to True."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["--quiet", "translate-json"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.quiet is True
        config_module._config = None

    def test_quiet_default_false(self):
        """Without --quiet, quiet attribute is False."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        import core.config as config_module

        config_module._config = None
        config = build_config_from_args(args)
        assert config.quiet is False
        config_module._config = None


# ─── build_config_from_args — nil args fall through to defaults ──


class TestBuildConfigFromArgsDefaults:
    """Tests that nil CLI args fall through to Config defaults."""

    def test_no_cli_no_env_uses_config_defaults(self):
        """When no CLI args and no env vars, Config defaults are used."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        # Clear relevant env vars
        env_vars_to_clear = [
            "MODE",
            "SOURCE_LANG",
            "TARGET_LANG",
            "SOURCE_FILE",
            "OUTPUT_DIR",
            "BATCH_LANGS",
            "OUTPUT_FORMAT",
        ]
        with patch.dict(os.environ, {}, clear=False):
            for var in env_vars_to_clear:
                os.environ.pop(var, None)

            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.SOURCE_LANG == "en"
            assert config.TARGET_LANG == "cs"
            assert config.BATCH_LANGS == "en,fr,cz,sk,de,it,ar"
            assert config.OUTPUT_FORMAT == "auto"
            config_module._config = None

    def test_translate_json_default_mode(self):
        """When mode is set via CLI, it overrides env MODE."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(["translate-json"])

        with patch.dict(os.environ, {"MODE": "analyze"}):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.MODE == "translate-json"
            config_module._config = None

    def test_all_cli_args_override(self):
        """All CLI args override their respective env vars simultaneously."""
        from service import build_config_from_args, build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "translate-json",
                "--source-lang",
                "it",
                "--target-lang",
                "de",
                "--input",
                "/cli/file.json",
                "--output-dir",
                "/cli/output",
                "--batch-langs",
                "it,de,fr",
            ]
        )

        with patch.dict(
            os.environ,
            {
                "SOURCE_LANG": "en",
                "TARGET_LANG": "cs",
                "SOURCE_FILE": "/env/file.json",
                "OUTPUT_DIR": "/env/output",
                "BATCH_LANGS": "en,fr,cz",
            },
        ):
            import core.config as config_module

            config_module._config = None
            config = build_config_from_args(args)
            assert config.SOURCE_LANG == "it"
            assert config.TARGET_LANG == "de"
            assert config.SOURCE_FILE == "/cli/file.json"
            assert config.OUTPUT_DIR == "/cli/output"
            assert config.BATCH_LANGS == "it,de,fr"
            config_module._config = None
