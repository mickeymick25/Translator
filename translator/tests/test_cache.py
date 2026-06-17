"""
Tests for core/cache.py — Translation cache module.

Covers:
- TranslationCache.__init__(): initialization, loading existing cache, missing/corrupt files
- TranslationCache.get() / put(): cache lookups, inserts, hit/miss counting
- TranslationCache.flush() / _load() / _save(): persistence, dirty flag, error handling
- TranslationCache.stats(): hit rate computation, entry count
- TranslationCache._make_key(): cache key format
- get_cache(): singleton behavior, lazy initialization
"""

import json

# ─── TranslationCache.__init__ ────────────────────────────────────


class TestTranslationCacheInit:
    """Tests for TranslationCache initialization."""

    def test_creates_empty_cache_when_no_file_exists(self, temp_dir):
        """When the cache file doesn't exist, starts with an empty cache."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        assert len(cache._entries) == 0

    def test_loads_existing_cache_file(self, temp_dir):
        """When a valid cache file exists, entries are loaded."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        data = {
            "metadata": {"version": 1, "total_entries": 2},
            "entries": {
                "en:fr:Hello": "Bonjour",
                "en:de:Button": "Taste",
            },
        }
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))
        assert cache._entries["en:fr:Hello"] == "Bonjour"
        assert cache._entries["en:de:Button"] == "Taste"
        assert len(cache._entries) == 2

    def test_handles_corrupt_cache_file_gracefully(self, temp_dir):
        """A corrupt JSON cache file is ignored; starts with an empty cache."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        cache_path.write_text("NOT VALID JSON {{{", encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))
        assert len(cache._entries) == 0

    def test_handles_missing_entries_key_gracefully(self, temp_dir):
        """A cache file without the 'entries' key starts with an empty cache."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        data = {"metadata": {"version": 1}}
        cache_path.write_text(json.dumps(data), encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))
        assert len(cache._entries) == 0

    def test_initial_stats_are_zero(self, temp_dir):
        """Fresh cache has zero hits and misses."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_entries"] == 0

    def test_dirty_flag_starts_false(self, temp_dir):
        """A freshly loaded cache is not dirty."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        assert cache._dirty is False

    def test_accepts_string_path(self, temp_dir):
        """Cache path can be provided as a string."""
        from core.cache import TranslationCache

        cache_path = str(temp_dir / ".translation_cache.json")
        cache = TranslationCache(cache_path=cache_path)
        assert str(cache._path) == cache_path

    def test_accepts_path_object(self, temp_dir):
        """Cache path can be provided as a Path object."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        cache = TranslationCache(cache_path=cache_path)
        assert cache._path == cache_path


# ─── TranslationCache._make_key ────────────────────────────────────


class TestTranslationCacheMakeKey:
    """Tests for TranslationCache._make_key() — cache key format."""

    def test_key_format(self):
        """Key format is source_lang:target_lang:text."""
        from core.cache import TranslationCache

        key = TranslationCache._make_key("en", "fr", "Hello")
        assert key == "en:fr:Hello"

    def test_different_target_langs_produce_different_keys(self):
        """Same text with different target languages produces different keys."""
        from core.cache import TranslationCache

        key_fr = TranslationCache._make_key("en", "fr", "Hello")
        key_de = TranslationCache._make_key("en", "de", "Hello")
        assert key_fr != key_de

    def test_different_source_langs_produce_different_keys(self):
        """Same text with different source languages produces different keys."""
        from core.cache import TranslationCache

        key_en = TranslationCache._make_key("en", "fr", "Hello")
        key_de = TranslationCache._make_key("de", "fr", "Hello")
        assert key_en != key_de

    def test_different_texts_produce_different_keys(self):
        """Different texts produce different keys."""
        from core.cache import TranslationCache

        key1 = TranslationCache._make_key("en", "fr", "Hello")
        key2 = TranslationCache._make_key("en", "fr", "Goodbye")
        assert key1 != key2

    def test_same_triplet_produces_same_key(self):
        """Same (source, target, text) produces the same key."""
        from core.cache import TranslationCache

        key1 = TranslationCache._make_key("en", "fr", "Hello")
        key2 = TranslationCache._make_key("en", "fr", "Hello")
        assert key1 == key2

    def test_handles_special_characters_in_text(self):
        """Text with special characters is preserved in the key."""
        from core.cache import TranslationCache

        key = TranslationCache._make_key("en", "fr", "100% résumé")
        assert "100% résumé" in key

    def test_handles_empty_text(self):
        """Empty text still produces a valid key."""
        from core.cache import TranslationCache

        key = TranslationCache._make_key("en", "fr", "")
        assert key == "en:fr:"


# ─── TranslationCache.get / put ────────────────────────────────────


class TestTranslationCacheGetPut:
    """Tests for TranslationCache.get() and put()."""

    def test_get_returns_none_for_missing_entry(self, temp_dir):
        """get() returns None when the key is not in the cache."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        result = cache.get("en", "fr", "Hello")
        assert result is None

    def test_put_then_get_returns_value(self, temp_dir):
        """After put(), get() returns the stored value."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        result = cache.get("en", "fr", "Hello")
        assert result == "Bonjour"

    def test_put_sets_dirty_flag(self, temp_dir):
        """put() sets the dirty flag when a new entry is added."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        assert cache._dirty is False
        cache.put("en", "fr", "Hello", "Bonjour")
        assert cache._dirty is True

    def test_put_does_not_set_dirty_if_value_unchanged(self, temp_dir):
        """put() does not set dirty when the same value already exists."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache._dirty = False  # reset
        cache.put("en", "fr", "Hello", "Bonjour")
        assert cache._dirty is False

    def test_put_updates_dirty_if_value_changed(self, temp_dir):
        """put() sets dirty when the value differs from the existing one."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache._dirty = False  # reset
        cache.put("en", "fr", "Hello", "Salut")
        assert cache._dirty is True
        assert cache.get("en", "fr", "Hello") == "Salut"

    def test_get_increments_misses_on_cache_miss(self, temp_dir):
        """A cache miss increments the misses counter."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.get("en", "fr", "Hello")
        assert cache._misses == 1

    def test_get_increments_hits_on_cache_hit(self, temp_dir):
        """A cache hit increments the hits counter."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache._hits = 0  # reset after put side-effects
        cache.get("en", "fr", "Hello")
        assert cache._hits == 1

    def test_multiple_gets_track_hits_and_misses(self, temp_dir):
        """Multiple get() calls correctly accumulate hits and misses."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache._hits = 0
        cache._misses = 0

        cache.get("en", "fr", "Hello")  # hit
        cache.get("en", "fr", "Goodbye")  # miss
        cache.get("en", "fr", "Hello")  # hit
        cache.get("en", "de", "Hello")  # miss (different target lang)

        assert cache._hits == 2
        assert cache._misses == 2

    def test_put_and_get_with_unicode(self, temp_dir):
        """Unicode text is stored and retrieved correctly."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("ar", "fr", "الرئيسية", "Accueil")
        result = cache.get("ar", "fr", "الرئيسية")
        assert result == "Accueil"

    def test_put_and_get_preserves_special_chars(self, temp_dir):
        """Special characters like %, é, etc. are preserved."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "100% résumé", "100 % résumé")
        result = cache.get("en", "fr", "100% résumé")
        assert result == "100 % résumé"


# ─── TranslationCache.flush / _save / _load ────────────────────────


class TestTranslationCacheFlush:
    """Tests for TranslationCache.flush() — persisting the cache to disk."""

    def test_flush_creates_cache_file(self, temp_dir):
        """flush() creates the cache file if it doesn't exist."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.flush()

        assert cache_path.exists()

    def test_flush_writes_valid_json(self, temp_dir):
        """flush() writes valid JSON that can be parsed."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.flush()

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "entries" in data
        assert data["entries"]["en:fr:Hello"] == "Bonjour"

    def test_flush_includes_metadata(self, temp_dir):
        """flush() writes metadata with version and entry count."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.put("en", "de", "Button", "Taste")
        cache.flush()

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["metadata"]["version"] == 1
        assert data["metadata"]["total_entries"] == 2

    def test_flush_clears_dirty_flag(self, temp_dir):
        """After flush(), the dirty flag is cleared."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("en", "fr", "Hello", "Bonjour")
        assert cache._dirty is True
        cache.flush()
        assert cache._dirty is False

    def test_flush_noop_when_not_dirty(self, temp_dir):
        """flush() does nothing when the cache is not dirty."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        # No put() called, so not dirty
        cache.flush()
        assert not cache_path.exists()

    def test_flush_creates_parent_directories(self, temp_dir):
        """flush() creates parent directories if they don't exist."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "sub" / "dir" / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.flush()

        assert cache_path.exists()

    def test_flush_overwrites_existing_file(self, temp_dir):
        """flush() overwrites an existing cache file with current data."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.flush()

        # Add a new entry and flush again
        cache.put("en", "de", "Button", "Taste")
        cache.flush()

        # Re-load and verify both entries are present
        cache2 = TranslationCache(cache_path=str(cache_path))
        assert cache2._entries["en:fr:Hello"] == "Bonjour"
        assert cache2._entries["en:de:Button"] == "Taste"
        assert len(cache2._entries) == 2

    def test_flush_preserves_unicode(self, temp_dir):
        """flush() correctly persists Unicode characters."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache.put("ar", "fr", "الرئيسية", "Accueil")
        cache.flush()

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["entries"]["ar:fr:الرئيسية"] == "Accueil"


class TestTranslationCacheLoad:
    """Tests for TranslationCache._load() — loading cache from disk."""

    def test_load_reads_entries_from_valid_file(self, temp_dir):
        """_load() reads entries from a valid cache file."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        data = {
            "metadata": {"version": 1, "total_entries": 1},
            "entries": {"en:fr:Hello": "Bonjour"},
        }
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))
        assert "en:fr:Hello" in cache._entries
        assert cache._entries["en:fr:Hello"] == "Bonjour"

    def test_load_handles_empty_entries(self, temp_dir):
        """_load() handles a file with empty entries dict."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        data = {"metadata": {"version": 1, "total_entries": 0}, "entries": {}}
        cache_path.write_text(json.dumps(data), encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))
        assert len(cache._entries) == 0

    def test_load_handles_missing_file_gracefully(self, temp_dir):
        """_load() handles a missing cache file gracefully."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "nonexistent.json"
        cache = TranslationCache(cache_path=str(cache_path))
        assert len(cache._entries) == 0

    def test_load_handles_invalid_json_gracefully(self, temp_dir):
        """_load() handles an invalid JSON file gracefully."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache_path.write_text("{broken json", encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))
        assert len(cache._entries) == 0


class TestTranslationCacheSave:
    """Tests for TranslationCache._save() — writing cache to disk."""

    def test_save_creates_file_with_correct_structure(self, temp_dir):
        """_save() writes a file with metadata and entries keys."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache._entries = {"en:fr:Hello": "Bonjour"}
        cache._save()

        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "metadata" in data
        assert "entries" in data
        assert data["metadata"]["version"] == 1
        assert data["metadata"]["total_entries"] == 1

    def test_save_creates_parent_directories(self, temp_dir):
        """_save() creates parent directories if they don't exist."""
        from core.cache import TranslationCache

        cache_path = temp_dir / "deep" / "nested" / "cache.json"
        cache = TranslationCache(cache_path=str(cache_path))
        cache._entries = {"en:fr:Hello": "Bonjour"}
        cache._save()

        assert cache_path.exists()


