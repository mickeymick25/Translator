"""
Translation module for the COP translations service.
Encapsulates all API calls to the translation provider with retry logic,
rate limiting, and batch processing support.
"""

import logging
import time
from typing import Any, Callable, Iterator

from deep_translator import GoogleTranslator

from core.cache import get_cache
from core.config import get_config

logger = logging.getLogger(__name__)


def is_rate_limit_error(error_msg: str) -> bool:
    """Detect if an error message indicates a rate limit (429 / Too Many Requests).

    Args:
        error_msg: The error message string to check.

    Returns:
        True if the error is a rate limit error, False otherwise.
    """
    msg = error_msg.lower()
    return "too many requests" in msg or "429" in msg


def translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
    max_retries: int = 3,
    base_delay: float = 0.2,
) -> str:
    """
    Translate a single text with smart rate limiting and optional caching.

    If the translation cache is enabled, checks the cache first and stores
    successful translations for future reuse.

    Args:
        text: The text to translate.
        source_lang: Source language code (e.g., 'en').
        target_lang: Target language code (e.g., 'cs').
        max_retries: Maximum number of retry attempts on failure.
        base_delay: Base delay between requests in seconds (default 0.2s = 5 req/s max for Google).
                   Gets multiplied by 2^(attempts-1) on rate limit errors.

    Returns:
        The translated text, or the original text if translation failed.

    Raises:
        No exceptions are raised - failures are logged and original text is returned.
    """
    if not text or len(text.strip()) == 0:
        return text

    # Check cache if enabled
    config = get_config()
    if config.cache_enabled:
        cache = get_cache(cache_path=config.TRANSLATION_CACHE_PATH)
        cached = cache.get(source_lang, target_lang, text)
        if cached is not None:
            return cached
    else:
        cache = None

    current_delay = base_delay

    for attempt in range(max_retries):
        try:
            result = GoogleTranslator(source=source_lang, target=target_lang).translate(
                text
            )
            if result:
                if cache:
                    cache.put(source_lang, target_lang, text, result)
                return result
            logger.warning(
                "Translation returned empty result for text: %s...", text[:50]
            )
            return text
        except Exception as e:
            is_rate_limit = is_rate_limit_error(str(e))

            if attempt < max_retries - 1:
                if is_rate_limit:
                    # Exponential backoff on rate limit errors
                    wait_time = current_delay * (2**attempt)
                    logger.warning(
                        "Rate limit hit, backing off %.1fs (attempt %d): %s",
                        wait_time,
                        attempt + 1,
                        str(e)[:100],
                    )
                else:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        "Translation attempt %d failed, retrying in %ds: %s",
                        attempt + 1,
                        wait_time,
                        str(e),
                    )
                time.sleep(wait_time)
                if is_rate_limit:
                    current_delay *= 2  # Increase delay for next attempt
            else:
                logger.error(
                    "Failed to translate after %d attempts: %s...",
                    max_retries,
                    text[:50],
                )
                return text

    return text


def translate_batch(
    items: list[str],
    source_lang: str,
    target_lang: str,
    rate_limit_seconds: float = 0.2,
    checkpoint_callback: Callable[[int, list[str]], None] | None = None,
    checkpoint_every: int = 100,
) -> list[str]:
    """
    Translate a batch of texts with rate limiting and checkpoint support.

    Args:
        items: List of texts to translate.
        source_lang: Source language code.
        target_lang: Target language code.
        rate_limit_seconds: Delay between API calls to respect rate limits.
        checkpoint_callback: Optional callback called every checkpoint_every items.
            Receives (completed_count, translatedTexts) to enable progressive saving.
        checkpoint_every: Number of items between checkpoint callbacks.

    Returns:
        List of translated texts in the same order as input items.

    Example:
        >>> def save_progress(done, texts):
        ...     save_json("checkpoint.json", texts[:done])
        >>> results = translate_batch(items, "en", "cs",
        ...     checkpoint_callback=save_progress, checkpoint_every=100)
    """
    total = len(items)
    results: list[str] = []
    translated_since_checkpoint: list[str] = []

    logger.info(
        "Starting batch translation: %d items from '%s' to '%s'",
        total,
        source_lang,
        target_lang,
    )

    for idx, item in enumerate(items):
        translated = translate_text(item, source_lang, target_lang)
        results.append(translated)
        translated_since_checkpoint.append(translated)

        # Rate limiting
        if rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)

        # Checkpoint callback
        if checkpoint_callback and len(translated_since_checkpoint) >= checkpoint_every:
            logger.debug("Checkpoint at %d/%d items", idx + 1, total)
            checkpoint_callback(idx + 1, results)
            translated_since_checkpoint.clear()

        # Progress logging every 100 items
        if (idx + 1) % 100 == 0:
            logger.info(
                "Progress: %d/%d (%.1f%%)",
                idx + 1,
                total,
                (idx + 1) / total * 100,
            )

    # Final checkpoint if there are remaining items
    if checkpoint_callback and translated_since_checkpoint:
        checkpoint_callback(total, results)

    # Flush cache if enabled
    config = get_config()
    if config.cache_enabled:
        cache = get_cache(cache_path=config.TRANSLATION_CACHE_PATH)
        cache.flush()
        stats = cache.stats()
        logger.info(
            "Cache stats: %d hits, %d misses (%.1f%% hit rate), %d total cached entries",
            stats["hits"],
            stats["misses"],
            stats["hit_rate_pct"],
            stats["total_entries"],
        )

    logger.info("Batch translation completed: %d/%d items", total, total)
    return results


def translate_batch_generator(
    items: list[str],
    source_lang: str,
    target_lang: str,
    rate_limit_seconds: float = 0.2,
) -> Iterator[tuple[int, str, str]]:
    """
    Translate a batch of texts as a generator, yielding results progressively.

    Args:
        items: List of texts to translate.
        source_lang: Source language code.
        target_lang: Target language code.
        rate_limit_seconds: Delay between API calls.

    Yields:
        Tuple of (index, original_text, translated_text).

    Example:
        >>> for idx, original, translated in translate_batch_generator(items, "en", "cs"):
        ...     print(f"{idx}: {original} -> {translated}")
    """
    total = len(items)

    for idx, item in enumerate(items):
        translated = translate_text(item, source_lang, target_lang)
        yield idx, item, translated

        if rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)

        if (idx + 1) % 100 == 0:
            logger.info(
                "Progress: %d/%d (%.1f%%)",
                idx + 1,
                total,
                (idx + 1) / total * 100,
            )
