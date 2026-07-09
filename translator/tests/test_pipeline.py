"""
Characterization tests for translator/pipeline.py — Phase 1 (étapes 1-5).

Ces tests figent le comportement existant du pipeline (développé sans TDD)
pour servir de filet de sécurité avant d'entamer la Phase 2 en TDD strict.

Couverture visée : ≥ 90% sur pipeline.py.

Organisation : une classe `TestXxx` par fonction publique/privée, cohérent
avec les conventions de la suite existante (test_cli, test_translator, ...).
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# compare_sources.py et analyze_translation_gap.py vivent à la racine du dépôt
# (hors translator/). On ajoute la racine au sys.path pour les rendre
# importables. En Docker (seul translator/ est monté), l'import échoue et
# importorskip saute proprement toute la classe de tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
pytest.importorskip("compare_sources")
pytest.importorskip("analyze_translation_gap")

import pipeline  # noqa: E402
from pipeline import (  # noqa: E402
    PipelineContext,
    _latest_export_dir,
    _list_import_folders,
    _pick_source_in_import,
    apply_typo_corrections,
    backup_translation_file,
    build_analysis_report,
    build_parser,
    confirm,
    detect_typos_in_source,
    load_typos,
    manage_modified_keys,
    prepopulate_output,
    reorder_translation_file,
    run_pipeline,
    step1_detect_sources,
    step2_compare_sources,
    step3_detect_typos,
    step4_analyze_gap,
    step5_report_and_confirm,
    step6_prepopulate_and_manage,
    step7_translate,
    step8_reorder,
    step_banner,
)

# ─── Fixtures : arborescence de test ────────────────────────────────


@pytest.fixture
def fake_translator_dir(tmp_path):
    """Construit un translator/ factice avec 2 imports + 1 export + 2 langues.

    Layout :
        tmp_path/source/2026_06_25_Import/en 9.json   (3 clés)
        tmp_path/source/2026_07_08_Import/en 10.json  (4 clés, dont coquille "Hiearchy")
        tmp_path/output/2026_07_08_Export/translation_en_fr.json
        tmp_path/output/2026_07_08_Export/translation_en_de.json
    """
    src = tmp_path / "source"
    src.mkdir()
    old_imp = src / "2026_06_25_Import"
    new_imp = src / "2026_07_08_Import"
    old_imp.mkdir()
    new_imp.mkdir()

    (old_imp / "en 9.json").write_text(
        json.dumps(
            {"K1": "Hello", "K2": "World", "K3": "Pairing Error"}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    (new_imp / "en 10.json").write_text(
        json.dumps(
            {
                "K1": "Hello",
                "K2": "Goodbye",  # K2 modifiée
                "K4": "New key",  # K4 ajoutée
                "K5": "Hiearchy menu",  # coquille "Hiearchy"
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out = tmp_path / "output"
    out.mkdir()
    exp = out / "2026_07_08_Export"
    exp.mkdir()
    (exp / "translation_en_fr.json").write_text(
        json.dumps(
            {"K1": "Bonjour", "K2": "Monde", "K3": "Appairage"}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    (exp / "translation_en_de.json").write_text(
        json.dumps({"K1": "Hallo", "K2": "Welt", "K3": "Kopplung"}, ensure_ascii=False),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def fake_typos_file(tmp_path):
    """Dictionnaire de coquilles de test (1 entrée : Hiearchy)."""
    p = tmp_path / "source_typos.json"
    p.write_text(
        json.dumps(
            {
                "typos": [
                    {
                        "typo": "Hiearchy",
                        "correction": "Hierarchy",
                        "first_seen_key": "K5",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def patched_translator_dir(fake_translator_dir, monkeypatch):
    """Monkeypatche pipeline.TRANSLATOR_DIR et TYPHOS_PATH vers le fs de test."""
    monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", fake_translator_dir)
    monkeypatch.setattr(
        pipeline, "TYPHOS_PATH", fake_translator_dir / "source_typos.json"
    )
    return fake_translator_dir


# ─── TestPipelineContext ────────────────────────────────────────────


class TestPipelineContext:
    """Tests des valeurs par défaut du dataclass PipelineContext."""

    def test_defaults(self):
        ctx = PipelineContext()
        assert ctx.new_source is None
        assert ctx.prev_source is None
        assert ctx.export_dir is None
        assert ctx.provider == "hybride"
        assert ctx.dry_run is False
        assert ctx.interactive is True
        assert ctx.report_path is None
        assert ctx.comparison is None
        assert ctx.typos_found == []
        assert ctx.typos_corrected is False
        assert ctx.gaps == []

    def test_languages_default_all_except_en(self):
        ctx = PipelineContext()
        assert "en" not in ctx.languages
        assert "fr" in ctx.languages
        assert "de" in ctx.languages

    def test_languages_independent_per_instance(self):
        """Les listes default_factory sont indépendantes entre instances."""
        a = PipelineContext()
        b = PipelineContext()
        a.languages.append("xx")
        assert "xx" not in b.languages


# ─── TestConfirm ───────────────────────────────────────────────────


class TestConfirm:
    """Tests de la fonction confirm() — gestion de l'interactivité."""

    def test_non_interactive_returns_default_true(self):
        ctx = PipelineContext(interactive=False)
        assert confirm(ctx, "Continue?", default=True) is True

    def test_non_interactive_returns_default_false(self):
        ctx = PipelineContext(interactive=False)
        assert confirm(ctx, "Continue?", default=False) is False

    @pytest.mark.parametrize(
        "answer,expected",
        [("y", True), ("yes", True), ("o", True), ("oui", True), ("Y", True)],
    )
    def test_yes_answers(self, answer, expected):
        ctx = PipelineContext(interactive=True)
        with patch("builtins.input", return_value=answer):
            assert confirm(ctx, "Ok?", default=False) is expected

    @pytest.mark.parametrize(
        "answer,expected",
        [("n", False), ("no", False), ("non", False), ("N", False)],
    )
    def test_no_answers(self, answer, expected):
        ctx = PipelineContext(interactive=True)
        with patch("builtins.input", return_value=answer):
            assert confirm(ctx, "Ok?", default=True) is expected

    def test_empty_answer_returns_default(self):
        ctx = PipelineContext(interactive=True)
        with patch("builtins.input", return_value=""):
            assert confirm(ctx, "Ok?", default=True) is True
            assert confirm(ctx, "Ok?", default=False) is False

    def test_eof_returns_default(self):
        """EOFError (stdin fermé) retourne le défaut."""
        ctx = PipelineContext(interactive=True)
        with patch("builtins.input", side_effect=EOFError):
            assert confirm(ctx, "Ok?", default=True) is True

    def test_whitespace_only_answer_returns_default(self):
        ctx = PipelineContext(interactive=True)
        with patch("builtins.input", return_value="   "):
            assert confirm(ctx, "Ok?", default=True) is True


