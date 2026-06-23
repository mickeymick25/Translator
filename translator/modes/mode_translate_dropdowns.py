"""
Mode: translate-dropdowns — Multi-language dropdown generation from XLSX or JSON source.

This module generates translation files for dropdown menus in multiple languages,
supporting both XLSX and JSON input formats with resume-on-interruption capability.

Output is organized in date-based folders: {OUTPUT_DIR}/{YYYY_MM_DD}_Dropdown/
"""

import logging
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import LANGUAGES, get_config
from core.io_json import (
    create_dropdown_metadata,
    load_structured_json,
    save_structured_json,
)
from core.io_xlsx import load_dropdown_xlsx, save_dropdown_xlsx
from core.translator import translate_batch, translate_text

logger = logging.getLogger(__name__)

# Rate limiting delay between API calls (in seconds)
RATE_LIMIT_SECONDS = 0.15


def _translate_dropdown_entry(text: str, target_lang: str) -> str:
    """
    Translate a single dropdown entry text to the target language.

    Args:
        text: The text to translate.
        target_lang: Target language code (e.g., 'cz', 'de').

    Returns:
        The translated text, or the original if translation fails.
    """
    if not text or len(text.strip()) == 0:
        return text

    lang_info = LANGUAGES.get(target_lang, {})
    target_code = lang_info.get("target", target_lang)

    result = translate_text(text, source_lang="en", target_lang=target_code)
    time.sleep(RATE_LIMIT_SECONDS)
    return result


def _detect_input_format(file_path: str | Path) -> str:
    """
    Detect the input file format based on extension.

    Args:
        file_path: Path to the input file.

    Returns:
        'xlsx', 'json', or 'unknown'.
    """
    ext = Path(file_path).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return "xlsx"
    elif ext == ".json":
        return "json"
    return "unknown"


def _load_source_data(file_path: str | Path, input_format: str) -> list[dict[str, str]]:
    """
    Load source dropdown data from the appropriate format.

    Args:
        file_path: Path to the source file.
        input_format: Either 'xlsx' or 'json'.

    Returns:
        List of entry dictionaries with 'origin', 'french', and 'context' keys.

    Raises:
        ValueError: If the format is not supported.
    """
    path = Path(file_path)

    if input_format == "xlsx":
        logger.info("Loading XLSX source: %s", path)
        return load_dropdown_xlsx(path)
    elif input_format == "json":
        logger.info("Loading JSON source: %s", path)
        structured_data = load_structured_json(path)
        return _extract_entries_from_structured_json(structured_data)
    else:
        raise ValueError(f"Unsupported input format: {input_format}")


def _extract_entries_from_structured_json(
    structured_data: dict[str, Any],
) -> list[dict[str, str]]:
    """
    Extract flat entry list from structured JSON data.

    Args:
        structured_data: Structured JSON with 'contexts' key.

    Returns:
        List of entry dictionaries.
    """
    entries: list[dict[str, str]] = []
    contexts = structured_data.get("contexts", {})

    for context_name, translations in contexts.items():
        for origin_text, translation_value in translations.items():
            entries.append(
                {
                    "origin": origin_text,
                    "french": translation_value,
                    "context": context_name,
                }
            )

    logger.info("Extracted %d entries from structured JSON", len(entries))
    return entries


def _get_source_file() -> tuple[str, str]:
    """
    Get the source file path and detect its format.

    Returns:
        Tuple of (file_path, format).
    """
    config = get_config()

    if config.SOURCE_FILE:
        file_path = config.SOURCE_FILE
    else:
        default_path = Path(config.EXCEL_DIR) / "Dropdown_a_traduire.xlsx"
        if default_path.exists():
            file_path = str(default_path)
        else:
            raise FileNotFoundError(f"Default source file not found: {default_path}")

    input_format = _detect_input_format(file_path)
    return file_path, input_format


def _load_or_create_output(
    output_path: Path,
) -> dict[str, Any]:
    """
    Load existing output file or create empty dict for resume support.

    Args:
        output_path: Path to the output file.

    Returns:
        Existing structured translation dictionary or empty dict.
    """
    if output_path.exists():
        logger.info("Loading existing file for resume: %s", output_path)
        return load_structured_json(output_path)
    return {}


def _generate_json_output(
    entries: list[dict[str, str]],
    target_lang: str,
    output_path: Path,
    source_file: str,
) -> None:
    """
    Generate a JSON output file for a single language.

    Args:
        entries: List of source entries.
        target_lang: Target language code.
        output_path: Path to the output JSON file.
        source_file: Name of the source file.
    """
    lang_info = LANGUAGES.get(target_lang, {})
    source_col = lang_info.get("source_col", "origin")

    # Build contexts dictionary
    contexts: dict[str, dict[str, str]] = defaultdict(dict)

    for entry in entries:
        context = entry["context"]

        if source_col == "origin":
            value = entry["origin"]
        else:
            value = entry.get("french", entry["origin"])

        contexts[context][entry["origin"]] = value

    # Create metadata
    metadata = create_dropdown_metadata(
        language_code=lang_info.get("code", target_lang.upper()),
        language_name=lang_info.get("name", target_lang),
        total_entries=len(entries),
        source_file=source_file,
    )

    output_data: dict[str, Any] = {
        "metadata": metadata,
        "contexts": dict(contexts),
    }

    save_structured_json(output_path, output_data)
    logger.info("Generated JSON: %s (%d entries)", output_path.name, len(entries))


