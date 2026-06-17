"""
Factory for translation providers with fallback support (IMP-T004).

Provides TranslationProvider ABC, GoogleProvider, DeepLProvider, FallbackProvider,
and a create_provider factory function for constructing translation providers
with optional automatic fallback on persistent rate limit errors.
"""

import logging
import threading
from abc import ABC, abstractmethod

from deep_translator import DeeplTranslator, GoogleTranslator

logger = logging.getLogger(__name__)

# DeepL language code mapping: project codes → DeepL API codes (uppercase ISO)
DEEPL_LANG_MAP = {
    "cz": "CS",
    "cs": "CS",
    "sk": "SK",
    "fr": "FR",
    "de": "DE",
    "it": "IT",
    "ar": "AR",
    "en": "EN",
}


class TranslationProvider(ABC):
    """Abstract base class for translation providers."""

    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str:
        """Translate text from source language to target language."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the human-readable name of this provider."""


class GoogleProvider(TranslationProvider):
    """Translation provider using Google Translate via deep_translator.

    Thread-safety: the underlying `deep_translator.GoogleTranslator` library is
    NOT thread-safe (shared internal state across calls). To prevent the race
    condition observed in Bug #1 (export 05_27 — target language overwritten
    between translator construction and `.translate()` call), a single
    `threading.Lock` serializes all calls to `translate()`. The lock is held
    for the entire duration of the underlying HTTP request, ensuring that at
    most one thread is interacting with the library at a time.

    Note: serializing Google calls removes the network-level parallelism for
    the multi-language batch mode. Providers that are thread-safe at the
    network level (e.g. Ollama) can still benefit from ThreadPoolExecutor.
    """

    def __init__(self):
        self._translator_cls = GoogleTranslator
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "Google Translate"

    def translate(self, text: str, source: str, target: str) -> str:
        with self._lock:
            result = self._translator_cls(source=source, target=target).translate(text)
        if result is None or result == "":
            return text
        return result


class DeepLProvider(TranslationProvider):
    """Translation provider using DeepL via deep_translator."""

    def __init__(self, api_key: str, use_free_api: bool = True):
        if api_key == "":
            raise ValueError("DeepL API key is required")
        self._translator_cls = DeeplTranslator
        self._api_key = api_key
        self._use_free_api = use_free_api

    @property
    def name(self) -> str:
        if self._use_free_api:
            return "DeepL (Free)"
        return "DeepL (Pro)"

    def translate(self, text: str, source: str, target: str) -> str:
        mapped_source = DEEPL_LANG_MAP.get(source, source.upper())
        mapped_target = DEEPL_LANG_MAP.get(target, target.upper())
        result = self._translator_cls(
            source=mapped_source,
            target=mapped_target,
            api_key=self._api_key,
            use_free_api=self._use_free_api,
        ).translate(text)
        if result is None:
            return text
        return result


class FallbackProvider(TranslationProvider):
    """Composite provider that falls back to a secondary provider after rate limit errors.

    After 3 consecutive rate limit errors (containing "429" or "too many requests")
    from the primary provider, switches to the fallback provider. Returns to primary
    after a successful fallback call or a failed fallback call.
    """

    def __init__(self, primary: TranslationProvider, fallback: TranslationProvider):
        self._primary = primary
        self._fallback = fallback
        self._primary_failures = 0
        self._fallback_active = False

    @property
    def name(self) -> str:
        return f"{self._primary.name} (fallback: {self._fallback.name})"

    def translate(self, text: str, source: str, target: str) -> str:
        if self._fallback_active:
            try:
                result = self._fallback.translate(text, source, target)
                self._primary_failures = 0
                self._fallback_active = False
                return result
            except Exception:
                self._fallback_active = False
                return text

        try:
            result = self._primary.translate(text, source, target)
            self._primary_failures = 0
            return result
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "429" in error_msg or "too many requests" in error_msg

            if is_rate_limit:
                self._primary_failures += 1
                if self._primary_failures >= 3:
                    logger.warning(
                        "Primary provider %s hit %d rate limits, switching to fallback %s",
                        self._primary.name,
                        self._primary_failures,
                        self._fallback.name,
                    )
                    self._fallback_active = True
                    try:
                        result = self._fallback.translate(text, source, target)
                        self._primary_failures = 0
                        self._fallback_active = False
                        return result
                    except Exception:
                        self._fallback_active = False
                        return text
            return text


def create_provider(
    provider_type: str = "google",
    deepl_api_key: str = "",
    deepl_use_free_api: bool = True,
    fallback_enabled: bool = False,
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "minimax-m2.7:cloud",
    ollama_chunk_size: int = 50,
    ollama_temperature: float = 0,
    ollama_timeout: int = 300,
    ollama_max_retries: int = 2,
) -> TranslationProvider:
    """Factory function to create a translation provider, optionally with fallback.

    Args:
        provider_type: "google", "deepl", or "ollama" (case-insensitive).
        deepl_api_key: API key for DeepL. Required if provider_type is "deepl".
        deepl_use_free_api: Whether to use DeepL's free API tier.
        fallback_enabled: If True and deepl_api_key is provided, wraps the
            provider in a FallbackProvider with the other provider as fallback.
        ollama_url: URL for Ollama server (default: http://localhost:11434).
        ollama_model: Ollama model to use (default: qwen3).
        ollama_chunk_size: Number of items per chunk (default: 50).
        ollama_temperature: LLM temperature (default: 0).
        ollama_timeout: Request timeout in seconds (default: 300).
        ollama_max_retries: Max retries per chunk (default: 2).

    Returns:
        A TranslationProvider instance.

    Raises:
        ValueError: If provider_type is unknown or empty.
    """
    if not provider_type:
        raise ValueError("provider_type cannot be empty")

    provider_lower = provider_type.lower()

    if provider_lower == "google":
        provider = GoogleProvider()
    elif provider_lower == "deepl":
        provider = DeepLProvider(api_key=deepl_api_key, use_free_api=deepl_use_free_api)
    elif provider_lower == "ollama":
        from core.ollama_provider import OllamaProvider

        provider = OllamaProvider(
            model=ollama_model,
            base_url=ollama_url,
            chunk_size=ollama_chunk_size,
            temperature=ollama_temperature,
            timeout=ollama_timeout,
            max_retries=ollama_max_retries,
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")

    if fallback_enabled and deepl_api_key:
        if provider_lower == "google":
            fallback = DeepLProvider(
                api_key=deepl_api_key, use_free_api=deepl_use_free_api
            )
        elif provider_lower == "ollama":
            # For Ollama with fallback, use Google as fallback
            fallback = GoogleProvider()
        else:
            fallback = GoogleProvider()
        return FallbackProvider(provider, fallback)

    return provider
