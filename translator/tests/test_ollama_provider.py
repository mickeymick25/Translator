"""
Tests for OllamaProvider (IMP3).

Covers: OllamaValidationError, translate(), translate_batch(), chunking,
structural validation, placeholder validation, intelligent retry,
JSON extraction, and prompt building.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from core.ollama_provider import OllamaProvider, OllamaValidationError
from core.translator_factory import TranslationProvider

# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def provider():
    """Create an OllamaProvider with default settings and mocked _make_request."""
    return OllamaProvider(
        model="test-model",
        base_url="http://localhost:11434",
        chunk_size=5,
        max_retries=2,
        timeout=60,
        temperature=0,
    )


@pytest.fixture
def provider_no_retries():
    """OllamaProvider with 0 retries for simpler test scenarios."""
    return OllamaProvider(
        model="test-model", chunk_size=5, max_retries=0, temperature=0
    )


# ─── OllamaValidationError ──────────────────────────────────────────


class TestOllamaValidationError:
    def test_stores_error_type(self):
        err = OllamaValidationError("test error", error_type="json_parse")
        assert err.error_type == "json_parse"

    def test_default_error_type_is_unknown(self):
        err = OllamaValidationError("test error")
        assert err.error_type == "unknown"

    def test_is_exception(self):
        err = OllamaValidationError("test")
        assert isinstance(err, Exception)

    def test_message_preserved(self):
        err = OllamaValidationError("detail msg", error_type="completion_threshold")
        assert str(err) == "detail msg"


# ─── IMP3-T001: OllamaProvider basics + translate() ────────────────


class TestOllamaProviderBasics:
    def test_is_translation_provider_subclass(self):
        assert issubclass(OllamaProvider, TranslationProvider)

    def test_name_property(self, provider):
        assert provider.name == "Ollama (test-model)"

    def test_default_constructor(self):
        p = OllamaProvider()
        assert p._model == "minimax-m2.7:cloud"
        assert p._base_url == "http://localhost:11434"
        assert p._chunk_size == 50
        assert p._max_retries == 2
        assert p._timeout == 300
        assert p._temperature == 0

    def test_custom_constructor(self):
        p = OllamaProvider(
            model="mistral",
            base_url="http://host:12345",
            chunk_size=100,
            max_retries=3,
            timeout=120,
            temperature=0.1,
        )
        assert p._model == "mistral"
        assert p._base_url == "http://host:12345"
        assert p._chunk_size == 100
        assert p._max_retries == 3
        assert p._timeout == 120
        assert p._temperature == 0.1

    def test_translate_empty_string(self, provider):
        assert provider.translate("", "en", "fr") == ""

    def test_translate_whitespace_only(self, provider):
        assert provider.translate("   ", "en", "fr") == "   "

    def test_translate_single_text(self, provider):
        mock_response = json.dumps({"__single__": "Bonjour"})
        with patch.object(provider, "_make_request", return_value=mock_response):
            result = provider.translate("Hello", "en", "fr")
            assert result == "Bonjour"

    def test_translate_single_text_returns_original_on_failure(self, provider):
        with patch.object(
            provider, "_make_request", side_effect=Exception("connection error")
        ):
            result = provider.translate("Hello", "en", "fr")
            assert result == "Hello"


# ─── IMP3-T002: translate_batch() + chunking ───────────────────────


class TestChunkItems:
    def test_single_chunk(self, provider):
        items = {"k1": "v1", "k2": "v2", "k3": "v3"}
        chunks = provider._chunk_items(items)
        assert len(chunks) == 1
        assert chunks[0] == items

    def test_multiple_chunks(self, provider):
        items = {f"k{i}": f"v{i}" for i in range(12)}
        chunks = provider._chunk_items(items)
        assert len(chunks) == 3  # ceil(12/5) = 3
        assert len(chunks[0]) == 5
        assert len(chunks[1]) == 5
        assert len(chunks[2]) == 2

    def test_exact_chunk_size(self, provider):
        items = {f"k{i}": f"v{i}" for i in range(5)}
        chunks = provider._chunk_items(items)
        assert len(chunks) == 1
        assert len(chunks[0]) == 5

    def test_empty_items(self, provider):
        chunks = provider._chunk_items({})
        assert chunks == []

    def test_single_item(self, provider):
        chunks = provider._chunk_items({"k1": "v1"})
        assert len(chunks) == 1
        assert chunks[0] == {"k1": "v1"}


class TestTranslateBatch:
    def test_batch_single_chunk(self, provider):
        items = {"Btn_Home": "Home", "Btn_Cancel": "Cancel"}
        mock_response = json.dumps({"Btn_Home": "Accueil", "Btn_Cancel": "Annuler"})
        with patch.object(provider, "_make_request", return_value=mock_response):
            result = provider.translate_batch(items, "en", "fr")
            assert result["Btn_Home"] == "Accueil"
            assert result["Btn_Cancel"] == "Annuler"

    def test_batch_multiple_chunks(self, provider):
        items = {f"k{i}": f"Value {i}" for i in range(8)}
        # chunk_size=5 → 2 chunks
        call_count = {"n": 0}

        def mock_request(prompt):
            call_count["n"] += 1
            # Extract JSON from prompt and return translated values
            if "k0" in prompt:
                chunk = {f"k{i}": f"Valeur {i}" for i in range(5)}
            else:
                chunk = {f"k{i}": f"Valeur {i}" for i in range(5, 8)}
            return json.dumps(chunk)

        with patch.object(provider, "_make_request", side_effect=mock_request):
            result = provider.translate_batch(items, "en", "fr")
            assert len(result) == 8
            assert result["k0"] == "Valeur 0"
            assert result["k7"] == "Valeur 7"
            assert call_count["n"] == 2

    def test_batch_fallback_on_all_retries_exhausted(self, provider_no_retries):
        items = {"k1": "Hello", "k2": "World"}
        with patch.object(
            provider_no_retries,
            "_make_request",
            side_effect=Exception("connection error"),
        ):
            result = provider_no_retries.translate_batch(items, "en", "fr")
            # Fallback: original values kept
            assert result == {"k1": "Hello", "k2": "World"}


# ─── IMP3-T003: Structural Validation ──────────────────────────────


class TestValidateStructureCompletionThreshold:
    def test_completion_threshold_pass(self, provider):
        """80%+ keys present → targeted repair."""
        original = {f"k{i}": f"val{i}" for i in range(10)}
        parsed = {f"k{i}": f"translated{i}" for i in range(9)}  # 90%
        result = provider._validate_structure(parsed, original)
        assert len(result) == 10
        assert result["k9"] == "val9"  # Missing key → original

    def test_completion_threshold_fail(self, provider):
        """< 80% keys → full rejection + OllamaValidationError."""
        original = {f"k{i}": f"val{i}" for i in range(10)}
        parsed = {f"k{i}": f"translated{i}" for i in range(7)}  # 70%
        with pytest.raises(OllamaValidationError) as exc_info:
            provider._validate_structure(parsed, original)
        assert exc_info.value.error_type == "completion_threshold"

    def test_completion_empty_response(self, provider):
        """{} on a chunk → full rejection."""
        original = {"k1": "v1", "k2": "v2"}
        with pytest.raises(OllamaValidationError) as exc_info:
            provider._validate_structure({}, original)
        assert exc_info.value.error_type == "completion_threshold"

    def test_completion_near_threshold_79_percent(self, provider):
        """79% → reject."""
        original = {f"k{i}": f"val{i}" for i in range(100)}
        parsed = {f"k{i}": f"t{i}" for i in range(79)}  # 79%
        with pytest.raises(OllamaValidationError) as exc_info:
            provider._validate_structure(parsed, original)
        assert exc_info.value.error_type == "completion_threshold"

    def test_completion_near_threshold_80_percent(self, provider):
        """80% → targeted repair (not rejection)."""
        original = {f"k{i}": f"val{i}" for i in range(10)}
        parsed = {f"k{i}": f"t{i}" for i in range(8)}  # 80%
        # Should not raise completion_threshold — may raise structural_validation
        # due to missing keys, but that's a different error type
        try:
            result = provider._validate_structure(parsed, original)
            assert len(result) == 10
        except OllamaValidationError as e:
            assert e.error_type != "completion_threshold"

    def test_completion_100_percent(self, provider):
        """100% keys → all good."""
        original = {"k1": "v1", "k2": "v2"}
        parsed = {"k1": "t1", "k2": "t2"}
        result = provider._validate_structure(parsed, original)
        assert result == {"k1": "t1", "k2": "t2"}


class TestValidateStructureKeys:
    def test_keys_match_exactly(self, provider):
        original = {"k1": "v1", "k2": "v2"}
        parsed = {"k1": "t1", "k2": "t2"}
        result = provider._validate_structure(parsed, original)
        assert result == parsed

    def test_missing_keys_below_threshold(self, provider):
        """<80% keys → completion_threshold rejection."""
        original = {"k1": "v1", "k2": "v2", "k3": "v3"}
        parsed = {"k1": "t1"}  # 33% → below threshold
        with pytest.raises(OllamaValidationError) as exc_info:
            provider._validate_structure(parsed, original)
        assert exc_info.value.error_type == "completion_threshold"

    def test_missing_keys_above_threshold_repaired(self, provider):
        """Missing keys above 80% threshold → repaired silently, no error."""
        original = {f"k{i}": f"val{i}" for i in range(10)}
        parsed = {f"k{i}": f"t{i}" for i in range(9)}  # 90%, missing k9
        result = provider._validate_structure(parsed, original)
        assert len(result) == 10
        assert result["k9"] == "val9"  # Missing key → original

    def test_extra_keys_removed(self, provider):
        """Extra keys are removed silently, no error raised."""
        original = {"k1": "v1", "k2": "v2"}
        parsed = {"k1": "t1", "k2": "t2", "k_extra": "t_extra"}
        result = provider._validate_structure(parsed, original)
        assert "k_extra" not in result
        assert result["k1"] == "t1"
        assert result["k2"] == "t2"


class TestValidateStructureTypes:
    def test_type_coercion_int(self, provider):
        """Integer 5 → string "5" (coercion OK)."""
        original = {"k1": "5"}
        parsed = {"k1": 5}
        # This will raise structural_validation because the original "5" has no
        # placeholders and the coerced "5" is fine, but actually it should pass
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "5"

    def test_type_coercion_float(self, provider):
        """Float 3.14 → string "3.14" (coercion OK)."""
        original = {"k1": "3.14"}
        parsed = {"k1": 3.14}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "3.14"

    def test_type_coercion_bool(self, provider):
        """Bool True → string "True" (coercion OK)."""
        original = {"k1": "True"}
        parsed = {"k1": True}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "True"

    def test_type_nested_object_keeps_original(self, provider):
        """Nested object → keep original value, repaired silently."""
        original = {"k1": "v1"}
        parsed = {"k1": {"nested": "value"}}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "v1"

    def test_type_null_keeps_original(self, provider):
        """null → keep original value, repaired silently."""
        original = {"k1": "v1"}
        parsed = {"k1": None}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "v1"

    def test_type_list_keeps_original(self, provider):
        """List → keep original value, repaired silently."""
        original = {"k1": "v1"}
        parsed = {"k1": ["a", "b"]}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "v1"


class TestValidateStructurePlaceholders:
    def test_placeholder_preserved_success(self, provider):
        original = {"k1": "Delete %s?"}
        parsed = {"k1": "Supprimer %s ?"}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "Supprimer %s ?"

    def test_placeholder_missing_fallback_repaired(self, provider):
        """Placeholder mismatch → fallback to original, repaired silently."""
        original = {"k1": "Delete %s?"}
        parsed = {"k1": "Supprimer ?"}  # %s missing!
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "Delete %s?"  # Falls back to original

    def test_no_placeholders_in_original(self, provider):
        """No placeholders → no validation needed."""
        original = {"k1": "Hello"}
        parsed = {"k1": "Bonjour"}
        result = provider._validate_structure(parsed, original)
        assert result["k1"] == "Bonjour"


# ─── Placeholder Extraction ──────────────────────────────────────────


class TestExtractPlaceholders:
    def test_percent_s(self, provider):
        assert "%s" in provider._extract_placeholders("Delete %s?")

    def test_percent_d(self, provider):
        assert "%d" in provider._extract_placeholders("%d items")

    def test_percent_f(self, provider):
        assert "%f" in provider._extract_placeholders("Value: %f")

    def test_curly_name(self, provider):
        assert "{name}" in provider._extract_placeholders("Hello {name}")

    def test_double_curly(self, provider):
        assert "{{count}}" in provider._extract_placeholders("{{count}} items")

    def test_numeric_placeholder(self, provider):
        assert "{0}" in provider._extract_placeholders("Item {0} of {1}")

    def test_icu_plural(self, provider):
        result = provider._extract_placeholders(
            "{count, plural, one{item} other{items}}"
        )
        assert any("plural" in r for r in result)

    def test_html_tags(self, provider):
        result = provider._extract_placeholders("<b>text</b>")
        assert "<b>" in result
        assert "</b>" in result

    def test_escape_sequences(self, provider):
        result = provider._extract_placeholders("Line1\\nLine2")
        assert "\\n" in result

    def test_escape_tab(self, provider):
        result = provider._extract_placeholders("Col1\\tCol2")
        assert "\\t" in result

    def test_escape_quote(self, provider):
        result = provider._extract_placeholders('He said \\"hello\\"')
        assert '\\"' in result

    def test_escape_backslash(self, provider):
        result = provider._extract_placeholders("Path: C:\\\\Users")
        assert "\\\\" in result

    def test_multiple_placeholders(self, provider):
        text = "Delete %s? <b>%d</b> items {name}"
        result = provider._extract_placeholders(text)
        assert "%s" in result
        assert "<b>" in result
        assert "</b>" in result
        assert "{name}" in result
        assert "%d" in result

    def test_no_placeholders(self, provider):
        assert provider._extract_placeholders("Hello world") == []

    def test_empty_string(self, provider):
        assert provider._extract_placeholders("") == []

    def test_html_false_positive_accepted(self, provider):
        """'a < b > c' → '< b >' captured as HTML (accepted tradeoff)."""
        result = provider._extract_placeholders("a < b > c")
        assert len(result) > 0  # False positive, but accepted


class TestValidatePlaceholders:
    def test_matching_placeholders(self, provider):
        assert provider._validate_placeholders("Delete %s?", "Supprimer %s ?", "k1")

    def test_mismatching_placeholders(self, provider):
        assert not provider._validate_placeholders("Delete %s?", "Supprimer ?", "k1")

    def test_no_placeholders_in_either(self, provider):
        assert provider._validate_placeholders("Hello", "Bonjour", "k1")

    def test_no_placeholders_in_original_only(self, provider):
        """Original has no placeholders → always valid."""
        assert provider._validate_placeholders("Hello", "Bonjour <b>test</b>", "k1")

    def test_html_preserved(self, provider):
        assert provider._validate_placeholders(
            "<b>Important</b>", "<b>Important</b>", "k1"
        )

    def test_html_removed(self, provider):
        assert not provider._validate_placeholders(
            "<b>Important</b>", "Important", "k1"
        )

    def test_icu_plural_preserved(self, provider):
        original = "{count, plural, one{item} other{items}}"
        translated = "{count, plural, one{article} other{articles}}"
        # ICU constructs are extracted as whole units, so inner {word}
        # tokens don't cause false mismatches
        assert provider._validate_placeholders(original, translated, "k1")

    def test_multiple_placeholders_preserved(self, provider):
        original = "%s has %d items in {name}"
        translated = "%s a %d éléments dans {name}"
        assert provider._validate_placeholders(original, translated, "k1")


# ─── JSON Extraction ────────────────────────────────────────────────


class TestExtractJson:
    def test_plain_json(self, provider):
        text = '{"k1": "v1"}'
        assert provider._extract_json(text) == '{"k1": "v1"}'

    def test_json_with_markdown_fences(self, provider):
        text = '```json\n{"k1": "v1"}\n```'
        assert provider._extract_json(text) == '{"k1": "v1"}'

    def test_json_with_generic_fences(self, provider):
        text = '```\n{"k1": "v1"}\n```'
        assert provider._extract_json(text) == '{"k1": "v1"}'

    def test_json_with_surrounding_text(self, provider):
        text = 'Here is the result: {"k1": "v1"} done.'
        result = provider._extract_json(text)
        assert result == '{"k1": "v1"}'

    def test_json_with_text_before_and_after(self, provider):
        text = 'Some text {"k1": "v1", "k2": "v2"} more text'
        result = provider._extract_json(text)
        assert '"k1"' in result
        assert '"k2"' in result

    def test_no_json_braces(self, provider):
        text = "just plain text"
        assert provider._extract_json(text) == "just plain text"


# ─── Prompt Building ────────────────────────────────────────────────


class TestBuildPrompt:
    def test_contains_source_and_target(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "fr")
        assert "English" in prompt
        assert "French" in prompt

    def test_contains_json_input(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "fr")
        assert '"k1"' in prompt
        assert "Hello" in prompt

    def test_contains_strict_rules(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "fr")
        assert "STRICT RULES" in prompt
        assert "JSON" in prompt

    def test_no_error_context_by_default(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "fr")
        assert "CORRECTION NEEDED" not in prompt

    def test_error_context_injected(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "fr", error_context="Missing keys")
        assert "CORRECTION NEEDED" in prompt
        assert "Missing keys" in prompt

    def test_unknown_language_code_uses_code_as_name(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "xx")
        assert "xx" in prompt

    def test_placeholder_preservation_in_rules(self, provider):
        items = {"k1": "Hello"}
        prompt = provider._build_prompt(items, "en", "fr")
        assert "placeholder" in prompt.lower() or "%s" in prompt


# ─── IMP3-T003: Intelligent Retry ──────────────────────────────────


class TestRetryIntelligent:
    def test_retry_injects_error_context(self, provider):
        """On validation failure, error_context is injected into the next prompt."""
        items = {"k1": "Hello"}
        call_args = []

        def mock_request(prompt):
            call_args.append(prompt)
            if len(call_args) == 1:
                # First call: return invalid JSON to trigger validation error
                return "not valid json at all"
            # Second call: return valid JSON
            return json.dumps({"k1": "Bonjour"})

        with patch.object(provider, "_make_request", side_effect=mock_request):
            result = provider.translate_batch(items, "en", "fr")
            assert result["k1"] == "Bonjour"
            # Second call should contain CORRECTION NEEDED
            assert len(call_args) >= 2
            assert "CORRECTION NEEDED" in call_args[1]

    def test_retry_success_after_error(self, provider):
        """Retry succeeds after initial validation failure."""
        items = {"k1": "Hello"}
        call_count = {"n": 0}

        def mock_request(prompt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "invalid response"
            return json.dumps({"k1": "Bonjour"})

        with patch.object(provider, "_make_request", side_effect=mock_request):
            result = provider.translate_batch(items, "en", "fr")
            assert result["k1"] == "Bonjour"
            assert call_count["n"] == 2

    def test_retry_exhausted_fallback(self, provider_no_retries):
        """After max retries → keep original text."""
        items = {"k1": "Hello"}
        with patch.object(
            provider_no_retries,
            "_make_request",
            return_value="invalid json",
        ):
            result = provider_no_retries.translate_batch(items, "en", "fr")
            assert result["k1"] == "Hello"

    def test_retry_completion_threshold_triggers_retry(self, provider):
        """Completion threshold failure triggers retry with error injection."""
        items = {f"k{i}": f"v{i}" for i in range(10)}
        call_count = {"n": 0}

        def mock_request(prompt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Return very incomplete response (40% of first chunk's 5 keys)
                return json.dumps({"k0": "t0", "k1": "t1"})
            # Subsequent calls: return complete response for the requested chunk
            if "k0" in prompt:
                return json.dumps({f"k{i}": f"t{i}" for i in range(5)})
            return json.dumps({f"k{i}": f"t{i}" for i in range(5, 10)})

        with patch.object(provider, "_make_request", side_effect=mock_request):
            result = provider.translate_batch(items, "en", "fr")
            assert len(result) == 10
            # chunk 1: 2 attempts (1 fail + 1 success) = 2 calls
            # chunk 2: 1 attempt (success) = 1 call
            # total = 3
            assert call_count["n"] == 3

    def test_retry_with_generic_exception(self, provider):
        """Generic exceptions (connection error) are caught and trigger retry."""
        items = {"k1": "Hello"}
        call_count = {"n": 0}

        def mock_request(prompt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("connection error")
            return json.dumps({"k1": "Bonjour"})

        with patch.object(provider, "_make_request", side_effect=mock_request):
            result = provider.translate_batch(items, "en", "fr")
            assert result["k1"] == "Bonjour"
            assert call_count["n"] == 2


# ─── Parse Response ────────────────────────────────────────────────


class TestParseResponse:
    def test_valid_json_response(self, provider):
        original = {"k1": "Hello", "k2": "World"}
        response = json.dumps({"k1": "Bonjour", "k2": "Monde"})
        result = provider._parse_response(response, original)
        assert result == {"k1": "Bonjour", "k2": "Monde"}

    def test_invalid_json_raises(self, provider):
        original = {"k1": "Hello"}
        with pytest.raises(OllamaValidationError) as exc_info:
            provider._parse_response("not json", original)
        assert exc_info.value.error_type == "json_parse"

    def test_json_in_markdown_fences(self, provider):
        original = {"k1": "Hello"}
        response = f"```json\n{json.dumps({'k1': 'Bonjour'})}\n```"
        result = provider._parse_response(response, original)
        assert result == {"k1": "Bonjour"}

    def test_json_with_extra_keys_removed(self, provider):
        """Extra keys are removed silently in repair."""
        original = {"k1": "Hello"}
        response = json.dumps({"k1": "Bonjour", "k_extra": "extra"})
        result = provider._parse_response(response, original)
        assert result == {"k1": "Bonjour"}

    def test_json_with_missing_keys_above_threshold_repaired(self, provider):
        """Missing keys above 80% → repaired with original values."""
        original = {f"k{i}": f"v{i}" for i in range(10)}
        parsed = {f"k{i}": f"t{i}" for i in range(9)}  # 90%, missing k9
        response = json.dumps(parsed)
        result = provider._parse_response(response, original)
        assert len(result) == 10
        assert result["k9"] == "v9"


# ─── Placeholder Integration Tests ─────────────────────────────────


class TestPlaceholderIntegration:
    def test_percent_s_preserved(self, provider):
        original = {"k1": "Delete %s?"}
        response = json.dumps({"k1": "Supprimer %s ?"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "Supprimer %s ?"

    def test_percent_d_preserved(self, provider):
        original = {"k1": "%d items"}
        response = json.dumps({"k1": "%d articles"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "%d articles"

    def test_curly_name_preserved(self, provider):
        original = {"k1": "Hello {name}"}
        response = json.dumps({"k1": "Bonjour {name}"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "Bonjour {name}"

    def test_double_curly_preserved(self, provider):
        original = {"k1": "{{count}} items"}
        response = json.dumps({"k1": "{{count}} articles"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "{{count}} articles"

    def test_icu_plural_preserved(self, provider):
        original = {"k1": "{count, plural, one{item} other{items}}"}
        response = json.dumps({"k1": "{count, plural, one{article} other{articles}}"})
        result = provider._parse_response(response, original)
        assert "plural" in result["k1"]

    def test_html_tags_preserved(self, provider):
        original = {"k1": "<b>Important</b>"}
        response = json.dumps({"k1": "<b>Important</b>"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "<b>Important</b>"

    def test_escape_sequences_preserved(self, provider):
        original = {"k1": "Line1\\nLine2"}
        response = json.dumps({"k1": "Ligne1\\nLigne2"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "Ligne1\\nLigne2"

    def test_placeholder_mismatch_fallback_repaired(self, provider):
        """Placeholder mismatch → fallback to original, repaired silently."""
        original = {"k1": "Delete %s?"}
        response = json.dumps({"k1": "Supprimer ?"})  # %s missing!
        result = provider._parse_response(response, original)
        assert result["k1"] == "Delete %s?"  # Falls back to original

    def test_html_tags_removed_fallback_repaired(self, provider):
        """HTML tags removed → fallback to original, repaired silently."""
        original = {"k1": "<b>Important</b>"}
        response = json.dumps({"k1": "Important"})  # HTML tags removed!
        result = provider._parse_response(response, original)
        assert result["k1"] == "<b>Important</b>"

    def test_numeric_placeholder_preserved(self, provider):
        original = {"k1": "Item {0} of {1}"}
        response = json.dumps({"k1": "Élément {0} sur {1}"})
        result = provider._parse_response(response, original)
        assert result["k1"] == "Élément {0} sur {1}"


# ─── Make Request ───────────────────────────────────────────────────


class TestMakeRequest:
    def test_calls_ollama_api(self, provider):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": '{"k1": "v1"}'}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "core.ollama_provider.requests.post", return_value=mock_resp
        ) as mock_post:
            result = provider._make_request("test prompt")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs[0][0] == "http://localhost:11434/api/generate"
            body = call_kwargs[1]["json"]
            assert body["model"] == "test-model"
            assert body["stream"] is False
            assert body["options"]["temperature"] == 0
            assert result == '{"k1": "v1"}'

    def test_timeout_passed(self, provider):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "test"}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "core.ollama_provider.requests.post", return_value=mock_resp
        ) as mock_post:
            provider._make_request("prompt")
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["timeout"] == 60

    def test_custom_base_url(self):
        provider = OllamaProvider(base_url="http://host.docker.internal:11434")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "test"}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "core.ollama_provider.requests.post", return_value=mock_resp
        ) as mock_post:
            provider._make_request("prompt")
            call_url = mock_post.call_args[0][0]
            assert call_url == "http://host.docker.internal:11434/api/generate"

    def test_http_error_raised(self, provider):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("core.ollama_provider.requests.post", return_value=mock_resp):
            with pytest.raises(Exception, match="500 Server Error"):
                provider._make_request("prompt")
