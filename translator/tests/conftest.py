"""
Shared fixtures for the COP translation service tests.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ─── Fixtures: Filesystem ─────────────────────────────────────────


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test I/O. Cleaned up after test."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def temp_output_dir(temp_dir):
    """Create a temporary output directory with standard subdirs."""
    out = temp_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def temp_source_dir(temp_dir):
    """Create a temporary source directory with an import subfolder."""
    src = temp_dir / "source"
    src.mkdir(parents=True, exist_ok=True)
    return src


@pytest.fixture
def temp_json_flat_file(temp_dir, sample_json_flat):
    """Create a temporary flat JSON file on disk."""
    filepath = temp_dir / "test_flat.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(sample_json_flat, f, ensure_ascii=False, indent=2)
    return filepath


@pytest.fixture
def temp_json_structured_file(temp_dir, sample_json_structured):
    """Create a temporary structured JSON file on disk."""
    filepath = temp_dir / "test_structured.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(sample_json_structured, f, ensure_ascii=False, indent=2)
    return filepath


@pytest.fixture
def temp_xlsx_file(temp_dir):
    """Create a minimal XLSX file for testing load_dropdown_xlsx."""
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl not installed")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Origin", "French", "Context"])
    ws.append(["Button", "Bouton", "btn"])
    ws.append(["Cancel", "Annuler", "btn"])
    ws.append(["File", "Fichier", "menu"])
    ws.append(["Open", "Ouvrir", "menu"])

    filepath = temp_dir / "test_dropdown.xlsx"
    wb.save(filepath)
    return filepath


# ─── Fixtures: Test Data ──────────────────────────────────────────


@pytest.fixture
def sample_json_flat():
    """Flat JSON data: keys map directly to translation values."""
    return {
        "Btn_Home": "Home",
        "Btn_Action": "Action",
        "Btn_Cancel": "Cancel",
        "Lbl_Welcome": "Welcome to the application",
        "Lbl_Goodbye": "See you soon",
    }


@pytest.fixture
def sample_json_structured():
    """Structured JSON data with metadata and contexts."""
    return {
        "metadata": {
            "language": "FR",
            "language_name": "Français",
            "source_file": "test_dropdown.xlsx",
            "generated_date": "2026-05-08",
            "total_entries": 4,
        },
        "contexts": {
            "btn": {
                "Button": "Bouton",
                "Cancel": "Annuler",
            },
            "menu": {
                "File": "Fichier",
                "Open": "Ouvrir",
            },
        },
    }


@pytest.fixture
def sample_dropdown_entries():
    """Dropdown entries as returned by load_dropdown_xlsx."""
    return [
        {"origin": "Button", "french": "Bouton", "context": "btn"},
        {"origin": "Cancel", "french": "Annuler", "context": "btn"},
        {"origin": "File", "french": "Fichier", "context": "menu"},
        {"origin": "Open", "french": "Ouvrir", "context": "menu"},
    ]


# ─── Fixtures: Mock API ───────────────────────────────────────────


@pytest.fixture
def mock_google_translator():
    """
    Mock GoogleTranslator that returns predefined translations.
    Does NOT make any real API calls.
    """
    translations = {
        ("Hello", "en", "fr"): "Bonjour",
        ("Action", "en", "fr"): "Action",
        ("Cancel", "en", "fr"): "Annuler",
        ("Welcome to the application", "en", "fr"): "Bienvenue dans l'application",
        ("See you soon", "en", "fr"): "À bientôt",
        ("Button", "en", "de"): "Taste",
        ("File", "en", "de"): "Datei",
        ("Open", "en", "de"): "Öffnen",
        ("Cancel", "en", "de"): "Abbrechen",
        ("Home", "en", "cs"): "Domů",
        ("Home", "en", "sk"): "Domov",
        ("Home", "en", "it"): "Casa",
        ("Home", "en", "ar"): "الرئيسية",
    }

    with pytest.mock.patch("core.translator.GoogleTranslator") as mock_cls:
        mock_instance = MagicMock()

        def translate_side_effect(text):
            # Handle the case where translate is called on the instance
            # after GoogleTranslator(source=..., target=...) construction
            key = (text, mock_instance._source, mock_instance._target)
            return translations.get(key, f"[{mock_instance._target}] {text}")

        mock_instance.translate = MagicMock(side_effect=translate_side_effect)

        def constructor_side_effect(source, target):
            mock_instance._source = source
            mock_instance._target = target
            return mock_instance

        mock_cls.side_effect = constructor_side_effect
        mock_cls.return_value = mock_instance

        yield mock_cls


@pytest.fixture
def mock_google_translator_error():
    """
    Mock GoogleTranslator that always raises an exception.
    For testing error handling and retry logic.
    """
    with pytest.mock.patch("core.translator.GoogleTranslator") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception(
            "Server Error: Internal Server Error"
        )
        mock_cls.return_value = mock_instance
        yield mock_cls


@pytest.fixture
def mock_google_translator_rate_limit():
    """
    Mock GoogleTranslator that raises a rate limit error on first call,
    then succeeds on subsequent calls.
    """
    with pytest.mock.patch("core.translator.GoogleTranslator") as mock_cls:
        call_count = {"n": 0}

        def translate_side_effect(text):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                raise Exception("429 Too Many Requests")
            return f"[translated] {text}"

        mock_instance = MagicMock()
        mock_instance.translate.side_effect = translate_side_effect
        mock_cls.return_value = mock_instance
        yield mock_cls


# ─── Fixtures: Environment ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset the Config singleton between tests to avoid state leakage."""
    import core.config as config_module

    config_module._config = None
    yield
    config_module._config = None
