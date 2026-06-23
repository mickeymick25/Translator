#!/usr/bin/env python3
"""
Mode: translate-json — Translation of a flat JSON file.

This module implements the translation mode that processes a flat JSON file,
translates all values, and saves the result progressively to handle
interruptions gracefully.

Supports batch processing via BATCH_LANGS environment variable for parallel
translations to multiple target languages.
"""

import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.config import LANGUAGES, get_config
from core.io_json import load_flat_json, save_flat_json
from core.translator import translate_batch
from core.translator_factory import TranslationProvider

logger = logging.getLogger(__name__)

# Global state for signal handling
_translated_data: dict[str, str] = {}
_output_path: Optional[Path] = None


def _create_checkpoint_callback(
    output_path: Path,
    keys_to_translate: list[str],
    existing_data: dict[str, str],
) -> Callable:
    """
    Create a checkpoint callback for progressive saving.

    The callback merges new translations with existing data before saving,
    ensuring that previously translated entries are never lost on interruption.

    Args:
        output_path: Path to the output file.
        keys_to_translate: Ordered list of keys being translated.
        existing_data: Previously translated data to preserve in checkpoints.

    Returns:
        A callback function that saves progress.
    """

    def checkpoint_callback(completed: int, results: list[str]) -> None:
        """Save current translation progress to disk."""
        new_translations = dict(zip(keys_to_translate[:completed], results[:completed]))
        # Merge new translations with existing data (new takes precedence)
        merged_data = {**existing_data, **new_translations}
        save_flat_json(output_path, merged_data)
        # Update existing_data so subsequent checkpoints include previous new translations
        existing_data.update(new_translations)
        logger.info(
            "Checkpoint saved: %d/%d entries (%.1f%%) -> %s (total: %d)",
            completed,
            len(results),
            completed / len(results) * 100 if results else 0,
            output_path.name,
            len(merged_data),
        )

    return checkpoint_callback


def _create_batch_checkpoint_callback(
    output_path: Path,
    all_keys: list[str],
    existing_data: dict[str, str],
) -> Callable:
    """Create a checkpoint callback for batch provider chunk-level saving (IMP3-T005).

    Called after each chunk completes, receives the chunk's translated dict
    and merges it with existing data before saving.

    Args:
        output_path: Path to the output file.
        all_keys: All keys being translated (for logging).
        existing_data: Previously translated data to preserve.

    Returns:
        A callback function(chunk_idx, total_chunks, chunk_result).
    """
    total_keys = len(all_keys)

    def batch_checkpoint_callback(
        chunk_idx: int, total_chunks: int, chunk_result: dict[str, str]
    ) -> None:
        """Save progress after a chunk completes."""
        existing_data.update(chunk_result)
        merged_data = dict(existing_data)
        save_flat_json(output_path, merged_data)
        logger.info(
            "Batch checkpoint: chunk %d/%d -> %s (total: %d/%d entries)",
            chunk_idx + 1,
            total_chunks,
            output_path.name,
            len(merged_data),
            total_keys,
        )

    return batch_checkpoint_callback


def _translate_with_batch_provider(
    provider: TranslationProvider,
    items: dict[str, str],
    source_lang: str,
    target_lang: str,
    checkpoint_callback: Callable | None = None,
) -> dict[str, str]:
    """Translate items using a batch-capable provider with chunk-level checkpoint (IMP3-T005).

    Chunks the items according to the provider's chunk_size, calls
    translate_batch on each chunk, and triggers checkpoint after each chunk.

    Args:
        provider: Batch-capable TranslationProvider (e.g. OllamaProvider).
        items: Key-value pairs to translate.
        source_lang: Source language code.
        target_lang: Target language code.
        checkpoint_callback: Optional callback(chunk_idx, total_chunks, chunk_result).

    Returns:
        Dict with all keys and their translated values.
    """
    # Chunk items using the provider's chunk_size
    chunk_size = getattr(provider, "_chunk_size", 50)
    keys = list(items.keys())
    chunks = []
    for i in range(0, len(keys), chunk_size):
        chunk_keys = keys[i : i + chunk_size]
        chunks.append({k: items[k] for k in chunk_keys})

    total_chunks = len(chunks)
    results: dict[str, str] = {}

    for chunk_idx, chunk in enumerate(chunks):
        chunk_result = provider.translate_batch(chunk, source_lang, target_lang)
        results.update(chunk_result)

        # Checkpoint after each chunk
        if checkpoint_callback:
            checkpoint_callback(chunk_idx, total_chunks, chunk_result)

    return results