# ─── TranslationCache.stats ────────────────────────────────────────


class TestTranslationCacheStats:
    """Tests for TranslationCache.stats()."""

    def test_stats_on_empty_cache(self, temp_dir):
        """Stats on an empty, unused cache."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        stats = cache.stats()
        assert stats["total_entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_pct"] == 0.0

    def test_stats_after_hits_and_misses(self, temp_dir):
        """Stats reflect hits and misses from get() calls."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.put("en", "fr", "Goodbye", "Au revoir")

        # Reset counters that may have been affected by put
        cache._hits = 0
        cache._misses = 0

        cache.get("en", "fr", "Hello")  # hit
        cache.get("en", "fr", "Hello")  # hit
        cache.get("en", "fr", "Goodbye")  # hit
        cache.get("en", "fr", "Unknown")  # miss

        stats = cache.stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 1
        assert stats["hit_rate_pct"] == 75.0

    def test_stats_total_entries(self, temp_dir):
        """total_entries counts the number of cached translations."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")
        cache.put("en", "de", "Button", "Taste")

        stats = cache.stats()
        assert stats["total_entries"] == 2

    def test_stats_hit_rate_rounded_to_one_decimal(self, temp_dir):
        """hit_rate_pct is rounded to one decimal place."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")

        cache._hits = 0
        cache._misses = 0

        # 1 hit, 2 misses = 33.333...%
        cache.get("en", "fr", "Hello")  # hit
        cache.get("en", "fr", "X")  # miss
        cache.get("en", "fr", "Y")  # miss

        stats = cache.stats()
        assert stats["hit_rate_pct"] == 33.3

    def test_stats_all_hits_gives_100_percent(self, temp_dir):
        """100% hit rate when all lookups are hits."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "fr", "Hello", "Bonjour")

        cache._hits = 0
        cache._misses = 0

        cache.get("en", "fr", "Hello")  # hit
        cache.get("en", "fr", "Hello")  # hit

        stats = cache.stats()
        assert stats["hit_rate_pct"] == 100.0

    def test_stats_returns_dict_with_expected_keys(self, temp_dir):
        """stats() returns a dict with the expected keys."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        stats = cache.stats()
        assert "total_entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate_pct" in stats


