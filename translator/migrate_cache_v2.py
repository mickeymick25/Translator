"""Migre le cache existant vers le format composite (key_id).

Lit les fichiers de traduction valides (FR, CZ, DE, IT, SK, AR) et reconstruit
le cache avec le nouveau format "en:lang:key_id:text".

L'ancien cache est sauvegarde dans .translation_cache.json.legacy_backup.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

base = Path("/Users/michaelboitin/Documents/02_Dev/COP_translations")
cache_path = base / "translator/output/.translation_cache.json"
source_path = base / "translator/source/2026_06_12_Import/en 7.json"
out_dir = base / "translator/output/2026_06_12_Export"

# Backup de l'ancien cache
backup_path = cache_path.with_suffix(".json.legacy_backup")
if not backup_path.exists():
    with cache_path.open(encoding="utf-8") as f:
        old_cache = json.load(f)
    with backup_path.open("w", encoding="utf-8") as f:
        json.dump(old_cache, f, ensure_ascii=False, indent=2)
    print(f"Backup ancien cache: {backup_path.name}")
else:
    print(f"Backup existe deja: {backup_path.name}")

# Charger source EN
with source_path.open(encoding="utf-8") as f:
    en = json.load(f)
print(
    f"Source EN: {len(en)} cles, {sum(1 for v in en.values() if v and v.strip())} non vides"
)

# Construire nouveau cache au format composite
new_entries = {}
for lang in ["fr", "cz", "de", "it", "sk", "ar"]:
    translation_file = out_dir / f"translation_en_{lang}.json"
    if not translation_file.exists():
        print(f"  SKIP {lang}: fichier absent")
        continue
    with translation_file.open(encoding="utf-8") as f:
        translations = json.load(f)

    count = 0
    for key_id, source_value in en.items():
        if not source_value or not source_value.strip():
            continue
        tr_value = translations.get(key_id, "")
        if not tr_value or not tr_value.strip():
            continue
        cache_key = f"en:{lang}:{key_id}:{source_value}"
        new_entries[cache_key] = tr_value
        count += 1
    print(f"  {lang}: {count} traductions ajoutees au format composite")

# Reconstruire le cache
new_cache = {
    "metadata": {
        "version": 2,
        "format": "composite",
        "key_format": "en:lang:key_id:text",
        "total_entries": len(new_entries),
        "last_migration": datetime.now().isoformat(),
        "source_file": str(source_path.relative_to(base)),
        "translation_files": [
            f"translator/output/2026_06_12_Export/translation_en_{lang}.json"
            for lang in ["fr", "cz", "de", "it", "sk", "ar"]
        ],
    },
    "entries": new_entries,
}

# Stats finales
prefixes = Counter()
for key in new_entries:
    parts = key.split(":", 3)
    if len(parts) >= 3:
        prefixes[(parts[0], parts[1])] += 1

print("\nRepartition finale:")
for (src, tgt), count in sorted(prefixes.items()):
    print(f"  {src}:{tgt}: {count}")
print(f"TOTAL: {len(new_entries)} entries")

# Sauvegarder
with cache_path.open("w", encoding="utf-8") as f:
    json.dump(new_cache, f, ensure_ascii=False, indent=2)

print(f"\nCache migre sauvegarde: {cache_path}")
print(f"Taille: {cache_path.stat().st_size} bytes")