def _setup_signal_handlers() -> None:
    """
    Setup signal handlers for graceful interruption handling.
    Uses global _translated_data and _output_path for emergency save.
    """

    def signal_handler(signum: int, frame) -> None:
        logger.info("Received signal %d, saving current progress...", signum)
        if _translated_data and _output_path:
            save_flat_json(_output_path, _translated_data)
            logger.info("Emergency save completed: %d entries", len(_translated_data))
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def _check_untranslated_keys(
    source_data: dict[str, str],
    translated_data: dict[str, str],
    target_lang: str,
    min_length: int = 15,
) -> list[str]:
    """Detect untranslated keys by comparing translated values to source.

    A value is considered potentially untranslated if it is identical to the
    source text and longer than min_length characters. Short texts (like
    "OK" or "Cancel") may legitimately be the same across languages.

    Args:
        source_data: Original key-value pairs.
        translated_data: Translated key-value pairs.
        target_lang: Target language code (for logging).
        min_length: Minimum text length to flag (default: 15).

    Returns:
        List of keys that appear untranslated.
    """
    untranslated: list[str] = []
    for key, source_text in source_data.items():
        translated = translated_data.get(key, "")
        if (
            source_text
            and len(source_text.strip()) >= min_length
            and translated == source_text
        ):
            untranslated.append(key)
            logger.warning(
                "[%s] Untranslated key '%s': value matches source (%d chars)",
                target_lang.upper(),
                key,
                len(source_text),
            )

    if untranslated:
        logger.warning(
            "[%s] %d key(s) appear untranslated (value == source, len >= %d): %s",
            target_lang.upper(),
            len(untranslated),
            min_length,
            ", ".join(untranslated),
        )

    return untranslated


def _translate_single_language(
    source_file: str,
    source_data: dict[str, str],
    source_lang: str,
    target_lang: str,
    output_dir: Path,
) -> tuple[str, bool, int]:
    """
    Translate all entries for a single target language.

    Thread-safe: uses local variables instead of module globals to avoid
    race conditions when running multiple languages in parallel.

    Args:
        source_file: Path to source file for logging.
        source_data: Dictionary of source translations.
        source_lang: Source language code.
        target_lang: Target language code (user-facing).
        output_dir: Output directory path.

    Returns:
        Tuple of (target_lang, success, entries_translated)
    """
    # Get API target code (e.g., 'cz' user code -> 'cs' for Google Translate)
    lang_info = LANGUAGES.get(target_lang, {})
    api_target_lang = lang_info.get("target", target_lang)

    # Create output path for this language
    output_path = output_dir / f"translation_{source_lang}_{target_lang}.json"

    # Use thread-local data instead of module globals
    global _output_path  # only for signal handler (main thread)
    _output_path = output_path

    logger.info("-" * 40)
    logger.info(f"Translating to: {target_lang.upper()} (API: {api_target_lang})")
    logger.info(f"Output file: {output_path.name}")
    logger.info("-" * 40)

    keys = list(source_data.keys())
    total = len(keys)

    # Check for resume — use local variable for thread safety
    translated_data: dict[str, str] = {}
    if output_path.exists():
        logger.info("Output file exists, loading existing translations for resume...")
        translated_data = load_flat_json(output_path)
        existing_keys = set(translated_data.keys())
        logger.info(f"Loaded {len(existing_keys)} existing translations")
    else:
        existing_keys = set()

    logger.info(f"Total keys: {total}")

    # Filter out already translated keys
    keys_to_translate = [k for k in keys if k not in existing_keys]
    remaining = len(keys_to_translate)
    logger.info(f"Keys remaining to translate: {remaining}")

    # Dry-run: simulate without API calls and without writing output files.
    # We return after the resume diff so the caller gets a useful preview of
    # what would be translated, but no provider call and no file write happen.
    config = get_config()
    if config.dry_run:
        logger.info(
            f"[{target_lang.upper()}] DRY RUN -- would translate {remaining} key(s) "
            f"({len(existing_keys)} already translated, {total} total). "
            "No API calls, no file written."
        )
        return target_lang, True, 0

    if remaining == 0:
        logger.info(
            f"[{target_lang.upper()}] All keys already translated. Nothing to do."
        )
        return target_lang, True, 0

    # Note: Signal handlers are not set up in parallel mode (only works in main thread)

    # Prepare texts to translate
    texts_to_translate = [source_data[key] for key in keys_to_translate]

    # IMP3-T005: Detect batch-capable provider (e.g. Ollama) for chunk-level checkpoint
    from core.translator import get_provider

    current_provider = get_provider()
    use_batch_provider = hasattr(current_provider, "translate_batch")

    if use_batch_provider:
        # Batch mode: use provider's translate_batch with chunk-level checkpoint
        logger.info(
            f"[{target_lang.upper()}] Using batch provider: {current_provider.name}"
        )

        items_to_translate = dict(zip(keys_to_translate, texts_to_translate))

        # Create a chunk-level checkpoint callback
        batch_checkpoint_cb = _create_batch_checkpoint_callback(
            output_path, keys_to_translate, translated_data
        )

        # Translate using the batch provider
        logger.info(f"[{target_lang.upper()}] Starting batch translation...")

        translated_dict = _translate_with_batch_provider(
            current_provider,
            items_to_translate,
            source_lang,
            api_target_lang,
            batch_checkpoint_cb,
        )

        # Merge new translations into local data
        translated_data.update(translated_dict)
    else:
        # Classic mode: translate item by item with entry-level checkpoint
        logger.info(
            f"[{target_lang.upper()}] Using provider: {current_provider.name} "
            f"(serialized — provider is not batch-capable)"
        )
        # Create checkpoint callback (pass existing data so checkpoints preserve it)
        checkpoint_cb = _create_checkpoint_callback(
            output_path, keys_to_translate, translated_data
        )

        # Translate in batch with rate limiting
        logger.info(f"[{target_lang.upper()}] Starting translation...")

        translated_texts = translate_batch(
            items=texts_to_translate,
            source_lang=source_lang,
            target_lang=api_target_lang,
            rate_limit_seconds=0.15,
            checkpoint_callback=checkpoint_cb,
            checkpoint_every=100,
        )

        # Merge new translations into local data
        for key, translated in zip(keys_to_translate, translated_texts):
            translated_data[key] = translated

    # Final save — use local output_path, not global _output_path
    save_flat_json(output_path, translated_data)

    # Post-translation check: detect untranslated keys (Bug #2)
    _check_untranslated_keys(source_data, translated_data, target_lang)

    logger.info(
        f"[{target_lang.upper()}] Completed! Total entries: {len(translated_data)}"
    )
    return target_lang, True, remaining


