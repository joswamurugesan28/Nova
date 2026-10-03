"""Configuration loading for NOVA.

Reads TOML configuration with the standard library ``tomllib`` (no
third-party dependency). The config path is resolved in this order:

1. explicit ``path`` argument
2. ``NOVA_CONFIG`` environment variable
3. ``<project root>/config/nova.toml``
4. built-in defaults (if no file exists)

All relative paths stored in the configuration are resolved against the
project root (the directory containing ``pyproject.toml``).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

#: Project root: ``nova/config.py`` -> ``nova/`` -> project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "nova.toml"

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(Exception):
    """Raised when the configuration file cannot be loaded or is invalid."""


@dataclass(frozen=True)
class LoggingSettings:
    level: str = "INFO"
    file: str = "logs/nova.log"
    max_bytes: int = 1_048_576
    backup_count: int = 3

    @property
    def path(self) -> Path:
        return resolve_path(self.file)


@dataclass(frozen=True)
class PersonalitySettings:
    name: str = "NOVA"
    style: str = "helpful, concise, honest about limitations"
    system_prompt: str = (
        "You are NOVA, a modular personal AI assistant. "
        "Be concise and honest about what you can and cannot do."
    )


@dataclass(frozen=True)
class LlamaServerSettings:
    """Connection/behavior settings for the llama.cpp llama-server backend.

    ``enabled = false`` keeps M1-A safe: the backend interface exists but
    NOVA will not route to it until a llama-server is actually running
    and the user opts in.
    """

    enabled: bool = False
    base_url: str = "http://127.0.0.1:8080"
    model: str = "qwen3-4b"
    timeout_seconds: float = 120.0
    health_timeout_seconds: float = 2.0
    context_size: int = 4096
    temperature: float = 0.7
    max_tokens: int = 512


@dataclass(frozen=True)
class ModelSettings:
    """Which backend serves each logical task.

    Per-task values select a backend implementation: ``"stub"`` (mock,
    the safe default) or ``"llama-server"`` (M1-A). Unknown values fall
    back to the stub with a warning in ``nova.models.factory``.
    """

    brain: str = "stub"
    vision: str = "stub"
    stt: str = "stub"
    tts: str = "stub"
    artifact: str = "stub"
    llama_server: LlamaServerSettings = field(default_factory=LlamaServerSettings)


@dataclass(frozen=True)
class ArtifactSettings:
    workspace_dir: str = "nova/artifacts/workspace"
    templates_dir: str = "nova/artifacts/templates"
    output_dir: str = "nova/artifacts/output"
    max_file_mb: int = 50

    @property
    def workspace_path(self) -> Path:
        return resolve_path(self.workspace_dir)

    @property
    def templates_path(self) -> Path:
        return resolve_path(self.templates_dir)

    @property
    def output_path(self) -> Path:
        return resolve_path(self.output_dir)


@dataclass(frozen=True)
class Settings:
    app_name: str = "NOVA"
    app_version: str = "0.1.0"
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    personality: PersonalitySettings = field(default_factory=PersonalitySettings)
    models: ModelSettings = field(default_factory=ModelSettings)
    artifacts: ArtifactSettings = field(default_factory=ArtifactSettings)
    config_path: Path | None = None
    project_root: Path = PROJECT_ROOT


def resolve_path(path: str | Path) -> Path:
    """Resolve a possibly-relative configured path against the project root."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def _section(data: dict, key: str) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"config section [{key}] must be a table, got {type(value).__name__}")
    return value


def _build_settings(data: dict, config_path: Path | None) -> Settings:
    app = _section(data, "app")
    log = _section(data, "logging")
    pers = _section(data, "personality")
    models = _section(data, "models")
    art = _section(data, "artifacts")

    ls = models.get("llama_server", {})
    if not isinstance(ls, dict):
        raise ConfigError(
            "config section [models.llama_server] must be a table, "
            f"got {type(ls).__name__}"
        )

    level = str(log.get("level", "INFO")).upper()
    if level not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"invalid log level {level!r}; expected one of {', '.join(VALID_LOG_LEVELS)}"
        )

    return Settings(
        app_name=str(app.get("name", "NOVA")),
        app_version=str(app.get("version", "0.1.0")),
        logging=LoggingSettings(
            level=level,
            file=str(log.get("file", "logs/nova.log")),
            max_bytes=int(log.get("max_bytes", 1_048_576)),
            backup_count=int(log.get("backup_count", 3)),
        ),
        personality=PersonalitySettings(
            name=str(pers.get("name", "NOVA")),
            style=str(pers.get("style", "helpful, concise, honest about limitations")),
            system_prompt=str(
                pers.get(
                    "system_prompt",
                    "You are NOVA, a modular personal AI assistant. "
                    "Be concise and honest about what you can and cannot do.",
                )
            ),
        ),
        models=ModelSettings(
            brain=str(models.get("brain", "stub")),
            vision=str(models.get("vision", "stub")),
            stt=str(models.get("stt", "stub")),
            tts=str(models.get("tts", "stub")),
            artifact=str(models.get("artifact", "stub")),
            llama_server=LlamaServerSettings(
                enabled=bool(ls.get("enabled", False)),
                base_url=str(ls.get("base_url", "http://127.0.0.1:8080")).rstrip("/"),
                model=str(ls.get("model", "qwen3-4b")),
                timeout_seconds=float(ls.get("timeout_seconds", 120)),
                health_timeout_seconds=float(ls.get("health_timeout_seconds", 2)),
                context_size=int(ls.get("context_size", 4096)),
                temperature=float(ls.get("temperature", 0.7)),
                max_tokens=int(ls.get("max_tokens", 512)),
            ),
        ),
        artifacts=ArtifactSettings(
            workspace_dir=str(art.get("workspace_dir", "nova/artifacts/workspace")),
            templates_dir=str(art.get("templates_dir", "nova/artifacts/templates")),
            output_dir=str(art.get("output_dir", "nova/artifacts/output")),
            max_file_mb=int(art.get("max_file_mb", 50)),
        ),
        config_path=config_path,
    )


def load_settings(path: str | Path | None = None) -> Settings:
    """Load settings from TOML. Falls back to built-in defaults if absent.

    Raises:
        ConfigError: if the file exists but cannot be parsed or is invalid.
    """
    if path is not None:
        config_path: Path | None = Path(path).expanduser()
        must_exist = True
    else:
        env_path = os.environ.get("NOVA_CONFIG")
        if env_path:
            config_path = Path(env_path).expanduser()
            must_exist = True
        else:
            config_path = DEFAULT_CONFIG_PATH
            must_exist = False

    if config_path is None or not config_path.exists():
        if must_exist:
            raise ConfigError(f"config file not found: {config_path}")
        return _build_settings({}, None)

    try:
        with open(config_path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"top level of {config_path} must be a table")

    return _build_settings(data, config_path)


def with_overrides(settings: Settings, **sections: dict) -> Settings:
    """Return a copy of ``settings`` with section overrides (used by tests)."""
    data = {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "logging": settings.logging,
        "personality": settings.personality,
        "models": settings.models,
        "artifacts": settings.artifacts,
        "config_path": settings.config_path,
        "project_root": settings.project_root,
    }
    for key, value in sections.items():
        if key not in data:
            raise ConfigError(f"unknown settings field: {key}")
        data[key] = value
    return replace(settings, **data)
