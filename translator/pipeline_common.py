"""Shared kernel du pipeline orchestré — helpers communs JSON + dropdown.

Contient les fonctions et le dataclass de base partagés entre les deux
pipelines (`pipeline_json.py` et `pipeline_dropdown.py`). Permet d'éviter
la duplication de l'orchestration (confirmations, bandaux, sauvegarde, I/O
JSON) tout en gardant chaque pipeline spécialisé (DDD — bounded contexts
séparés).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Langues cibles par défaut (toutes configurées sauf 'en' = source).
# Import ici pour être partagé par les deux pipelines.
from core.config import LANGUAGES

DEFAULT_TARGET_LANGS = [code for code in LANGUAGES if code != "en"]

# ─── Constantes nommées (Sprint 2 - tâche 21) ───────────────────────
# Centralise les magic numbers previously hardcoded dans les pipelines.
BANNER_WIDTH = 70
PREVIEW_LIMIT = 5
MAX_REPORT_ENTRIES = 120

# ─── Logger du pipeline (Sprint 2 - tâche 18) ───────────────────────
# Les pipelines utilisent `logger.info` pour les messages d'information ;
# `print` est conservé uniquement pour les rapports markdown affichés,
# les bandeaux `step_banner` et les confirmations interactives.
logger = logging.getLogger("pipeline")

# Répertoire de référence pour les fichiers partagés (source_typos.json).
TRANSLATOR_DIR = Path(__file__).resolve().parent
TYPOS_PATH = TRANSLATOR_DIR / "source_typos.json"

# ─── Patterns de placeholders partagés (C14) ────────────────────────
# Liste des patterns bruts (utilisée par validate_translations) + forme
# compilée combinée (utilisée par compare_sources). Centraliser évite la
# divergence entre les deux modules.
PLACEHOLDER_PATTERNS: list[str] = [
    r"%[sd]",  # %s, %d
    r"\{[^}]+\}",  # {name}, {count}, {0}, {1}, ICU
    r"<[^>]+>",  # <b>, </b>, <br/>
    r"\\n",  # \n littéral
]
PLACEHOLDER_RE = re.compile("|".join(PLACEHOLDER_PATTERNS))


# ─── Context manager : override du singleton Config (C2) ─────────────


@contextmanager
def override_config(
    *,
    source_file: str,
    output_dir: str,
    provider: str,
    no_cache: bool = False,
) -> Iterator[None]:
    """Injecte temporairement une `Config` dans le singleton `core.config`.

    Sauvegarde l'ancienne valeur de `config_module._config`, installe une
    nouvelle `Config` configurée pour l'exécution d'une étape du pipeline
    (typiquement `step7_translate`), puis restaure l'ancienne valeur dans un
    `finally` — y compris si l'étape lève une exception. Évite la pollution
    du singleton entre appels successifs (tests, usage programmatique).
    """
    import core.config as config_module
    from core.config import Config

    prev = config_module._config
    config = Config(
        SOURCE_LANG="en",
        SOURCE_FILE=source_file,
        OUTPUT_DIR=output_dir,
        TRANSLATION_PROVIDER=provider,
        dry_run=False,
    )
    if no_cache:
        config.TRANSLATION_CACHE = "false"
    config_module._config = config
    try:
        yield
    finally:
        config_module._config = prev


# ─── Contexte de base ────────────────────────────────────────────────


@dataclass
class BasePipelineContext:
    """Champs communs à tous les pipelines (JSON, dropdown, …).

    Chaque pipeline spécialisé hérite et ajoute ses propres champs
    (résultats d'étapes, données spécifiques au format).
    """

    # Sources
    new_source: Path | None = None
    prev_source: Path | None = None

    # Paramètres
    languages: list[str] = field(default_factory=lambda: list(DEFAULT_TARGET_LANGS))
    provider: str = "hybride"  # google | ollama | hybride
    dry_run: bool = False
    interactive: bool = True
    report_path: Path | None = None


# ─── Utilitaires interactifs ─────────────────────────────────────────


def confirm(ctx: BasePipelineContext, prompt: str, default: bool = False) -> bool:
    """Demande une confirmation oui/non.

    En mode non-interactif (--yes / --dry-run), retourne `default` sans
    demander.
    """
    if not ctx.interactive:
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except EOFError:
        return default
    if answer in ("y", "yes", "o", "oui"):
        return True
    if answer in ("n", "no", "non"):
        return False
    return default


def step_banner(num: int, title: str) -> None:
    """Affiche un bandeau d'étape standardisé."""
    print("\n" + section_separator("═"))
    print(f"  ÉTAPE {num} — {title}")
    print(section_separator("═"))


# ─── Coquilles source (Sprint 2 - tâche 16 : load_typos unifié) ─────


def load_typos(path: Path | None = None, scope: str = "both") -> list[dict]:
    """Charge le dictionnaire des coquilles connues, optionnellement filtré.

    Lit `source_typos.json` depuis `TRANSLATOR_DIR` (ou un chemin explicite)
    et retourne les entrées dont le `scope` correspond.

    Args:
        path: Chemin du fichier `source_typos.json`. Si `None`, utilise
            `pipeline_common.TYPOS_PATH` (TRANSLATOR_DIR / source_typos.json).
        scope: Filtre de portée — "both" (défaut) retourne toutes les
            entrées ; "json" retourne les entrées dont le scope est
            "json" ou "both" ; "dropdown" retourne celles dont le scope
            est "dropdown" ou "both". Les entrées sans champ `scope`
            sont considérées comme "both".

    Returns:
        Liste des entrées typo ({typo, correction, ...}). Liste vide si
        le fichier est absent ou ne contient pas la clé `typos`.
    """
    if path is None:
        path = TYPOS_PATH
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    typos = data.get("typos", [])
    if scope == "both":
        return typos
    return [e for e in typos if e.get("scope", "both") in (scope, "both")]


# ─── Sauvegarde ──────────────────────────────────────────────────────


def backup_translation_file(path: Path) -> Path:
    """Copie un fichier de traduction en `<name>.bak_pre_pipeline`.

    Écrase un backup existant (cas d'un re-run du pipeline).
    Retourne le chemin du backup.
    """
    backup = path.with_suffix(path.suffix + ".bak_pre_pipeline")
    shutil.copy2(path, backup)
    return backup


# ─── I/O JSON utilitaires ────────────────────────────────────────────


def json_load(path: Path) -> dict:
    """Charge un fichier JSON en dict.

    Sprint 4 - tâche 5 : version de référence centralisée. Les autres
    modules (`compare_sources`, `analyze_translation_gap`, `validate_translations`)
    importent cette fonction (avec fallback pour usage standalone hors
    `translator/`).

    Raises:
        ValueError: si le JSON n'est pas un objet dict (C13).
    """
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f"Source {path} n'est pas un objet JSON (type: {type(data).__name__})"
        )
    return data


