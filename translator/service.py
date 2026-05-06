#!/usr/bin/env python3
"""
Service de traduction générique COP.

Point d'entrée unique piloté par la variable d'environnement MODE.

Modes disponibles :
    - translate-json   : Traduit un fichier JSON plat (EN → TARGET_LANG)
    - translate-dropdowns : Génère les traductions multi-langues des dropdowns (XLSX/JSON)
    - analyze          : Analyse la structure d'un fichier XLSX source

Variables d'environnement :
    MODE            : Mode d'opération (défaut: translate-json)
    SOURCE_LANG     : Langue source (défaut: en)
    TARGET_LANG     : Langue cible (défaut: cs)
    SOURCE_FILE     : Chemin vers le fichier source (défaut: auto selon le mode)
    OUTPUT_DIR      : Répertoire de sortie (défaut: /app/output)
    EXCEL_DIR       : Répertoire des fichiers Excel (défaut: /app/excel)
    DOC_DIR         : Répertoire de documentation (défaut: /app/doc)
    SOURCE_DIR      : Répertoire des fichiers source JSON (défaut: /app/source)
    BATCH_LANGS     : Langues à générer en batch, séparées par virgules
                      (défaut: en,fr,cz,sk,de,it,ar)
    OUTPUT_FORMAT   : Format de sortie — json, xlsx, ou auto (défaut: auto)
"""

import logging
import os
import sys
from pathlib import Path

from core.config import (
    MODE_ANALYZE,
    MODE_TRANSLATE_DROPDOWNS,
    MODE_TRANSLATE_JSON,
    get_config,
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("service")


# Mapping mode → module à importer
_MODES = {
    MODE_TRANSLATE_JSON: ("modes.mode_translate_json", "run"),
    MODE_TRANSLATE_DROPDOWNS: ("modes.mode_translate_dropdowns", "run"),
    MODE_ANALYZE: ("modes.mode_analyze", "run"),
}


def resolve_mode() -> str:
    """Lit et valide la variable d'environnement MODE."""
    config = get_config()
    mode = config.MODE

    if mode not in _MODES:
        supported = ", ".join(sorted(_MODES.keys()))
        logger.error(f"Mode inconnu: '{mode}'. Modes disponibles : {supported}")
        sys.exit(1)

    return mode


def run_mode(mode: str) -> None:
    """Charge et exécute le module correspondant au mode demandé."""
    module_name, function_name = _MODES[mode]

    try:
        module = __import__(module_name, fromlist=[function_name])
    except ImportError as e:
        logger.error(f"Impossible d'importer le module '{module_name}' : {e}")
        sys.exit(1)

    run_func = getattr(module, function_name, None)
    if not callable(run_func):
        logger.error(
            f"Le module '{module_name}' n'expose pas de fonction '{function_name}'."
        )
        sys.exit(1)

    logger.info(f"Démarrage du mode : {mode}")
    run_func()


def main() -> None:
    """Point d'entrée principal du service."""
    logger.info("=" * 60)
    logger.info("COP Generic Translation Service")
    logger.info("=" * 60)

    # Lecture et validation du mode
    mode = resolve_mode()
    config = get_config()

    logger.info(f"  Mode         : {mode}")
    logger.info(f"  Source lang  : {config.SOURCE_LANG}")
    logger.info(f"  Target lang  : {config.TARGET_LANG}")
    logger.info(f"  Output dir   : {config.OUTPUT_DIR}")
    logger.info(f"  Source file  : {config.SOURCE_FILE or '(auto)'}")

    if mode == MODE_TRANSLATE_DROPDOWNS:
        logger.info(f"  Batch langs  : {config.BATCH_LANGS}")
        logger.info(f"  Output format: {config.OUTPUT_FORMAT}")

    logger.info("-" * 60)

    # Exécution du mode
    try:
        run_mode(mode)
    except KeyboardInterrupt:
        logger.warning("Interruption clavier — arrêt propre.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Erreur fatale : {e}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Service terminé avec succès.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
