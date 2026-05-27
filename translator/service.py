#!/usr/bin/env python3
"""
Service de traduction générique COP.

Point d'entrée principal avec support CLI (argparse) et variables d'environnement.

Modes disponibles :
    - translate-json   : Traduit un fichier JSON plat (EN → TARGET_LANG)
    - translate-dropdowns : Génère les traductions multi-langues des dropdowns (XLSX/JSON)
    - analyze          : Analyse la structure d'un fichier XLSX source

Utilisation CLI :
    python service.py translate-json -s en -t fr -i file.json
    python service.py translate-dropdowns --input dropdown.xlsx --format json
    python service.py analyze --input data.xlsx
    python service.py --dry-run translate-json -s en -t fr
    python service.py -v translate-json -s en -t fr
    python service.py --version

Priorité des configurations :
    1. Arguments CLI (priorité maximale)
    2. Variables d'environnement
    3. Valeurs par défaut du Config

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
    TRANSLATION_PROVIDER : Provider de traduction — google ou deepl (défaut: google)
    DEEPL_API_KEY   : Clé API DeepL (requise pour le provider deepl)
    DEEPL_USE_FREE_API  : Utiliser l'API gratuite DeepL (défaut: true)
    TRANSLATION_FALLBACK : Activer le fallback automatique (défaut: false)
"""

import argparse
import logging
import os
import sys

from core.config import (
    MODE_ANALYZE,
    MODE_TRANSLATE_DROPDOWNS,
    MODE_TRANSLATE_JSON,
    Config,
    get_config,
)

__version__ = "2.0.0"

# Configuration du logging (will be adjusted based on --verbose/--quiet)
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


