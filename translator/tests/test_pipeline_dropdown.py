"""
Tests pour le pipeline dropdown (TDD strict).

Couvre :
- D3 : load_dropdown_xlsx_all_sheets() + detect_missing_languages() (io_xlsx)
- D4 : PipelineDropdownContext + build_parser_dropdown() + flags (pipeline_dropdown)
- D5 : Étapes 1-2 — Détection XLSX + comparaison (pipeline_dropdown)
- D6 : Étape 3 — Coquilles sur Origins (pipeline_dropdown)
- D7-D14 : étapes 4-11 du pipeline dropdown (à venir)
"""

import openpyxl
import pytest
from unittest.mock import patch


# ─── Fixtures XLSX de test ─────────────────────────────────────────


@pytest.fixture
def xlsx_3_langs(tmp_path):
    """XLSX avec 3 feuilles (EN, FR, CZ), 2 entrées chacune."""
    wb = openpyxl.Workbook()
    ws_en = wb.active
    ws_en.title = "EN"
    ws_en.append(["Origin", "Anglais", "Contexte"])
    ws_en.append(["Hello", "Hello", "greeting"])
    ws_en.append(["World", "World", "greeting"])
    ws_fr = wb.create_sheet("FR")
    ws_fr.append(["Origin", "Français", "Contexte"])
    ws_fr.append(["Hello", "Bonjour", "greeting"])
    ws_fr.append(["World", "Monde", "greeting"])
    ws_cz = wb.create_sheet("CZ")
    ws_cz.append(["Origin", "Tchèque", "Contexte"])
    ws_cz.append(["Hello", "Ahoj", "greeting"])
    ws_cz.append(["World", "Svět", "greeting"])
    path = tmp_path / "test_dropdown.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def xlsx_empty(tmp_path):
    """XLSX vide (aucune feuille de langue)."""
    wb = openpyxl.Workbook()
    wb.active.title = "EN"
    wb.active.append(["Origin", "Anglais", "Contexte"])
    path = tmp_path / "empty_dropdown.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def xlsx_prev(tmp_path):
    """XLSX précédent : 2 feuilles (EN/FR), Origins = Hello, World, Goodbye."""
    wb = openpyxl.Workbook()
    ws_en = wb.active
    ws_en.title = "EN"
    ws_en.append(["Origin", "Anglais", "Contexte"])
    ws_en.append(["Hello", "Hello", "greeting"])
    ws_en.append(["World", "World", "greeting"])
    ws_en.append(["Goodbye", "Goodbye", "farewell"])
    ws_fr = wb.create_sheet("FR")
    ws_fr.append(["Origin", "Français", "Contexte"])
    ws_fr.append(["Hello", "Bonjour", "greeting"])
    ws_fr.append(["World", "Monde", "greeting"])
    ws_fr.append(["Goodbye", "Au revoir", "farewell"])
    path = tmp_path / "prev_dropdown.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def xlsx_new(tmp_path):
    """XLSX nouveau : Origins = Hello, World, Welcome (Goodbye supprimé, Welcome ajouté)."""
    wb = openpyxl.Workbook()
    ws_en = wb.active
    ws_en.title = "EN"
    ws_en.append(["Origin", "Anglais", "Contexte"])
    ws_en.append(["Hello", "Hello", "greeting"])
    ws_en.append(["World", "World", "greeting"])
    ws_en.append(["Welcome", "Welcome", "greeting"])
    ws_fr = wb.create_sheet("FR")
    ws_fr.append(["Origin", "Français", "Contexte"])
    ws_fr.append(["Hello", "Bonjour", "greeting"])
    ws_fr.append(["World", "Monde", "greeting"])
    ws_fr.append(["Welcome", "Bienvenue", "greeting"])
    ws_cz = wb.create_sheet("CZ")
    ws_cz.append(["Origin", "Tchèque", "Contexte"])
    ws_cz.append(["Hello", "Ahoj", "greeting"])
    ws_cz.append(["World", "Svět", "greeting"])
    ws_cz.append(["Welcome", "Vítej", "greeting"])
    path = tmp_path / "new_dropdown.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def xlsx_with_typo(tmp_path):
    """XLSX avec une coquille 'Hiearchy' dans un Origin."""
    wb = openpyxl.Workbook()
    ws_en = wb.active
    ws_en.title = "EN"
    ws_en.append(["Origin", "Anglais", "Contexte"])
    ws_en.append(["Hello", "Hello", "greeting"])
    ws_en.append(["Hiearchy menu", "Hiearchy menu", "menu"])
    path = tmp_path / "typo_dropdown.xlsx"
    wb.save(path)
    return path