# ─── get_cache singleton ──────────────────────────────────────────


class TestGetCache:
    """Tests for get_cache() singleton behavior."""

    def test_returns_translation_cache_instance(self):
        """get_cache() returns a TranslationCache instance."""
        from core.cache import TranslationCache, get_cache

        cache = get_cache()
        assert isinstance(cache, TranslationCache)

    def test_singleton_returns_same_instance(self):
        """Repeated calls to get_cache() return the same instance."""
        from core.cache import get_cache

        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_uses_custom_path_when_provided(self, temp_dir):
        """get_cache() uses the provided path on first call."""
        # Reset singleton
        import core.cache as cache_module
        from core.cache import get_cache

        cache_module._cache = None

        custom_path = str(temp_dir / "custom_cache.json")
        cache = get_cache(cache_path=custom_path)
        assert str(cache._path) == custom_path

        # Clean up
        cache_module._cache = None

    def test_ignores_path_on_subsequent_calls(self, temp_dir):
        """get_cache() ignores the path argument on subsequent calls (already initialized)."""
        # Reset singleton
        import core.cache as cache_module
        from core.cache import get_cache

        cache_module._cache = None

        cache1 = get_cache(cache_path=str(temp_dir / "first.json"))
        cache2 = get_cache(cache_path=str(temp_dir / "second.json"))
        assert cache1 is cache2
        # Path should still be the first one
        assert "first.json" in str(cache2._path)

        # Clean up
        cache_module._cache = None