def _translate_dropdown_entries_batch(
    entries: list[dict[str, str]],
    target_lang: str,
    existing_translations: dict[str, str],
) -> dict[str, str]:
    """
    Translate all dropdown entries for a target language in batch mode.

    Args:
        entries: List of source entries.
        target_lang: Target language code.
        existing_translations: Already translated entries (for resume).

    Returns:
        Dictionary mapping origin text to translated text.
    """
    # Get texts to translate (not already in existing_translations)
    texts_to_translate: list[str] = []
    origin_order: list[str] = []

    for entry in entries:
        origin = entry["origin"]
        if origin not in existing_translations:
            texts_to_translate.append(origin)
            origin_order.append(origin)

    total = len(texts_to_translate)
    if total == 0:
        logger.info("All entries already translated for %s", target_lang)
        return existing_translations

    logger.info(
        "Translating %d entries for %s (rate limited @ %.2fs)...",
        total,
        target_lang,
        RATE_LIMIT_SECONDS,
    )

    def checkpoint_callback(completed: int, results: list[str]) -> None:
        logger.info(
            "Progress: %d/%d (%.1f%%)",
            completed,
            total,
            completed / total * 100,
        )

    translated_texts = translate_batch(
        items=texts_to_translate,
        source_lang="en",
        target_lang=LANGUAGES.get(target_lang, {}).get("target", target_lang),
        rate_limit_seconds=RATE_LIMIT_SECONDS,
        checkpoint_callback=checkpoint_callback,
        checkpoint_every=100,
    )

    # Merge results
    for origin, translated in zip(origin_order, translated_texts):
        existing_translations[origin] = translated

    return existing_translations


def _build_contexts_from_translations(
    entries: list[dict[str, str]],
    translations: dict[str, str],
) -> dict[str, dict[str, str]]:
    """
    Build a contexts dictionary from a flat translations dictionary.

    Args:
        entries: List of source entries.
        translations: Dictionary mapping origin text to translated text.

    Returns:
        Dictionary mapping context name to {origin: translation}.
    """
    contexts: dict[str, dict[str, str]] = defaultdict(dict)
    for entry in entries:
        context = entry["context"]
        contexts[context][entry["origin"]] = translations.get(
            entry["origin"], entry["origin"]
        )
    return dict(contexts)


def _generate_all_json(
    entries: list[dict[str, str]],
    target_langs: list[str],
    source_file: str,
    output_dir: Path,
) -> None:
    """
    Generate JSON files for all target languages.

    Args:
        entries: List of source entries.
        target_langs: List of target language codes.
        source_file: Name of the source file.
        output_dir: Output directory path (already includes date folder).
    """
    logger.info("Generating JSON files for %d languages...", len(target_langs))

    for lang in target_langs:
        lang_info = LANGUAGES.get(lang, {})
        _source_col = lang_info.get("source_col", "origin")

        output_path = output_dir / f"dropdown_{lang}.json"

        if lang in ("en", "fr"):
            # No API translation needed, extract from source columns
            logger.info("Processing %s (no translation needed)...", lang.upper())
            _generate_json_output(entries, lang, output_path, source_file)
        else:
            # Check for resume capability
            existing = _load_or_create_output(output_path)

            if existing:
                # Partial resume: translate only missing entries
                # Merge existing translations with new ones
                existing_contexts = existing.get("contexts", {})
                flat_existing: dict[str, str] = {}
                for ctx_translations in existing_contexts.values():
                    flat_existing.update(ctx_translations)

                translations = _translate_dropdown_entries_batch(
                    entries, lang, flat_existing
                )

                # Rebuild contexts with new translations
                contexts = _build_contexts_from_translations(entries, translations)

                metadata = create_dropdown_metadata(
                    language_code=lang_info.get("code", lang.upper()),
                    language_name=lang_info.get("name", lang),
                    total_entries=len(entries),
                    source_file=source_file,
                )

                output_data: dict[str, Any] = {
                    "metadata": metadata,
                    "contexts": contexts,
                }

                save_structured_json(output_path, output_data)
                logger.info("Generated JSON (resumed): %s", output_path.name)
            else:
                # Full translation needed
                translations = _translate_dropdown_entries_batch(entries, lang, {})

                contexts = _build_contexts_from_translations(entries, translations)

                metadata = create_dropdown_metadata(
                    language_code=lang_info.get("code", lang.upper()),
                    language_name=lang_info.get("name", lang),
                    total_entries=len(entries),
                    source_file=source_file,
                )

                output_data: dict[str, Any] = {
                    "metadata": metadata,
                    "contexts": contexts,
                }

                save_structured_json(output_path, output_data)
                logger.info("Generated JSON: %s", output_path.name)


