#!/usr/bin/env python3
"""
Mini-benchmark Ollama — Compare glm-5.2 vs minimax-m2.7.

Usage:
    python3 benchmark_glm_5.2.py

Teste 3 modeles (glm-5.2:cloud, minimax-m2.7:cloud, glm-5.1:cloud)
sur 30 entrees, en FR et CZ, et mesure :
  - Temps total et par chunk
  - Taux de JSON invalide
  - Taux de corruption placeholders
  - Taux de fallback (valeurs originales conservees)
  - Completeur (% cles retournees)

Resultats affiches en tableau comparatif, avec focus sur glm-5.2.
"""

import json
import re
import time
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────

SOURCE_FILE = Path(__file__).parent / "source" / "2026_06_12_Import" / "en 7.json"
SAMPLE_SIZE = 30
CHUNK_SIZE = 20
TEMPERATURE = 0
MAX_RETRIES = 2
TIMEOUT = 300

MODELS = [
    "glm-5.2:cloud",
    "minimax-m3:cloud",
    "minimax-m2.7:cloud",
    "glm-5.1:cloud",
]

LANGUAGES = [
    ("en", "fr", "French"),
    ("en", "cs", "Czech"),
]

OLLAMA_URL = "http://host.docker.internal:11434"

# ─── Helpers ────────────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    re.compile(r"%[sdrfifFeEgG]"),
    re.compile(r"\{[a-zA-Z_]\w*\}"),
    re.compile(r"\{\{[a-zA-Z_]\w*\}\}"),
    re.compile(r"\{\d+\}"),
    re.compile(r"\{[^}]+,\s*\w+,"),  # ICU
    re.compile(r"<[^>]+>"),
    re.compile(r"\\[nt\"\\]"),
]


def extract_placeholders(text: str) -> list[str]:
    placeholders = []
    icu_ranges = []

    icu_pattern = PLACEHOLDER_PATTERNS[4]
    for match in icu_pattern.finditer(text):
        start = match.start()
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
            placeholders.append(text[start:end])

    for idx, pattern in enumerate(PLACEHOLDER_PATTERNS):
        if idx == 4:
            continue
        for match in pattern.finditer(text):
            if any(s <= match.start() < e for s, e in icu_ranges):
                continue
            placeholders.append(match.group())

    return sorted(placeholders)


def call_ollama(model: str, prompt: str) -> str | None:
    """Call Ollama API and return response text, or None on failure."""
    import requests

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": TEMPERATURE,
                    "num_predict": 8192,
                },
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print(f"    ⚠️  API error: {e}")
        return None


def extract_json(text: str) -> str:
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.rindex("```")
        return text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.rindex("```")
        return text[start:end].strip()
    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    return text


def build_prompt(items: dict, source_lang: str, target_lang: str) -> str:
    lang_names = {
        "en": "English",
        "fr": "French",
        "de": "German",
        "cs": "Czech",
        "sk": "Slovak",
        "it": "Italian",
        "ar": "Arabic",
    }
    source_name = lang_names.get(source_lang, source_lang)
    target_name = lang_names.get(target_lang, target_lang)
    json_input = json.dumps(items, ensure_ascii=False, indent=2)

    return f"""You are a professional software localization translator.

STRICT RULES:
- Return VALID JSON only — no markdown, no explanations, no comments
- Keep ALL keys exactly as they are — do NOT rename, reorder, or remove any key
- Translate VALUES only from {source_name} to {target_name}
- Preserve ALL placeholders exactly: {{name}}, %s, %d, {{count}}, {{value}}, etc.
- Preserve ALL escape characters exactly: \\n, \\t, \\", etc.
- Preserve ALL HTML tags exactly: <b>, <br/>, <strong>, etc.
- If a value is empty, keep it empty
- If a value is a technical term that doesn't need translation, keep it as-is
- Output ONLY the JSON object — no other text before or after

JSON to translate:
{json_input}"""


# ─── Benchmark runner ──────────────────────────────────────────────


def benchmark_model(
    model: str,
    source_data: dict,
    sample: dict,
    source_lang: str,
    target_lang: str,
    target_name: str,
    run_idx: int = 1,
) -> dict:
    """Run benchmark for one model+language combo. Returns metrics dict."""

    label = f"run {run_idx}" if run_idx > 1 else ""
    print(f"\n  🔄 {model} → {target_name} ({len(sample)} entries) {label}...")

    prompt = build_prompt(sample, source_lang, target_lang)

    t0 = time.time()
    raw_response = call_ollama(model, prompt)
    elapsed = time.time() - t0

    if raw_response is None:
        return {
            "model": model,
            "lang": target_lang,
            "time": elapsed,
            "json_valid": False,
            "completion": 0,
            "placeholders_total": 0,
            "placeholders_ok": 0,
            "placeholder_rate": 0,
            "fallbacks": len(sample),
            "entries_ok": 0,
            "error": "API error",
        }

    # Parse JSON
    json_str = extract_json(raw_response)
    try:
        parsed = json.loads(json_str)
        json_valid = True
    except json.JSONDecodeError:
        parsed = {}
        json_valid = False

    # Metrics
    original_keys = set(sample.keys())
    parsed_keys = set(parsed.keys()) if isinstance(parsed, dict) else set()
    common_keys = original_keys & parsed_keys
    completion = len(common_keys) / len(original_keys) if original_keys else 0

    # Placeholder check
    placeholder_total = 0
    placeholder_ok = 0
    fallbacks = 0

    for key in original_keys:
        original_val = sample[key]
        if key not in parsed or not isinstance(parsed.get(key), str):
            fallbacks += 1
            continue

        translated_val = parsed[key]
        orig_ph = extract_placeholders(original_val)

        if orig_ph:
            placeholder_total += 1
            trans_ph = extract_placeholders(translated_val)

            # ICU prefix normalization
            icu_prefix_pat = re.compile(r"\{[^}]+,\s*\w+,")

            def norm_icu(ph_list):
                result = []
                for ph in ph_list:
                    m = icu_prefix_pat.match(ph)
                    result.append(m.group() if m else ph)
                return sorted(result)

            if sorted(norm_icu(orig_ph)) == sorted(norm_icu(trans_ph)):
                placeholder_ok += 1
            else:
                fallbacks += 1
        elif original_val == translated_val and target_lang != "en":
            # Same as original — may indicate untranslated or technical term
            pass

    return {
        "model": model,
        "lang": target_lang,
        "lang_name": target_name,
        "time": round(elapsed, 1),
        "json_valid": json_valid,
        "completion": round(completion * 100, 1),
        "placeholders_total": placeholder_total,
        "placeholders_ok": placeholder_ok,
        "placeholder_rate": round(
            placeholder_ok / placeholder_total * 100 if placeholder_total else 100, 1
        ),
        "fallbacks": fallbacks,
        "entries_ok": len(common_keys) - fallbacks,
        "error": None,
    }


