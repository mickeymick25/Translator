"""
Tests for core/translator_factory.py — Multi-Provider with Fallback (IMP-T004).

Covers:
- TranslationProvider: ABC enforcement, abstract method requirements
- DEEPL_LANG_MAP: language code mappings for DeepL API
- GoogleProvider: translation via GoogleTranslator, name property, empty result handling
- DeepLProvider: translation via DeeplTranslator, language mapping, name variants, api_key validation
- FallbackProvider: composite pattern, rate limit switching after 3 errors, reset on success, fallback failure
- create_provider(): factory logic, provider selection, fallback wrapping, validation
"""

from abc import ABC
from unittest.mock import MagicMock, patch

import pytest
from core.translator_factory import (
    DEEPL_LANG_MAP,
    DeepLProvider,
    FallbackProvider,
    GoogleProvider,
    TranslationProvider,
    create_provider,
)

# ─── TranslationProvider (ABC) ──────────────────────────────────────


class TestTranslationProvider:
    """Tests for the TranslationProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """TranslationProvider is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TranslationProvider()

    def test_subclass_must_implement_translate(self):
        """A subclass missing translate() cannot be instantiated."""

        class IncompleteProvider(TranslationProvider):
            @property
            def name(self):
                return "Incomplete"

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_must_implement_name(self):
        """A subclass missing the name property cannot be instantiated."""

        class IncompleteProvider(TranslationProvider):
            def translate(self, text, source, target):
                return text

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_complete_subclass_can_be_instantiated(self):
        """A subclass implementing both abstract methods can be instantiated."""

        class CompleteProvider(TranslationProvider):
            @property
            def name(self):
                return "Complete"

            def translate(self, text, source, target):
                return text

        provider = CompleteProvider()
        assert provider.name == "Complete"
        assert provider.translate("Hello", "en", "fr") == "Hello"

    def test_is_subclass_of_abc(self):
        """TranslationProvider inherits from ABC."""
        assert issubclass(TranslationProvider, ABC)


# ─── DEEPL_LANG_MAP ────────────────────────────────────────────────


class TestDeeplLangMap:
    """Tests for the DEEPL_LANG_MAP language code mapping constant."""

    def test_is_dict(self):
        """DEEPL_LANG_MAP is a dictionary."""
        assert isinstance(DEEPL_LANG_MAP, dict)

    def test_maps_cz_to_cs(self):
        """The project code 'cz' maps to DeepL's 'CS' for Czech."""
        assert DEEPL_LANG_MAP.get("cz") == "CS"

    def test_maps_common_codes(self):
        """Common language codes are mapped to their uppercase DeepL equivalents."""
        expected = {
            "en": "EN",
            "fr": "FR",
            "de": "DE",
            "it": "IT",
            "sk": "SK",
            "ar": "AR",
        }
        for code, expected_upper in expected.items():
            assert DEEPL_LANG_MAP.get(code) == expected_upper

    def test_keys_are_lowercase(self):
        """All keys in DEEPL_LANG_MAP are lowercase."""
        for key in DEEPL_LANG_MAP:
            assert key == key.lower()


# ─── GoogleProvider ────────────────────────────────────────────────


class TestGoogleProvider:
    """Tests for the GoogleProvider concrete implementation."""

    @patch("core.translator_factory.GoogleTranslator")
    def test_translate_calls_google_translator(self, mock_cls):
        """translate() delegates to deep_translator.GoogleTranslator."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        provider = GoogleProvider()
        result = provider.translate("Hello", "en", "fr")

        assert result == "Bonjour"
        mock_cls.assert_called_once_with(source="en", target="fr")
        mock_instance.translate.assert_called_once_with("Hello")

    @patch("core.translator_factory.GoogleTranslator")
    def test_translate_passes_correct_source_and_target(self, mock_cls):
        """GoogleTranslator is constructed with the exact source and target codes."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Hallo"
        mock_cls.return_value = mock_instance

        provider = GoogleProvider()
        provider.translate("Hello", "en", "de")

        mock_cls.assert_called_once_with(source="en", target="de")

    @patch("core.translator_factory.GoogleTranslator")
    def test_returns_original_on_none_result(self, mock_cls):
        """If GoogleTranslator returns None, the original text is returned."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = None
        mock_cls.return_value = mock_instance

        provider = GoogleProvider()
        result = provider.translate("Hello", "en", "fr")
        assert result == "Hello"

    @patch("core.translator_factory.GoogleTranslator")
    def test_returns_original_on_empty_string_result(self, mock_cls):
        """If GoogleTranslator returns an empty string, the original text is returned."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = ""
        mock_cls.return_value = mock_instance

        provider = GoogleProvider()
        result = provider.translate("Hello", "en", "fr")
        assert result == "Hello"

    def test_name_property(self):
        """The name property returns 'Google Translate'."""
        provider = GoogleProvider()
        assert provider.name == "Google Translate"

    def test_is_translation_provider_subclass(self):
        """GoogleProvider is a subclass of TranslationProvider."""
        assert issubclass(GoogleProvider, TranslationProvider)


