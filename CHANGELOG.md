# CHANGELOG

All notable changes to NOVA are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [Semantic Versioning](https://semver.org/) with milestone tags (M0, M1, …).

## [Unreleased]

## [M1-A] — 2026-10-03

### Added
- **llama-server backend interface** (`nova/models/llama_server.py`): `LlamaServerClient` implements `ModelClient` over llama.cpp `llama-server`'s HTTP/OpenAI-compatible API using **only the standard library** (`urllib` + `json`). Supports configurable base URL/model metadata, `GET /health` health checks, non-streaming chat completion, SSE streaming (`stream()`), configurable timeouts, and typed error handling (`ServerUnreachableError`, `RequestTimeoutError`, `MalformedResponseError`, generic `LlamaServerError`). Errors are raised, never converted into fake text; real responses carry `is_mock=False`.
- **Backend factory** (`nova/models/factory.py`): maps `[models]` config names to clients — `stub` (default, unchanged M0 behavior) or `llama-server`; disabled/unknown backends fall back to the stub with a logged warning (safe by default). Non-chat tasks remain on the stub until M2/M4.
- **Configuration**: `[models.llama_server]` section (`enabled = false`, `base_url`, `model`, `timeout_seconds`, `health_timeout_seconds`, `context_size`, `temperature`, `max_tokens`) added to `config/nova.toml` and parsed in `nova/config.py`. `ModelSettings` gained a `llama_server` field; all defaults preserve M0 behavior.
- **CLI**: `nova model status [--url URL]` diagnostic — reports `Backend` / `URL` / `Model` / `Enabled` / `Status: RUNNING|NOT RUNNING` and **never starts a server** (exit 0 = reachable, 1 = not reachable). `nova config` now prints the llama-server settings; the chat banner only shows the MOCK warning when the stub is actually active.
- **Tests**: `tests/test_llama_server.py` — 26 new tests using a stdlib `http.server` mock (no llama-server, no model, no network): health success/failure/timeout/refused, completion success + payload shape, timeout, connection refused, malformed JSON, bad shape, null content, HTTP 500, streaming deltas/malformed/refused, factory selection, config parsing, and `model status` CLI behavior.
- **Docs**: README (backends table + enable instructions), ARCHITECTURE (routing rules + backend implementations), ROADMAP (M1 split into M1-A ✅ / M1-B pending).

### Not changed
- No model downloaded, no llama.cpp/Ollama installed, no inference benchmarked, no dependencies added, M0 architecture and all 59 M0 tests preserved.

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