def json_write(path: Path, data: dict) -> None:
    """Écrit un dict dans un fichier JSON (indent=2, ensure_ascii=False)."""
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def short_repr(v) -> str:
    """Représentation courte d'une valeur pour l'affichage interactif."""
    return truncate(v, length=80)


# ─── Helpers partagés (Sprint 4 - polish) ─────────────────────────────


def parse_languages_arg(s: str | None) -> list[str]:
    """Parse une chaîne "fr,de" en liste ["fr", "de"].

    Args:
        s: Chaîne CSV (ex : "fr,de") ou `None`.

    Returns:
        Liste des codes non vides, sans espaces autour. Liste vide si `s`
        est `None` ou vide.
    """
    if not s:
        return []
    return [lg.strip() for lg in s.split(",") if lg.strip()]


def truncate(v, length: int = 100) -> str:
    """Tronque une valeur à `length` caractères, en ajoutant "..." si coupée.

    Généralisation paramétrable de `short_repr` (80) / `compare_sources.short`
    (120) / `analyze_translation_gap.short` (100). Les newlines sont replacées
    par des espaces pour préserver l'affichage sur une ligne.
    """
    s = str(v).replace("\n", " ")
    if len(s) > length:
        return s[: length - 3] + "..."
    return s


def write_report(content: str, path: Path) -> Path:
    """Écrit un rapport markdown sur disque et retourne le chemin.

    Crée les répertoires parents si nécessaire. Utilisé par `step5` (rapport
    d'analyse) et `step11` (rapport final) des deux pipelines.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def section_separator(char: str = "─", width: int = BANNER_WIDTH) -> str:
    """Retourne une chaîne de séparation de largeur `width` (défaut BANNER_WIDTH).

    Utilisé pour les bandeaux de [ÉTAPE CLÉ] intermédiaires dans les pipelines.
    """
    return char * width
