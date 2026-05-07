"""
Configuration module for the translation service.
Centralizes all environment variables and configuration settings.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

# Mode constants
MODE_TRANSLATE_JSON = "translate-json"
MODE_TRANSLATE_DROPDOWNS = "translate-dropdowns"
MODE_ANALYZE = "analyze"

LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {"name": "Anglais", "code": "EN", "target": "en", "source_col": "origin"},
    "fr": {"name": "Français", "code": "FR", "target": "fr", "source_col": "french"},
    "cz": {"name": "Tchèque", "code": "CZ", "target": "cs", "source_col": "origin"},
    "sk": {"name": "Slovaque", "code": "SK", "target": "sk", "source_col": "origin"},
    "de": {"name": "Allemand", "code": "DE", "target": "de", "source_col": "origin"},
    "it": {"name": "Italien", "code": "IT", "target": "it", "source_col": "origin"},
    "ar": {"name": "Arabe", "code": "AR", "target": "ar", "source_col": "origin"},
}


def _is_docker() -> bool:
    """
    Detect whether the service is running inside a Docker container.

    Checks for the presence of /.dockerenv (Docker) or /run/.containerenv (Podman).

    Returns:
        True if running inside a container, False otherwise.
    """
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")


def _default_dir(env_var: str, docker_default: str, local_default: str) -> str:
    """
    Return a directory path adapted to the execution environment.

    In Docker, returns the env var value or docker_default.
    Outside Docker, returns the env var value or local_default.

    Args:
        env_var: Name of the environment variable to check.
        docker_default: Default path when running in Docker.
        local_default: Default path when running locally.

    Returns:
        The resolved directory path.
    """
    if _is_docker():
        return os.environ.get(env_var, docker_default)
    return os.environ.get(env_var, local_default)


def _default_output_dir() -> str:
    """Return the default output directory, adapted to the execution environment."""
    return _default_dir("OUTPUT_DIR", "/app/output", str(Path.cwd() / "output"))


def _default_source_dir() -> str:
    """Return the default source directory, adapted to the execution environment."""
    return _default_dir("SOURCE_DIR", "/app/source", str(Path.cwd() / "source"))


def _default_excel_dir() -> str:
    """Return the default excel directory, adapted to the execution environment."""
    return _default_dir("EXCEL_DIR", "/app/excel", str(Path.cwd() / "excel"))


def _default_doc_dir() -> str:
    """Return the default doc directory, adapted to the execution environment."""
    return _default_dir("DOC_DIR", "/app/doc", str(Path.cwd() / "Doc"))


def _find_latest_import_folder(source_dir: str) -> str | None:
    """
    Find the most recent YYYY_MM_DD_Import folder in source_dir.

    Scans source_dir for subfolders matching the pattern 'YYYY_MM_DD_Import',
    sorts them by date descending, and returns the most recent folder name.
    Returns None if no import folder is found.

    Args:
        source_dir: Path to the source directory to scan.

    Returns:
        The most recent import folder name (e.g. '2026_04_21_Import') or None.
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        return None

    import_folder_pattern = re.compile(r"^(\d{4}_\d{2}_\d{2})_Import$")

    import_folders: list[str] = []
    for item in sorted(source_path.iterdir()):
        if item.is_dir():
            match = import_folder_pattern.match(item.name)
            if match:
                import_folders.append(item.name)

    if not import_folders:
        return None

    # Sort by date string descending -> most recent first
    import_folders.sort(reverse=True)
    return import_folders[0]


