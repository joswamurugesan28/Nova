# CHANGELOG

All notable changes to NOVA are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [Semantic Versioning](https://semver.org/) with milestone tags (M0, M1, …).

## [Unreleased]

## [M0] — 2026-10-03

### Added
- **Project scaffold**: `git` repository, `pyproject.toml` (zero runtime dependencies, Python ≥ 3.11), `.gitignore`.
- **Configuration** (`nova/config.py`): TOML loading via stdlib `tomllib`, defaults, `NOVA_CONFIG` env override, validation (log levels, section types), project-root path resolution. Default file: `config/nova.toml`.
- **Logging** (`nova/logging_setup.py`): namespaced `nova.*` loggers, rotating file handler → `logs/nova.log`, console handler, idempotent setup.
- **Core orchestrator** (`nova/core/orchestrator.py`): turn pipeline (input → memory → personality prompt → router → response → memory), `OrchestratorResult` with timing and mock flag.
- **Model layer** (`nova/models/`): `ModelClient` ABC, `TaskType` (chat/vision/stt/tts/artifact), `ModelRequest`/`ModelResponse`, `ModelRouter` with registration/dispatch and typed errors, honest `StubModelClient` (`is_mock=True`).
- **Personality engine** (`nova/personality/`): config-driven system prompt + style injection; persona switching designed for later milestones.
- **Memory** (`nova/memory/`): bounded `ShortTermMemory` rolling buffer with context formatting.
- **Tool registry** (`nova/tools/`): register/decorator/dispatch mechanics, typed errors; no tools registered yet (LLM tool-calling arrives in M4).
- **Artifact Engine skeleton** (`nova/artifacts/`): `ArtifactEngine` facade (create/open/inspect/validate/save routing), `ArtifactRegistry` (extension → handler), `ArtifactHandler` protocol, `workspace/` `templates/` `output/` layout, **path safety** (rejects absolute paths and `..` escapes). Zero format handlers registered — requesting one raises `HandlerNotAvailableError` ("planned M3+").
- **CLI** (`nova/cli.py`, `python -m nova`): `chat`, `routes`, `artifacts`, `config`, `version` subcommands; chat REPL with `/help` `/memory` `/routes` `/clear` `/exit`; prominent **MOCK BACKEND banner** while the stub is active.
- **Tests**: 59 stdlib-unittest tests covering config, models/router/stub, orchestrator, memory, tools, personality, logging, artifacts (incl. path safety and a full fake-handler lifecycle), and CLI commands.
- **Docs**: README.md, AGENTS.md, ARCHITECTURE.md, ROADMAP.md, this CHANGELOG.

### Known limitations (intentional in M0)
- No AI inference of any kind: every response comes from `StubModelClient` and is labeled as mock.
- No artifact format libraries installed; no model weights downloaded.
- Memory is in-memory only (no persistence yet).
