"""
Tests pour validate_translations.py — Sprint 3 - tâche 29 (R13).

Couvre en particulier `_detect_duplicate_keys` réimplémenté via
`json.JSONDecoder.object_pairs_hook` (C7) : la détection par regex précédente
cassait sur le JSON minifié, les objets imbriqués et les clés contenant `":"`.
"""

import json

import validate_translations


# ─── _detect_duplicate_keys (C7 / R9) ─────────────────────────────────


class TestDetectDuplicateKeys:
    """Tests de _detect_duplicate_keys() — détection par object_pairs_hook."""

    def test_no_duplicates_returns_empty(self, tmp_path):
        p = tmp_path / "ok.json"
        p.write_text(json.dumps({"K1": "v1", "K2": "v2"}), encoding="utf-8")
        assert validate_translations._detect_duplicate_keys(p) == {}

    def test_detects_top_level_duplicates(self, tmp_path):
        """Deux clés identiques au top-level → comptées."""
        # json.dump écrase les doublons silencieusement, on écrit à la main.
        p = tmp_path / "dup.json"
        p.write_text('{"K1": "a", "K1": "b"}', encoding="utf-8")
        result = validate_translations._detect_duplicate_keys(p)
        assert result == {"K1": 2}

    def test_detects_nested_duplicates(self, tmp_path):
        """Les doublons dans un objet imbriqué sont détectés (C7 : regex cassait ici)."""
        p = tmp_path / "nested.json"
        p.write_text(
            '{"outer": {"inner": "a", "inner": "b"}, "K": "v"}',
            encoding="utf-8",
        )
        result = validate_translations._detect_duplicate_keys(p)
        assert result == {"inner": 2}

    def test_minified_json_detected(self, tmp_path):
        """Le JSON minifié (sans espaces) est correctement parsé (C7)."""
        p = tmp_path / "minified.json"
        p.write_text('{"K1":"a","K1":"b","K2":"c"}', encoding="utf-8")
        result = validate_translations._detect_duplicate_keys(p)
        assert result == {"K1": 2}

    def test_key_with_colon_detected(self, tmp_path):
        """Une clé contenant `:` est correctement détectée (C7 : regex cassait ici)."""
        p = tmp_path / "colon.json"
        p.write_text('{"key:with:colon": "a", "key:with:colon": "b"}', encoding="utf-8")
        result = validate_translations._detect_duplicate_keys(p)
        assert result == {"key:with:colon": 2}

    def test_missing_file_returns_empty(self, tmp_path):
        """Un chemin absent retourne un dict vide (pas d'exception)."""
        assert (
            validate_translations._detect_duplicate_keys(tmp_path / "absent.json") == {}
        )