# ─── TestStepBanner ─────────────────────────────────────────────────


class TestStepBanner:
    """Tests du formatage du bandeau d'étape."""

    def test_banner_prints_step_number_and_title(self, capsys):
        step_banner(3, "Détection coquilles")
        out = capsys.readouterr().out
        assert "ÉTAPE 3" in out
        assert "Détection coquilles" in out

    def test_banner_starts_with_blank_line(self, capsys):
        step_banner(1, "Test")
        out = capsys.readouterr().out
        assert out.startswith("\n")


# ─── TestListImportFolders ──────────────────────────────────────────


class TestListImportFolders:
    """Tests de _list_import_folders() — tri décroissant et filtrage."""

    def test_sorted_descending(self, fake_translator_dir):
        src = fake_translator_dir / "source"
        folders = _list_import_folders(src)
        assert len(folders) == 2
        assert folders[0].name == "2026_07_08_Import"
        assert folders[1].name == "2026_06_25_Import"

    def test_ignores_non_matching_dirs(self, tmp_path):
        """Les dossiers ne respectant pas le pattern YYYY_MM_DD_Import sont ignorés."""
        (tmp_path / "2026_07_08_Export").mkdir()
        (tmp_path / "random_dir").mkdir()
        (tmp_path / "2026_13_01_Import").mkdir()  # mois 13 mais pattern ok
        folders = _list_import_folders(tmp_path)
        names = [f.name for f in folders]
        assert "random_dir" not in names
        assert "2026_07_08_Export" not in names
        assert "2026_13_01_Import" in names  # le pattern ne valide pas le mois

    def test_empty_when_dir_missing(self, tmp_path):
        assert _list_import_folders(tmp_path / "nonexistent") == []

    def test_ignores_files_not_dirs(self, tmp_path):
        (tmp_path / "2026_07_08_Import").mkdir()
        (tmp_path / "2026_09_01_Import.json").write_text("{}", encoding="utf-8")
        folders = _list_import_folders(tmp_path)
        assert len(folders) == 1
        assert folders[0].name == "2026_07_08_Import"


# ─── TestPickSourceInImport ─────────────────────────────────────────


class TestPickSourceInImport:
    """Tests de _pick_source_in_import() — détection du fichier source EN."""

    def test_finds_en_source(self, fake_translator_dir):
        new_imp = fake_translator_dir / "source" / "2026_07_08_Import"
        src = _pick_source_in_import(new_imp)
        assert src is not None
        assert "en 10" in src.name

    def test_returns_none_when_no_json(self, tmp_path):
        empty_imp = tmp_path / "2026_01_01_Import"
        empty_imp.mkdir()
        assert _pick_source_in_import(empty_imp) is None

    def test_returns_none_when_no_en_file(self, tmp_path):
        """Un dossier avec un JSON ne contenant pas 'en' dans le stem retourne None."""
        imp = tmp_path / "2026_01_01_Import"
        imp.mkdir()
        (imp / "fr.json").write_text("{}", encoding="utf-8")
        assert _pick_source_in_import(imp) is None


# ─── TestLatestExportDir ────────────────────────────────────────────


