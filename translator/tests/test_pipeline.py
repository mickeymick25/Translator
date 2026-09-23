"""
Characterization tests for translator/pipeline.py — Phase 1 (étapes 1-5).

Ces tests figent le comportement existant du pipeline (développé sans TDD)
pour servir de filet de sécurité avant d'entamer la Phase 2 en TDD strict.

Couverture visée : ≥ 90% sur pipeline.py.

Organisation : une classe `TestXxx` par fonction publique/privée, cohérent
avec les conventions de la suite existante (test_cli, test_translator, ...).
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# compare_sources.py et analyze_translation_gap.py vivent à la racine du dépôt
# (hors translator/). En Docker (seul translator/ est monté), l'import
# échoue et importorskip saute proprement toute la classe de tests. Le
# sys.path setup est géré par conftest.py (Sprint 4 - tâche 3).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
pytest.importorskip("compare_sources")
pytest.importorskip("analyze_translation_gap")

import pipeline  # noqa: E402  (après importorskip ci-dessus)
from pipeline_common import (  # noqa: E402  (après importorskip ci-dessus)
    DuplicateReferenceKeysError,
    load_reference_csv,
)
from pipeline import (  # noqa: E402  (après importorskip ci-dessus)
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
    build_final_report,
    detect_misalignments,
    detect_duplicated_translations,
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
    step9_validate,
    step10_detect_misalignments,
    step11_final_report,
    step_banner,
)
from pipeline import detect_source_kind  # noqa: E402  (après importorskip)

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
    """Monkeypatche pipeline.TRANSLATOR_DIR et TYPOS_PATH vers le fs de test."""
    monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", fake_translator_dir)
    monkeypatch.setattr(
        pipeline, "TYPOS_PATH", fake_translator_dir / "source_typos.json"
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

    @pytest.mark.parametrize(
        "scope,expected_typos",
        [
            # scope="json" : n'inclut que les entrées json+both (exclut dropdown)
            ("json", ["Both1", "JsonOnly", "NoScope"]),
            # scope="dropdown" : n'inclut que les entrées dropdown+both
            ("dropdown", ["Both1", "DropdownOnly", "NoScope"]),
            # scope="both" (défaut explicite) : inclut tout
            ("both", ["Both1", "JsonOnly", "DropdownOnly", "NoScope"]),
        ],
    )
    def test_scope_filtering(self, tmp_path, scope, expected_typos):
        """Sprint 3 - tâche 29 : load_typos(scope) filtre selon le champ scope.

        - scope="json" retient les entrées dont scope ∈ {json, both}.
        - scope="dropdown" retient celles dont scope ∈ {dropdown, both}.
        - scope="both" (défaut) retourne tout.
        - Une entrée sans champ scope est considérée comme "both".
        """
        p = tmp_path / "scoped_typos.json"
        p.write_text(
            json.dumps(
                {
                    "typos": [
                        {"typo": "Both1", "correction": "C", "scope": "both"},
                        {"typo": "JsonOnly", "correction": "C", "scope": "json"},
                        {
                            "typo": "DropdownOnly",
                            "correction": "C",
                            "scope": "dropdown",
                        },
                        # Pas de champ scope → défaut "both"
                        {"typo": "NoScope", "correction": "C"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        typos = load_typos(p, scope=scope)
        found = sorted(t["typo"] for t in typos)
        assert found == sorted(expected_typos)

    def test_scope_defaults_to_both(self, tmp_path):
        """Sans argument scope, load_typos retourne toutes les entrées."""
        p = tmp_path / "scoped_typos.json"
        p.write_text(
            json.dumps(
                {
                    "typos": [
                        {"typo": "A", "correction": "C", "scope": "json"},
                        {"typo": "B", "correction": "C", "scope": "dropdown"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        typos = load_typos(p)
        assert sorted(t["typo"] for t in typos) == ["A", "B"]


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

    def test_source_key_count_stored_in_step1(self, patched_translator_dir, capsys):
        """Sprint 3 - tâche 29 : ctx.source_key_count est calculé à l'étape 1.

        Évite une relecture de la source dans les rapports (I11, Sprint 2 tâche 25).
        """
        ctx = PipelineContext()
        step1_detect_sources(ctx)
        # La source en 10.json du fixture contient 4 clés (K1, K2, K4, K5)
        assert ctx.source_key_count == 4
        out = capsys.readouterr().out
        assert "4" in out


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
        monkeypatch.setattr(pipeline, "TYPOS_PATH", fake_typos_file)
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
        monkeypatch.setattr(pipeline, "TYPOS_PATH", fake_typos_file)
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
        monkeypatch.setattr(pipeline, "TYPOS_PATH", fake_typos_file)
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
        monkeypatch.setattr(pipeline, "TYPOS_PATH", fake_typos_file)
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
        monkeypatch.setattr(pipeline, "TYPOS_PATH", fake_typos_file)
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

    @pytest.mark.parametrize(
        "flag",
        ["-y", "--yes"],
        ids=["short", "long"],
    )
    def test_yes_flag(self, flag):
        args = build_parser().parse_args([flag])
        assert args.yes is True

    @pytest.mark.parametrize(
        "attr",
        ["dry_run", "yes"],
        ids=["dry_run", "yes"],
    )
    def test_boolean_flag_default_false(self, attr):
        args = build_parser().parse_args([])
        assert getattr(args, attr) is False

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

    def test_yes_returns_zero(self, patched_translator_dir, monkeypatch, tmp_path):
        """--yes (non-interactif) → étapes 6-11 avec traduction mockée → rc 0."""
        monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
        (tmp_path / "doc").mkdir()
        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            lambda *a, **kw: None,
        )
        args = build_parser().parse_args(["--yes", "--languages", "fr"])
        rc = run_pipeline(args)
        assert rc == 0

    def test_full_pipeline_creates_and_reorders(
        self, patched_translator_dir, monkeypatch, tmp_path
    ):
        """--yes : pré-peuplement + traduction mockée + réordonnancement → rc 0."""
        from pathlib import Path

        monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
        (tmp_path / "doc").mkdir()

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


# ═══ Phase 3 — Étape 9 : Validation structurelle (TDD) ═══


class TestStep9Validate:
    """Tests de step9_validate() — validation structurelle des fichiers traduits."""

    def test_validates_all_languages(self, patched_translator_dir, capsys):
        """step9 appelle validate() sur le dossier export et retourne un rapport."""
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        report = step9_validate(ctx, export)
        assert report is not None
        assert len(report.languages) == 2
        out = capsys.readouterr().out
        assert "Validation" in out or "validation" in out.lower()

    def test_dry_run_skips(self, patched_translator_dir, capsys):
        ctx = PipelineContext(languages=["fr"], dry_run=True)
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        report = step9_validate(ctx, export)
        assert report is None
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_detects_missing_keys(self, patched_translator_dir, capsys):
        """Une clé présente dans la source mais absente de la trad est signalée."""
        ctx = PipelineContext(languages=["fr"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        # Supprime K1 du fichier FR pour créer une clé manquante
        fr = json.loads((export / "translation_en_fr.json").read_text(encoding="utf-8"))
        del fr["K1"]
        (export / "translation_en_fr.json").write_text(
            json.dumps(fr, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report = step9_validate(ctx, export)
        fr_result = next(lv for lv in report.languages if lv.lang == "fr")
        assert "K1" in fr_result.missing

    def test_detects_extra_keys(self, patched_translator_dir):
        """Une clé présente dans la trad mais absente de la source est signalée."""
        ctx = PipelineContext(languages=["de"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        de = json.loads((export / "translation_en_de.json").read_text(encoding="utf-8"))
        de["EXTRA_KEY"] = "extra"
        (export / "translation_en_de.json").write_text(
            json.dumps(de, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report = step9_validate(ctx, export)
        de_result = next(lv for lv in report.languages if lv.lang == "de")
        assert "EXTRA_KEY" in de_result.extra


# ═══ Phase 3 — Étape 10 : Détection mésalignements (TDD) ═══


class TestDetectMisalignments:
    """Tests de detect_misalignments() — heuristique token overlap intra-langue."""

    @pytest.mark.parametrize(
        "source,translation,test_id",
        [
            # Deux clés, même source, traductions identiques → pas de mésalignement
            (
                {"K1": "Hello", "K2": "Hello"},
                {"K1": "Bonjour", "K2": "Bonjour"},
                "identical",
            ),
            # Traductions différentes mais partageant des mots → pas de mésalignement
            (
                {"K1": "Hello world", "K2": "Hello world"},
                {"K1": "Bonjour monde", "K2": "Bonjour le monde"},
                "shared_tokens",
            ),
            # Chaque clé a un texte source unique → pas de groupe → pas de mésalignement
            (
                {"K1": "Hello", "K2": "World"},
                {"K1": "Bonjour", "K2": "Monde"},
                "unique_source",
            ),
            # Les traductions vides ne sont pas comparées
            (
                {"K1": "Hello", "K2": "Hello"},
                {"K1": "Bonjour", "K2": ""},
                "empty_translation",
            ),
        ],
        ids=[
            "identical_translations",
            "shared_tokens",
            "unique_source",
            "empty_translations",
        ],
    )
    def test_no_misalignment_cases(self, source, translation, test_id):
        """Cas ne devant produire aucun mésalignement (factorisé via parametrize)."""
        assert detect_misalignments(source, translation, "fr") == []

    def test_misalignment_when_divergent_translations(self):
        """Deux clés, même source, traductions sans mot commun → mésalignement."""
        source = {"K1": "Hello", "K2": "Hello"}
        translation = {"K1": "Bonjour", "K2": "Salut là"}
        result = detect_misalignments(source, translation, "fr")
        assert len(result) == 1
        assert result[0]["source_text"] == "Hello"
        assert {"K1", "K2"} == set(result[0]["keys"])

    def test_multiple_source_groups(self):
        """Plusieurs groupes source divergents signalés séparément."""
        source = {"K1": "Yes", "K2": "Yes", "K3": "No", "K4": "No"}
        translation = {
            "K1": "Oui",
            "K2": "Affirmatif",
            "K3": "Non",
            "K4": "Négatif",
        }
        result = detect_misalignments(source, translation, "fr")
        assert len(result) == 2
        source_texts = {r["source_text"] for r in result}
        assert source_texts == {"Yes", "No"}

    def test_three_keys_same_source(self):
        """Trois clés, même source, une traduction divergente → signalée."""
        source = {"K1": "Save", "K2": "Save", "K3": "Save"}
        translation = {"K1": "Enregistrer", "K2": "Enregistrer", "K3": "Sauvegarder"}
        result = detect_misalignments(source, translation, "fr")
        assert len(result) == 1
        assert len(result[0]["keys"]) == 3


class TestDetectDuplicatedTranslations:
    """Tests de detect_duplicated_translations() — cas jumeau des mésalignements.

    Fixture de référence : la corruption FR 06_12 sur LO_LI_AC_1865/1866
    (cf. doc/2026_09_23_LO_LI_AC_1865_FR_Misalignment_Analysis.md).
    """

    def test_detects_corrupted_1865_case(self):
        """Deux textes source différents, traduction identique → signalée."""
        source = {
            "LO_LI_AC_1865": "Add logistic link",
            "LO_LI_AC_1866": "Add an animation link",
        }
        translation = {
            "LO_LI_AC_1865": "Ajouter un lien d'animation",
            "LO_LI_AC_1866": "Ajouter un lien d'animation",
        }
        result = detect_duplicated_translations(source, translation, "fr")
        assert len(result) == 1
        assert result[0]["translation_text"] == "Ajouter un lien d'animation"
        assert set(result[0]["keys"]) == {"LO_LI_AC_1865", "LO_LI_AC_1866"}
        assert result[0]["source_values"]["LO_LI_AC_1865"] == "Add logistic link"
        assert result[0]["source_values"]["LO_LI_AC_1866"] == "Add an animation link"

    def test_same_en_case_insensitive_not_flagged(self):
        """Textes source identiques à la casse près → traduction identique légitime."""
        source = {"K1": "Legal Identifier", "K2": "legal identifier"}
        translation = {"K1": "Identifiant légal", "K2": "Identifiant légal"}
        assert detect_duplicated_translations(source, translation, "fr") == []

    def test_legit_synonyms_flagged_advisory(self):
        """Synonymes légitimes (Cancel/Rollback → Annuler) : signalés, advisory."""
        source = {"Btn_Cancel": "Cancel", "Btn_Rollback": "Rollback"}
        translation = {"Btn_Cancel": "Annuler", "Btn_Rollback": "Annuler"}
        result = detect_duplicated_translations(source, translation, "fr")
        assert len(result) == 1
        assert set(result[0]["keys"]) == {"Btn_Cancel", "Btn_Rollback"}

    def test_single_key_not_flagged(self):
        """Une seule clé dans le groupe → rien à comparer."""
        source = {"K1": "Save"}
        translation = {"K1": "Enregistrer"}
        assert detect_duplicated_translations(source, translation, "fr") == []

    def test_empty_source_value_skipped(self):
        """Clé absente ou texte source vide → ignorée (pas de comparaison fiable)."""
        source = {"K1": "", "K2": "Save"}
        translation = {"K1": "Enregistrer", "K2": "Enregistrer"}
        assert detect_duplicated_translations(source, translation, "fr") == []

    def test_punctuation_only_source_skipped(self):
        """Texte source sans token (ponctuation seule, C15) → ignoré."""
        source = {"K1": "...", "K2": "Save"}
        translation = {"K1": "Enregistrer", "K2": "Enregistrer"}
        assert detect_duplicated_translations(source, translation, "fr") == []


# ─── TestLoadReferenceCsv (FIX-1865-05) ──────────────────────────────


class TestLoadReferenceCsv:
    """Tests de load_reference_csv() — garde-fou clés dupliquées.

    Fixture : les 3 clés dupliquées réelles du CSV 2026_06_12_Import
    (cf. doc/2026_09_23_LO_LI_AC_1865_FR_Misalignment_Analysis.md).
    """

    @staticmethod
    def _write_csv(path: Path, rows: list[list[str]]) -> Path:
        content = "Translation variable;Label;EN:en;FR:fr\n"
        content += "\n".join(";".join(row) for row in rows) + "\n"
        path.write_text(content, encoding="utf-8")
        return path

    def test_clean_csv_parsed(self, tmp_path):
        """CSV propre → dict {cle: {label, en, fr}} correct."""
        path = self._write_csv(
            tmp_path / "Export_COP_Excel.csv",
            [["K1", "Label", "Hello", "Bonjour"], ["K2", "", "World", "Monde"]],
        )
        data = load_reference_csv(path)
        assert data["K1"] == {"label": "Label", "en": "Hello", "fr": "Bonjour"}
        assert data["K2"]["fr"] == "Monde"

    def test_duplicate_keys_raise_with_lines(self, tmp_path):
        """Les 3 clés dupliquées réelles du CSV 06_12 → erreur explicite."""
        path = self._write_csv(
            tmp_path / "Export_COP_Excel.csv",
            [
                [
                    "LO_LI_AC_1865",
                    "Activate logistic link",
                    "Add logistic link",
                    "Ajouter un lien logistique",
                ],
                [
                    "LO_LI_AC_1865",
                    "Activate Amination link",
                    "Add an animation link",
                    "Ajouter un lien d'animation",
                ],
                [
                    "LO_LO_AD_413",
                    "Fax number",
                    "Fax number",
                    "Numéro de fax",
                ],
                [
                    "LO_LO_AD_413",
                    "Mobile number",
                    "Mobile number",
                    "Numéro de téléphone portable",
                ],
                ["PA_CO_VI_859", "Start date", "Start date", "Date de début"],
                ["PA_CO_VI_859", "End date", "End date", "Date de fin"],
                ["PA_CO_VI_859", "Save", "Save", "Soumettre"],
            ],
        )
        with pytest.raises(DuplicateReferenceKeysError) as excinfo:
            load_reference_csv(path)
        message = str(excinfo.value)
        assert "3 clé(s) dupliquée(s)" in message
        for key in ("LO_LI_AC_1865", "LO_LO_AD_413", "PA_CO_VI_859"):
            assert key in message
        assert "lignes 2, 3" in message

    def test_step3_warns_on_duplicate_reference_csv(
        self, tmp_path, monkeypatch, capsys
    ):
        """Un CSV de référence à doublons dans l'import → avertissement step3."""
        monkeypatch.setattr(pipeline, "load_typos", lambda path=None: [])
        source_file = tmp_path / "en.json"
        source_file.write_text(json.dumps({"K": "v"}), encoding="utf-8")
        self._write_csv(
            tmp_path / "Export_COP_Excel.csv",
            [["K1", "", "Save", "Soumettre"], ["K1", "", "Submit", "Soumettre"]],
        )
        ctx = PipelineContext(new_source=source_file)
        ctx.new_import_folder = tmp_path
        step3_detect_typos(ctx)
        out = capsys.readouterr().out
        assert "clé(s) dupliquée(s)" in out
        assert "K1" in out

    def test_step3_clean_reference_csv(self, tmp_path, monkeypatch, capsys):
        """CSV de référence propre dans l'import → message OK."""
        monkeypatch.setattr(pipeline, "load_typos", lambda path=None: [])
        source_file = tmp_path / "en.json"
        source_file.write_text(json.dumps({"K": "v"}), encoding="utf-8")
        self._write_csv(
            tmp_path / "Export_COP_Excel.csv",
            [["K1", "", "Save", "Enregistrer"]],
        )
        ctx = PipelineContext(new_source=source_file)
        ctx.new_import_folder = tmp_path
        step3_detect_typos(ctx)
        out = capsys.readouterr().out
        assert "aucune clé dupliquée" in out


