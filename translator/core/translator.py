"""
Translation module for the COP translations service.
Encapsulates all API calls to the translation provider with retry logic,
rate limiting, and batch processing support.
"""

import logging
import time
from typing import Callable, Iterator

from core.cache import get_cache
from core.config import get_config
from core.rate_limiter import get_rate_limiter
from core.translator_factory import TranslationProvider, create_provider

logger = logging.getLogger(__name__)

# Global provider instance (lazy-loaded)
_provider: TranslationProvider | None = None


def get_provider() -> TranslationProvider:
    """
    Get the translation provider (lazy initialization).

    Creates the provider based on configuration:
    - TRANSLATION_PROVIDER: 'google' (default) or 'deepl'
    - DEEPL_API_KEY: required for DeepL
    - DEEPL_USE_FREE_API: use free tier (default: true)
    - TRANSLATION_FALLBACK: auto-fallback on rate limits (default: false)
    """
    global _provider
    if _provider is None:
        config = get_config()
        logger.info(
            "Creating translation provider: %s (fallback=%s)",
            config.TRANSLATION_PROVIDER,
            config.fallback_enabled,
        )
        _provider = create_provider(
            provider_type=config.TRANSLATION_PROVIDER,
            deepl_api_key=config.DEEPL_API_KEY,
            deepl_use_free_api=config.deepl_use_free_api_enabled,
            fallback_enabled=config.fallback_enabled,
            ollama_url=config.OLLAMA_URL,
            ollama_model=config.OLLAMA_MODEL,
            ollama_chunk_size=config.ollama_chunk_size_int,
            ollama_temperature=config.ollama_temperature_float,
            ollama_timeout=config.ollama_timeout_int,
            ollama_max_retries=config.ollama_max_retries_int,
        )
    return _provider


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
    key_id: str | None = None,
) -> str:
    """
    Translate a single text with smart rate limiting and optional caching.

    If the translation cache is enabled, checks the cache first and stores
    successful translations for future reuse.

    For rate limit (429) errors, the adaptive rate limiter manages wait delays.
    For other errors, a linear backoff of (attempt+1)*2 seconds is used.

    Args:
        text: The text to translate.
        source_lang: Source language code (e.g., 'en').
        target_lang: Target language code (e.g., 'cs').
        max_retries: Maximum number of retry attempts on failure.

    Returns:
        The translated text, or the original text if translation failed.

    Raises:
        No exceptions are raised - failures are logged and original text is returned.
    """
    if not text or len(text.strip()) == 0:
        return text

    # Check cache if enabled
    config = get_config()

    # Dry-run: simulate without API calls and without cache side effects.
    # The source text is returned unchanged so callers can preview what would
    # be translated without consuming quota or mutating the cache.
    if config.dry_run:
        logger.info("Dry run: skip translation for text: %s...", text[:50])
        return text

    if config.cache_enabled:
        cache = get_cache(cache_path=config.TRANSLATION_CACHE_PATH)
        cached = cache.get(source_lang, target_lang, text, key_id=key_id)
        if cached is not None:
            return cached
    else:
        cache = None

    rate_limiter = get_rate_limiter()

    for attempt in range(max_retries):
        try:
            provider = get_provider()
            result = provider.translate(text, source_lang, target_lang)
            if result:
                rate_limiter.record_success()
                if cache:
                    cache.put(source_lang, target_lang, text, result, key_id=key_id)
                return result
            logger.warning(
                "Translation returned empty result for text: %s...", text[:50]
            )
            return text
        except Exception as e:
            is_rate_limit = is_rate_limit_error(str(e))

            if is_rate_limit:
                # Rate limit error: use adaptive rate limiter (no double backoff)
                rate_limiter.record_error()
                _, wait_time = rate_limiter.should_wait()
                if attempt < max_retries - 1:
                    logger.warning(
                        "Rate limit hit (attempt %d), waiting %.1fs: %s",
                        attempt + 1,
                        wait_time,
                        str(e)[:100],
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "Failed to translate after %d attempts: %s...",
                        max_retries,
                        text[:50],
                    )
                    return text
            else:
                # Non-rate-limit error: linear backoff
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        "Translation attempt %d failed, retrying in %ds: %s",
                        attempt + 1,
                        wait_time,
                        str(e),
                    )
                    time.sleep(wait_time)
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