# ─── Language Code Normalization (Bug #3) ──────────────────────────


class TestNormalizeLangCode:
    """Tests for _normalize_lang_code() — language code normalization (Bug #3).

    Bug #3: cache keys used the API code 'cs' for Czech, while the
    project uses 'cz' (e.g. translation_en_cz.json). This led to
    inconsistencies between cache keys and file names, and could cause
    re-translations when the code was used inconsistently.

    The fix normalizes API codes to user-facing codes at cache key
    construction time and migrates existing keys on load.
    """

    def test_normalizes_czech_api_code_to_user_code(self):
        """API code 'cs' is normalized to user code 'cz'."""
        from core.cache import _normalize_lang_code

        assert _normalize_lang_code("cs") == "cz"

    def test_czech_user_code_passes_through_unchanged(self):
        """User code 'cz' is left as-is."""
        from core.cache import _normalize_lang_code

        assert _normalize_lang_code("cz") == "cz"

    def test_other_languages_pass_through_unchanged(self):
        """Languages not in the normalization table are unchanged."""
        from core.cache import _normalize_lang_code

        for lang in ["en", "fr", "de", "it", "sk", "ar"]:
            assert _normalize_lang_code(lang) == lang

    def test_empty_string_returns_empty_string(self):
        """Empty string is returned as-is (no mapping)."""
        from core.cache import _normalize_lang_code

        assert _normalize_lang_code("") == ""

    def test_unknown_code_returns_input_unchanged(self):
        """Unknown language code is returned as-is."""
        from core.cache import _normalize_lang_code

        assert _normalize_lang_code("xx") == "xx"


