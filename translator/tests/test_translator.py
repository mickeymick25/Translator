"""
Tests for core/translator.py — Translation module.

Covers:
- is_rate_limit_error(): rate limit detection
- translate_text(): empty/whitespace input, successful translation, retry logic, rate limit handling
- translate_text(): cache integration (hit, miss, disabled)
- translate_batch(): batch processing with checkpoint callback, cache flush
- translate_batch_generator(): generator mode
"""

import os
from unittest.mock import MagicMock, call, patch

import pytest
from core.translator import (
    is_rate_limit_error,
    translate_batch,
    translate_batch_generator,
    translate_text,
)

# ─── is_rate_limit_error ──────────────────────────────────────────


class TestIsRateLimitError:
    """Tests for the rate limit error detection function."""

    def test_429_code_detected(self):
        """HTTP 429 is a rate limit error."""
        assert is_rate_limit_error("HTTP 429 Too Many Requests") is True

    def test_too_many_requests_detected(self):
        """'Too Many Requests' message is a rate limit error."""
        assert is_rate_limit_error("Server Error: You made too many requests") is True

    def test_case_insensitive(self):
        """Detection is case-insensitive."""
        assert is_rate_limit_error("429 TOO MANY REQUESTS") is True
        assert is_rate_limit_error("Too Many Requests") is True

    def test_429_in_longer_message(self):
        """429 embedded in a longer error message is detected."""
        assert is_rate_limit_error("Request failed with status 429 from server") is True

    def test_generic_server_error_not_detected(self):
        """A generic server error (500) is NOT a rate limit error."""
        assert is_rate_limit_error("Server Error: Internal Server Error") is False

    def test_connection_error_not_detected(self):
        """A connection error is NOT a rate limit error."""
        assert is_rate_limit_error("ConnectionError: Network unreachable") is False

    def test_empty_string_not_detected(self):
        """An empty string is NOT a rate limit error."""
        assert is_rate_limit_error("") is False

    def test_rate_limit_with_additional_info(self):
        """Rate limit error with additional context is detected."""
        assert (
            is_rate_limit_error(
                "429: You have exceeded the rate limit of 5 requests per second"
            )
            is True
        )


# ─── translate_text ───────────────────────────────────────────────


class TestTranslateTextEmptyInput:
    """Tests for translate_text with empty/whitespace input."""

    def test_empty_string_returns_empty(self):
        """An empty string should return an empty string without calling the API."""
        assert translate_text("", "en", "fr") == ""

    def test_whitespace_only_returns_whitespace(self):
        """A whitespace-only string should be returned as-is."""
        assert translate_text("   ", "en", "fr") == "   "

    def test_none_like_empty(self):
        """A string with only tabs/newlines should be returned as-is."""
        assert translate_text("\t\n", "en", "fr") == "\t\n"


class TestTranslateTextSuccess:
    """Tests for translate_text with successful API calls."""

    @patch("core.translator.GoogleTranslator")
    def test_returns_translated_text(self, mock_cls):
        """A successful translation returns the translated text."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        result = translate_text("Hello", "en", "fr")
        assert result == "Bonjour"

    @patch("core.translator.GoogleTranslator")
    def test_passes_correct_source_and_target(self, mock_cls):
        """GoogleTranslator is called with the correct source and target."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        translate_text("Hello", "en", "fr")
        mock_cls.assert_called_once_with(source="en", target="fr")

    @patch("core.translator.GoogleTranslator")
    def test_returns_original_on_empty_api_result(self, mock_cls):
        """If the API returns None/empty, the original text is returned."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = None
        mock_cls.return_value = mock_instance

        result = translate_text("Hello", "en", "fr")
        assert result == "Hello"

    @patch("core.translator.GoogleTranslator")
    def test_special_characters_preserved(self, mock_cls):
        """Special characters in input are preserved in the output."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "100 %"
        mock_cls.return_value = mock_instance

        result = translate_text("100%", "en", "fr")
        assert "%" in result


