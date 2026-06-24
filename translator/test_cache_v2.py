"""Tests fonctionnels pour le cache v2 (format composite)."""

import json
import sys
import tempfile
from pathlib import Path

# Ajouter le path pour les imports
sys.path.insert(0, str(Path(__file__).parent))

from core.cache import TranslationCache


def test_legacy_key_format():
    """Le format legacy (en:lang:text) reste fonctionnel."""
    key = TranslationCache._make_key("en", "cz", "Hello")
    assert key == "en:cz:Hello", f"Expected en:cz:Hello, got {key}"
    print("PASS: test_legacy_key_format")


def test_composite_key_format():
    """Le nouveau format composite (en:lang:key_id:text) est utilise si key_id fourni."""
    key = TranslationCache._make_key("en", "cz", "Hello", key_id="Btn_Home")
    assert key == "en:cz:Btn_Home:Hello", f"Expected en:cz:Btn_Home:Hello, got {key}"
    print("PASS: test_composite_key_format")


def test_is_composite_key():
    """Detection du format de cle."""
    assert TranslationCache._is_composite_key("en:cz:Hello") is False
    assert TranslationCache._is_composite_key("en:cz:Btn_Home:Hello") is True
    assert (
        TranslationCache._is_composite_key("en:cz:PA_CO_VI_851:Update role type")
        is True
    )
    print("PASS: test_is_composite_key")


def test_put_get_with_key_id():
    """Put puis get avec key_id retourne la traduction."""
    cache_path = tempfile.mktemp(suffix=".json")
    cache = TranslationCache(cache_path=cache_path)
    cache.put("en", "cz", "Hello", "Ahoj", key_id="Btn_Home")
    result = cache.get("en", "cz", "Hello", key_id="Btn_Home")
    assert result == "Ahoj", f"Expected Ahoj, got {result}"
    print("PASS: test_put_get_with_key_id")


def test_collision_avoided_with_key_id():
    """Deux cles i18n avec le meme texte source ont des entrees separees."""
    cache_path = tempfile.mktemp(suffix=".json")
    cache = TranslationCache(cache_path=cache_path)
    # "Action" est utilise par 37 cles i18n differentes
    cache.put("en", "cz", "Action", "Akce1", key_id="Btn_Action")
    cache.put("en", "cz", "Action", "Akce2", key_id="Menu_Action")
    cache.put("en", "cz", "Action", "Akce3", key_id="Toolbar_Action")
    assert cache.get("en", "cz", "Action", key_id="Btn_Action") == "Akce1"
    assert cache.get("en", "cz", "Action", key_id="Menu_Action") == "Akce2"
    assert cache.get("en", "cz", "Action", key_id="Toolbar_Action") == "Akce3"
    # Sans key_id, c'est un MISS car aucune entree legacy n'a ete cree
    assert cache.get("en", "cz", "Action") is None
    print("PASS: test_collision_avoided_with_key_id")


def test_backward_compatibility_legacy_key():
    """Une entree legacy (sans key_id) reste lisible."""
    cache_path = tempfile.mktemp(suffix=".json")
    cache = TranslationCache(cache_path=cache_path)
    # Simuler une entree legacy (ancien format)
    cache.put("en", "cz", "Hello", "Ahoj")
    # Lecture avec key_id doit retomber sur la cle legacy
    result_with_key = cache.get("en", "cz", "Hello", key_id="Btn_Home")
    result_without_key = cache.get("en", "cz", "Hello")
    assert result_with_key == "Ahoj", f"Got {result_with_key}"
    assert result_without_key == "Ahoj", f"Got {result_without_key}"
    print("PASS: test_backward_compatibility_legacy_key")


def test_composite_priority_over_legacy():
    """Si composite et legacy existent, le composite gagne."""
    cache_path = tempfile.mktemp(suffix=".json")
    cache = TranslationCache(cache_path=cache_path)
    cache.put("en", "cz", "Hello", "Ahoj_legacy")
    cache.put("en", "cz", "Hello", "Ahoj_composite", key_id="Btn_Home")
    assert cache.get("en", "cz", "Hello", key_id="Btn_Home") == "Ahoj_composite"
    assert cache.get("en", "cz", "Hello") == "Ahoj_legacy"
    print("PASS: test_composite_priority_over_legacy")


def test_cache_miss():
    """Un cache.get sans entree doit retourner None."""
    cache_path = tempfile.mktemp(suffix=".json")
    cache = TranslationCache(cache_path=cache_path)
    assert cache.get("en", "cz", "NonExistent") is None
    assert cache.get("en", "cz", "NonExistent", key_id="Btn_X") is None
    print("PASS: test_cache_miss")


def test_stats_tracking():
    """Les hits/misses sont incrementes correctement."""
    cache_path = tempfile.mktemp(suffix=".json")
    cache = TranslationCache(cache_path=cache_path)
    cache.put("en", "cz", "Hello", "Ahoj", key_id="Btn_Home")
    cache.get("en", "cz", "Hello", key_id="Btn_Home")  # hit
    cache.get("en", "cz", "Hello", key_id="Btn_Home")  # hit
    cache.get("en", "cz", "Missing")  # miss
    cache.get("en", "cz", "Missing", key_id="X")  # miss
    stats = cache.stats()
    assert stats["hits"] == 2, f"Expected 2 hits, got {stats['hits']}"
    assert stats["misses"] == 2, f"Expected 2 misses, got {stats['misses']}"
    assert stats["total_entries"] == 1, (
        f"Expected 1 entry, got {stats['total_entries']}"
    )
    print("PASS: test_stats_tracking")


def test_real_cache_file_v2():
    """Le cache reel v2 est charge et fonctionnel."""
    cache_path = Path(__file__).parent / "output" / ".translation_cache.json"
    if not cache_path.exists():
        import pytest

        pytest.skip(f"Cache file not found: {cache_path}")
    cache = TranslationCache(cache_path=cache_path)

    with cache_path.open(encoding="utf-8") as f:
        raw = json.load(f)

    print("\nCache v2 charge:")
    print(f"  Total entries: {len(cache._entries)}")
    print(f"  Format metadata: {raw['metadata'].get('format', 'unknown')}")
    print(f"  Key format: {raw['metadata'].get('key_format', 'unknown')}")

    # Tester avec une cle connue
    sample_key = "en:fr:Btn_Home:Home"
    if sample_key in cache._entries:
        val = cache.get("en", "fr", "Home", key_id="Btn_Home")
        assert val is not None
        print(f"  Lookup Btn_Home (FR): {val!r}")

    # Tester la collision : 3 cles i18n avec "Action"
    test_keys = ["Btn_Action", "CO_CO_TA_184", "PA_US_TA_614"]
    for key_id in test_keys:
        val = cache.get("en", "cz", "Action", key_id=key_id)
        if val:
            print(f"  Lookup {key_id} (CZ): {val!r}")

    print("PASS: test_real_cache_file_v2")


if __name__ == "__main__":
    test_legacy_key_format()
    test_composite_key_format()
    test_is_composite_key()
    test_put_get_with_key_id()
    test_collision_avoided_with_key_id()
    test_backward_compatibility_legacy_key()
    test_composite_priority_over_legacy()
    test_cache_miss()
    test_stats_tracking()
    test_real_cache_file_v2()
    print("\nTous les tests PASS.")