# ─── DeepLProvider ─────────────────────────────────────────────────


class TestDeepLProvider:
    """Tests for the DeepLProvider concrete implementation."""

    @patch("core.translator_factory.DeeplTranslator")
    def test_translate_calls_deepl_translator(self, mock_cls):
        """translate() delegates to deep_translator.DeeplTranslator."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        provider = DeepLProvider(api_key="test-key")
        result = provider.translate("Hello", "en", "fr")

        assert result == "Bonjour"
        mock_instance.translate.assert_called_once_with("Hello")

    @patch("core.translator_factory.DeeplTranslator")
    def test_translate_maps_language_codes_to_uppercase(self, mock_cls):
        """Lowercase language codes are mapped to uppercase for the DeepL API."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Bonjour"
        mock_cls.return_value = mock_instance

        provider = DeepLProvider(api_key="test-key")
        provider.translate("Hello", "en", "fr")

        mock_cls.assert_called_once_with(
            source="EN", target="FR", api_key="test-key", use_free_api=True
        )

    @patch("core.translator_factory.DeeplTranslator")
    def test_translate_maps_cz_to_cs(self, mock_cls):
        """The 'cz' code is mapped to 'CS' for DeepL (Czech language)."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Ahoj"
        mock_cls.return_value = mock_instance

        provider = DeepLProvider(api_key="test-key")
        provider.translate("Hello", "en", "cz")

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["source"] == "EN"
        assert call_kwargs["target"] == "CS"

    @patch("core.translator_factory.DeeplTranslator")
    def test_name_free_api(self, mock_cls):
        """Name is 'DeepL (Free)' when using the free API."""
        provider = DeepLProvider(api_key="test-key", use_free_api=True)
        assert provider.name == "DeepL (Free)"

    @patch("core.translator_factory.DeeplTranslator")
    def test_name_pro_api(self, mock_cls):
        """Name is 'DeepL (Pro)' when using the pro API."""
        provider = DeepLProvider(api_key="test-key", use_free_api=False)
        assert provider.name == "DeepL (Pro)"

    def test_requires_api_key_empty(self):
        """DeepLProvider raises ValueError when api_key is an empty string."""
        with pytest.raises(ValueError):
            DeepLProvider(api_key="")

    @patch("core.translator_factory.DeeplTranslator")
    def test_returns_original_on_none_result(self, mock_cls):
        """If DeeplTranslator returns None, the original text is returned."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = None
        mock_cls.return_value = mock_instance

        provider = DeepLProvider(api_key="test-key")
        result = provider.translate("Hello", "en", "fr")
        assert result == "Hello"

    @patch("core.translator_factory.DeeplTranslator")
    def test_use_free_api_passed_to_constructor(self, mock_cls):
        """The use_free_api flag is forwarded to the DeeplTranslator constructor."""
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Hallo"
        mock_cls.return_value = mock_instance

        provider = DeepLProvider(api_key="pro-key", use_free_api=False)
        provider.translate("Hello", "en", "de")

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["use_free_api"] is False

    def test_is_translation_provider_subclass(self):
        """DeepLProvider is a subclass of TranslationProvider."""
        assert issubclass(DeepLProvider, TranslationProvider)


# ─── FallbackProvider ─────────────────────────────────────────────