class TestTranslateTextRetry:
    """Tests for translate_text retry logic on errors."""

    @patch("core.translator.time.sleep")
    @patch("core.translator.GoogleTranslator")
    def test_retries_on_server_error(self, mock_cls, mock_sleep):
        """After a server error, translate_text retries and succeeds on 2nd attempt."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = [
            Exception("Server Error: Internal Server Error"),
            "Résultat",
        ]
        mock_cls.return_value = mock_instance

        result = translate_text("Test", "en", "fr", max_retries=3)
        assert result == "Résultat"
        assert mock_instance.translate.call_count == 2

    @patch("core.translator.time.sleep")
    @patch("core.translator.GoogleTranslator")
    def test_returns_original_after_max_retries(self, mock_cls, mock_sleep):
        """After max retries, the original text is returned."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception("Persistent server error")
        mock_cls.return_value = mock_instance

        result = translate_text("Test", "en", "fr", max_retries=2)
        assert result == "Test"
        assert mock_instance.translate.call_count == 2

    @patch("core.translator.time.sleep")
    @patch("core.translator.GoogleTranslator")
    def test_rate_limit_triggers_backoff(self, mock_cls, mock_sleep):
        """A 429 rate limit error triggers exponential backoff."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = [
            Exception("429 Too Many Requests"),
            "OK",
        ]
        mock_cls.return_value = mock_instance

        result = translate_text("Test", "en", "fr", max_retries=3, base_delay=0.2)
        assert result == "OK"
        # sleep is called once (after the rate limit error)
        assert mock_sleep.call_count >= 1

    @patch("core.translator.time.sleep")
    @patch("core.translator.GoogleTranslator")
    def test_rate_limit_increases_delay(self, mock_cls, mock_sleep):
        """On consecutive rate limit errors, the delay increases (exponential backoff)."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = [
            Exception("429 Too Many Requests"),
            Exception("429 Too Many Requests"),
            "OK",
        ]
        mock_cls.return_value = mock_instance

        result = translate_text("Test", "en", "fr", max_retries=3, base_delay=0.2)
        assert result == "OK"

        # Collect all sleep call arguments
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        # There should be at least 2 sleep calls (one per retry)
        assert len(sleep_calls) >= 2
        # First delay should be base_delay * 2^0 = 0.2
        # Second delay should be base_delay * 2^1 = 0.4 (current_delay doubles)
        assert sleep_calls[1] > sleep_calls[0] or sleep_calls[1] >= 0.4

    @patch("core.translator.time.sleep")
    @patch("core.translator.GoogleTranslator")
    def test_non_rate_limit_error_uses_linear_backoff(self, mock_cls, mock_sleep):
        """Non-rate-limit errors use a linear backoff: (attempt+1)*2 seconds."""
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = [
            Exception("ConnectionError: Network unreachable"),
            "OK",
        ]
        mock_cls.return_value = mock_instance

        result = translate_text("Test", "en", "fr", max_retries=3)
        assert result == "OK"

        # First retry should sleep 2 seconds (=(0+1)*2)
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] == 2.0


# ─── translate_batch ──────────────────────────────────────────────


class TestTranslateBatch:
    """Tests for translate_batch with mocked API."""

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    def test_batch_returns_translations_in_order(self, mock_translate, mock_sleep):
        """translate_batch returns translations in the same order as input."""
        mock_translate.side_effect = ["Bonjour", "Action", "Annuler"]
        mock_sleep.return_value = None

        results = translate_batch(
            ["Hello", "Action", "Cancel"],
            "en",
            "fr",
            rate_limit_seconds=0,  # No sleep for tests
        )
        assert results == ["Bonjour", "Action", "Annuler"]

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    def test_batch_calls_translate_text_for_each_item(self, mock_translate, mock_sleep):
        """translate_batch calls translate_text once per item."""
        mock_translate.side_effect = ["A", "B", "C"]
        mock_sleep.return_value = None

        translate_batch(
            ["item1", "item2", "item3"],
            "en",
            "fr",
            rate_limit_seconds=0,
        )
        assert mock_translate.call_count == 3

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    def test_batch_checkpoint_callback_called(self, mock_translate, mock_sleep):
        """Checkpoint callback is called every checkpoint_every items."""
        mock_translate.side_effect = ["A", "B", "C", "D", "E"]
        mock_sleep.return_value = None

        checkpoints = []

        def checkpoint_cb(completed, results):
            checkpoints.append(completed)

        translate_batch(
            ["a", "b", "c", "d", "e"],
            "en",
            "fr",
            rate_limit_seconds=0,
            checkpoint_callback=checkpoint_cb,
            checkpoint_every=2,
        )
        # Checkpoint at 2, 4, then final at 5
        assert 2 in checkpoints
        assert 4 in checkpoints
        assert 5 in checkpoints

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    def test_batch_empty_list(self, mock_translate, mock_sleep):
        """An empty list returns an empty list without calling translate_text."""
        mock_sleep.return_value = None

        results = translate_batch([], "en", "fr", rate_limit_seconds=0)
        assert results == []
        mock_translate.assert_not_called()


# ─── translate_batch_generator ────────────────────────────────────


class TestTranslateBatchGenerator:
    """Tests for translate_batch_generator."""

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    def test_yields_index_original_translated(self, mock_translate, mock_sleep):
        """Each yield is a tuple of (index, original, translated)."""
        mock_translate.side_effect = ["Bonjour", "Action"]
        mock_sleep.return_value = None

        results = list(
            translate_batch_generator(
                ["Hello", "Action"], "en", "fr", rate_limit_seconds=0
            )
        )
        assert results[0] == (0, "Hello", "Bonjour")
        assert results[1] == (1, "Action", "Action")

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    def test_generator_empty_list(self, mock_translate, mock_sleep):
        """An empty input yields nothing."""
        mock_sleep.return_value = None

        results = list(translate_batch_generator([], "en", "fr", rate_limit_seconds=0))
        assert results == []
        mock_translate.assert_not_called()


# ─── translate_text with cache ─────────────────────────────────────


