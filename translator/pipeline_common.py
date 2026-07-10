"""Shared kernel du pipeline orchestré — helpers communs JSON + dropdown.

Contient les fonctions et le dataclass de base partagés entre les deux
pipelines (`pipeline_json.py` et `pipeline_dropdown.py`). Permet d'éviter
la duplication de l'orchestration (confirmations, bandaux, sauvegarde, I/O
JSON) tout en gardant chaque pipeline spécialisé (DDD — bounded contexts
séparés).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Langues cibles par défaut (toutes configurées sauf 'en' = source).
# Import ici pour être partagé par les deux pipelines.
from core.config import LANGUAGES

DEFAULT_TARGET_LANGS = [code for code in LANGUAGES if code != "en"]


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
    print("\n" + "═" * 70)
    print(f"  ÉTAPE {num} — {title}")
    print("═" * 70)


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
    """Charge un fichier JSON en dict."""
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def json_write(path: Path, data: dict) -> None:
    """Écrit un dict dans un fichier JSON (indent=2, ensure_ascii=False)."""
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def short_repr(v) -> str:
    """Représentation courte d'une valeur pour l'affichage interactif."""
    s = str(v).replace("\n", " ")
    return s[:80] + "..." if len(s) > 80 else s
