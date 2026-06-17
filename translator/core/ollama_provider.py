"""
Ollama translation provider with chunking and structural validation (IMP3).

Uses a local Ollama LLM to translate batches of key-value pairs via chunking,
with strict structural validation, placeholder preservation, and intelligent
retry with error injection.
"""

import json
import logging
import re

import requests

from core.translator_factory import TranslationProvider

logger = logging.getLogger(__name__)


class OllamaValidationError(Exception):
    """Raised when Ollama response fails structural validation.

    Attributes:
        error_type: Category of validation failure.
            One of: "completion_threshold", "missing_keys", "extra_keys",
            "type_mismatch", "placeholder_mismatch", "json_parse",
            "structural_validation".
    """

    def __init__(self, message: str, error_type: str = "unknown"):
        self.error_type = error_type
        super().__init__(message)


class OllamaProvider(TranslationProvider):
    """Translation provider using local Ollama LLM with chunking.

    Uses batch translation with structural validation and
    intelligent retry to ensure production-grade output quality.
    """

    # Placeholder patterns to protect during translation
    PLACEHOLDER_PATTERNS: list[re.Pattern] = [
        re.compile(r"%[sdrfifFeEgG]"),  # %s, %d, %f, etc.
        re.compile(r"\{[a-zA-Z_]\w*\}"),  # {name}, {count}
        re.compile(r"\{\{[a-zA-Z_]\w*\}\}"),  # {{name}}, {{count}}
        re.compile(r"\{\d+\}"),  # {0}, {1}
        re.compile(r"\{[^}]+,\s*\w+,"),  # ICU plural/select
        re.compile(r"<[^>]+>"),  # HTML tags
        re.compile(r"\\[nt\"\\]"),  # Escape sequences: \n, \t, \", \\
    ]

    # Minimum completion threshold — if less than 80% of keys are present,
    # the response is considered totally invalid (no silent partial repair).
    COMPLETION_THRESHOLD: float = 0.8

    # Language code to human-readable name mapping for prompts
    LANG_NAMES: dict[str, str] = {
        "en": "English",
        "fr": "French",
        "de": "German",
        "cs": "Czech",
        "sk": "Slovak",
        "it": "Italian",
        "ar": "Arabic",
    }

    def __init__(
        self,
        model: str = "minimax-m3:cloud",
        base_url: str = "http://localhost:11434",
        chunk_size: int = 50,
        max_retries: int = 2,
        timeout: int = 300,
        temperature: float = 0,
    ):
        self._model = model
        self._base_url = base_url
        self._chunk_size = chunk_size
        self._max_retries = max_retries
        self._timeout = timeout
        self._temperature = temperature

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    def translate(self, text: str, source: str, target: str) -> str:
        """Translate a single text using Ollama.

        Wraps translate_batch with a single-item dict for consistency.
        """
        if not text or not text.strip():
            return text
        result = self.translate_batch({"__single__": text}, source, target)
        return result.get("__single__", text)

    def translate_batch(
        self,
        items: dict[str, str],
        source: str,
        target: str,
    ) -> dict[str, str]:
        """Translate a batch of texts using chunking with intelligent retry.

        Splits items into chunks, translates each chunk via the Ollama LLM,
        and applies structural validation with retry on failure.

        If the translation cache is enabled, checks the cache first for each
        item and only sends uncached items to Ollama. Newly translated items
        are stored in the cache for future reuse.

        Args:
            items: Key-value pairs to translate (values are source texts).
            source: Source language code.
            target: Target language code.

        Returns:
            Dict with same keys and translated values. On failure, original
            values are preserved for the failing chunk.
        """
        results: dict[str, str] = {}

        # Check cache for all items before chunking
        from core.cache import get_cache
        from core.config import get_config

        config = get_config()
        cache = (
            get_cache(cache_path=config.TRANSLATION_CACHE_PATH)
            if config.cache_enabled
            else None
        )

        if cache:
            cached_items: dict[str, str] = {}
            uncached_items: dict[str, str] = {}
            for key, text in items.items():
                if not text or len(text.strip()) == 0:
                    # Empty values: pass through without caching
                    cached_items[key] = text
                else:
                    cached_result = cache.get(source, target, text)
                    if cached_result is not None:
                        cached_items[key] = cached_result
                    else:
                        uncached_items[key] = text

            results.update(cached_items)
            cache_hits = len(cached_items)
            cache_misses = len(uncached_items)
            logger.info(
                "Cache lookup: %d hits, %d misses (skipping Ollama for %d items)",
                cache_hits,
                cache_misses,
                cache_hits,
            )
            items = uncached_items

        if not items:
            logger.info("All items found in cache — no Ollama call needed")
            return results

        chunks = self._chunk_items(items)
        total_chunks = len(chunks)

        for chunk_idx, chunk in enumerate(chunks):
            logger.info(
                "Ollama chunk %d/%d (%d items)",
                chunk_idx + 1,
                total_chunks,
                len(chunk),
            )
            error_context: str | None = None

            for attempt in range(self._max_retries + 1):
                try:
                    chunk_result = self._call_ollama(
                        chunk, source, target, error_context=error_context
                    )
                    results.update(chunk_result)
                    # Store successful translations in cache
                    if cache:
                        for k, v in chunk_result.items():
                            original_text = chunk.get(k, v)
                            if original_text and len(original_text.strip()) > 0:
                                cache.put(source, target, original_text, v)
                    error_context = None  # Reset on success
                    break
                except OllamaValidationError as e:
                    error_context = str(e)  # Inject error into next retry
                    logger.warning(
                        "Ollama chunk %d/%d attempt %d/%d failed: %s",
                        chunk_idx + 1,
                        total_chunks,
                        attempt + 1,
                        self._max_retries + 1,
                        e,
                    )
                    if attempt == self._max_retries:
                        logger.error(
                            "Ollama chunk %d/%d failed after %d attempts — "
                            "keeping original text",
                            chunk_idx + 1,
                            total_chunks,
                            self._max_retries + 1,
                        )
                        # Per-key fallback: try Google Translate for each item
                        fallback_result = self._fallback_per_key(chunk, source, target)
                        results.update(fallback_result)
                        if cache:
                            for k, v in fallback_result.items():
                                original_text = chunk.get(k, v)
                                if (
                                    original_text
                                    and len(original_text.strip()) > 0
                                    and v != original_text
                                ):
                                    cache.put(source, target, original_text, v)
                except Exception as e:
                    # Non-validation errors (connection, timeout, etc.)
                    logger.warning(
                        "Ollama chunk %d/%d attempt %d/%d error: %s",
                        chunk_idx + 1,
                        total_chunks,
                        attempt + 1,
                        self._max_retries + 1,
                        e,
                    )
                    if attempt == self._max_retries:
                        logger.error(
                            "Ollama chunk %d/%d failed after %d attempts — "
                            "keeping original text",
                            chunk_idx + 1,
                            total_chunks,
                            self._max_retries + 1,
                        )
                        # Per-key fallback: try Google Translate for each item
                        fallback_result = self._fallback_per_key(chunk, source, target)
                        results.update(fallback_result)
                        if cache:
                            for k, v in fallback_result.items():
                                original_text = chunk.get(k, v)
                                if (
                                    original_text
                                    and len(original_text.strip()) > 0
                                    and v != original_text
                                ):
                                    cache.put(source, target, original_text, v)

        # Flush cache to disk after all chunks
        if cache:
            cache.flush()
            stats = cache.stats()
            logger.info(
                "Cache stats after batch: %d hits, %d misses (%.1f%% hit rate)",
                stats["hits"],
                stats["misses"],
                stats["hit_rate_pct"],
            )

        return results

    def _fallback_per_key(
        self, items: dict[str, str], source: str, target: str
    ) -> dict[str, str]:
        """Attempt per-key translation via Google Translate as fallback.

        Called when Ollama fails to translate a chunk after all retries.
        Tries each key individually via Google Translate. If Google also
        fails for a key, keeps the original text.

        Args:
            items: Key-value pairs that Ollama failed to translate.
            source: Source language code.
            target: Target language code.

        Returns:
            Dict with same keys and translated (or original) values.
        """
        results: dict[str, str] = {}
        try:
            from core.translator_factory import GoogleProvider

            google = GoogleProvider()
            logger.info("Falling back to Google Translate for %d items", len(items))
        except Exception as e:
            logger.warning("Cannot create Google Translate fallback: %s", e)
            return dict(items)

        for key, text in items.items():
            if not text or len(text.strip()) == 0:
                results[key] = text
                continue
            try:
                translated = google.translate(text, source, target)
                if translated and translated != text:
                    results[key] = translated
                    logger.debug("Google fallback OK for key '%s'", key)
                else:
                    results[key] = text
                    logger.warning(
                        "Google fallback returned same text for key '%s'", key
                    )
            except Exception as e:
                results[key] = text
                logger.warning("Google fallback failed for key '%s': %s", key, e)
        return results

    def _chunk_items(self, items: dict[str, str]) -> list[dict[str, str]]:
        """Split items into chunks of chunk_size."""
        keys = list(items.keys())
        chunks = []
        for i in range(0, len(keys), self._chunk_size):
            chunk_keys = keys[i : i + self._chunk_size]
            chunks.append({k: items[k] for k in chunk_keys})
        return chunks

    def _call_ollama(
        self,
        items: dict[str, str],
        source: str,
        target: str,
        error_context: str | None = None,
    ) -> dict[str, str]:
        """Send a chunk to Ollama and parse the response.

        Args:
            items: Key-value pairs to translate.
            source: Source language code.
            target: Target language code.
            error_context: If provided, injected into the prompt to help the LLM
                           correct a previous error.

        Returns:
            Validated translation dict.

        Raises:
            OllamaValidationError: If structural validation fails.
        """
        prompt = self._build_prompt(items, source, target, error_context=error_context)
        response = self._make_request(prompt)
        return self._parse_response(response, items)

    def _build_prompt(
        self,
        items: dict[str, str],
        source: str,
        target: str,
        error_context: str | None = None,
    ) -> str:
        """Build the translation prompt for the LLM.

        Args:
            items: Key-value pairs to translate.
            source: Source language code.
            target: Target language code.
            error_context: If provided, injected to help the LLM correct
                           a previous error on retry.
        """
        source_name = self.LANG_NAMES.get(source, source)
        target_name = self.LANG_NAMES.get(target, target)

        json_input = json.dumps(items, ensure_ascii=False, indent=2)

        prompt = f"""You are a professional software localization translator.

STRICT RULES:
- Return VALID JSON only — no markdown, no explanations, no comments
- Keep ALL keys exactly as they are — do NOT rename, reorder, or remove any key
- Translate VALUES only from {source_name} to {target_name}
- Preserve ALL placeholders exactly: {{name}}, %s, %d, {{count}}, {{value}}, etc.
- Preserve ALL escape characters exactly: \\n, \\t, \\", etc.
- Preserve ALL HTML tags exactly: <b>, <br/>, <strong>, etc.
- Translate ALL text including content inside HTML tags (e.g. text between <strong> and </strong>)
- Keep HTML tags in their exact position but translate the text they wrap
- NEVER return the original {source_name} text untranslated — always translate to {target_name}
- If a value is empty, keep it empty
- If a value is a technical term that doesn't need translation, keep it as-is
- Output ONLY the JSON object — no other text before or after

JSON to translate:
{json_input}"""

        if error_context:
            prompt += f"""

CORRECTION NEEDED:
Previous attempt failed with this error: {error_context}
Please fix the issue and return valid JSON following ALL the rules above."""

        return prompt

    def _make_request(self, prompt: str) -> str:
        """Make a request to the Ollama API.

        Args:
            prompt: The translation prompt to send.

        Returns:
            The LLM response text.

        Raises:
            requests.RequestException: If the HTTP request fails.
        """
        # IMPORTANT: stream=False is mandatory for batch translation.
        # Streaming adds complexity without benefit here — we need the full
        # response to validate JSON structure before processing.
        response = requests.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self._temperature,
                    "num_predict": 8192,
                },
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["response"]

    def _parse_response(
        self,
        response: str,
        original_items: dict[str, str],
    ) -> dict[str, str]:
        """Parse and structurally validate the LLM response.

        1. Extract JSON from response (handle markdown fences)
        2. Parse JSON
        3. Validate structure (keys, types, placeholders)

        Args:
            response: Raw LLM response text.
            original_items: Original key-value pairs for validation.

        Returns:
            Validated translation dict.

        Raises:
            OllamaValidationError: If JSON parsing or structural validation fails.
        """
        json_str = self._extract_json(response)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise OllamaValidationError(
                f"Invalid JSON response: {e}",
                error_type="json_parse",
            )

        return self._validate_structure(parsed, original_items)

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handle markdown fences).

        Tries, in order:
        1. Extract content from ```json ... ``` fences
        2. Extract content from ``` ... ``` fences
        3. Find JSON object boundaries { ... }

        Args:
            text: Raw LLM response text.

        Returns:
            Extracted JSON string.
        """
        # Remove markdown code fences if present
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.rindex("```")
            return text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.rindex("```")
            return text[start:end].strip()
        # Try to find JSON object boundaries
        if "{" in text and "}" in text:
            start = text.index("{")
            end = text.rindex("}") + 1
            return text[start:end]
        return text

    # Index of the ICU plural/select pattern in PLACEHOLDER_PATTERNS
    _ICU_PATTERN_IDX = 4  # re.compile(r'\{[^}]+,\s*\w+,')

    def _extract_placeholders(self, text: str) -> list[str]:
        """Extract all placeholder patterns from a text string.

        Protected patterns: %s/%d, {name}, {{count}}, {0},
        ICU syntax, HTML tags, escape sequences.

        ICU patterns are processed first. When an ICU pattern prefix is found
        (e.g. "{count, plural,"), the full ICU construct is extracted by finding
        the matching closing brace. Subsequent {name} patterns inside ICU
        ranges are skipped to avoid false mismatches from translated inner tokens.

        Args:
            text: Text to scan for placeholders.

        Returns:
            Sorted list of all found placeholders.
        """
        placeholders: list[str] = []
        icu_ranges: list[tuple[int, int]] = []  # Character ranges covered by ICU

        # First pass: extract ICU patterns and find their full extent
        icu_pattern = self.PLACEHOLDER_PATTERNS[self._ICU_PATTERN_IDX]
        for match in icu_pattern.finditer(text):
            start = match.start()
            # Find matching closing brace by counting brace depth
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > start:
                icu_ranges.append((start, end))
                placeholders.append(text[start:end])  # Full ICU construct

        # Second pass: extract other patterns, skipping ICU ranges
        for idx, pattern in enumerate(self.PLACEHOLDER_PATTERNS):
            if idx == self._ICU_PATTERN_IDX:
                continue  # Already processed above
            for match in pattern.finditer(text):
                if any(s <= match.start() < e for s, e in icu_ranges):
                    continue  # Skip matches inside ICU constructs
                placeholders.append(match.group())

        return sorted(placeholders)

    def _validate_placeholders(
        self,
        original: str,
        translated: str,
        key: str,
    ) -> bool:
        """Verify that all placeholders from original are preserved in translation.

        For ICU plural/select patterns, compares only the structural prefix
        (e.g. "{count, plural,") rather than the full construct, since inner
        tokens are expected to differ in translations.

        Args:
            original: Source text with placeholders.
            translated: Translated text to check.
            key: Key name for logging.

        Returns:
            True if valid, False if any placeholder is missing or altered.
        """
        original_ph = self._extract_placeholders(original)
        translated_ph = self._extract_placeholders(translated)

        if not original_ph:
            return True

        # Separate ICU constructs from other placeholders for comparison.
        # ICU constructs are compared by their structural prefix only,
        # since inner tokens (translated words inside plural clauses)
        # legitimately differ between source and target.
        icu_prefix_pattern = re.compile(r"\{[^}]+,\s*\w+,")

        def icu_prefix(placeholder: str) -> str:
            """Extract the ICU structural prefix from a full ICU construct."""
            m = icu_prefix_pattern.match(placeholder)
            return m.group() if m else placeholder

        def normalize(ph_list: list[str]) -> list[str]:
            """Normalize ICU placeholders to their prefix, keep others as-is."""
            result = []
            for ph in ph_list:
                if icu_prefix_pattern.match(ph):
                    result.append(icu_prefix(ph))
                else:
                    result.append(ph)
            return sorted(result)

        if sorted(normalize(original_ph)) != sorted(normalize(translated_ph)):
            logger.warning(
                "Placeholder mismatch for key '%s': expected %s, got %s",
                key,
                original_ph,
                translated_ph,
            )
            return False
        return True

    def _validate_structure(
        self,
        parsed: dict,
        original: dict[str, str],
    ) -> dict[str, str]:
        """Validate and repair the LLM response structure.

        5 checks in order:
        0. Minimum completion threshold (< 80% keys → reject entirely, trigger retry)
        1. Keys match exactly (missing → inject original, extra → remove)
        2. All values are strings (coerce numbers, else keep original)
        3. No nested objects (keep original for nested values)
        4. Placeholders preserved (compare before/after for each value)

        When completion is ≥80%, repairable issues (missing keys, type coercion,
        placeholder fallback) are applied silently and the repaired result
        is returned without raising — this prevents unnecessary retries on
        partially valid responses.

        Args:
            parsed: Parsed JSON response from LLM.
            original: Original key-value pairs.

        Returns:
            A cleaned dict with all original keys and validated values.

        Raises:
            OllamaValidationError: Only when completion is below the 80% threshold
                (to trigger retry with error injection).
        """
        result: dict[str, str] = {}
        original_keys = set(original.keys())
        parsed_keys = set(parsed.keys())

        # Check 0: Minimum completion threshold
        # If less than 80% of keys are present, the response is totally invalid.
        # Do NOT attempt partial repair — trigger a retry with error injection.
        completion_ratio = (
            len(parsed_keys & original_keys) / len(original_keys)
            if original_keys
            else 1.0
        )
        if completion_ratio < self.COMPLETION_THRESHOLD:
            raise OllamaValidationError(
                f"Response completion too low: {completion_ratio:.0%} "
                f"({len(parsed_keys & original_keys)}/{len(original_keys)} keys). "
                f"Minimum required: {self.COMPLETION_THRESHOLD:.0%}",
                error_type="completion_threshold",
            )

        # Log repairable issues but do NOT raise — targeted repair is applied
        missing_keys = original_keys - parsed_keys
        extra_keys = parsed_keys - original_keys
        if missing_keys:
            logger.info("Repairing missing keys in Ollama response: %s", missing_keys)
        if extra_keys:
            logger.info("Removing extra keys from Ollama response: %s", extra_keys)

        # Build result with validation per value
        for key in original_keys:
            if key not in parsed:
                # Missing key: keep original
                result[key] = original[key]
                continue

            value = parsed[key]

            # Check 2: Type — value must be a string
            if not isinstance(value, str):
                if isinstance(value, (int, float, bool)):
                    value = str(value)
                else:
                    # Nested object or other — keep original
                    logger.info(
                        "Key '%s': expected string, got %s — keeping original",
                        key,
                        type(value).__name__,
                    )
                    result[key] = original[key]
                    continue

            # Check 4: Placeholders preserved
            if not self._validate_placeholders(original[key], value, key):
                result[key] = original[key]  # Fallback to original
                continue

            result[key] = value

        return result