class TestTranslateTextWithCache:
    """Tests for translate_text() integration with the translation cache."""

    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_cache_hit_returns_cached_translation(
        self, mock_get_cache, mock_get_config, mock_cls
    ):
        """When cache is enabled and has a hit, the cached result is returned without API call."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_cache = MagicMock()
        mock_cache.get.return_value = "Bonjour"
        mock_get_cache.return_value = mock_cache

        result = translate_text("Hello", "en", "fr")
        assert result == "Bonjour"
        mock_cache.get.assert_called_once_with("en", "fr", "Hello")
        # API should NOT be called
        mock_cls.assert_not_called()

    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_cache_miss_calls_api_and_stores_result(
        self, mock_get_cache, mock_get_config, mock_cls
    ):
        """When cache is enabled but misses, the API is called and result is cached."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # cache miss
        mock_get_cache.return_value = mock_cache

        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        result = translate_text("Hello", "en", "fr")
        assert result == "Bonjour"
        # Cache miss was checked
        mock_cache.get.assert_called_once_with("en", "fr", "Hello")
        # Result was stored in cache
        mock_cache.put.assert_called_once_with("en", "fr", "Hello", "Bonjour")

    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_cache_disabled_does_not_check_cache(
        self, mock_get_cache, mock_get_config, mock_cls
    ):
        """When cache is disabled, no cache lookup or store is performed."""
        mock_config = MagicMock()
        mock_config.cache_enabled = False
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        result = translate_text("Hello", "en", "fr")
        assert result == "Bonjour"
        # get_cache should not be called when cache is disabled
        mock_get_cache.assert_not_called()

    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_cache_hit_for_different_language_pairs(
        self, mock_get_cache, mock_get_config, mock_cls
    ):
        """Cache lookups use the correct (source, target, text) key."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_cache = MagicMock()
        mock_cache.get.return_value = "Taste"
        mock_get_cache.return_value = mock_cache

        result = translate_text("Button", "en", "de")
        assert result == "Taste"
        mock_cache.get.assert_called_once_with("en", "de", "Button")

    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_empty_text_skips_cache(self, mock_get_cache, mock_get_config, mock_cls):
        """Empty text is returned as-is without checking the cache."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        result = translate_text("", "en", "fr")
        assert result == ""
        # Neither get_cache nor get_config should be called for empty text
        # (get_config IS called for the empty check, but get_cache is not)
        mock_cls.assert_not_called()

    @patch("core.translator.GoogleTranslator")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_failed_translation_does_not_cache(
        self, mock_get_cache, mock_get_config, mock_cls
    ):
        """When translation fails after retries, the result is NOT cached."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # cache miss
        mock_get_cache.return_value = mock_cache

        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception("Persistent error")
        mock_cls.return_value = mock_instance

        result = translate_text("Hello", "en", "fr", max_retries=1)
        assert result == "Hello"
        # Only get() was called (cache miss), but put() was never called
        mock_cache.get.assert_called_once_with("en", "fr", "Hello")
        mock_cache.put.assert_not_called()


# ─── translate_batch with cache ─────────────────────────────────────


class TestTranslateBatchWithCache:
    """Tests for translate_batch() integration with the translation cache."""

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_batch_flushes_cache_on_completion(
        self, mock_get_cache, mock_get_config, mock_translate, mock_sleep
    ):
        """translate_batch flushes the cache at the end."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_cache = MagicMock()
        mock_cache.stats.return_value = {
            "total_entries": 3,
            "hits": 2,
            "misses": 1,
            "hit_rate_pct": 66.7,
        }
        mock_get_cache.return_value = mock_cache

        mock_translate.side_effect = ["A", "B", "C"]
        mock_sleep.return_value = None

        translate_batch(["x", "y", "z"], "en", "fr", rate_limit_seconds=0)
        mock_cache.flush.assert_called_once()

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    @patch("core.translator.get_config")
    @patch("core.translator.get_cache")
    def test_batch_logs_cache_stats(
        self, mock_get_cache, mock_get_config, mock_translate, mock_sleep
    ):
        """translate_batch logs cache statistics after completion."""
        mock_config = MagicMock()
        mock_config.cache_enabled = True
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_cache = MagicMock()
        mock_cache.stats.return_value = {
            "total_entries": 10,
            "hits": 8,
            "misses": 2,
            "hit_rate_pct": 80.0,
        }
        mock_get_cache.return_value = mock_cache

        mock_translate.side_effect = ["A", "B"]
        mock_sleep.return_value = None

        translate_batch(["x", "y"], "en", "fr", rate_limit_seconds=0)
        mock_cache.stats.assert_called()

    @patch("core.translator.time.sleep")
    @patch("core.translator.translate_text")
    @patch("core.translator.get_config")
    def test_batch_does_not_flush_cache_when_disabled(
        self, mock_get_config, mock_translate, mock_sleep
    ):
        """When cache is disabled, no flush or stats are performed."""
        mock_config = MagicMock()
        mock_config.cache_enabled = False
        mock_config.TRANSLATION_CACHE_PATH = "/tmp/test_cache.json"
        mock_get_config.return_value = mock_config

        mock_translate.side_effect = ["A", "B"]
        mock_sleep.return_value = None

        # Should not raise any errors — cache code is skipped entirely
        results = translate_batch(["x", "y"], "en", "fr", rate_limit_seconds=0)
        assert results == ["A", "B"]