class TestFallbackProvider:
    """Tests for the FallbackProvider composite implementation."""

    def test_uses_primary_by_default(self):
        """FallbackProvider delegates to the primary provider when no errors occur."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        primary.translate.return_value = "Bonjour"

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"
        fallback.translate.return_value = "Bonjour (DeepL)"

        provider = FallbackProvider(primary, fallback)
        result = provider.translate("Hello", "en", "fr")

        assert result == "Bonjour"
        primary.translate.assert_called_once_with("Hello", "en", "fr")
        fallback.translate.assert_not_called()

    def test_does_not_switch_on_non_rate_limit_error(self):
        """Non-rate-limit errors from primary do NOT trigger fallback switching."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        primary.translate.side_effect = Exception("Server Error: 500")

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"
        fallback.translate.return_value = "Bonjour (DeepL)"

        provider = FallbackProvider(primary, fallback)
        result = provider.translate("Hello", "en", "fr")

        assert result == "Hello"
        fallback.translate.assert_not_called()

    def test_does_not_switch_after_one_rate_limit_error(self):
        """A single rate limit error does NOT switch to fallback (need 3)."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        primary.translate.side_effect = Exception("429 Too Many Requests")

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"

        provider = FallbackProvider(primary, fallback)
        provider.translate("Hello", "en", "fr")

        fallback.translate.assert_not_called()

    def test_does_not_switch_after_two_rate_limit_errors(self):
        """Two consecutive rate limit errors do NOT switch to fallback (need 3)."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        primary.translate.side_effect = Exception("429 Too Many Requests")

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"

        provider = FallbackProvider(primary, fallback)
        provider.translate("Hello", "en", "fr")
        provider.translate("Hello", "en", "fr")

        fallback.translate.assert_not_called()

    def test_switches_to_fallback_after_three_rate_limit_errors(self):
        """After 3 consecutive rate limit errors on primary, switches to fallback."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        primary.translate.side_effect = Exception("429 Too Many Requests")

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"
        fallback.translate.return_value = "Bonjour (DeepL)"

        provider = FallbackProvider(primary, fallback)
        provider.translate("Hello", "en", "fr")  # 1st rate limit
        provider.translate("Hello", "en", "fr")  # 2nd rate limit
        result = provider.translate("Hello", "en", "fr")  # 3rd -> switch

        assert result == "Bonjour (DeepL)"
        fallback.translate.assert_called_once_with("Hello", "en", "fr")

    def test_resets_counter_on_primary_success(self):
        """A successful call to primary resets the consecutive rate limit counter."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"

        provider = FallbackProvider(primary, fallback)

        # 2 rate limit errors
        primary.translate.side_effect = Exception("429 Too Many Requests")
        provider.translate("Hello", "en", "fr")
        provider.translate("Hello", "en", "fr")

        # A success resets the counter to 0
        primary.translate.side_effect = None
        primary.translate.return_value = "Bonjour"
        provider.translate("Hello", "en", "fr")

        # 1 more rate limit should NOT trigger fallback (counter was reset)
        primary.translate.side_effect = Exception("429 Too Many Requests")
        provider.translate("Hello", "en", "fr")

        fallback.translate.assert_not_called()

    def test_fallback_success_returns_to_primary(self):
        """After a successful fallback translation, subsequent calls return to primary."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"
        fallback.translate.return_value = "Bonjour (DeepL)"

        provider = FallbackProvider(primary, fallback)

        # Trigger 3 rate limit errors to switch to fallback
        primary.translate.side_effect = Exception("429 Too Many Requests")
        provider.translate("Hello", "en", "fr")  # 1st
        provider.translate("Hello", "en", "fr")  # 2nd
        result = provider.translate("Hello", "en", "fr")  # 3rd -> fallback
        assert result == "Bonjour (DeepL)"

        # Fallback succeeds -> return to primary
        primary.translate.side_effect = None
        primary.translate.return_value = "Bonjour"
        result = provider.translate("Hello", "en", "fr")
        assert result == "Bonjour"

    def test_fallback_failure_returns_to_primary(self):
        """If fallback also fails, returns to primary on the next call."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        primary.translate.side_effect = Exception("429 Too Many Requests")

        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"
        fallback.translate.side_effect = Exception("DeepL quota exceeded")

        provider = FallbackProvider(primary, fallback)

        # Trigger 3 rate limit errors to switch to fallback
        provider.translate("Hello", "en", "fr")  # 1st
        provider.translate("Hello", "en", "fr")  # 2nd
        result = provider.translate("Hello", "en", "fr")  # 3rd -> fallback also fails
        assert result == "Hello"

        # Next call should go back to primary (no infinite fallback loop)
        primary.translate.side_effect = None
        primary.translate.return_value = "Bonjour"
        result = provider.translate("Hello", "en", "fr")
        assert result == "Bonjour"

    def test_name_format(self):
        """Name follows the format '{primary.name} (fallback: {fallback.name})'."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Google Translate"
        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "DeepL (Free)"

        provider = FallbackProvider(primary, fallback)
        assert provider.name == "Google Translate (fallback: DeepL (Free))"

    def test_is_translation_provider_subclass(self):
        """FallbackProvider is a subclass of TranslationProvider."""
        primary = MagicMock(spec=TranslationProvider)
        primary.name = "Primary"
        fallback = MagicMock(spec=TranslationProvider)
        fallback.name = "Fallback"

        provider = FallbackProvider(primary, fallback)
        assert isinstance(provider, TranslationProvider)


# ─── create_provider ───────────────────────────────────────────────


class TestCreateProvider:
    """Tests for the create_provider factory function."""

    def test_creates_google_provider_by_default(self):
        """Default provider_type creates a GoogleProvider."""
        provider = create_provider()
        assert isinstance(provider, GoogleProvider)

    def test_creates_google_provider_explicitly(self):
        """provider_type='google' creates a GoogleProvider."""
        provider = create_provider(provider_type="google")
        assert isinstance(provider, GoogleProvider)

    @patch("core.translator_factory.DeeplTranslator")
    def test_creates_deepl_provider_with_api_key(self, mock_cls):
        """provider_type='deepl' with api_key creates a DeepLProvider."""
        provider = create_provider(provider_type="deepl", deepl_api_key="test-key")
        assert isinstance(provider, DeepLProvider)
        assert provider.name == "DeepL (Free)"

    @patch("core.translator_factory.DeeplTranslator")
    def test_creates_deepl_provider_pro(self, mock_cls):
        """provider_type='deepl' with use_free_api=False creates a pro DeepLProvider."""
        provider = create_provider(
            provider_type="deepl",
            deepl_api_key="pro-key",
            deepl_use_free_api=False,
        )
        assert isinstance(provider, DeepLProvider)
        assert provider.name == "DeepL (Pro)"

    def test_raises_value_error_for_unknown_provider(self):
        """An unknown provider_type raises ValueError."""
        with pytest.raises(ValueError):
            create_provider(provider_type="unknown")

    def test_raises_value_error_for_empty_provider_type(self):
        """An empty string provider_type raises ValueError."""
        with pytest.raises(ValueError):
            create_provider(provider_type="")

    @patch("core.translator_factory.DeeplTranslator")
    def test_creates_fallback_when_enabled_with_deepl_key(self, mock_cls):
        """fallback_enabled=True with deepl_api_key wraps in FallbackProvider."""
        provider = create_provider(
            provider_type="google",
            deepl_api_key="test-key",
            fallback_enabled=True,
        )
        assert isinstance(provider, FallbackProvider)
        assert "Google Translate" in provider.name
        assert "DeepL" in provider.name

    def test_no_fallback_without_deepl_key(self):
        """fallback_enabled=True without deepl_api_key returns unwrapped GoogleProvider."""
        provider = create_provider(
            provider_type="google",
            deepl_api_key="",
            fallback_enabled=True,
        )
        assert isinstance(provider, GoogleProvider)

    def test_no_fallback_when_disabled(self):
        """fallback_enabled=False returns unwrapped provider even with deepl_api_key."""
        provider = create_provider(
            provider_type="google",
            deepl_api_key="test-key",
            fallback_enabled=False,
        )
        assert isinstance(provider, GoogleProvider)

    @patch("core.translator_factory.DeeplTranslator")
    def test_deepl_primary_with_google_fallback(self, mock_cls):
        """provider_type='deepl' with fallback uses DeepL as primary, Google as fallback."""
        provider = create_provider(
            provider_type="deepl",
            deepl_api_key="test-key",
            fallback_enabled=True,
        )
        assert isinstance(provider, FallbackProvider)
        assert "DeepL" in provider.name
        assert "Google" in provider.name


# ─── GoogleProvider — Thread Safety (Bug #1) ────────────────────────


class TestGoogleProviderThreadSafety:
    """Tests for GoogleProvider thread safety (Bug #1, export 05_27).

    The Google provider uses the `deep_translator` library, which has shared
    internal state and is NOT thread-safe. When multiple threads call
    `translate()` concurrently with different target languages, the target
    language can be overwritten between translator construction and the
    `.translate()` call, producing translations in the wrong language.

    These tests reproduce the race condition and verify the fix:
    a single threading.Lock serializes calls to GoogleProvider.translate().
    """

    @patch("core.translator_factory.GoogleTranslator")
    def test_translate_uses_internal_lock(self, mock_cls):
        """GoogleProvider exposes a threading.Lock used to serialize translate() calls."""
        import threading

        provider = GoogleProvider()
        assert hasattr(provider, "_lock"), "GoogleProvider should expose a _lock"
        assert isinstance(provider._lock, type(threading.Lock()))

    @patch("core.translator_factory.GoogleTranslator")
    def test_translate_acquires_lock_during_call(self, mock_cls):
        """translate() holds the provider's lock for the entire duration of the call.

        This is the contract that protects against the race condition observed in
        Bug #1: while one thread is calling GoogleTranslator(...).translate(text),
        no other thread can start a competing call on the same provider.
        """
        import threading

        # Track when the lock is held and when the call is in-flight.
        state = {"lock_held_during_call": False, "concurrent_calls": 0}
        max_concurrent = {"value": 0}
        call_started = threading.Event()
        second_call_can_proceed = threading.Event()

        def slow_translate(text):
            state["concurrent_calls"] += 1
            max_concurrent["value"] = max(
                max_concurrent["value"], state["concurrent_calls"]
            )
            call_started.set()
            # Wait until we've checked that the second call is blocked.
            second_call_can_proceed.wait(timeout=2)
            state["concurrent_calls"] -= 1
            return f"OK:{text}"

        mock_instance = MagicMock()
        mock_instance.translate.side_effect = slow_translate
        mock_cls.return_value = mock_instance

        provider = GoogleProvider()

        # Patch the lock with a tracked version.
        real_lock = provider._lock
        lock_acquired_count = {"n": 0}

        class TrackedLock:
            def __init__(self, wrapped):
                self._wrapped = wrapped

            def __enter__(self):
                lock_acquired_count["n"] += 1
                state["lock_held_during_call"] = True
                return self._wrapped.__enter__()

            def __exit__(self, *args):
                state["lock_held_during_call"] = False
                return self._wrapped.__exit__(*args)

        provider._lock = TrackedLock(real_lock)

        # Start the first call (will block on the event).
        first_result: dict = {}
        first_error: dict = {}

        def first_call():
            try:
                first_result["value"] = provider.translate("Hello", "en", "fr")
            except Exception as e:
                first_error["value"] = e

        t1 = threading.Thread(target=first_call)
        t1.start()
        call_started.wait(timeout=2)

        # While the first call is in-flight, try a second call: it must wait
        # on the lock and only one call must be active at a time.
        second_result: dict = {}
        second_error: dict = {}

        def second_call():
            try:
                second_result["value"] = provider.translate("Hello", "en", "cs")
            except Exception as e:
                second_error["value"] = e

        t2 = threading.Thread(target=second_call)
        t2.start()
        # Give t2 a chance to (try to) acquire the lock.
        import time

        time.sleep(0.1)
        # At this point t1 is still running, so max_concurrent must be 1.
        assert max_concurrent["value"] == 1, (
            f"Concurrent calls detected: {max_concurrent['value']}"
        )

        # Release the first call.
        second_call_can_proceed.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not first_error.get("value"), f"First call error: {first_error}"
        assert not second_error.get("value"), f"Second call error: {second_error}"
        assert first_result["value"] == "OK:Hello"
        assert second_result["value"] == "OK:Hello"
        assert max_concurrent["value"] == 1, "Lock failed to serialize calls"
        assert lock_acquired_count["n"] >= 2, "Lock was not acquired for both calls"

    @patch("core.translator_factory.GoogleTranslator")
    def test_lock_does_not_deadlock_under_load(self, mock_cls):
        """The serialization lock is reentrant-safe: 20 threads x 10 calls complete."""
        import threading

        mock_instance = MagicMock()
        mock_instance.translate.return_value = "OK"
        mock_cls.return_value = mock_instance

        provider = GoogleProvider()

        def worker():
            for _ in range(10):
                provider.translate("Hello", "en", "fr")

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "Thread deadlocked"