def _add_provider_args(parser: argparse.ArgumentParser) -> None:
    """Add provider-related arguments to a subcommand parser (IMP2-T001, IMP3-T004).

    These flags are shared across all subcommands since the translation
    provider is a global concern, not specific to any mode.

    Args:
        parser: The argparse subparser to add provider flags to.
    """
    parser.add_argument(
        "--provider",
        choices=["google", "deepl", "ollama"],
        default=None,
        help="Provider de traduction: google, deepl ou ollama (défaut: google)",
    )
    parser.add_argument(
        "--deepl-api-key",
        default=None,
        help="Clé API DeepL (requise pour le provider deepl)",
    )
    parser.add_argument(
        "--deepl-use-free-api",
        action="store_true",
        default=None,
        help="Utiliser l'API gratuite DeepL (défaut: true)",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        default=None,
        help="Activer le fallback automatique entre providers (défaut: false)",
    )
    # Ollama-specific flags (IMP3-T004)
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="URL du serveur Ollama (défaut: http://localhost:11434)",
    )
    parser.add_argument(
        "--ollama-model",
        default=None,
        help="Modèle Ollama à utiliser (défaut: minimax-m2.7:cloud)",
    )
    parser.add_argument(
        "--ollama-chunk-size",
        type=int,
        default=None,
        help="Taille des chunks Ollama (défaut: 50)",
    )
    parser.add_argument(
        "--ollama-temperature",
        type=float,
        default=None,
        help="Température du modèle Ollama (défaut: 0)",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=int,
        default=None,
        help="Timeout par chunk en secondes (défaut: 300)",
    )
    parser.add_argument(
        "--ollama-max-retries",
        type=int,
        default=None,
        help="Max retries par chunk Ollama (défaut: 2)",
    )


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the CLI interface.

    Supports three subcommands (translate-json, translate-dropdowns, analyze)
    with global flags (--verbose, --quiet, --dry-run, --version).

    Returns:
        argparse.ArgumentParser configured with all CLI arguments.
    """
    parser = argparse.ArgumentParser(
        prog="service.py",
        description="Service de traduction générique COP",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Mode verbeux (niveau DEBUG)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Mode silencieux (niveau WARNING)",
    )
    subparsers = parser.add_subparsers(dest="mode", help="Mode d'opération")

    # ─── translate-json ─────────────────────────────────────────────
    p_json = subparsers.add_parser(
        "translate-json", help="Traduire un fichier JSON plat"
    )
    p_json.add_argument(
        "-s",
        "--source-lang",
        default=None,
        help="Langue source (défaut: en)",
    )
    p_json.add_argument(
        "-t",
        "--target-lang",
        default=None,
        help="Langue cible (défaut: cs)",
    )
    p_json.add_argument(
        "-i",
        "--input",
        default=None,
        help="Fichier source JSON",
    )
    p_json.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire de sortie",
    )
    p_json.add_argument(
        "--batch-langs",
        default=None,
        help="Langues batch (séparées par virgules)",
    )
    p_json.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simuler sans appels API de traduction",
    )
    _add_provider_args(p_json)

    # ─── translate-dropdowns ────────────────────────────────────────
    p_dd = subparsers.add_parser(
        "translate-dropdowns", help="Générer traductions dropdowns multi-langues"
    )
    p_dd.add_argument(
        "-s",
        "--source-lang",
        default=None,
        help="Langue source (défaut: en)",
    )
    p_dd.add_argument(
        "-i",
        "--input",
        default=None,
        help="Fichier source XLSX ou JSON",
    )
    p_dd.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire de sortie",
    )
    p_dd.add_argument(
        "--batch-langs",
        default=None,
        help="Langues batch (séparées par virgules)",
    )
    p_dd.add_argument(
        "--format",
        choices=["json", "xlsx", "auto"],
        default=None,
        help="Format de sortie (json, xlsx, auto)",
    )
    p_dd.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simuler sans appels API de traduction",
    )
    _add_provider_args(p_dd)

    # ─── analyze ─────────────────────────────────────────────────────
    p_analyze = subparsers.add_parser("analyze", help="Analyser un fichier XLSX")
    p_analyze.add_argument(
        "-i",
        "--input",
        default=None,
        help="Fichier XLSX à analyser",
    )
    p_analyze.add_argument(
        "--output-dir",
        default=None,
        help="Répertoire de sortie du rapport",
    )
    p_analyze.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simuler sans appels API de traduction",
    )
    _add_provider_args(p_analyze)

    return parser


def build_config_from_args(args: argparse.Namespace) -> Config:
    """
    Build a Config instance from parsed CLI arguments.

    Resolution priority: CLI args > environment variables > Config defaults.
    Any CLI argument that is None (not provided) falls through to the
    environment variable or Config default.

    Args:
        args: Parsed argparse Namespace.

    Returns:
        A Config instance with CLI overrides applied.
    """
    # Build kwargs for Config — only override if CLI arg was explicitly provided
    kwargs: dict = {}

    # Mode from subcommand
    if args.mode is not None:
        kwargs["MODE"] = args.mode

    # Global flags
    kwargs["dry_run"] = getattr(args, "dry_run", False)
    kwargs["verbose"] = getattr(args, "verbose", False)
    kwargs["quiet"] = getattr(args, "quiet", False)

    # Per-field overrides: CLI > env > default
    # If CLI arg is None, Config's default_factory will handle env var lookup
    if getattr(args, "source_lang", None) is not None:
        kwargs["SOURCE_LANG"] = args.source_lang
    if getattr(args, "target_lang", None) is not None:
        kwargs["TARGET_LANG"] = args.target_lang
    if getattr(args, "input", None) is not None:
        kwargs["SOURCE_FILE"] = args.input
    if getattr(args, "output_dir", None) is not None:
        kwargs["OUTPUT_DIR"] = args.output_dir
    if getattr(args, "batch_langs", None) is not None:
        kwargs["BATCH_LANGS"] = args.batch_langs
    if getattr(args, "format", None) is not None:
        kwargs["OUTPUT_FORMAT"] = args.format

    # IMP2-T001: Provider flags — CLI > env > default
    if getattr(args, "provider", None) is not None:
        kwargs["TRANSLATION_PROVIDER"] = args.provider
    if getattr(args, "deepl_api_key", None) is not None:
        kwargs["DEEPL_API_KEY"] = args.deepl_api_key
    if getattr(args, "deepl_use_free_api", None) is not None:
        kwargs["DEEPL_USE_FREE_API"] = "true" if args.deepl_use_free_api else "false"
    if getattr(args, "fallback", None) is not None:
        kwargs["TRANSLATION_FALLBACK"] = "true" if args.fallback else "false"

    # IMP3-T004: Ollama flags — CLI > env > default
    if getattr(args, "ollama_url", None) is not None:
        kwargs["OLLAMA_URL"] = args.ollama_url
    if getattr(args, "ollama_model", None) is not None:
        kwargs["OLLAMA_MODEL"] = args.ollama_model
    if getattr(args, "ollama_chunk_size", None) is not None:
        kwargs["OLLAMA_CHUNK_SIZE"] = str(args.ollama_chunk_size)
    if getattr(args, "ollama_temperature", None) is not None:
        kwargs["OLLAMA_TEMPERATURE"] = str(args.ollama_temperature)
    if getattr(args, "ollama_timeout", None) is not None:
        kwargs["OLLAMA_TIMEOUT"] = str(args.ollama_timeout)
    if getattr(args, "ollama_max_retries", None) is not None:
        kwargs["OLLAMA_MAX_RETRIES"] = str(args.ollama_max_retries)

    # Reset global config to force re-creation with new values
    import core.config as config_module

    config_module._config = None

    config = Config(**kwargs)

    # Set as global singleton so get_config() returns it
    config_module._config = config

    return config


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


def configure_logging(verbose: bool, quiet: bool) -> None:
    """
    Adjust logging level based on --verbose and --quiet flags.

    Args:
        verbose: If True, set logging to DEBUG level.
        quiet: If True, set logging to WARNING level.
    """
    if verbose and quiet:
        logger.warning("Both --verbose and --quiet specified; using --verbose.")

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.WARNING)
    else:
        logging.getLogger().setLevel(logging.INFO)


def main() -> None:
    """Point d'entrée principal du service."""
    parser = build_parser()
    args = parser.parse_args()

    # If no subcommand provided, try env var MODE or print help
    if args.mode is None:
        # Check if MODE env var is set for backward compatibility
        env_mode = os.environ.get("MODE")
        if env_mode:
            args.mode = env_mode
        else:
            parser.print_help()
            sys.exit(1)

    # Build config from CLI args (with CLI > env > default resolution)
    config = build_config_from_args(args)

    # Configure logging based on flags
    configure_logging(verbose=config.verbose, quiet=config.quiet)

    logger.info("=" * 60)
    logger.info("COP Generic Translation Service v%s", __version__)
    logger.info("=" * 60)

    # Lecture et validation du mode
    mode = config.MODE

    if mode not in _MODES:
        supported = ", ".join(sorted(_MODES.keys()))
        logger.error(f"Mode inconnu: '{mode}'. Modes disponibles : {supported}")
        sys.exit(1)

    logger.info(f"  Mode         : {mode}")
    logger.info(f"  Source lang  : {config.SOURCE_LANG}")
    logger.info(f"  Target lang  : {config.TARGET_LANG}")
    logger.info(f"  Output dir   : {config.OUTPUT_DIR}")
    logger.info(f"  Source file  : {config.SOURCE_FILE or '(auto)'}")

    if config.dry_run:
        logger.info("  Dry run      : YES (no API calls will be made)")

    # IMP2-T001: Provider info in startup banner
    logger.info(f"  Provider     : {config.TRANSLATION_PROVIDER}")
    if config.TRANSLATION_PROVIDER.lower() == "deepl" or config.DEEPL_API_KEY:
        logger.info(
            f"  DeepL API    : {'Free' if config.deepl_use_free_api_enabled else 'Pro'}"
        )
    if config.TRANSLATION_PROVIDER.lower() == "ollama":
        logger.info(f"  Ollama URL   : {config.OLLAMA_URL}")
        logger.info(f"  Ollama Model : {config.OLLAMA_MODEL}")
        logger.info(f"  Ollama Chunk : {config.ollama_chunk_size_int}")
        logger.info(f"  Ollama Temp  : {config.ollama_temperature_float}")
        logger.info(f"  Ollama Retry : {config.ollama_max_retries_int}")
    logger.info(
        f"  Fallback     : {'Enabled' if config.fallback_enabled else 'Disabled'}"
    )

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