# ─── Main ──────────────────────────────────────────────────────────


def main():
    # Load source data
    with open(SOURCE_FILE, encoding="utf-8") as f:
        source_data = json.load(f)

    print(f"Source: {len(source_data)} entries, sampling {SAMPLE_SIZE}")

    # Select sample — first N entries with variety (some with placeholders)
    items = list(source_data.items())

    # Mix: prioritize entries with placeholders for meaningful test
    with_placeholders = [(k, v) for k, v in items if extract_placeholders(v)]
    without_placeholders = [(k, v) for k, v in items if not extract_placeholders(v)]

    # Ensure at least half with placeholders for meaningful test, rest without
    n_ph = min(len(with_placeholders), SAMPLE_SIZE // 2)
    n_no = min(len(without_placeholders), SAMPLE_SIZE - n_ph)
    sample_items = with_placeholders[:n_ph] + without_placeholders[:n_no]
    sample = dict(sample_items)

    print(f"Sample: {len(sample)} entries ({n_ph} with placeholders, {n_no} without)")

    # Check Ollama connectivity
    import requests as req

    try:
        req.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        print(f"Ollama: ✅ connected at {OLLAMA_URL}")
    except Exception:
        print(f"Ollama: ❌ NOT reachable at {OLLAMA_URL}")
        return

    # Available models
    resp = req.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    available = [m["name"] for m in resp.json().get("models", [])]
    print(f"Models available: {available}")

    # Run benchmarks
    results = []

    for model in MODELS:
        if model not in available:
            print(f"\n  ⏭️  {model} not available, skipping")
            continue

        # For glm-5.2 and glm-5.1, run twice (check stability)
        n_runs = 2 if model in ("glm-5.2:cloud", "glm-5.1:cloud") else 1
        for run_idx in range(1, n_runs + 1):
            for source_lang, target_lang, target_name in LANGUAGES:
                result = benchmark_model(
                    model,
                    source_data,
                    sample,
                    source_lang,
                    target_lang,
                    target_name,
                    run_idx=run_idx,
                )
                result["run"] = run_idx
                results.append(result)

    # Display results
    print("\n")
    print("=" * 100)
    print("BENCHMARK RESULTS")
    print("=" * 100)
    print(
        f"{'Model':<22} {'Lang':<6} {'Run':>4} {'Time':>6} {'JSON':>6} "
        f"{'Compl%':>7} {'PH ok':>6} {'PH%':>5} {'Fallbacks':>9} {'OK':>5}"
    )
    print("-" * 100)

    for r in results:
        json_mark = "✅" if r["json_valid"] else "❌"
        run_label = f"#{r.get('run', 1)}"
        print(
            f"{r['model']:<22} {r['lang']:<6} {run_label:>4} {r['time']:>5.1f}s {json_mark:>4} "
            f"{r['completion']:>6.1f}% {r['placeholders_ok']:>5}/{r['placeholders_total']:<2} "
            f"{r['placeholder_rate']:>4.0f}% {r['fallbacks']:>8} {r['entries_ok']:>5}"
        )

    print("=" * 100)

    # Winner per language
    print("\n🏆 Best per language:")
    for source_lang, target_lang, target_name in LANGUAGES:
        lang_results = [
            r for r in results if r["lang"] == target_lang and r["error"] is None
        ]
        if lang_results:
            best = min(
                lang_results,
                key=lambda r: (-r["completion"], r["fallbacks"], r["time"]),
            )
            print(
                f"  {target_name}: {best['model']} "
                f"(compl={best['completion']:.0f}%, fallbacks={best['fallbacks']}, "
                f"time={best['time']:.1f}s)"
            )

    # Sample output preview
    print("\n📝 Sample translations (first 3 entries):")
    for model in MODELS:
        if model not in available:
            continue
        print(f"\n  --- {model} (FR) ---")
        prompt = build_prompt(dict(sample_items[:3]), "en", "fr")
        raw = call_ollama(model, prompt)
        if raw:
            json_str = extract_json(raw)
            try:
                parsed = json.loads(json_str)
                for k, v in list(parsed.items())[:3]:
                    orig = sample[k]
                    marker = "✅" if orig != v else "⚠️=orig"
                    print(f"    {k}: {v[:80]} {marker}")
            except json.JSONDecodeError:
                print(f"    ❌ Invalid JSON: {json_str[:100]}...")


if __name__ == "__main__":
    main()