class TestMakeKeyWithNormalization:
    """Tests for _make_key() with language code normalization (Bug #3).

    After normalization, _make_key('en', 'cs', 'Hello') and
    _make_key('en', 'cz', 'Hello') must produce the SAME key.
    """

    def test_cs_and_cz_produce_same_key(self):
        """API 'cs' and user 'cz' produce the same cache key for the same text."""
        from core.cache import TranslationCache

        key_cs = TranslationCache._make_key("en", "cs", "Hello")
        key_cz = TranslationCache._make_key("en", "cz", "Hello")
        assert key_cs == key_cz == "en:cz:Hello"

    def test_normalized_key_used_in_get_and_put(self, temp_dir):
        """put('en', 'cs', ...) and get('en', 'cz', ...) hit the same entry."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache.put("en", "cs", "Hello", "Ahoj")

        # Retrieve with the user code — must hit the entry stored via 'cs'.
        assert cache.get("en", "cz", "Hello") == "Ahoj"
        # And the inverse: store with 'cz', retrieve with 'cs'.
        cache.put("en", "cz", "Goodbye", "Nashledanou")
        assert cache.get("en", "cs", "Goodbye") == "Nashledanou"

    def test_source_lang_also_normalized(self):
        """Source language codes are normalized too (symmetric)."""
        from core.cache import TranslationCache

        # If 'cs' were ever used as a source code, it would normalize to 'cz'.
        # Today only 'en' is used as source, but the contract is symmetric.
        key = TranslationCache._make_key("cs", "fr", "Hello")
        assert key == "cz:fr:Hello"

    def test_other_lang_pairs_unchanged(self):
        """Non-Czech pairs are not affected by normalization."""
        from core.cache import TranslationCache

        assert TranslationCache._make_key("en", "fr", "Hello") == "en:fr:Hello"
        assert TranslationCache._make_key("en", "de", "Hello") == "en:de:Hello"
        assert TranslationCache._make_key("en", "sk", "Hello") == "en:sk:Hello"


class TestMigrateKeys:
    """Tests for migrate_keys() — automatic migration on cache load (Bug #3).

    When the cache file is loaded, any entry keyed with the API code 'cs'
    must be transparently renamed to 'cz' to match the project's file
    naming convention and avoid cache misses.
    """

    def test_migrates_cs_keys_to_cz(self, temp_dir):
        """Entries keyed with 'en:cs:...' are renamed to 'en:cz:...'."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache._entries = {
            "en:cs:Hello": "Ahoj",
            "en:cs:Goodbye": "Nashledanou",
        }

        migrated = cache.migrate_keys()

        assert migrated == 2
        assert "en:cs:Hello" not in cache._entries
        assert "en:cz:Hello" in cache._entries
        assert cache._entries["en:cz:Hello"] == "Ahoj"
        assert cache._entries["en:cz:Goodbye"] == "Nashledanou"

    def test_migration_sets_dirty_flag(self, temp_dir):
        """Migration marks the cache as dirty so it gets flushed on next save."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache._entries = {"en:cs:Hello": "Ahoj"}
        cache._dirty = False

        cache.migrate_keys()

        assert cache._dirty is True

    def test_no_migration_needed_for_normalized_keys(self, temp_dir):
        """Keys already using 'cz' are not touched."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache._entries = {
            "en:cz:Hello": "Ahoj",
            "en:fr:Bonjour": "Hello",
        }
        cache._dirty = False

        migrated = cache.migrate_keys()

        assert migrated == 0
        assert cache._entries == {
            "en:cz:Hello": "Ahoj",
            "en:fr:Bonjour": "Hello",
        }
        # No migration → cache stays clean.
        assert cache._dirty is False

    def test_empty_cache_migration_returns_zero(self, temp_dir):
        """Migrating an empty cache is a no-op."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))

        assert cache.migrate_keys() == 0
        assert cache._entries == {}

    def test_load_triggers_migration_automatically(self, temp_dir):
        """Loading a cache file with 'en:cs:' keys migrates them on the fly."""
        from core.cache import TranslationCache

        cache_path = temp_dir / ".translation_cache.json"
        data = {
            "metadata": {"version": 1, "total_entries": 2},
            "entries": {
                "en:cs:Hello": "Ahoj",
                "en:cs:World": "Svete",
            },
        }
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        cache = TranslationCache(cache_path=str(cache_path))

        # Both entries were migrated at load time.
        assert "en:cs:Hello" not in cache._entries
        assert "en:cz:Hello" in cache._entries
        assert cache._entries["en:cz:Hello"] == "Ahoj"
        assert cache._entries["en:cz:World"] == "Svete"
        # And the cache is dirty so the next flush writes the migrated form.
        assert cache._dirty is True

    def test_migration_does_not_overwrite_existing_target_key(self, temp_dir):
        """If both 'en:cs:Hello' and 'en:cz:Hello' exist, the migration is skipped
        for the duplicate to avoid losing data."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache._entries = {
            "en:cs:Hello": "OLD_CZ",
            "en:cz:Hello": "NEW_CZ",
        }

        migrated = cache.migrate_keys()

        # The 'cs' key is NOT migrated because 'cz' already exists.
        assert migrated == 0
        assert cache._entries["en:cs:Hello"] == "OLD_CZ"
        assert cache._entries["en:cz:Hello"] == "NEW_CZ"

    def test_migration_handles_keys_with_colons_in_text(self, temp_dir):
        """Texts containing ':' are split correctly (key split is limited to 2)."""
        from core.cache import TranslationCache

        cache = TranslationCache(cache_path=str(temp_dir / "cache.json"))
        cache._entries = {
            "en:cs:Time: 10:30": "Cas: 10:30",
        }

        cache.migrate_keys()

        # The key part 'en:cs:' is migrated to 'en:cz:', the rest stays intact.
        assert "en:cs:Time: 10:30" not in cache._entries
        assert "en:cz:Time: 10:30" in cache._entries
        assert cache._entries["en:cz:Time: 10:30"] == "Cas: 10:30"
