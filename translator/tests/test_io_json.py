"""
Tests for core/io_json.py — JSON I/O module.

Covers:
- load_flat_json(): loading flat JSON files, missing files, invalid JSON
- save_flat_json(): saving flat JSON, creating parent directories
- load_structured_json(): loading structured JSON with metadata and contexts
- save_structured_json(): saving structured JSON
- create_dropdown_metadata(): metadata format and field consistency
"""

import json
from pathlib import Path

import pytest
from core.io_json import (
    create_dropdown_metadata,
    load_flat_json,
    load_structured_json,
    save_flat_json,
    save_structured_json,
)

# ─── load_flat_json ───────────────────────────────────────────────


class TestLoadFlatJson:
    """Tests for load_flat_json()."""

    def test_loads_valid_flat_json(self, temp_json_flat_file):
        """A valid flat JSON file is loaded correctly as a dict[str, str]."""
        data = load_flat_json(temp_json_flat_file)
        assert isinstance(data, dict)
        assert "Btn_Home" in data
        assert data["Btn_Home"] == "Home"
        assert data["Btn_Action"] == "Action"
        assert data["Btn_Cancel"] == "Cancel"

    def test_loads_all_entries(self, temp_json_flat_file):
        """All entries in the file are loaded."""
        data = load_flat_json(temp_json_flat_file)
        assert len(data) == 5

    def test_raises_on_missing_file(self):
        """FileNotFoundError is raised when the file does not exist."""
        with pytest.raises(FileNotFoundError):
            load_flat_json("/nonexistent/path/file.json")

    def test_raises_on_invalid_json(self, temp_dir):
        """json.JSONDecodeError is raised when the file contains invalid JSON."""
        bad_file = temp_dir / "bad.json"
        bad_file.write_text("{invalid json content", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_flat_json(bad_file)

    def test_loads_file_with_string_path(self, temp_json_flat_file):
        """load_flat_json works with a string path, not just Path."""
        data = load_flat_json(str(temp_json_flat_file))
        assert isinstance(data, dict)
        assert "Btn_Home" in data

    def test_preserves_unicode(self, temp_dir):
        """Unicode characters are preserved when loading."""
        filepath = temp_dir / "unicode.json"
        data = {"greeting": "Bonjour", "arabic": "مرحبا", "czech": "Dobrý den"}
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        loaded = load_flat_json(filepath)
        assert loaded["arabic"] == "مرحبا"
        assert loaded["czech"] == "Dobrý den"

    def test_empty_json_object(self, temp_dir):
        """An empty JSON object {} is loaded as an empty dict."""
        filepath = temp_dir / "empty.json"
        filepath.write_text("{}", encoding="utf-8")

        data = load_flat_json(filepath)
        assert data == {}


# ─── save_flat_json ───────────────────────────────────────────────


class TestSaveFlatJson:
    """Tests for save_flat_json()."""

    def test_saves_flat_json(self, temp_dir, sample_json_flat):
        """Flat JSON data is saved correctly to disk."""
        filepath = temp_dir / "output.json"
        save_flat_json(filepath, sample_json_flat)

        assert filepath.exists()
        with filepath.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == sample_json_flat

    def test_creates_parent_directories(self, temp_dir, sample_json_flat):
        """save_flat_json creates parent directories if they don't exist."""
        filepath = temp_dir / "subdir" / "nested" / "output.json"
        save_flat_json(filepath, sample_json_flat)

        assert filepath.exists()

    def test_overwrites_existing_file(self, temp_dir, sample_json_flat):
        """save_flat_json overwrites an existing file."""
        filepath = temp_dir / "output.json"
        save_flat_json(filepath, {"old_key": "old_value"})
        save_flat_json(filepath, sample_json_flat)

        with filepath.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == sample_json_flat
        assert "old_key" not in loaded

    def test_preserves_unicode(self, temp_dir):
        """Unicode characters are preserved when saving."""
        filepath = temp_dir / "unicode_output.json"
        data = {"greeting": "Bonjour", "arabic": "مرحبا", "czech": "Dobrý den"}
        save_flat_json(filepath, data)

        with filepath.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["arabic"] == "مرحبا"
        assert loaded["czech"] == "Dobrý den"

    def test_uses_string_path(self, temp_dir, sample_json_flat):
        """save_flat_json works with a string path, not just Path."""
        filepath = str(temp_dir / "str_output.json")
        save_flat_json(filepath, sample_json_flat)

        assert Path(filepath).exists()

    def test_saved_json_is_readable_by_load_flat_json(self, temp_dir, sample_json_flat):
        """Data saved by save_flat_json can be loaded by load_flat_json."""
        filepath = temp_dir / "roundtrip.json"
        save_flat_json(filepath, sample_json_flat)

        loaded = load_flat_json(filepath)
        assert loaded == sample_json_flat


# ─── load_structured_json ─────────────────────────────────────────


class TestLoadStructuredJson:
    """Tests for load_structured_json()."""

    def test_loads_valid_structured_json(self, temp_json_structured_file):
        """A valid structured JSON file is loaded with metadata and contexts."""
        data = load_structured_json(temp_json_structured_file)

        assert "metadata" in data
        assert "contexts" in data
        assert data["metadata"]["language"] == "FR"
        assert data["metadata"]["language_name"] == "Français"

    def test_loads_all_contexts(self, temp_json_structured_file):
        """All context sections are loaded."""
        data = load_structured_json(temp_json_structured_file)
        assert "btn" in data["contexts"]
        assert "menu" in data["contexts"]

    def test_counts_total_entries(self, temp_json_structured_file):
        """Total entries across all contexts are correct."""
        data = load_structured_json(temp_json_structured_file)
        total = sum(len(ctx) for ctx in data["contexts"].values())
        assert total == 4

    def test_raises_on_missing_file(self):
        """FileNotFoundError is raised when the file does not exist."""
        with pytest.raises(FileNotFoundError):
            load_structured_json("/nonexistent/path/structured.json")

    def test_raises_on_invalid_json(self, temp_dir):
        """json.JSONDecodeError is raised for invalid JSON."""
        bad_file = temp_dir / "bad_structured.json"
        bad_file.write_text("{invalid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_structured_json(bad_file)

    def test_handles_missing_metadata(self, temp_dir):
        """Structured JSON with no metadata still loads contexts."""
        filepath = temp_dir / "no_meta.json"
        data = {"contexts": {"btn": {"Button": "Bouton"}}}
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded = load_structured_json(filepath)
        assert loaded.get("metadata") is None
        assert "btn" in loaded["contexts"]


# ─── save_structured_json ─────────────────────────────────────────


class TestSaveStructuredJson:
    """Tests for save_structured_json()."""

    def test_saves_structured_json(self, temp_dir, sample_json_structured):
        """Structured JSON data is saved correctly."""
        filepath = temp_dir / "structured_output.json"
        save_structured_json(filepath, sample_json_structured)

        assert filepath.exists()
        loaded = load_structured_json(filepath)
        assert loaded["metadata"]["language"] == "FR"
        assert "btn" in loaded["contexts"]

    def test_creates_parent_directories(self, temp_dir, sample_json_structured):
        """save_structured_json creates parent directories."""
        filepath = temp_dir / "deep" / "nested" / "output.json"
        save_structured_json(filepath, sample_json_structured)

        assert filepath.exists()

    def test_roundtrip_structured_json(self, temp_dir, sample_json_structured):
        """Data saved by save_structured_json can be loaded by load_structured_json."""
        filepath = temp_dir / "roundtrip_structured.json"
        save_structured_json(filepath, sample_json_structured)

        loaded = load_structured_json(filepath)
        assert loaded == sample_json_structured

    def test_preserves_unicode_in_structured(self, temp_dir):
        """Unicode in structured JSON is preserved on roundtrip."""
        data = {
            "metadata": {"language": "AR", "language_name": "Arabe"},
            "contexts": {"ui": {"Hello": "مرحبا", "Goodbye": "مع السلامة"}},
        }
        filepath = temp_dir / "arabic.json"
        save_structured_json(filepath, data)

        loaded = load_structured_json(filepath)
        assert loaded["contexts"]["ui"]["Hello"] == "مرحبا"
        assert loaded["contexts"]["ui"]["Goodbye"] == "مع السلامة"


# ─── create_dropdown_metadata ──────────────────────────────────────


class TestCreateDropdownMetadata:
    """Tests for create_dropdown_metadata()."""

    def test_creates_metadata_with_required_fields(self):
        """Metadata dict contains all required fields."""
        metadata = create_dropdown_metadata(
            language_code="FR",
            language_name="Français",
            total_entries=100,
            source_file="dropdown.xlsx",
        )

        assert "language" in metadata
        assert "language_name" in metadata
        assert "source_file" in metadata
        assert "generated_date" in metadata
        assert "total_entries" in metadata

    def test_metadata_values_are_correct(self):
        """Metadata values match the function arguments."""
        metadata = create_dropdown_metadata(
            language_code="CZ",
            language_name="Tchèque",
            total_entries=2629,
            source_file="Dropdown_a_traduire.xlsx",
        )

        assert metadata["language"] == "CZ"
        assert metadata["language_name"] == "Tchèque"
        assert metadata["total_entries"] == 2629
        assert metadata["source_file"] == "Dropdown_a_traduire.xlsx"

    def test_metadata_date_format(self):
        """generated_date is in YYYY-MM-DD format."""
        metadata = create_dropdown_metadata(
            language_code="EN",
            language_name="Anglais",
            total_entries=50,
            source_file="test.xlsx",
        )

        import re

        assert re.match(r"\d{4}-\d{2}-\d{2}", metadata["generated_date"])

    def test_metadata_with_zero_entries(self):
        """Metadata can be created with zero entries."""
        metadata = create_dropdown_metadata(
            language_code="DE",
            language_name="Allemand",
            total_entries=0,
            source_file="empty.xlsx",
        )

        assert metadata["total_entries"] == 0
