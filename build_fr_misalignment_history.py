#!/usr/bin/env python3
"""Build a per-version history table for the FR misaligned keys.

For each FR key flagged as a genuine misalignment (its FR value is the majority
translation of an UNRELATED source text, no token overlap), output:
  key | EN source at each version | FR translation at each version

Versions (source EN + FR export paired by date):
  05_05, en4 (05_13), en5 (05_27), en7 (06_12), en8 (06_23), en9 (06_25), current (06_26)

Outputs:
  doc/2026_06_26_FR_Misalignment_History.csv  (Excel-friendly)
  doc/2026_06_26_FR_Misalignment_History.md   (markdown, full table)
"""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SRC = {
    "05_05": "translator/source/2026_05_05_Import/2026_05_05_translation_en_en.json",
    "en4": "translator/source/2026_05_13_Import/en 4.json",
    "en5": "translator/source/2026_05_27_Import/en 5.json",
    "en7": "translator/source/2026_06_12_Import/en 7.json",
    "en8": "translator/source/2026_06_23_Import/en8.json",
    "en9": "translator/source/2026_06_25_Import/en 9.json",
}
FR = {
    "05_05": "translator/output/2026_05_05_Export/translation_en_fr.json",
    "en4": "translator/output/2026_05_13_Export/translation_en_fr.json",
    "en5": "translator/output/2026_05_27_Export/translation_en_fr.json",
    "en7": "translator/output/2026_06_12_Export/translation_en_fr.json",
    "en8": "translator/output/2026_06_23_Export/translation_en_fr.json",
    "en9": "translator/output/2026_06_25_Export/translation_en_fr.json",
    "current": "translator/output/2026_06_26_Export/translation_en_fr.json",
}
VERSIONS = [
    "05_05",
    "en4",
    "en5",
    "en7",
    "en8",
    "en9",
]  # source versions (current FR == en9 for these keys)


def load(p):
    return json.load(open(p))


def tokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


en9 = load(SRC["en9"])
fr_cur = load(FR["current"])

# 1) detect genuine misalignment keys in current FR (same method as before)
by_src = defaultdict(list)
for k, v in en9.items():
    if v and v.strip():
        by_src[v].append(k)
majority = {}
for src, keys in by_src.items():
    vals = [fr_cur.get(k) for k in keys if fr_cur.get(k) is not None]
    if vals:
        majority[src] = Counter(vals).most_common(1)[0][0]
val_to_src = {}
for src, mv in majority.items():
    if mv not in val_to_src or len(by_src[src]) > len(by_src[val_to_src[mv]]):
        val_to_src[mv] = src
mis_keys = []
for k, src in en9.items():
    if not (src and src.strip()):
        continue
    v = fr_cur.get(k)
    if v is None or v == src:
        continue
    osrc = val_to_src.get(v)
    if osrc and osrc != src and not (tokens(src) & tokens(osrc)):
        mis_keys.append(k)
mis_keys = sorted(mis_keys)

# 2) load all source + FR versions
src_data = {v: load(p) for v, p in SRC.items()}
fr_data = {v: load(p) for v, p in FR.items()}

# 3) build rows
header = [
    "key",
    "EN@05_05",
    "EN@en4",
    "EN@en5",
    "EN@en7",
    "EN@en8",
    "EN@en9",
    "FR@05_05",
    "FR@en4",
    "FR@en5",
    "FR@en7",
    "FR@en8",
    "FR@en9",
    "FR@current",
    "FR_first_seen",
    "EN_changed?",
]
rows = []
for k in mis_keys:
    en_vals = [src_data[v].get(k, "") for v in VERSIONS]
    fr_vals = [fr_data[v].get(k, "") for v in VERSIONS]
    fr_cur_val = fr_cur.get(k, "")
    # first FR version where the current (wrong) value appeared
    first_seen = ""
    for v in VERSIONS:
        if fr_data[v].get(k, "") == fr_cur_val:
            first_seen = v
            break
    en_changed = "YES" if len(set(en_vals)) > 1 else "no"
    rows.append([k] + en_vals + fr_vals + [fr_cur_val, first_seen, en_changed])

# 4) write CSV
Path("doc").mkdir(exist_ok=True)
with open(
    "doc/2026_06_26_FR_Misalignment_History.csv", "w", encoding="utf-8", newline=""
) as f:
    w = csv.writer(f)
    w.writerow(header)
    w.writerows(rows)


# 5) write markdown (full table)
def esc(x):
    s = str(x).replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= 60 else s[:57] + "..."


with open("doc/2026_06_26_FR_Misalignment_History.md", "w", encoding="utf-8") as f:
    f.write(f"# Historique des traductions FR erronées ({len(rows)} clés)\n\n")
    f.write(
        "Colonnes : clé | Source EN à chaque version (05_05, en4, en5, en7, en8, en9) | "
    )
    f.write(
        "traduction FR à chaque version + current | FR_first_seen (1ère version où la valeur courante est apparue) | EN_changed? (la source a-t-elle changé).\n\n"
    )
    f.write("| " + " | ".join(header) + " |\n")
    f.write("|" + "|".join(["---"] * len(header)) + "|\n")
    for r in rows:
        f.write("| " + " | ".join(esc(c) for c in r) + " |\n")

print(f"{len(rows)} keys written to doc/2026_06_26_FR_Misalignment_History.csv and .md")
print()
print("=== EN_changed? distribution (confirms source-driven or not) ===")
print("  EN changed across versions:", dict(Counter(r[-1] for r in rows)))
print()
print("=== FR_first_seen distribution (when the current wrong value appeared) ===")
print("  ", dict(Counter(r[-2] for r in rows)))
print()
print("=== preview (first 12 rows, truncated) ===")
print("| " + " | ".join(header[:7]) + " | FR@en9 | FR_first_seen | EN_changed? |")
for r in rows[:12]:
    print("| " + " | ".join(esc(c) for c in (r[:7] + [r[12], r[-2], r[-1]])) + " |")