# ═══ D3 : load_dropdown_xlsx_all_sheets + detect_missing_languages ═══


class TestLoadDropdownXlsxAllSheets:
    """Tests de load_dropdown_xlsx_all_sheets() — lit toutes les feuilles."""

    def test_returns_dict_lang_to_translations(self, xlsx_3_langs):
        from core.io_xlsx import load_dropdown_xlsx_all_sheets

        result = load_dropdown_xlsx_all_sheets(xlsx_3_langs)
        assert "EN" in result
        assert "FR" in result
        assert "CZ" in result
        assert result["FR"]["Hello"] == "Bonjour"
        assert result["FR"]["World"] == "Monde"
        assert result["EN"]["Hello"] == "Hello"

    def test_empty_rows_skipped(self, xlsx_3_langs):
        from core.io_xlsx import load_dropdown_xlsx_all_sheets

        result = load_dropdown_xlsx_all_sheets(xlsx_3_langs)
        assert len(result["FR"]) == 2

    def test_only_header_row(self, xlsx_empty):
        from core.io_xlsx import load_dropdown_xlsx_all_sheets

        result = load_dropdown_xlsx_all_sheets(xlsx_empty)
        assert result["EN"] == {}

    def test_file_not_found_raises(self, tmp_path):
        from core.io_xlsx import load_dropdown_xlsx_all_sheets

        with pytest.raises(FileNotFoundError):
            load_dropdown_xlsx_all_sheets(tmp_path / "absent.xlsx")


class TestDetectMissingLanguages:
    """Tests de detect_missing_languages() — compare feuilles vs langues configurées."""

    def test_detects_missing(self, xlsx_3_langs):
        from core.io_xlsx import detect_missing_languages

        configured = ["fr", "cz", "sk", "de", "it", "ar", "pt", "es", "hu"]
        missing = detect_missing_languages(xlsx_3_langs, configured)
        assert sorted(missing) == ["ar", "de", "es", "hu", "it", "pt", "sk"]

    def test_all_present_returns_empty(self, xlsx_3_langs):
        from core.io_xlsx import detect_missing_languages

        missing = detect_missing_languages(xlsx_3_langs, ["fr", "cz"])
        assert missing == []

    def test_case_insensitive_sheet_names(self, xlsx_3_langs):
        from core.io_xlsx import detect_missing_languages

        missing = detect_missing_languages(xlsx_3_langs, ["fr", "cz", "sk"])
        assert missing == ["sk"]

    def test_en_excluded_from_missing(self, xlsx_3_langs):
        from core.io_xlsx import detect_missing_languages

        missing = detect_missing_languages(xlsx_3_langs, ["en", "fr", "sk"])
        assert missing == ["sk"]


# ═══ D4 : PipelineDropdownContext + parser + flags (TDD) ═══


class TestPipelineDropdownContext:
    """Tests de PipelineDropdownContext — champs spécifiques dropdown."""

    def test_defaults(self):
        from pipeline_dropdown import PipelineDropdownContext

        ctx = PipelineDropdownContext()
        assert ctx.xlsx_path is None
        assert ctx.prev_xlsx_path is None
        assert ctx.output_dir is None
        assert ctx.existing_translations == {}
        assert ctx.missing_languages == []
        assert ctx.retranslate_all is False
        assert ctx.retranslate_langs == []
        assert ctx.no_cache is False
        assert ctx.output_format == "auto"
        assert ctx.entries == []

    def test_inherits_base_fields(self):
        from pipeline_dropdown import PipelineDropdownContext

        ctx = PipelineDropdownContext(dry_run=True, provider="ollama", languages=["pt"])
        assert ctx.dry_run is True
        assert ctx.provider == "ollama"
        assert ctx.languages == ["pt"]

    def test_independent_list_factories(self):
        from pipeline_dropdown import PipelineDropdownContext

        a = PipelineDropdownContext()
        b = PipelineDropdownContext()
        a.missing_languages.append("pt")
        assert b.missing_languages == []