class TestLatestExportDir:
    """Tests de _latest_export_dir() — détection du dernier *_Export."""

    def test_returns_most_recent(self, fake_translator_dir):
        out = fake_translator_dir / "output"
        latest = _latest_export_dir(out)
        assert latest is not None
        assert latest.name == "2026_07_08_Export"

    def test_returns_none_when_no_export(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        assert _latest_export_dir(out) is None

    def test_returns_none_when_dir_missing(self, tmp_path):
        assert _latest_export_dir(tmp_path / "nonexistent") is None

    def test_ignores_import_folders(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        (out / "2026_07_08_Import").mkdir()
        assert _latest_export_dir(out) is None


# ─── TestLoadTypos ──────────────────────────────────────────────────


class TestLoadTypos:
    """Tests de load_typos() — chargement du dictionnaire de coquilles."""

    def test_loads_typos_list(self, fake_typos_file):
        typos = load_typos(fake_typos_file)
        assert len(typos) == 1
        assert typos[0]["typo"] == "Hiearchy"
        assert typos[0]["correction"] == "Hierarchy"

    def test_returns_empty_when_file_missing(self, tmp_path):
        assert load_typos(tmp_path / "absent.json") == []

    def test_returns_empty_when_no_typos_key(self, tmp_path):
        p = tmp_path / "typos.json"
        p.write_text(json.dumps({"other": []}), encoding="utf-8")
        assert load_typos(p) == []


# ─── TestDetectTyposInSource ────────────────────────────────────────


class TestDetectTyposInSource:
    """Tests de detect_typos_in_source() — détection des coquilles connues."""

    def test_detects_known_typo(self, tmp_path):
        src = tmp_path / "en.json"
        src.write_text(
            json.dumps({"K1": "Hiearchy menu", "K2": "Clean"}), encoding="utf-8"
        )
        typos = [{"typo": "Hiearchy", "correction": "Hierarchy"}]
        found = detect_typos_in_source(src, typos)
        assert len(found) == 1
        assert found[0]["typo"] == "Hiearchy"
        assert found[0]["correction"] == "Hierarchy"
        assert "K1" in found[0]["keys"]

    def test_no_typo_returns_empty(self, tmp_path):
        src = tmp_path / "en.json"
        src.write_text(json.dumps({"K1": "Clean text"}), encoding="utf-8")
        typos = [{"typo": "Hiearchy", "correction": "Hierarchy"}]
        assert detect_typos_in_source(src, typos) == []

    def test_multiple_keys_affected(self, tmp_path):
        """Une coquille présente dans plusieurs clés est listée pour chacune."""
        src = tmp_path / "en.json"
        src.write_text(
            json.dumps({"K1": "Hiearchy a", "K2": "Hiearchy b", "K3": "ok"}),
            encoding="utf-8",
        )
        typos = [{"typo": "Hiearchy", "correction": "Hierarchy"}]
        found = detect_typos_in_source(src, typos)
        assert len(found) == 1
        assert sorted(found[0]["keys"]) == ["K1", "K2"]

    def test_multiple_typos(self, tmp_path):
        src = tmp_path / "en.json"
        src.write_text(
            json.dumps({"K1": "Hiearchy", "K2": "TItle here"}),
            encoding="utf-8",
        )
        typos = [
            {"typo": "Hiearchy", "correction": "Hierarchy"},
            {"typo": "TItle", "correction": "Title"},
        ]
        found = detect_typos_in_source(src, typos)
        assert len(found) == 2

    def test_ignores_non_string_values(self, tmp_path):
        """Les valeurs non-strings (int, null) sont ignorées."""
        src = tmp_path / "en.json"
        src.write_text(
            json.dumps({"K1": 42, "K2": None, "K3": "Hiearchy"}),
            encoding="utf-8",
        )
        typos = [{"typo": "Hiearchy", "correction": "Hierarchy"}]
        found = detect_typos_in_source(src, typos)
        assert len(found) == 1
        assert found[0]["keys"] == ["K3"]

    def test_empty_typos_list(self, tmp_path):
        src = tmp_path / "en.json"
        src.write_text(json.dumps({"K1": "Hiearchy"}), encoding="utf-8")
        assert detect_typos_in_source(src, []) == []


# ─── TestApplyTypoCorrections ───────────────────────────────────────


class TestApplyTypoCorrections:
    """Tests de apply_typo_corrections() — correction du fichier source."""

    def test_corrects_and_counts(self, tmp_path):
        src = tmp_path / "en.json"
        src.write_text(
            json.dumps({"K1": "Hiearchy menu", "K2": "clean"}),
            encoding="utf-8",
        )
        typos_found = [{"typo": "Hiearchy", "correction": "Hierarchy", "keys": ["K1"]}]
        count = apply_typo_corrections(src, typos_found)
        assert count == 1
        data = json.loads(src.read_text(encoding="utf-8"))
        assert data["K1"] == "Hierarchy menu"
        assert data["K2"] == "clean"

    def test_preserves_unaffected_keys(self, tmp_path):
        src = tmp_path / "en.json"
        original = {"K1": "Hello", "K2": "World", "K3": "Other"}
        src.write_text(json.dumps(original), encoding="utf-8")
        typos_found = [{"typo": "AbsentTypo", "correction": "X", "keys": []}]
        count = apply_typo_corrections(src, typos_found)
        assert count == 0
        data = json.loads(src.read_text(encoding="utf-8"))
        assert data == original

    def test_empty_typos_found(self, tmp_path):
        src = tmp_path / "en.json"
        src.write_text(json.dumps({"K1": "Hi"}), encoding="utf-8")
        assert apply_typo_corrections(src, []) == 0


# ─── TestStep1DetectSources ─────────────────────────────────────────


class TestStep1DetectSources:
    """Tests de step1_detect_sources() — auto-détection et overrides."""

    def test_auto_detect_new_and_prev(self, patched_translator_dir, capsys):
        ctx = PipelineContext()
        step1_detect_sources(ctx)
        assert ctx.new_source is not None
        assert "en 10" in ctx.new_source.name
        assert ctx.new_import_folder.name == "2026_07_08_Import"
        assert ctx.prev_source is not None
        assert "en 9" in ctx.prev_source.name
        assert ctx.prev_import_folder.name == "2026_06_25_Import"
        assert ctx.export_dir is not None
        assert ctx.export_dir.name == "2026_07_08_Export"
        out = capsys.readouterr().out
        assert "2545" not in out  # notre source de test a 4 clés, pas 2545
        assert "4" in out  # nombre de clés de en 10.json

    def test_override_new_source(self, patched_translator_dir, tmp_path, capsys):
        custom = tmp_path / "custom.json"
        custom.write_text(json.dumps({"X": "x"}), encoding="utf-8")
        ctx = PipelineContext(new_source=custom)
        step1_detect_sources(ctx)
        assert ctx.new_source == custom
        assert ctx.new_import_folder == tmp_path
        out = capsys.readouterr().out
        assert "override" in out.lower()

    def test_override_new_source_missing_raises(self, patched_translator_dir, tmp_path):
        ctx = PipelineContext(new_source=tmp_path / "absent.json")
        with pytest.raises(FileNotFoundError, match="introuvable"):
            step1_detect_sources(ctx)

    def test_override_prev_source(self, patched_translator_dir, tmp_path, capsys):
        prev = tmp_path / "old.json"
        prev.write_text(json.dumps({"Y": "y"}), encoding="utf-8")
        ctx = PipelineContext(prev_source=prev)
        step1_detect_sources(ctx)
        assert ctx.prev_source == prev
        out = capsys.readouterr().out
        assert "précédente (ovr)" in out

    def test_override_prev_source_missing_raises(
        self, patched_translator_dir, tmp_path
    ):
        ctx = PipelineContext(prev_source=tmp_path / "absent.json")
        with pytest.raises(FileNotFoundError, match="introuvable"):
            step1_detect_sources(ctx)

    def test_no_import_folders_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", tmp_path)
        ctx = PipelineContext()
        with pytest.raises(FileNotFoundError, match="Aucun dossier \\*_Import"):
            step1_detect_sources(ctx)

    def test_no_previous_source_warns(self, tmp_path, monkeypatch, capsys):
        """Un seul dossier *_Import → pas de source précédente (warning, pas d'erreur)."""
        src = tmp_path / "source"
        src.mkdir()
        imp = src / "2026_07_08_Import"
        imp.mkdir()
        (imp / "en 10.json").write_text(json.dumps({"K": "v"}), encoding="utf-8")
        out = tmp_path / "output"
        out.mkdir()
        (out / "2026_07_08_Export").mkdir()
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", tmp_path)
        ctx = PipelineContext()
        step1_detect_sources(ctx)
        assert ctx.prev_source is None
        captured = capsys.readouterr().out
        assert "Aucune source précédente" in captured

    def test_no_export_warns(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "source"
        src.mkdir()
        (src / "2026_07_08_Import").mkdir()
        (src / "2026_07_08_Import" / "en 10.json").write_text(
            json.dumps({"K": "v"}), encoding="utf-8"
        )
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", tmp_path)
        ctx = PipelineContext()
        step1_detect_sources(ctx)
        assert ctx.export_dir is None
        captured = capsys.readouterr().out
        assert "Aucun dossier *_Export" in captured


# ─── TestStep2CompareSources ────────────────────────────────────────


class TestStep2CompareSources:
    """Tests de step2_compare_sources() — avec et sans source précédente."""

    def test_compare_populates_comparison(self, patched_translator_dir, capsys):
        ctx = PipelineContext()
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        assert ctx.comparison is not None
        c = ctx.comparison
        assert len(c.added) == 2  # K4, K5
        assert len(c.removed) == 1  # K3
        assert len(c.modified) == 1  # K2 World→Goodbye
        out = capsys.readouterr().out
        assert "Ajoutées" in out

    def test_skips_when_no_prev_source(self, capsys):
        ctx = PipelineContext(prev_source=None)
        step2_compare_sources(ctx)
        assert ctx.comparison is None
        out = capsys.readouterr().out
        assert "ignorée" in out


# ─── TestStep3DetectTypos ───────────────────────────────────────────


class TestStep3DetectTypos:
    """Tests de step3_detect_typos() — détection + correction interactive."""

    def test_no_dictionary_warns(self, tmp_path, monkeypatch, capsys):
        """Pas de dictionnaire de coquilles → message d'absence, pas d'erreur."""
        monkeypatch.setattr(pipeline, "load_typos", lambda path=None: [])
        src = tmp_path / "en.json"
        src.write_text(json.dumps({"K": "v"}), encoding="utf-8")
        ctx = PipelineContext(new_source=src)
        step3_detect_typos(ctx)
        assert ctx.typos_found == []
        out = capsys.readouterr().out
        assert "Aucun dictionnaire" in out

    def test_no_typo_found(
        self, patched_translator_dir, fake_typos_file, monkeypatch, capsys
    ):
        """Source sans coquille connue → message OK."""
        monkeypatch.setattr(pipeline, "TYPHOS_PATH", fake_typos_file)
        ctx = PipelineContext()
        step1_detect_sources(ctx)
        # La source en 10 contient "Hiearchy" — remplaçons-la par une source propre
        clean_src = ctx.new_source.parent / "en clean.json"
        clean_src.write_text(json.dumps({"K1": "Hierarchy ok"}), encoding="utf-8")
        ctx.new_source = clean_src
        step3_detect_typos(ctx)
        assert ctx.typos_found == []
        out = capsys.readouterr().out
        assert "Aucune coquille connue" in out

    def test_dry_run_no_correction(
        self, patched_translator_dir, fake_typos_file, monkeypatch, capsys
    ):
        """En dry-run, les coquilles sont détectées mais non corrigées."""
        monkeypatch.setattr(pipeline, "TYPHOS_PATH", fake_typos_file)
        ctx = PipelineContext(dry_run=True)
        step1_detect_sources(ctx)
        original = json.loads(ctx.new_source.read_text(encoding="utf-8"))
        step3_detect_typos(ctx)
        assert len(ctx.typos_found) == 1
        assert ctx.typos_corrected is False
        # fichier non modifié
        after = json.loads(ctx.new_source.read_text(encoding="utf-8"))
        assert after == original
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_corrects_on_confirm_yes(
        self, patched_translator_dir, fake_typos_file, monkeypatch, capsys
    ):
        """Confirmation oui → le fichier source est corrigé."""
        monkeypatch.setattr(pipeline, "TYPHOS_PATH", fake_typos_file)
        ctx = PipelineContext(interactive=True)
        step1_detect_sources(ctx)
        with patch("builtins.input", return_value="y"):
            step3_detect_typos(ctx)
        assert ctx.typos_corrected is True
        data = json.loads(ctx.new_source.read_text(encoding="utf-8"))
        assert "Hiearchy" not in json.dumps(data)
        assert "Hierarchy" in data["K5"]

    def test_no_correction_on_confirm_no(
        self, patched_translator_dir, fake_typos_file, monkeypatch, capsys
    ):
        """Confirmation non → le fichier source n'est pas modifié."""
        monkeypatch.setattr(pipeline, "TYPHOS_PATH", fake_typos_file)
        ctx = PipelineContext(interactive=True)
        step1_detect_sources(ctx)
        original = json.loads(ctx.new_source.read_text(encoding="utf-8"))
        with patch("builtins.input", return_value="n"):
            step3_detect_typos(ctx)
        assert ctx.typos_corrected is False
        after = json.loads(ctx.new_source.read_text(encoding="utf-8"))
        assert after == original


# ─── TestStep4AnalyzeGap ────────────────────────────────────────────


class TestStep4AnalyzeGap:
    """Tests de step4_analyze_gap() — analyse d'écart par langue."""

    def test_analyze_populates_gaps(self, patched_translator_dir, capsys):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step4_analyze_gap(ctx)
        assert len(ctx.gaps) == 2
        fr_gap = next(g for g in ctx.gaps if g.lang == "fr")
        assert "K4" in fr_gap.to_add
        assert "K5" in fr_gap.to_add
        assert "K3" in fr_gap.to_remove
        assert "K2" in fr_gap.to_modify
        out = capsys.readouterr().out
        assert "fr" in out and "de" in out

    def test_skips_when_no_export(self, capsys):
        ctx = PipelineContext(export_dir=None)
        step4_analyze_gap(ctx)
        assert ctx.gaps == []
        out = capsys.readouterr().out
        assert "ignorée" in out

    def test_skips_when_no_prev_source(self, capsys):
        ctx = PipelineContext(export_dir=Path("/tmp"), prev_source=None)
        step4_analyze_gap(ctx)
        assert ctx.gaps == []
        out = capsys.readouterr().out
        assert "ignorée" in out


# ─── TestBuildAnalysisReport ───────────────────────────────────────


class TestBuildAnalysisReport:
    """Tests de build_analysis_report() — génération du rapport markdown."""

    def test_report_has_all_sections(
        self, patched_translator_dir, fake_typos_file, monkeypatch
    ):
        monkeypatch.setattr(pipeline, "TYPHOS_PATH", fake_typos_file)
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        with patch("builtins.input", return_value="n"):
            step3_detect_typos(ctx)
        step4_analyze_gap(ctx)
        report = build_analysis_report(ctx)
        assert "## 1. Source détectée" in report
        assert "## 2. Comparaison des sources" in report
        assert "## 3. Coquilles source détectées" in report
        assert "## 4. Écart de traduction" in report
        assert "## 5. Plan d'action" in report

    def test_report_includes_provider_and_languages(self):
        ctx = PipelineContext(provider="ollama", languages=["fr"])
        report = build_analysis_report(ctx)
        assert "ollama" in report
        assert "fr" in report

    def test_report_without_comparison(self, tmp_path):
        """Rapport généré même sans comparaison (pas de source précédente)."""
        src = tmp_path / "en.json"
        src.write_text(json.dumps({"K": "v"}), encoding="utf-8")
        ctx = PipelineContext(new_source=src)
        report = build_analysis_report(ctx)
        assert "comparaison ignorée" in report.lower()

    def test_report_without_gaps(self, tmp_path):
        """Rapport généré même sans écart (pas d'export)."""
        src = tmp_path / "en.json"
        src.write_text(json.dumps({"K": "v"}), encoding="utf-8")
        ctx = PipelineContext(new_source=src)
        report = build_analysis_report(ctx)
        assert "écart non calculé" in report.lower()

    def test_report_action_plan_counts(self, patched_translator_dir):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        step4_analyze_gap(ctx)
        report = build_analysis_report(ctx)
        assert "Ajouter" in report
        assert "Retraduire" in report


# ─── TestStep5ReportAndConfirm ──────────────────────────────────────


class TestStep5ReportAndConfirm:
    """Tests de step5_report_and_confirm() — rapport + confirmation."""

    def test_dry_run_returns_false(self, patched_translator_dir, capsys):
        ctx = PipelineContext(dry_run=True, languages=["fr"])
        step1_detect_sources(ctx)
        assert step5_report_and_confirm(ctx) is False
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_non_interactive_returns_true(self, patched_translator_dir):
        ctx = PipelineContext(interactive=False, languages=["fr"])
        step1_detect_sources(ctx)
        assert step5_report_and_confirm(ctx) is True

    def test_interactive_confirm_yes(self, patched_translator_dir):
        ctx = PipelineContext(interactive=True, languages=["fr"])
        step1_detect_sources(ctx)
        with patch("builtins.input", return_value="y"):
            assert step5_report_and_confirm(ctx) is True

    def test_interactive_confirm_no(self, patched_translator_dir):
        ctx = PipelineContext(interactive=True, languages=["fr"])
        step1_detect_sources(ctx)
        with patch("builtins.input", return_value="n"):
            assert step5_report_and_confirm(ctx) is False

    def test_writes_report_to_file(self, patched_translator_dir, tmp_path, capsys):
        report_file = tmp_path / "report.md"
        ctx = PipelineContext(report_path=report_file, dry_run=True, languages=["fr"])
        step1_detect_sources(ctx)
        step5_report_and_confirm(ctx)
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "Rapport d'analyse" in content
        out = capsys.readouterr().out
        assert "Rapport écrit" in out


# ─── TestBuildParser ───────────────────────────────────────────────


class TestBuildParser:
    """Tests de build_parser() — arguments et valeurs par défaut."""

    def test_dry_run_default_false(self):
        args = build_parser().parse_args([])
        assert args.dry_run is False

    def test_dry_run_flag(self):
        args = build_parser().parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_languages_default_none(self):
        args = build_parser().parse_args([])
        assert args.languages is None

    def test_languages_custom(self):
        args = build_parser().parse_args(["--languages", "fr,de"])
        assert args.languages == "fr,de"

    def test_provider_default_hybride(self):
        args = build_parser().parse_args([])
        assert args.provider == "hybride"

    def test_provider_choice_ollama(self):
        args = build_parser().parse_args(["--provider", "ollama"])
        assert args.provider == "ollama"

    def test_provider_invalid_choice_exits(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--provider", "invalid"])

    def test_source_default_none(self):
        args = build_parser().parse_args([])
        assert args.source is None

    def test_source_custom(self, tmp_path):
        p = tmp_path / "en.json"
        args = build_parser().parse_args(["--source", str(p)])
        assert args.source == p

    def test_yes_short_flag(self):
        args = build_parser().parse_args(["-y"])
        assert args.yes is True

    def test_yes_long_flag(self):
        args = build_parser().parse_args(["--yes"])
        assert args.yes is True

    def test_yes_default_false(self):
        args = build_parser().parse_args([])
        assert args.yes is False

    def test_report_default_none(self):
        args = build_parser().parse_args([])
        assert args.report is None


# ─── TestRunPipeline ────────────────────────────────────────────────


class TestRunPipeline:
    """Tests de run_pipeline() — parcours e2e (dry-run + --yes + erreurs)."""

    def test_dry_run_returns_zero(self, patched_translator_dir, monkeypatch):
        args = build_parser().parse_args(["--dry-run", "--languages", "fr"])
        rc = run_pipeline(args)
        assert rc == 0

    def test_yes_returns_zero(self, patched_translator_dir, monkeypatch):
        """--yes (non-interactif) → étapes 6-8 avec traduction mockée → rc 0."""
        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            lambda *a, **kw: None,
        )
        args = build_parser().parse_args(["--yes", "--languages", "fr"])
        rc = run_pipeline(args)
        assert rc == 0

    def test_full_pipeline_creates_and_reorders(
        self, patched_translator_dir, monkeypatch
    ):
        """--yes : pré-peuplement + traduction mockée + réordonnancement → rc 0."""
        from pathlib import Path

        def fake_translate(src_file, src_data, src_lang, tgt_lang, out_dir):
            # Écrit un fichier désordonné pour vérifier le réordonnancement
            path = Path(out_dir) / f"translation_en_{tgt_lang}.json"
            path.write_text(
                json.dumps({"K4": "new", "K1": "hi", "K2": "bye"}, ensure_ascii=False),
                encoding="utf-8",
            )

        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            fake_translate,
        )
        args = build_parser().parse_args(["--yes", "--languages", "fr"])
        rc = run_pipeline(args)
        assert rc == 0
        # Vérifier qu'un nouveau dossier daté a été créé
        out_base = patched_translator_dir / "output"
        dated = [d for d in out_base.iterdir() if d.is_dir() and "_Export" in d.name]
        # Au moins le nouvel export daté du jour
        today_exports = [
            d
            for d in dated
            if d.name.startswith(
                __import__("datetime").date.today().strftime("%Y_%m_%d")
            )
        ]
        assert today_exports, f"Aucun dossier daté du jour dans {out_base}"
        fr_file = today_exports[0] / "translation_en_fr.json"
        assert fr_file.exists()
        data = json.loads(fr_file.read_text(encoding="utf-8"))
        # Le réordonnancement a dû mettre K1 avant K4
        assert list(data.keys())[0] == "K1"

    def test_missing_source_returns_2(self, tmp_path, monkeypatch):
        """--source vers un fichier absent → rc 2 (FileNotFoundError géré)."""
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", tmp_path)
        args = build_parser().parse_args(["--source", str(tmp_path / "absent.json")])
        rc = run_pipeline(args)
        assert rc == 2

    def test_no_import_folders_returns_2(self, tmp_path, monkeypatch, capsys):
        """Aucun *_Import → rc 2."""
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", tmp_path)
        args = build_parser().parse_args(["--dry-run"])
        rc = run_pipeline(args)
        assert rc == 2
        err = capsys.readouterr().err
        assert "❌" in err

    def test_languages_parsed(self, patched_translator_dir, monkeypatch):
        args = build_parser().parse_args(["--dry-run", "--languages", "fr,de"])
        rc = run_pipeline(args)
        assert rc == 0

    def test_report_written(self, patched_translator_dir, tmp_path, monkeypatch):
        """--report écrit le rapport markdown sur disque."""
        report_file = tmp_path / "out_report.md"
        args = build_parser().parse_args(
            ["--dry-run", "--languages", "fr", "--report", str(report_file)]
        )
        rc = run_pipeline(args)
        assert rc == 0
        assert report_file.exists()


# ═══ Phase 2 — Étape 6 : Pré-peuplement + gestion clés modifiées (TDD) ═══


class TestBackupTranslationFile:
    """Tests de backup_translation_file() — copie .bak_pre_pipeline."""

    def test_creates_backup_with_correct_suffix(self, tmp_path):
        src = tmp_path / "translation_en_fr.json"
        src.write_text('{"K": "v"}', encoding="utf-8")
        backup = backup_translation_file(src)
        assert backup.exists()
        assert backup.name == "translation_en_fr.json.bak_pre_pipeline"
        assert backup.read_text(encoding="utf-8") == '{"K": "v"}'

    def test_original_preserved(self, tmp_path):
        src = tmp_path / "translation_en_de.json"
        src.write_text('{"A": "a"}', encoding="utf-8")
        backup_translation_file(src)
        assert src.read_text(encoding="utf-8") == '{"A": "a"}'

    def test_backup_overwrites_existing(self, tmp_path):
        """Un backup existant est écrasé (re-run du pipeline)."""
        src = tmp_path / "f.json"
        src.write_text('{"new": 1}', encoding="utf-8")
        existing_bak = tmp_path / "f.json.bak_pre_pipeline"
        existing_bak.write_text('{"old": 0}', encoding="utf-8")
        backup_translation_file(src)
        assert existing_bak.read_text(encoding="utf-8") == '{"new": 1}'


class TestPrepopulateOutput:
    """Tests de prepopulate_output() — copie du dernier export vers nouveau dossier."""

    def test_creates_new_dated_folder(self, fake_translator_dir):
        last_export = fake_translator_dir / "output" / "2026_07_08_Export"
        base = fake_translator_dir / "output"
        new_dir = prepopulate_output(last_export, ["fr", "de"], base)
        assert new_dir.exists()
        assert new_dir.parent == base
        # le nom suit le pattern YYYY_MM_DD_Export
        import re

        assert re.match(r"^\d{4}_\d{2}_\d{2}_Export$", new_dir.name)

    def test_copies_translation_files(self, fake_translator_dir):
        last_export = fake_translator_dir / "output" / "2026_07_08_Export"
        base = fake_translator_dir / "output"
        new_dir = prepopulate_output(last_export, ["fr", "de"], base)
        assert (new_dir / "translation_en_fr.json").exists()
        assert (new_dir / "translation_en_de.json").exists()
        fr = json.loads(
            (new_dir / "translation_en_fr.json").read_text(encoding="utf-8")
        )
        assert fr == {"K1": "Bonjour", "K2": "Monde", "K3": "Appairage"}

    def test_skips_missing_language_file(self, fake_translator_dir):
        """Si un fichier de langue n'existe pas dans l'export source, il est ignoré."""
        last_export = fake_translator_dir / "output" / "2026_07_08_Export"
        base = fake_translator_dir / "output"
        new_dir = prepopulate_output(last_export, ["fr", "de", "it"], base)
        assert (new_dir / "translation_en_fr.json").exists()
        assert not (new_dir / "translation_en_it.json").exists()

    def test_empty_last_export_creates_empty_folder(self, tmp_path):
        last_export = tmp_path / "old_export"
        last_export.mkdir()
        base = tmp_path / "output"
        base.mkdir()
        new_dir = prepopulate_output(last_export, ["fr"], base)
        assert new_dir.exists()
        assert list(new_dir.iterdir()) == []


class TestManageModifiedKeys:
    """Tests de manage_modified_keys() — actions 1/2/3 sur clés modifiées."""

    @pytest.fixture
    def export_with_modified(self, tmp_path):
        """Dossier d'export avec 2 langues et une clé K2 modifiée."""
        exp = tmp_path / "export"
        exp.mkdir()
        (exp / "translation_en_fr.json").write_text(
            json.dumps({"K1": "Bonjour", "K2": "Monde", "K3": "Appairage"}),
            encoding="utf-8",
        )
        (exp / "translation_en_de.json").write_text(
            json.dumps({"K1": "Hallo", "K2": "Welt", "K3": "Kopplung"}),
            encoding="utf-8",
        )
        return exp

    def test_option1_retraduire_removes_key(self, export_with_modified):
        """Option 1 : la clé est supprimée de tous les fichiers (reprise la retraduit)."""
        modified = [("K2", "World", "Goodbye")]
        inputs = iter(["1"])
        with patch("builtins.input", side_effect=lambda _: next(inputs)):
            manage_modified_keys(
                modified, export_with_modified, ["fr", "de"], interactive=True
            )
        fr = json.loads(
            (export_with_modified / "translation_en_fr.json").read_text(
                encoding="utf-8"
            )
        )
        de = json.loads(
            (export_with_modified / "translation_en_de.json").read_text(
                encoding="utf-8"
            )
        )
        assert "K2" not in fr
        assert "K2" not in de
        assert "K1" in fr and "K3" in fr

    def test_option2_keep_preserves_key(self, export_with_modified):
        """Option 2 : la traduction actuelle est conservée."""
        modified = [("K2", "World", "Goodbye")]
        with patch("builtins.input", return_value="2"):
            manage_modified_keys(
                modified, export_with_modified, ["fr", "de"], interactive=True
            )
        fr = json.loads(
            (export_with_modified / "translation_en_fr.json").read_text(
                encoding="utf-8"
            )
        )
        assert fr["K2"] == "Monde"

    def test_option3_manual_input_sets_value(self, export_with_modified):
        """Option 3 : saisie manuelle d'une nouvelle traduction par langue."""
        modified = [("K2", "World", "Goodbye")]
        # 1 pour l'action, puis saisie fr, puis saisie de
        inputs = iter(["3", "Au revoir", "Tschüss"])
        with patch("builtins.input", side_effect=lambda _: next(inputs)):
            manage_modified_keys(
                modified, export_with_modified, ["fr", "de"], interactive=True
            )
        fr = json.loads(
            (export_with_modified / "translation_en_fr.json").read_text(
                encoding="utf-8"
            )
        )
        de = json.loads(
            (export_with_modified / "translation_en_de.json").read_text(
                encoding="utf-8"
            )
        )
        assert fr["K2"] == "Au revoir"
        assert de["K2"] == "Tschüss"

    def test_non_interactive_keeps_all(self, export_with_modified):
        """Mode non-interactif : toutes les clés modifiées sont conservées (défaut sûr)."""
        modified = [("K2", "World", "Goodbye")]
        manage_modified_keys(
            modified, export_with_modified, ["fr", "de"], interactive=False
        )
        fr = json.loads(
            (export_with_modified / "translation_en_fr.json").read_text(
                encoding="utf-8"
            )
        )
        assert fr["K2"] == "Monde"

    def test_multiple_modified_keys(self, export_with_modified):
        """Deux clés modifiées, actions différentes (1 puis 2)."""
        (export_with_modified / "translation_en_fr.json").write_text(
            json.dumps({"K1": "Bonjour", "K2": "Monde", "K4": "Quatre"}),
            encoding="utf-8",
        )
        (export_with_modified / "translation_en_de.json").write_text(
            json.dumps({"K1": "Hallo", "K2": "Welt", "K4": "Vier"}), encoding="utf-8"
        )
        modified = [("K2", "World", "Goodbye"), ("K4", "Four", "Quatre")]
        inputs = iter(["1", "2"])
        with patch("builtins.input", side_effect=lambda _: next(inputs)):
            manage_modified_keys(
                modified, export_with_modified, ["fr", "de"], interactive=True
            )
        fr = json.loads(
            (export_with_modified / "translation_en_fr.json").read_text(
                encoding="utf-8"
            )
        )
        assert "K2" not in fr  # retraduire
        assert fr["K4"] == "Quatre"  # gardé

    def test_empty_modified_list(self, export_with_modified):
        """Aucune clé modifiée → aucun changement, aucun prompt."""
        original = (export_with_modified / "translation_en_fr.json").read_text(
            encoding="utf-8"
        )
        with patch("builtins.input") as mock_input:
            manage_modified_keys(
                [], export_with_modified, ["fr", "de"], interactive=True
            )
        mock_input.assert_not_called()
        assert (export_with_modified / "translation_en_fr.json").read_text(
            encoding="utf-8"
        ) == original


class TestStep6PrepopulateAndManage:
    """Tests de step6_prepopulate_and_manage() — orchestration + confirmation."""

    def test_returns_new_export_dir(self, patched_translator_dir, monkeypatch):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        ctx.interactive = False
        result = step6_prepopulate_and_manage(ctx)
        assert result is not None
        assert result.exists()
        assert (result / "translation_en_fr.json").exists()

    def test_backs_up_before_modification(self, patched_translator_dir, monkeypatch):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        ctx.interactive = False
        step6_prepopulate_and_manage(ctx)
        # les backups sont dans le dernier export (source de la copie)
        assert (ctx.export_dir / "translation_en_fr.json.bak_pre_pipeline").exists()

    def test_dry_run_skips_actions(self, patched_translator_dir, monkeypatch, capsys):
        ctx = PipelineContext(languages=["fr", "de"], dry_run=True)
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        result = step6_prepopulate_and_manage(ctx)
        assert result is None
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_interactive_confirmation_yes(self, patched_translator_dir, monkeypatch):
        ctx = PipelineContext(languages=["fr", "de"], interactive=True)
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        # manage_modified_keys : K2 modifiée → option 2 (garder) ; puis confirmation finale → y
        inputs = iter(["2", "y"])
        with patch("builtins.input", side_effect=lambda _: next(inputs)):
            result = step6_prepopulate_and_manage(ctx)
        assert result is not None
        assert result.exists()

    def test_interactive_confirmation_no_aborts(
        self, patched_translator_dir, monkeypatch, capsys
    ):
        ctx = PipelineContext(languages=["fr", "de"], interactive=True)
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        inputs = iter(["2", "n"])
        with patch("builtins.input", side_effect=lambda _: next(inputs)):
            result = step6_prepopulate_and_manage(ctx)
        assert result is None


# ═══ Phase 2 — Étape 7 : Traduction (TDD) ═══


class TestStep7Translate:
    """Tests de step7_translate() — appel au moteur de traduction (mocké)."""

    def test_translates_all_languages(self, patched_translator_dir, monkeypatch):
        """step7 appelle la traduction pour chaque langue demandée."""
        ctx = PipelineContext(languages=["fr", "de"], provider="google")
        step1_detect_sources(ctx)
        new_dir = patched_translator_dir / "output" / "2026_07_08_Export"
        calls = []

        def fake_translate_single(src_file, src_data, src_lang, tgt_lang, out_dir):
            calls.append((tgt_lang, str(out_dir)))
            # simule l'écriture d'un fichier traduit
            (out_dir / f"translation_en_{tgt_lang}.json").write_text(
                json.dumps({"K1": f"[{tgt_lang}]"}, ensure_ascii=False),
                encoding="utf-8",
            )

        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            fake_translate_single,
        )
        step7_translate(ctx, new_dir)
        assert len(calls) == 2
        langs_called = [c[0] for c in calls]
        assert "fr" in langs_called and "de" in langs_called

    def test_dry_run_skips_translation(
        self, patched_translator_dir, monkeypatch, capsys
    ):
        ctx = PipelineContext(languages=["fr"], provider="google", dry_run=True)
        step1_detect_sources(ctx)
        new_dir = patched_translator_dir / "output" / "2026_07_08_Export"
        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            lambda *a, **kw: None,
        )
        step7_translate(ctx, new_dir)
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_ollama_provider_sets_config(self, patched_translator_dir, monkeypatch):
        """Le provider ollama est propagé au singleton Config."""
        import core.config as config_module

        ctx = PipelineContext(languages=["fr"], provider="ollama")
        step1_detect_sources(ctx)
        new_dir = patched_translator_dir / "output" / "2026_07_08_Export"
        seen_provider = {}

        def fake_translate_single(src_file, src_data, src_lang, tgt_lang, out_dir):
            seen_provider["value"] = config_module.get_config().TRANSLATION_PROVIDER

        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            fake_translate_single,
        )
        step7_translate(ctx, new_dir)
        assert seen_provider.get("value") == "ollama"

    def test_no_languages_skips(self, patched_translator_dir, monkeypatch, capsys):
        ctx = PipelineContext(languages=[], provider="google")
        step1_detect_sources(ctx)
        new_dir = patched_translator_dir / "output" / "2026_07_08_Export"
        called = []
        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            lambda *a, **kw: called.append(1),
        )
        step7_translate(ctx, new_dir)
        assert called == []


