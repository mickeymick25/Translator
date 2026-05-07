"""
Cache module for the translation service.
Provides persistent translation caching to avoid re-translating
the same terms across multiple runs.

The cache stores (source_lang, target_lang, text) → translation pairs
in a JSON file, enabling instant retrieval of previously translated terms.
"""

import json
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class TranslationCache:
    """
    Persistent translation cache backed by a JSON file.

    Structure of the cache file:
    {
        "metadata": {
            "version": 1,
            "total_entries": 1500
        },
        "entries": {
            "en:fr:Hello": "Bonjour",
            "en:de:Button": "Taste",
            ...
        }
    }

    The cache key is composed of: {source_lang}:{target_lang}:{text}
    This guarantees uniqueness regardless of the language pair.
    """

    def __init__(self, cache_path: str | Path = "/app/output/.translation_cache.json"):
        self._path = Path(cache_path)
        self._entries: dict[str, str] = {}
        self._lock = Lock()
        self._dirty = False
        self._hits = 0
        self._misses = 0

        self._load()

    @staticmethod
    def _make_key(source_lang: str, target_lang: str, text: str) -> str:
        """Generate a unique cache key for a (source, target, text) triplet."""
        return f"{source_lang}:{target_lang}:{text}"

    def get(self, source_lang: str, target_lang: str, text: str) -> str | None:
        """
        Retrieve a translation from the cache.

        Returns:
            The translation if present (cache hit), None otherwise (cache miss).
        """
        key = self._make_key(source_lang, target_lang, text)
        with self._lock:
            if key in self._entries:
                self._hits += 1
                logger.debug("Cache HIT: %s", key[:80])
                return self._entries[key]
            self._misses += 1
            logger.debug("Cache MISS: %s", key[:80])
            return None

    def put(
        self, source_lang: str, target_lang: str, text: str, translation: str
    ) -> None:
        """Add a translation to the cache."""
        key = self._make_key(source_lang, target_lang, text)
        with self._lock:
            if key not in self._entries or self._entries[key] != translation:
                self._entries[key] = translation
                self._dirty = True

    def flush(self) -> None:
        """Save the cache to disk if it has been modified."""
        with self._lock:
            if not self._dirty:
                return
            self._save()
            self._dirty = False

    def stats(self) -> dict[str, int | float]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "total_entries": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 1),
            }

    def _load(self) -> None:
        """Load the cache from disk."""
        if not self._path.exists():
            logger.info("No existing translation cache at %s", self._path)
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = data.get("entries", {})
            logger.info(
                "Loaded translation cache: %d entries from %s",
                len(self._entries),
                self._path.name,
            )
        except Exception as e:
            logger.warning("Failed to load translation cache: %s — starting fresh", e)
            self._entries = {}

    def _save(self) -> None:
        """Write the cache to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "metadata": {
                    "version": 1,
                    "total_entries": len(self._entries),
                },
                "entries": self._entries,
            }
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(
                "Cache saved: %d entries to %s",
                len(self._entries),
                self._path.name,
            )
        except Exception as e:
            logger.error("Failed to save translation cache: %s", e)


# Global cache instance (lazy-loaded)
_cache: TranslationCache | None = None


def get_cache(cache_path: str | None = None) -> TranslationCache:
    """
    Get the global translation cache instance.
    Creates the instance on first call (lazy initialization).

    Args:
        cache_path: Optional path to the cache file. Only used on first call.

    Returns:
        The global TranslationCache instance.
    """
    global _cache
    if _cache is None:
        _cache = TranslationCache(
            cache_path=cache_path or "/app/output/.translation_cache.json"
        )
    return _cache