class TestBuildParserDropdown:
    """Tests de build_parser_dropdown() — flags spécifiques dropdown."""

    def test_dry_run_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_languages_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--languages", "pt,es,hu"])
        assert args.languages == "pt,es,hu"

    def test_provider_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--provider", "ollama"])
        assert args.provider == "ollama"

    def test_source_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--source", "dropdown.xlsx"])
        assert args.source is not None

    def test_yes_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--yes"])
        assert args.yes is True

    def test_mode_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--mode", "dropdown"])
        assert args.mode == "dropdown"

    def test_retranslate_all_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--retranslate-all"])
        assert args.retranslate_all is True

    def test_retranslate_all_default_false(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args([])
        assert args.retranslate_all is False

    def test_retranslate_langs_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--retranslate", "fr,de"])
        assert args.retranslate == "fr,de"

    def test_retranslate_default_none(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args([])
        assert args.retranslate is None

    def test_no_cache_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--no-cache"])
        assert args.no_cache is True

    def test_no_cache_default_false(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args([])
        assert args.no_cache is False

    def test_format_flag(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args(["--format", "xlsx"])
        assert args.format == "xlsx"

    def test_format_default_auto(self):
        from pipeline_dropdown import build_parser_dropdown

        args = build_parser_dropdown().parse_args([])
        assert args.format == "auto"


class TestRunPipelineDropdown:
    """Tests de run_pipeline_dropdown() — squelette (étapes à venir en D7+)."""

    def test_dry_run_returns_zero(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import build_parser_dropdown, run_pipeline_dropdown

        args = build_parser_dropdown().parse_args(
            ["--dry-run", "--source", str(xlsx_3_langs), "--languages", "pt"]
        )
        rc = run_pipeline_dropdown(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()


# ═══ D5 : Étapes 1-2 — Détection XLSX + comparaison (TDD) ═══


class TestStep1DetectSource:
    """Tests de step1_detect_source() — détection XLSX + chargement données."""

    def test_loads_existing_translations(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["pt"])
        step1_detect_source(ctx)
        assert "FR" in ctx.existing_translations
        assert ctx.existing_translations["FR"]["Hello"] == "Bonjour"
        assert "CZ" in ctx.existing_translations

    def test_detects_missing_languages(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(
            xlsx_path=xlsx_3_langs, languages=["fr", "cz", "pt", "es"]
        )
        step1_detect_source(ctx)
        assert sorted(ctx.missing_languages) == ["es", "pt"]

    def test_loads_entries(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["pt"])
        step1_detect_source(ctx)
        assert len(ctx.entries) == 2
        origins = [e["origin"] for e in ctx.entries]
        assert "Hello" in origins and "World" in origins

    def test_source_missing_raises(self, tmp_path):
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=tmp_path / "absent.xlsx")
        with pytest.raises(FileNotFoundError):
            step1_detect_source(ctx)

    def test_all_languages_present_no_missing(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr", "cz"])
        step1_detect_source(ctx)
        assert ctx.missing_languages == []


class TestStep2CompareSources:
    """Tests de step2_compare_sources() — comparaison par Origin."""

    def test_skips_without_prev(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs)
        step2_compare_sources(ctx)
        out = capsys.readouterr().out
        assert "ignorée" in out.lower() or "skip" in out.lower()

    def test_detects_added_origins(self, xlsx_prev, xlsx_new, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_new, prev_xlsx_path=xlsx_prev)
        step2_compare_sources(ctx)
        out = capsys.readouterr().out
        assert "Welcome" in out or "ajout" in out.lower()

    def test_detects_removed_origins(self, xlsx_prev, xlsx_new, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_new, prev_xlsx_path=xlsx_prev)
        step2_compare_sources(ctx)
        out = capsys.readouterr().out
        assert "Goodbye" in out or "supprim" in out.lower()

    def test_populates_comparison_results(self, xlsx_prev, xlsx_new):
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_new, prev_xlsx_path=xlsx_prev)
        step2_compare_sources(ctx)
        assert hasattr(ctx, "comparison_added")
        assert hasattr(ctx, "comparison_removed")
        assert "Welcome" in ctx.comparison_added
        assert "Goodbye" in ctx.comparison_removed


# ═══ D6 : Étape 3 — Coquilles sur Origins (TDD) ═══


class TestStep3DetectTypos:
    """Tests de step3_detect_typos() — coquilles sur Origins avec scope."""

    def test_no_typos_detected(self, xlsx_3_langs, monkeypatch, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step3_detect_typos

        monkeypatch.setattr(
            "pipeline_dropdown.load_typos_dropdown",
            lambda: [{"typo": "XYZNonexistent", "correction": "Fixed"}],
        )
        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs)
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        step3_detect_typos(ctx)
        out = capsys.readouterr().out
        assert "Aucune coquille" in out

    def test_detects_typo_in_origin(self, xlsx_with_typo, monkeypatch, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step3_detect_typos
        from core.io_xlsx import load_dropdown_xlsx

        monkeypatch.setattr(
            "pipeline_dropdown.load_typos_dropdown",
            lambda: [{"typo": "Hiearchy", "correction": "Hierarchy", "scope": "both"}],
        )
        ctx = PipelineDropdownContext(xlsx_path=xlsx_with_typo, dry_run=True)
        ctx.entries = load_dropdown_xlsx(xlsx_with_typo)
        step3_detect_typos(ctx)
        assert len(ctx.typos_found) == 1
        assert ctx.typos_found[0]["typo"] == "Hiearchy"

    def test_scope_dropdown_detected(self):
        from pipeline_dropdown import detect_typos_in_origins

        typos = [{"typo": "Desactive", "correction": "Deactivate", "scope": "dropdown"}]
        entries = [{"origin": "Desactive button"}, {"origin": "Hello"}]
        found = detect_typos_in_origins(entries, typos)
        assert len(found) == 1
        assert found[0]["typo"] == "Desactive"

    def test_no_scope_defaults_both(self):
        from pipeline_dropdown import detect_typos_in_origins

        typos = [{"typo": "Parners", "correction": "Partners"}]
        entries = [{"origin": "Parners list"}]
        found = detect_typos_in_origins(entries, typos)
        assert len(found) == 1

    def test_dry_run_no_correction(self, xlsx_with_typo, monkeypatch, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step3_detect_typos
        from core.io_xlsx import load_dropdown_xlsx

        monkeypatch.setattr(
            "pipeline_dropdown.load_typos_dropdown",
            lambda: [{"typo": "Hiearchy", "correction": "Hierarchy", "scope": "both"}],
        )
        ctx = PipelineDropdownContext(xlsx_path=xlsx_with_typo, dry_run=True)
        ctx.entries = load_dropdown_xlsx(xlsx_with_typo)
        step3_detect_typos(ctx)
        assert ctx.typos_corrected is False
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_corrects_on_confirm_yes(self, xlsx_with_typo, monkeypatch):
        from pipeline_dropdown import PipelineDropdownContext, step3_detect_typos
        from core.io_xlsx import load_dropdown_xlsx

        monkeypatch.setattr(
            "pipeline_dropdown.load_typos_dropdown",
            lambda: [{"typo": "Hiearchy", "correction": "Hierarchy", "scope": "both"}],
        )
        ctx = PipelineDropdownContext(xlsx_path=xlsx_with_typo, interactive=True)
        ctx.entries = load_dropdown_xlsx(xlsx_with_typo)
        with patch("builtins.input", return_value="y"):
            step3_detect_typos(ctx)
        assert ctx.typos_corrected is True
        corrected_entries = load_dropdown_xlsx(xlsx_with_typo)
        origins = [e["origin"] for e in corrected_entries]
        assert "Hierarchy menu" in origins
        assert "Hiearchy menu" not in origins


# ═══ D7 : Étape 4 — Écart dropdown par langue (TDD) ═══


class TestStep4AnalyzeGap:
    """Tests de step4_analyze_gap() — écart par langue (Origins manquants)."""

    def test_detects_missing_origins_for_existing_lang(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step4_analyze_gap

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr", "pt"])
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}, {"origin": "New"}]
        ctx.existing_translations = {
            "FR": {"Hello": "Bonjour", "World": "Monde"},
            "CZ": {"Hello": "Ahoj"},
        }
        ctx.missing_languages = ["pt"]
        step4_analyze_gap(ctx)
        assert "fr" in ctx.gap_by_lang
        assert "New" in ctx.gap_by_lang["fr"]["to_translate"]
        assert ctx.gap_by_lang["fr"]["missing_count"] == 1

    def test_missing_lang_all_entries_to_translate(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step4_analyze_gap

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["pt"])
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        ctx.existing_translations = {"FR": {"Hello": "Bonjour"}}
        ctx.missing_languages = ["pt"]
        step4_analyze_gap(ctx)
        assert "pt" in ctx.gap_by_lang
        assert ctx.gap_by_lang["pt"]["missing_count"] == 2
        assert set(ctx.gap_by_lang["pt"]["to_translate"]) == {"Hello", "World"}

    def test_all_origins_present_no_gap(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step4_analyze_gap

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr"])
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        ctx.existing_translations = {"FR": {"Hello": "Bonjour", "World": "Monde"}}
        ctx.missing_languages = []
        step4_analyze_gap(ctx)
        assert ctx.gap_by_lang["fr"]["missing_count"] == 0
        assert ctx.gap_by_lang["fr"]["to_translate"] == []


# ═══ D8 : Étape 5 — Rapport + confirmation (TDD) ═══


class TestStep5ReportAndConfirm:
    """Tests de step5_report_and_confirm() — rapport + confirmation [ÉTAPE CLÉ]."""

    def test_report_has_all_sections(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step5_report_and_confirm

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["pt"])
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        ctx.gap_by_lang = {"pt": {"missing_count": 1, "to_translate": ["Hello"]}}
        ctx.interactive = False
        step5_report_and_confirm(ctx)
        out = capsys.readouterr().out
        assert "Source" in out
        assert "Écart" in out or "écart" in out
        assert "Plan" in out

    def test_dry_run_returns_false(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step5_report_and_confirm

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, dry_run=True)
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        ctx.gap_by_lang = {"pt": {"missing_count": 1, "to_translate": ["Hello"]}}
        assert step5_report_and_confirm(ctx) is False
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_non_interactive_returns_true(self, xlsx_3_langs):
        from pipeline_dropdown import PipelineDropdownContext, step5_report_and_confirm

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, interactive=False)
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        ctx.gap_by_lang = {"pt": {"missing_count": 1, "to_translate": ["Hello"]}}
        assert step5_report_and_confirm(ctx) is True

    def test_interactive_confirm_yes(self, xlsx_3_langs):
        from pipeline_dropdown import PipelineDropdownContext, step5_report_and_confirm

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, interactive=True)
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        ctx.gap_by_lang = {"pt": {"missing_count": 1, "to_translate": ["Hello"]}}
        with patch("builtins.input", return_value="y"):
            assert step5_report_and_confirm(ctx) is True

    def test_interactive_confirm_no(self, xlsx_3_langs):
        from pipeline_dropdown import PipelineDropdownContext, step5_report_and_confirm

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, interactive=True)
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        ctx.gap_by_lang = {"pt": {"missing_count": 1, "to_translate": ["Hello"]}}
        with patch("builtins.input", return_value="n"):
            assert step5_report_and_confirm(ctx) is False


# ═══ D9-D11 : Étapes 6-8 (TDD) ═══


class TestStep6Prepopulate:
    """Tests de step6_prepopulate() — pré-peuplement du dossier de sortie."""

    def test_creates_dated_folder(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step6_prepopulate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr", "pt"])
        ctx.existing_translations = {
            "EN": {"Hello": "Hello"},
            "FR": {"Hello": "Bonjour"},
        }
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        ctx.missing_languages = ["pt"]
        ctx.interactive = False
        result = step6_prepopulate(ctx)
        assert result is not None
        assert result.exists()

    def test_dry_run_skips(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step6_prepopulate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, dry_run=True)
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        result = step6_prepopulate(ctx)
        assert result is None
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_interactive_confirm_yes(self, xlsx_3_langs):
        from pipeline_dropdown import PipelineDropdownContext, step6_prepopulate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, interactive=True)
        ctx.existing_translations = {
            "EN": {"Hello": "Hello"},
            "FR": {"Hello": "Bonjour"},
        }
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        with patch("builtins.input", return_value="y"):
            result = step6_prepopulate(ctx)
        assert result is not None
        assert result.exists()

    def test_interactive_confirm_no_aborts(self, xlsx_3_langs):
        from pipeline_dropdown import PipelineDropdownContext, step6_prepopulate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, interactive=True)
        ctx.existing_translations = {"EN": {"Hello": "Hello"}}
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        with patch("builtins.input", return_value="n"):
            result = step6_prepopulate(ctx)
        assert result is None


class TestStep7Translate:
    """Tests de step7_translate() — traduction avec réutilisation colonne B."""

    def test_translates_missing_languages(self, xlsx_3_langs, monkeypatch, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step7_translate

        ctx = PipelineDropdownContext(
            xlsx_path=xlsx_3_langs, languages=["pt"], provider="google"
        )
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        ctx.missing_languages = ["pt"]
        ctx.existing_translations = {"EN": {"Hello": "Hello", "World": "World"}}
        ctx.gap_by_lang = {
            "pt": {
                "missing_count": 2,
                "to_translate": ["Hello", "World"],
                "total": 2,
                "existing": 0,
            }
        }

        calls = []

        def fake_translate_batch(entries, lang, existing, **kw):
            calls.append(lang)
            return {e["origin"]: f"[{lang}] {e['origin']}" for e in entries}

        monkeypatch.setattr(
            "pipeline_dropdown._translate_dropdown_batch", fake_translate_batch
        )
        step7_translate(ctx)
        assert "pt" in calls

    def test_dry_run_skips(self, xlsx_3_langs, monkeypatch, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step7_translate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, dry_run=True)
        ctx.entries = [{"origin": "Hello"}]
        ctx.missing_languages = ["pt"]
        ctx.gap_by_lang = {
            "pt": {
                "missing_count": 1,
                "to_translate": ["Hello"],
                "total": 1,
                "existing": 0,
            }
        }
        monkeypatch.setattr(
            "pipeline_dropdown._translate_dropdown_batch", lambda *a, **kw: {}
        )
        step7_translate(ctx)
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_reuses_existing_translations(self, xlsx_3_langs, monkeypatch):
        """Les langues déjà présentes ne sont PAS re-traduites (cache col B)."""
        from pipeline_dropdown import PipelineDropdownContext, step7_translate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr", "pt"])
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        ctx.missing_languages = ["pt"]
        ctx.existing_translations = {
            "EN": {"Hello": "Hello", "World": "World"},
            "FR": {"Hello": "Bonjour", "World": "Monde"},
        }
        ctx.gap_by_lang = {
            "fr": {"missing_count": 0, "to_translate": [], "total": 2, "existing": 2},
            "pt": {
                "missing_count": 2,
                "to_translate": ["Hello", "World"],
                "total": 2,
                "existing": 0,
            },
        }

        calls = []
        monkeypatch.setattr(
            "pipeline_dropdown._translate_dropdown_batch",
            lambda *a, **kw: calls.append(a[1]) or {},
        )
        step7_translate(ctx)
        assert "fr" not in calls
        assert "pt" in calls

    def test_no_languages_skips(self, xlsx_3_langs, monkeypatch, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step7_translate

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=[])
        ctx.entries = []
        ctx.missing_languages = []
        ctx.gap_by_lang = {}
        called = []
        monkeypatch.setattr(
            "pipeline_dropdown._translate_dropdown_batch",
            lambda *a, **kw: called.append(1) or {},
        )
        step7_translate(ctx)
        assert called == []


class TestStep8Reorder:
    """Tests de step8_reorder() — réordonnancement par Origin source."""

    def test_reorders_xlsx_by_origin(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step8_reorder

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr"])
        ctx.entries = [{"origin": "Hello"}, {"origin": "World"}]
        ctx.output_dir = xlsx_3_langs.parent / "test_reorder_output"
        ctx.output_dir.mkdir(exist_ok=True)
        step8_reorder(ctx)
        out = capsys.readouterr().out
        assert "ÉTAPE 8" in out

    def test_dry_run_skips(self, xlsx_3_langs, capsys):
        from pipeline_dropdown import PipelineDropdownContext, step8_reorder

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, dry_run=True)
        ctx.entries = [{"origin": "Hello"}]
        ctx.output_dir = xlsx_3_langs.parent
        step8_reorder(ctx)
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()
