"""
Tests pour le pipeline dropdown (TDD strict).

Couvre :
- D3 : load_dropdown_xlsx_all_sheets() + detect_missing_languages() (io_xlsx)
- D4 : PipelineDropdownContext + build_parser_dropdown() + flags (pipeline_dropdown)
- D5 : Étapes 1-2 — Détection XLSX + comparaison (pipeline_dropdown)
- D6-D14 : étapes 3-11 du pipeline dropdown (à venir)
"""

import openpyxl
import pytest

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
    """XLSX nouveau : 3 feuilles (EN/FR/CZ), Origins = Hello, World, Welcome.

    Goodbye supprimé, Welcome ajouté vs xlsx_prev.
    """
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


# ═══ D3 : load_dropdown_xlsx_all_sheets + detect_missing_languages ═══


class TestLoadDropdownXlsxAllSheets:
    """Tests de load_dropdown_xlsx_all_sheets() — lit toutes les feuilles."""

    def test_returns_dict_lang_to_translations(self, xlsx_3_langs):
        """Retourne un dict {lang: {origin: traduction}}."""
        from core.io_xlsx import load_dropdown_xlsx_all_sheets

        result = load_dropdown_xlsx_all_sheets(xlsx_3_langs)
        assert "EN" in result
        assert "FR" in result
        assert "CZ" in result
        assert result["FR"]["Hello"] == "Bonjour"
        assert result["FR"]["World"] == "Monde"
        assert result["EN"]["Hello"] == "Hello"

    def test_empty_rows_skipped(self, xlsx_3_langs):
        """Les lignes vides (Origin vide) ne sont pas incluses."""
        from core.io_xlsx import load_dropdown_xlsx_all_sheets

        result = load_dropdown_xlsx_all_sheets(xlsx_3_langs)
        assert len(result["FR"]) == 2

    def test_only_header_row(self, xlsx_empty):
        """Une feuille avec uniquement l'en-tête retourne un dict vide."""
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
        """3 feuilles (EN/FR/CZ) + 9 langues configurées → 6 manquantes."""
        from core.io_xlsx import detect_missing_languages

        configured = ["fr", "cz", "sk", "de", "it", "ar", "pt", "es", "hu"]
        missing = detect_missing_languages(xlsx_3_langs, configured)
        assert sorted(missing) == ["ar", "de", "es", "hu", "it", "pt", "sk"]

    def test_all_present_returns_empty(self, xlsx_3_langs):
        from core.io_xlsx import detect_missing_languages

        missing = detect_missing_languages(xlsx_3_langs, ["fr", "cz"])
        assert missing == []

    def test_case_insensitive_sheet_names(self, xlsx_3_langs):
        """Les noms de feuilles sont comparés en majuscules (EN/fr/cz → match)."""
        from core.io_xlsx import detect_missing_languages

        missing = detect_missing_languages(xlsx_3_langs, ["fr", "cz", "sk"])
        assert missing == ["sk"]

    def test_en_excluded_from_missing(self, xlsx_3_langs):
        """EN est la source, jamais 'manquante'."""
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
        """Hérite des champs communs de BasePipelineContext."""
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
    """Tests de run_pipeline_dropdown() — squelette (étapes à venir en D5+)."""

    def test_dry_run_returns_zero(self, xlsx_3_langs, monkeypatch, capsys):
        """Dry-run sans source → message + rc 0."""
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
        """Step1 charge existing_translations depuis les feuilles par langue."""
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["pt"])
        step1_detect_source(ctx)
        assert "FR" in ctx.existing_translations
        assert ctx.existing_translations["FR"]["Hello"] == "Bonjour"
        assert "CZ" in ctx.existing_translations

    def test_detects_missing_languages(self, xlsx_3_langs, capsys):
        """Step1 détecte les langues manquantes vs les langues configurées."""
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(
            xlsx_path=xlsx_3_langs, languages=["fr", "cz", "pt", "es"]
        )
        step1_detect_source(ctx)
        assert sorted(ctx.missing_languages) == ["es", "pt"]

    def test_loads_entries(self, xlsx_3_langs, capsys):
        """Step1 charge les entries (Origin/French/Context) depuis la feuille active."""
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["pt"])
        step1_detect_source(ctx)
        assert len(ctx.entries) == 2  # Hello, World
        origins = [e["origin"] for e in ctx.entries]
        assert "Hello" in origins and "World" in origins

    def test_source_missing_raises(self, tmp_path, capsys):
        """Source inexistante → FileNotFoundError."""
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=tmp_path / "absent.xlsx")
        with pytest.raises(FileNotFoundError):
            step1_detect_source(ctx)

    def test_all_languages_present_no_missing(self, xlsx_3_langs, capsys):
        """Toutes les langues configurées sont déjà dans le XLSX → missing vide."""
        from pipeline_dropdown import PipelineDropdownContext, step1_detect_source

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs, languages=["fr", "cz"])
        step1_detect_source(ctx)
        assert ctx.missing_languages == []


class TestStep2CompareSources:
    """Tests de step2_compare_sources() — comparaison par Origin (skip si pas de précédent)."""

    def test_skips_without_prev(self, xlsx_3_langs, capsys):
        """Sans XLSX précédent → étape skippée."""
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_3_langs)
        step2_compare_sources(ctx)
        out = capsys.readouterr().out
        assert "ignorée" in out.lower() or "skip" in out.lower()

    def test_detects_added_origins(self, xlsx_prev, xlsx_new, capsys):
        """Origins ajoutés (Welcome) détectés."""
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_new, prev_xlsx_path=xlsx_prev)
        step2_compare_sources(ctx)
        out = capsys.readouterr().out
        assert "Welcome" in out or "ajout" in out.lower()

    def test_detects_removed_origins(self, xlsx_prev, xlsx_new, capsys):
        """Origins supprimés (Goodbye) détectés."""
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_new, prev_xlsx_path=xlsx_prev)
        step2_compare_sources(ctx)
        out = capsys.readouterr().out
        assert "Goodbye" in out or "supprim" in out.lower()

    def test_populates_comparison_results(self, xlsx_prev, xlsx_new):
        """La comparaison remplit ctx avec added/removed/unchanged."""
        from pipeline_dropdown import PipelineDropdownContext, step2_compare_sources

        ctx = PipelineDropdownContext(xlsx_path=xlsx_new, prev_xlsx_path=xlsx_prev)
        step2_compare_sources(ctx)
        assert hasattr(ctx, "comparison_added")
        assert hasattr(ctx, "comparison_removed")
        assert "Welcome" in ctx.comparison_added
        assert "Goodbye" in ctx.comparison_removed
