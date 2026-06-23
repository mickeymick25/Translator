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

# Language code normalization: API codes → user codes
# This ensures cache keys are consistent with file names (e.g. translation_en_cz.json)
_LANG_CODE_NORMALIZE = {
    "cs": "cz",  # Czech: API uses 'cs', project uses 'cz'
}


def _normalize_lang_code(lang: str) -> str:
    """Normalize a language code for cache key consistency.

    Maps API codes to user-facing codes (e.g. 'cs' → 'cz') so that
    cache entries match the output file naming convention.
    """
    return _LANG_CODE_NORMALIZE.get(lang, lang)


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
    def _make_key(
        source_lang: str, target_lang: str, text: str, key_id: str | None = None
    ) -> str:
        """Generate a unique cache key for a (source, target, text[, key_id]) triplet.

        If key_id is provided, uses the composite format "src:tgt:key_id:text"
        to avoid collisions when multiple i18n keys share the same source text.
        Otherwise, falls back to the legacy format "src:tgt:text" for backward
        compatibility with caches produced before v2.
        """
        src = _normalize_lang_code(source_lang)
        tgt = _normalize_lang_code(target_lang)
        if key_id:
            return f"{src}:{tgt}:{key_id}:{text}"
        return f"{src}:{tgt}:{text}"

    @staticmethod
    def _is_composite_key(key: str) -> bool:
        """Detect whether a key uses the v2 composite format.

        A composite key has the structure "src:tgt:key_id:text" where text may
        itself contain colons. We use the known language-code prefix length to
        distinguish the two formats:
        - Legacy "src:tgt:text"         → 2 colons
        - Composite "src:tgt:key:text"  → ≥ 3 colons
        """
        return key.count(":") >= 3

    def get(
        self,
        source_lang: str,
        target_lang: str,
        text: str,
        key_id: str | None = None,
    ) -> str | None:
        """
        Retrieve a translation from the cache.

        Lookup order:
        1. Composite key (src:tgt:key_id:text) if key_id is provided.
        2. Legacy key (src:tgt:text) as a fallback for entries written by v1.

        Returns:
            The translation if present (cache hit), None otherwise (cache miss).
        """
        with self._lock:
            if key_id:
                composite_key = self._make_key(source_lang, target_lang, text, key_id)
                if composite_key in self._entries:
                    self._hits += 1
                    logger.debug("Cache HIT (composite): %s", composite_key[:80])
                    return self._entries[composite_key]
            legacy_key = self._make_key(source_lang, target_lang, text)
            if legacy_key in self._entries:
                self._hits += 1
                logger.debug("Cache HIT (legacy): %s", legacy_key[:80])
                return self._entries[legacy_key]
            self._misses += 1
            logger.debug("Cache MISS: %s", legacy_key[:80])
            return None

    def put(
        self,
        source_lang: str,
        target_lang: str,
        text: str,
        translation: str,
        key_id: str | None = None,
    ) -> None:
        """Add a translation to the cache.

        If key_id is provided, the composite format is used. Otherwise the
        legacy format is used for backward compatibility.
        """
        key = self._make_key(source_lang, target_lang, text, key_id)
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
            # Migrate API lang codes to user codes (e.g. en:cs: → en:cz:)
            self.migrate_keys()
            logger.info(
                "Loaded translation cache: %d entries from %s",
                len(self._entries),
                self._path.name,
            )
        except Exception as e:
            logger.warning("Failed to load translation cache: %s — starting fresh", e)
            self._entries = {}

    def migrate_keys(self) -> int:
        """Migrate cache keys from API codes to normalized user codes.

        Renames entries like 'en:cs:text' → 'en:cz:text' to ensure
        consistency with the project's file naming convention.

        Returns:
            Number of migrated entries.
        """
        migrated = 0
        with self._lock:
            keys_to_rename: list[tuple[str, str]] = []
            for key in list(self._entries.keys()):
                # Parse key: format is "source:target:text"
                parts = key.split(":", 2)
                if len(parts) == 3:
                    src, tgt, text = parts
                    new_src = _normalize_lang_code(src)
                    new_tgt = _normalize_lang_code(tgt)
                    if new_src != src or new_tgt != tgt:
                        new_key = f"{new_src}:{new_tgt}:{text}"
                        if new_key not in self._entries:
                            keys_to_rename.append((key, new_key))
                        else:
                            logger.debug(
                                "Skipping migration of '%s' — '%s' already exists",
                                key[:80],
                                new_key[:80],
                            )
            for old_key, new_key in keys_to_rename:
                self._entries[new_key] = self._entries.pop(old_key)
                migrated += 1
                logger.debug("Migrated cache key: %s → %s", old_key[:80], new_key[:80])
            if migrated > 0:
                self._dirty = True
                logger.info("Migrated %d cache keys (API codes → user codes)", migrated)
        return migrated

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
