"""
Tests pour le pipeline dropdown (TDD strict).

Couvre :
- D3 : load_dropdown_xlsx_all_sheets() + detect_missing_languages() (io_xlsx)
- D4-D14 : pipeline_dropdown.py (à venir)
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
