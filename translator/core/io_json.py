"""
JSON I/O module for the translation service.
Handles reading and writing of flat and structured JSON files.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_flat_json(filepath: str | Path) -> dict[str, str]:
    """
    Load a flat JSON file where keys map directly to translation values.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Dictionary mapping keys to translation values.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    path = Path(filepath)
    logger.debug("Loading flat JSON from: %s", path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)

    logger.info("Loaded %d entries from flat JSON: %s", len(data), path.name)
    return data


def save_flat_json(filepath: str | Path, data: dict[str, str]) -> None:
    """
    Save a flat JSON dictionary to file.

    Args:
        filepath: Destination file path.
        data: Dictionary of key-value pairs to save.
    """
    path = Path(filepath)
    logger.debug("Saving flat JSON to: %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("Saved %d entries to flat JSON: %s", len(data), path.name)


def load_structured_json(filepath: str | Path) -> dict[str, Any]:
    """
    Load a structured JSON file with metadata and contexts.

    Expected structure:
        {
            "metadata": {...},
            "contexts": {
                "context_name": {
                    "origin_key": "translation_value",
                    ...
                },
                ...
            }
        }

    Args:
        filepath: Path to the JSON file.

    Returns:
        Dictionary containing metadata and contexts.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    path = Path(filepath)
    logger.debug("Loading structured JSON from: %s", path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    _metadata = data.get("metadata", {})
    contexts = data.get("contexts", {})
    total_entries = sum(len(ctx) for ctx in contexts.values())

    logger.info(
        "Loaded structured JSON: %s — %d contexts, %d total entries",
        path.name,
        len(contexts),
        total_entries,
    )

    return data


def save_structured_json(filepath: str | Path, data: dict[str, Any]) -> None:
    """
    Save a structured JSON file with metadata and contexts.

    Args:
        filepath: Destination file path.
        data: Dictionary containing metadata and contexts to save.
    """
    path = Path(filepath)
    logger.debug("Saving structured JSON to: %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    _metadata = data.get("metadata", {})
    contexts = data.get("contexts", {})
    total_entries = sum(len(ctx) for ctx in contexts.values())

    logger.info(
        "Saved structured JSON: %s — %d contexts, %d total entries",
        path.name,
        len(contexts),
        total_entries,
    )


def create_dropdown_metadata(
    language_code: str,
    language_name: str,
    total_entries: int,
    source_file: str,
) -> dict[str, Any]:
    """
    Create metadata block for dropdown translation files.

    Args:
        language_code: Two-letter language code (e.g., 'FR', 'CZ').
        language_name: Full language name (e.g., 'Français', 'Tchèque').
        total_entries: Total number of translation entries.
        source_file: Name of the source file used for translation.

    Returns:
        Metadata dictionary ready to be included in a structured JSON.
    """
    return {
        "language": language_code,
        "language_name": language_name,
        "source_file": source_file,
        "generated_date": datetime.now().strftime("%Y-%m-%d"),
        "total_entries": total_entries,
    }