class TestStep10DetectMisalignments:
    """Tests de step10_detect_misalignments() — orchestration multi-langues."""

    def test_returns_dict_per_lang(self, patched_translator_dir, capsys):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        result = step10_detect_misalignments(ctx, export)
        assert "fr" in result
        assert "de" in result

    def test_dry_run_skips(self, patched_translator_dir, capsys):
        ctx = PipelineContext(languages=["fr"], dry_run=True)
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        result = step10_detect_misalignments(ctx, export)
        assert result == {}
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()

    def test_detects_divergence_in_export(self, patched_translator_dir):
        """Prépare une divergence intra-langue et vérifie la détection."""
        ctx = PipelineContext(languages=["fr"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        # Deux clés avec même source mais traductions divergentes
        (export / "translation_en_fr.json").write_text(
            json.dumps({"K1": "Bonjour", "K2": "Bonjour", "K_dup": "Salut là"}),
            encoding="utf-8",
        )
        # Adapter la source pour que K1 et K_dup partagent le même texte
        src = json.loads(ctx.new_source.read_text(encoding="utf-8"))
        src["K_dup"] = src["K1"]  # même texte que K1
        ctx.new_source.write_text(json.dumps(src), encoding="utf-8")
        result = step10_detect_misalignments(ctx, export)
        assert len(result["fr"]) >= 1


# ═══ Phase 3 — Étape 11 : Rapport consolidé final (TDD) ═══


class TestBuildFinalReport:
    """Tests de build_final_report() — génération du rapport markdown final."""

    def test_has_all_nine_sections(self, patched_translator_dir, tmp_path):
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        validation_report = step9_validate(ctx, export)
        misalignments = step10_detect_misalignments(ctx, export)
        report = build_final_report(ctx, export, validation_report, misalignments)
        assert "## 1. Source" in report
        assert "## 2. Comparaison" in report
        assert "## 3. Coquilles" in report
        assert "## 4. Écart" in report
        assert "## 5. Plan d'action" in report
        assert "## 6. Traduction" in report
        assert "## 7. Validation" in report
        assert "## 8. Mésalignements" in report
        assert "## 9. Ordre" in report

    def test_includes_validation_summary(self, patched_translator_dir):
        ctx = PipelineContext(languages=["fr"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        validation_report = step9_validate(ctx, export)
        report = build_final_report(ctx, export, validation_report, {})
        assert "validation" in report.lower()
        assert "fr" in report.lower()

    def test_includes_misalignment_count(self, patched_translator_dir):
        ctx = PipelineContext(languages=["fr"])
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        misalignments = {"fr": [{"source_text": "X", "keys": ["A", "B"]}]}
        report = build_final_report(ctx, export, None, misalignments)
        assert "Mésalignements" in report
        assert "1" in report  # 1 mésalignement


class TestStep11FinalReport:
    """Tests de step11_final_report() — écrit le rapport dans doc/."""

    def test_writes_report_to_doc(self, patched_translator_dir, monkeypatch, tmp_path):
        """Le rapport final est écrit dans doc/{date}_Pipeline_Report.md."""
        # Rediriger le dossier doc vers tmp_path pour ne pas écrire dans le vrai doc/
        monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        ctx = PipelineContext(languages=["fr", "de"])
        step1_detect_sources(ctx)
        step2_compare_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        validation_report = step9_validate(ctx, export)
        misalignments = step10_detect_misalignments(ctx, export)
        path = step11_final_report(ctx, export, validation_report, misalignments)
        assert path is not None
        assert path.exists()
        assert "Pipeline_Report" in path.name
        content = path.read_text(encoding="utf-8")
        assert "Rapport" in content

    def test_dry_run_skips(self, patched_translator_dir, monkeypatch, tmp_path, capsys):
        ctx = PipelineContext(languages=["fr"], dry_run=True)
        step1_detect_sources(ctx)
        export = patched_translator_dir / "output" / "2026_07_08_Export"
        path = step11_final_report(ctx, export, None, {})
        assert path is None
        out = capsys.readouterr().out
        assert "dry-run" in out.lower()


# ═══ Tâche 19 — Test end-to-end avec la vraie source en10 ═══


class TestPipelineEndToEndEn10:
    """Test e2e : parcours complet sur la vraie source en10 (tâche 19).

    Copie la vraie source + le dernier export vers tmp_path (pour ne pas
    modifier les originaux), mocke la traduction, et vérifie que le pipeline
    produit un nouveau dossier export + un rapport final.
    Skippé si la source en10 n'est pas disponible (Docker).
    """

    @pytest.fixture
    def real_translator_dir(self):
        """Retourne le vrai translator/ (non mocké). Skip si absent."""
        real = _REPO_ROOT / "translator"
        src = real / "source" / "2026_07_08_Import" / "en 10.json"
        if not src.exists():
            pytest.skip("Source en10 non disponible (Docker ou contexte différent)")
        return real

    @pytest.fixture
    def e2e_env(self, real_translator_dir, tmp_path):
        """Copie la vraie source en10 + le dernier export vers tmp_path."""
        import shutil

        # Dossiers
        src_dir = tmp_path / "source"
        out_dir = tmp_path / "output"
        doc_dir = tmp_path / "doc"
        src_dir.mkdir()
        out_dir.mkdir()
        doc_dir.mkdir()

        # Copier la source en10 et en9
        imp10 = src_dir / "2026_07_08_Import"
        imp10.mkdir()
        shutil.copy2(
            real_translator_dir / "source" / "2026_07_08_Import" / "en 10.json",
            imp10 / "en 10.json",
        )
        imp9 = src_dir / "2026_06_25_Import"
        imp9.mkdir()
        shutil.copy2(
            real_translator_dir / "source" / "2026_06_25_Import" / "en 9.json",
            imp9 / "en 9.json",
        )

        # Copier le dernier export
        real_export = real_translator_dir / "output" / "2026_07_08_Export"
        exp = out_dir / "2026_07_08_Export"
        exp.mkdir()
        for f in real_export.glob("translation_en_*.json"):
            shutil.copy2(f, exp / f.name)

        return tmp_path

    def test_full_pipeline_en10(self, e2e_env, monkeypatch):
        """Parcours complet --yes sur en10 : pré-peuplement + trad mockée +
        réordonnancement + validation + rapport final → rc 0."""
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", e2e_env)
        monkeypatch.setattr(pipeline, "REPO_ROOT", e2e_env)

        def fake_translate(src_file, src_data, src_lang, tgt_lang, out_dir):
            # Simule une traduction : préserve les clés, ajoute un préfixe [lang]
            from pathlib import Path

            path = Path(out_dir) / f"translation_en_{tgt_lang}.json"
            existing = (
                json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            )
            for key, val in src_data.items():
                if key not in existing:
                    existing[key] = f"[{tgt_lang}] {val}"
            path.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        monkeypatch.setattr(
            "modes.mode_translate_json._translate_single_language",
            fake_translate,
        )
        args = build_parser().parse_args(
            ["--yes", "--languages", "fr,de", "--provider", "google"]
        )
        rc = run_pipeline(args)
        assert rc == 0

        # Vérifier qu'un nouveau dossier export daté du jour a été créé
        import datetime

        today = datetime.date.today().strftime("%Y_%m_%d")
        new_exports = [
            d
            for d in (e2e_env / "output").iterdir()
            if d.is_dir() and d.name.startswith(today) and "_Export" in d.name
        ]
        assert new_exports, f"Aucun dossier export daté du jour ({today})"
        new_export = new_exports[0]

        # Les fichiers de traduction existent pour fr et de
        assert (new_export / "translation_en_fr.json").exists()
        assert (new_export / "translation_en_de.json").exists()

        # Le réordonnancement a préservé l'ordre source
        source = json.loads(
            (e2e_env / "source" / "2026_07_08_Import" / "en 10.json").read_text(
                encoding="utf-8"
            )
        )
        source_keys = list(source.keys())
        fr = json.loads(
            (new_export / "translation_en_fr.json").read_text(encoding="utf-8")
        )
        fr_keys = list(fr.keys())
        # Les clés source doivent apparaître dans l'ordre source au début
        common = [k for k in source_keys if k in fr_keys]
        assert common == [k for k in fr_keys if k in source_keys]

        # Le rapport final a été écrit dans doc/
        reports = list((e2e_env / "doc").glob("*_Pipeline_Report.md"))
        assert reports, "Aucun rapport final généré"
        report_content = reports[0].read_text(encoding="utf-8")
        assert "## 1. Source" in report_content
        assert "## 7. Validation" in report_content
        assert "## 9. Ordre" in report_content

    def test_dry_run_en10(self, e2e_env, monkeypatch, capsys):
        """Dry-run sur en10 : rapport d'analyse sans exécution → rc 0."""
        monkeypatch.setattr(pipeline, "TRANSLATOR_DIR", e2e_env)
        monkeypatch.setattr(pipeline, "REPO_ROOT", e2e_env)
        args = build_parser().parse_args(["--dry-run", "--languages", "fr,de"])
        rc = run_pipeline(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "2545" in out  # nombre de clés de en10
        assert "dry-run" in out.lower()


class TestPipelineDryRunUnified:
    """Tests du dry-run unifié (tâche 17) : les 11 étapes sont simulées."""

    def test_dry_run_shows_all_11_steps(
        self, patched_translator_dir, monkeypatch, capsys
    ):
        """En dry-run, les 11 étapes sont affichées (simulation), pas seulement 1-5."""
        monkeypatch.setattr(pipeline, "REPO_ROOT", patched_translator_dir)
        args = build_parser().parse_args(["--dry-run", "--languages", "fr,de"])
        rc = run_pipeline(args)
        assert rc == 0
        out = capsys.readouterr().out
        for step in range(1, 12):
            assert f"ÉTAPE {step}" in out, f"Étape {step} manquante en dry-run"

    def test_dry_run_no_files_written(self, patched_translator_dir, monkeypatch):
        """En dry-run, aucun fichier n'est créé (pas de nouveau dossier export)."""
        monkeypatch.setattr(pipeline, "REPO_ROOT", patched_translator_dir)
        out_base = patched_translator_dir / "output"
        before = {d.name for d in out_base.iterdir() if d.is_dir()}
        args = build_parser().parse_args(["--dry-run", "--languages", "fr"])
        run_pipeline(args)
        after = {d.name for d in out_base.iterdir() if d.is_dir()}
        assert before == after, "dry-run a créé des dossiers"

    def test_dry_run_no_backup_files(self, patched_translator_dir, monkeypatch):
        """En dry-run, aucun fichier .bak_pre_pipeline n'est créé."""
        monkeypatch.setattr(pipeline, "REPO_ROOT", patched_translator_dir)
        args = build_parser().parse_args(["--dry-run", "--languages", "fr"])
        run_pipeline(args)
        baks = list(patched_translator_dir.rglob("*.bak_pre_pipeline"))
        assert baks == [], f"dry-run a créé des backups : {baks}"

    def test_dry_run_no_report_in_doc(self, patched_translator_dir, monkeypatch):
        """En dry-run, aucun rapport final n'est écrit dans doc/."""
        monkeypatch.setattr(pipeline, "REPO_ROOT", patched_translator_dir)
        (patched_translator_dir / "doc").mkdir(exist_ok=True)
        before = set((patched_translator_dir / "doc").iterdir())
        args = build_parser().parse_args(["--dry-run", "--languages", "fr"])
        run_pipeline(args)
        after = set((patched_translator_dir / "doc").iterdir())
        assert before == after, "dry-run a écrit un rapport dans doc/"


# ═══ Phase D1 — D2 : Dispatcher (detect_source_kind + --mode) (TDD) ═══


class TestDetectSourceKind:
    """Tests de detect_source_kind() — détection du type de source."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("en10.json", "json"),
            ("dropdown.xlsx", "dropdown"),
            ("dropdown.xls", "dropdown"),
            ("source.JSON", "json"),
            ("data.XLSX", "dropdown"),
        ],
    )
    def test_detect_by_extension(self, tmp_path, filename, expected):
        path = tmp_path / filename
        path.write_text("{}", encoding="utf-8")
        assert detect_source_kind(path) == expected

    def test_unknown_extension_defaults_json(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("{}", encoding="utf-8")
        assert detect_source_kind(path) == "json"

    def test_none_returns_json(self):
        assert detect_source_kind(None) == "json"


class TestBuildParserMode:
    """Tests du flag --mode du dispatcher."""

    def test_mode_default_none(self):
        args = build_parser().parse_args([])
        assert args.mode is None

    def test_mode_json(self):
        args = build_parser().parse_args(["--mode", "json"])
        assert args.mode == "json"

    def test_mode_dropdown(self):
        args = build_parser().parse_args(["--mode", "dropdown"])
        assert args.mode == "dropdown"

    def test_mode_invalid_exits(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--mode", "invalid"])


class TestRunPipelineDispatch:
    """Tests du dispatch selon --mode / détection."""

    def test_mode_json_runs_json_pipeline(self, patched_translator_dir, monkeypatch):
        """--mode json → pipeline JSON existant (dry-run)."""
        monkeypatch.setattr(pipeline, "REPO_ROOT", patched_translator_dir)
        args = build_parser().parse_args(
            ["--mode", "json", "--dry-run", "--languages", "fr"]
        )
        rc = run_pipeline(args)
        assert rc == 0

    def test_mode_dropdown_dispatches_to_dropdown_pipeline(
        self, tmp_path, monkeypatch, capsys
    ):
        """--mode dropdown délègue au pipeline dropdown (dry-run → rc 0)."""
        import openpyxl

        monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
        (tmp_path / "doc").mkdir(exist_ok=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "EN"
        ws.append(["Origin", "Anglais", "Contexte"])
        ws.append(["Hello", "Hello", "greeting"])
        xlsx_path = tmp_path / "test_dropdown.xlsx"
        wb.save(xlsx_path)
        args = build_parser().parse_args(
            [
                "--mode",
                "dropdown",
                "--dry-run",
                "--source",
                str(xlsx_path),
                "--languages",
                "pt",
            ]
        )
        rc = run_pipeline(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "dropdown" in out.lower()