# ═══ Phase 2 — Étape 8 : Réordonnancement auto (TDD) ═══


class TestReorderTranslationFile:
    """Tests de reorder_translation_file() — réordonnancement selon la source."""

    def test_reorders_to_source_order(self, tmp_path):
        """Fichier désordonné → réordonné selon l'ordre des clés source."""
        path = tmp_path / "translation_en_fr.json"
        path.write_text(
            json.dumps({"C": "c", "A": "a", "B": "b"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        reorder_translation_file(path, ["A", "B", "C"])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert list(data.keys()) == ["A", "B", "C"]

    def test_preserves_values(self, tmp_path):
        path = tmp_path / "f.json"
        path.write_text(
            json.dumps({"B": "deux", "A": "un"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        reorder_translation_file(path, ["A", "B"])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"A": "un", "B": "deux"}

    def test_keys_not_in_source_appended_at_end(self, tmp_path):
        """Les clés présentes dans la trad mais absentes de la source sont à la fin."""
        path = tmp_path / "f.json"
        path.write_text(
            json.dumps({"X": "x", "A": "a", "Y": "y"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        reorder_translation_file(path, ["A", "B"])
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = list(data.keys())
        assert keys[0] == "A"
        assert "X" in keys and "Y" in keys
        # les clés source d'abord, puis les extras
        assert keys.index("A") < keys.index("X")

    def test_missing_source_keys_omitted(self, tmp_path):
        """Les clés source absentes de la trad ne sont pas ajoutées (réordonne, n'ajoute pas)."""
        path = tmp_path / "f.json"
        path.write_text(
            json.dumps({"A": "a"}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        reorder_translation_file(path, ["A", "B", "C"])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert list(data.keys()) == ["A"]

    def test_already_ordered_unchanged_content(self, tmp_path):
        path = tmp_path / "f.json"
        original = json.dumps({"A": "a", "B": "b"}, ensure_ascii=False, indent=2)
        path.write_text(original, encoding="utf-8")
        reorder_translation_file(path, ["A", "B"])
        assert path.read_text(encoding="utf-8") == original

    def test_empty_file_unchanged(self, tmp_path):
        path = tmp_path / "f.json"
        path.write_text("{}", encoding="utf-8")
        reorder_translation_file(path, ["A", "B"])
        assert path.read_text(encoding="utf-8") == "{}"


class TestStep8Reorder:
    """Tests de step8_reorder() — réordonne tous les fichiers d'un export."""

    def test_reorders_all_languages(self, patched_translator_dir, capsys):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        # Désordonne les fichiers volontairement
        (export / "translation_en_fr.json").write_text(
            json.dumps({"K3": "Appairage", "K1": "Bonjour", "K2": "Monde"}),
            encoding="utf-8",
        )
        (export / "translation_en_de.json").write_text(
            json.dumps({"K3": "Kopplung", "K1": "Hallo", "K2": "Welt"}),
            encoding="utf-8",
        )
        step8_reorder(ctx, export)
        fr = json.loads((export / "translation_en_fr.json").read_text(encoding="utf-8"))
        de = json.loads((export / "translation_en_de.json").read_text(encoding="utf-8"))
        assert list(fr.keys()) == ["K1", "K2", "K3"]
        assert list(de.keys()) == ["K1", "K2", "K3"]

    def test_dry_run_skips(self, patched_translator_dir, capsys):
        ctx = PipelineContext(languages=["fr"], dry_run=True)
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        original = (export / "translation_en_fr.json").read_text(encoding="utf-8")
        step8_reorder(ctx, export)
        assert (export / "translation_en_fr.json").read_text(
            encoding="utf-8"
        ) == original
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_missing_file_skipped(self, patched_translator_dir, capsys):
        """Si un fichier de langue n'existe pas, il est ignoré (pas d'erreur)."""
        ctx = PipelineContext(languages=["fr", "it"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        step8_reorder(ctx, export)  # 'it' n'existe pas → pas d'erreur
        out = capsys.readouterr().out
        assert "FR" in out
        assert "IT" in out