def run() -> None:
    """
    Execute the translate-json mode.

    Loads a flat JSON source file, translates all values using the configured
    source and target languages, and saves the result progressively. Supports
    resume on interruption by loading existing translations from the output file.

    If BATCH_LANGS is set with multiple languages, translations run in parallel
    using ThreadPoolExecutor.
    """
    config = get_config()

    # Setup paths
    source_file = config.get_source_path()
    source_lang = config.SOURCE_LANG
    batch_langs = config.batch_langs_list

    # Build date-based output folder: {OUTPUT_DIR}/{YYYY_MM_DD}_Export/
    date_str = datetime.now().strftime("%Y_%m_%d")
    session_folder = f"{date_str}_Export"
    output_dir = Path(config.OUTPUT_DIR) / session_folder
    # In dry-run, do not create the output folder (no filesystem side effects);
    # _translate_single_language handles the simulation without writing.
    if not config.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("MODE: translate-json")
    logger.info("=" * 60)
    logger.info("Source file: %s", source_file)
    logger.info("Output dir: %s", output_dir)
    logger.info("Source lang: %s", source_lang.upper())
    logger.info("Batch langs: %s", batch_langs)
    logger.info("=" * 60)

    # Load source data once
    source_data = load_flat_json(source_file)
    total_keys = len(source_data)
    logger.info("Total keys to translate: %d", total_keys)

    # Determine target languages
    if len(batch_langs) > 1:
        # Batch mode: translate to multiple languages in parallel
        logger.info("=" * 60)
        logger.info(
            "BATCH MODE: Translating to %d languages in parallel", len(batch_langs)
        )
        logger.info("=" * 60)

        # Filter out source language if present (can't translate to itself)
        target_langs = [lang for lang in batch_langs if lang != source_lang]
        if source_lang in batch_langs:
            logger.info("Note: Skipping %s (same as source lang)", source_lang.upper())
        logger.info("Target languages: %s", [lang.upper() for lang in target_langs])

        # Use ThreadPoolExecutor for parallel translation
        max_workers = min(len(target_langs), 4)  # Limit to 4 parallel workers
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _translate_single_language,
                    source_file,
                    source_data,
                    source_lang,
                    target_lang,
                    output_dir,
                ): target_lang
                for target_lang in target_langs
            }

            for future in as_completed(futures):
                target_lang = futures[future]
                try:
                    lang, success, count = future.result()
                    results[lang] = (success, count)
                    logger.info(
                        "[%s] Translation finished: %d entries", lang.upper(), count
                    )
                except Exception as e:
                    logger.error("[%s] Translation failed: %s", target_lang.upper(), e)
                    results[target_lang] = (False, 0)

        # Summary
        logger.info("=" * 60)
        logger.info("BATCH SUMMARY")
        logger.info("=" * 60)
        for lang, (success, count) in sorted(results.items()):
            status = "✓" if success else "✗"
            logger.info("  %s %s: %d entries translated", status, lang.upper(), count)
        logger.info("=" * 60)

    elif len(batch_langs) == 1:
        # Single language mode (original behavior)
        target_lang = batch_langs[0]
        _translate_single_language(
            source_file, source_data, source_lang, target_lang, output_dir
        )
    else:
        # Fallback to TARGET_LANG if BATCH_LANGS is empty
        target_lang = config.TARGET_LANG
        logger.info("No BATCH_LANGS, using TARGET_LANG: %s", target_lang.upper())
        _translate_single_language(
            source_file, source_data, source_lang, target_lang, output_dir
        )

    logger.info("=" * 60)
    logger.info("Translation completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run()