def _find_source_file_in_import(import_folder: str, source_lang: str) -> str | None:
    """
    Find the source translation file inside an import folder.

    Looks for a file named '{date_prefix}_translation_{source_lang}_{source_lang}.json'
    inside the given import folder.

    Args:
        import_folder: Full path to the import folder (e.g. '/app/source/2026_04_21_Import').
        source_lang: Source language code (e.g. 'en').

    Returns:
        Full path to the source file, or None if not found.
    """
    folder_path = Path(import_folder)
    if not folder_path.exists():
        return None

    # Extract date prefix from folder name (e.g. '2026_04_21_Import' -> '2026_04_21')
    date_prefix = folder_path.name.split("_Import")[0]

    filename = f"{date_prefix}_translation_{source_lang}_{source_lang}.json"
    file_path = folder_path / filename

    if file_path.exists():
        return str(file_path)

    return None


@dataclass
class Config:
    """
    Central configuration for the translation service.
    All values are loaded from environment variables with sensible defaults.
    """

    # Operating mode: translate-json, translate-dropdowns, analyze
    MODE: str = field(default_factory=lambda: os.environ.get("MODE", "translate-json"))

    # Source and target languages
    SOURCE_LANG: str = field(
        default_factory=lambda: os.environ.get("SOURCE_LANG", "en")
    )
    TARGET_LANG: str = field(
        default_factory=lambda: os.environ.get("TARGET_LANG", "cs")
    )

    # Source file path (empty means auto-detect latest import)
    SOURCE_FILE: str = field(default_factory=lambda: os.environ.get("SOURCE_FILE", ""))

    # Directory paths (environment-aware: Docker vs local)
    OUTPUT_DIR: str = field(default_factory=_default_output_dir)
    EXCEL_DIR: str = field(default_factory=_default_excel_dir)
    DOC_DIR: str = field(default_factory=_default_doc_dir)
    SOURCE_DIR: str = field(default_factory=_default_source_dir)

    # Batch translation languages (comma-separated)
    BATCH_LANGS: str = field(
        default_factory=lambda: os.environ.get("BATCH_LANGS", "en,fr,cz,sk,de,it,ar")
    )

    # Output format: json, xlsx, or auto
    OUTPUT_FORMAT: str = field(
        default_factory=lambda: os.environ.get("OUTPUT_FORMAT", "auto")
    )

    @property
    def batch_langs_list(self) -> list[str]:
        """Parse BATCH_LANGS into a list of language codes."""
        return [lang.strip() for lang in self.BATCH_LANGS.split(",") if lang.strip()]

    def get_output_path(self, suffix: str = "") -> str:
        """Generate an output file path based on source and target languages."""
        filename = f"translation_{self.SOURCE_LANG}_{self.TARGET_LANG}{suffix}.json"
        return str(Path(self.OUTPUT_DIR) / filename)

    def get_source_path(self) -> str:
        """
        Get the source file path, auto-detecting the latest import if needed.

        Priority:
          1. SOURCE_FILE environment variable (explicit path)
          2. Latest YYYY_MM_DD_Import folder in SOURCE_DIR
          3. Fallback: {SOURCE_DIR}/translation_{SOURCE_LANG}_{SOURCE_LANG}.json

        Raises:
            FileNotFoundError: If no source file can be found.
        """
        # Explicit path provided
        if self.SOURCE_FILE:
            return self.SOURCE_FILE

        # Auto-detect: find latest import folder and its source file
        latest_import = _find_latest_import_folder(self.SOURCE_DIR)
        if latest_import:
            import_folder_path = str(Path(self.SOURCE_DIR) / latest_import)
            source_file = _find_source_file_in_import(
                import_folder_path, self.SOURCE_LANG
            )
            if source_file:
                return source_file

        # Fallback: legacy flat path
        fallback = str(
            Path(self.SOURCE_DIR)
            / f"translation_{self.SOURCE_LANG}_{self.SOURCE_LANG}.json"
        )
        if Path(fallback).exists():
            return fallback

        raise FileNotFoundError(
            f"No source file found for lang '{self.SOURCE_LANG}' "
            f"in '{self.SOURCE_DIR}' (no YYYY_MM_DD_Import folder found)."
        )


# Global config instance (lazy-loaded)
_config: Config | None = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    Creates the instance on first call (lazy initialization).
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