def _generate_all_xlsx(
    entries: list[dict[str, str]],
    target_langs: list[str],
    output_dir: Path,
) -> None:
    """
    Generate XLSX output with one sheet per language.

    All source JSON files must already exist in output_dir.

    Args:
        entries: List of source entries.
        target_langs: List of target language codes.
        output_dir: Output directory path (already includes date folder).
    """
    logger.info("Generating XLSX file...")

    output_path = output_dir / "dropdown_all_languages.xlsx"

    # Build translations dict for save_dropdown_xlsx
    translations: dict[str, dict[str, str]] = {}

    for lang in target_langs:
        lang_info = LANGUAGES.get(lang, {})
        _source_col = lang_info.get("source_col", "origin")

        if lang in ("en", "fr"):
            # No API translation
            translations[lang] = {}
        else:
            # Load from existing JSON in the same date folder
            json_file = output_dir / f"dropdown_{lang}.json"

            if json_file.exists():
                existing = load_structured_json(json_file)
                contexts = existing.get("contexts", {})
                lang_translations: dict[str, str] = {}
                for ctx_translations in contexts.values():
                    lang_translations.update(ctx_translations)
                translations[lang] = lang_translations
            else:
                # Translate all on the fly
                lang_translations = _translate_dropdown_entries_batch(entries, lang, {})
                translations[lang] = lang_translations

    # Filter to only supported languages for XLSX
    xlsx_langs = {k: v for k, v in LANGUAGES.items() if k in target_langs}

    save_dropdown_xlsx(entries, translations, output_path, xlsx_langs)
    logger.info("Generated XLSX: %s", output_path.name)


def run() -> None:
    """
    Execute the translate-dropdowns mode.

    Loads dropdown source data from XLSX or JSON, translates to all configured
    languages, and generates output files in the specified format.

    All output files are organized in a date-based folder: {OUTPUT_DIR}/{YYYY_MM_DD}_Dropdown/
    """
    config = get_config()

    # Build date-based output folder: {OUTPUT_DIR}/{YYYY_MM_DD}_Dropdown/
    date_str = datetime.now().strftime("%Y_%m_%d")
    session_folder = f"{date_str}_Dropdown"
    output_dir = Path(config.OUTPUT_DIR) / session_folder

    target_langs = config.batch_langs_list
    output_format = config.OUTPUT_FORMAT.lower()

    logger.info("=" * 60)
    logger.info("MODE: translate-dropdowns")
    logger.info("=" * 60)
    logger.info("Output folder: %s", output_dir)
    logger.info("Target languages: %s", target_langs)
    logger.info("Output format: %s", output_format)
    logger.info("=" * 60)

    # Get source file
    try:
        source_file, input_format = _get_source_file()
    except FileNotFoundError as e:
        logger.error("Source file not found: %s", e)
        return

    logger.info("Source file: %s (format: %s)", source_file, input_format.upper())

    # Load source data
    try:
        entries = _load_source_data(source_file, input_format)
    except Exception as e:
        logger.error("Failed to load source data: %s", e)
        return

    logger.info("Loaded %d entries", len(entries))

    # Context statistics
    context_counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        context_counts[entry["context"]] += 1
    logger.info("Contexts: %d", len(context_counts))
    for ctx, count in sorted(context_counts.items()):
        logger.info("  - %s: %d entries", ctx, count)

    # Dry-run: simulate without API calls and without writing output files.
    # Report what would be generated, then bail out before any file is created.
    if config.dry_run:
        langs_to_translate = [lang for lang in target_langs if lang not in ("en", "fr")]
        logger.info("=" * 60)
        logger.info("DRY RUN -- no API calls, no files written.")
        logger.info("  Entries: %d", len(entries))
        logger.info("  Target languages: %s", target_langs)
        logger.info("  Languages requiring API translation: %s", langs_to_translate)
        logger.info("  Output format: %s", output_format)
        logger.info("  Output folder (not created): %s", output_dir)
        logger.info("=" * 60)
        return

    # Ensure output directory exists (includes date folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine output format
    if output_format == "auto":
        output_format = input_format if input_format != "unknown" else "json"

    # Generate outputs based on format
    if output_format == "json":
        _generate_all_json(entries, target_langs, Path(source_file).name, output_dir)
    elif output_format == "xlsx":
        _generate_all_xlsx(entries, target_langs, output_dir)
    else:
        logger.error("Unsupported output format: %s", output_format)
        return

    logger.info("=" * 60)
    logger.info("Dropdown translation completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run()
