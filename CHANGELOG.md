# CHANGELOG

All notable changes to NOVA are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [Semantic Versioning](https://semver.org/) with milestone tags (M0, M1, …).

## [Unreleased]

### Added
- **Screenshot backend discovery:** X11Provider.discover_screenshot_backend, honest unavailable reporting.
- **Visual Desktop Intelligence:** screenshot capture tool, vision provider abstraction, describe_screen; honest unavailable reporting.
- **Desktop provider improvements:** X11 window listing via xlsclients, active window via xprop; verified desktop.inspect end-to-end.
- **Desktop inspection tool integration:** register desktop.inspect in ToolRegistry and wire into orchestrator prompt.
- **Autonomous Environment Operations (Phase G):** package execution, UniversalExecutor integration, verification.
- **Universal Environment & Software Management (Phase F):** package managers, discovery, planner, diagnostics.
- **Workflow Reliability, Persistence and Approval (Phase E.8):** SQLite store, approval pause/resume, recovery hooks.
- **Cross-Application Workflow Orchestration (Phase E.7):** workflow engine, DAG, context, artifacts.
- **Autonomous Execution Integration and Safe Recovery (Phase E.6):** resolver integrated, safety classes, execution states, safe fallback.
- **Autonomous Provider Selection (Phase E.5):** ProviderResolver with ranking, capability overrides, fallback; ApplicationProfile.
- **Universal Execution Pipeline (Phase E.4):** UniversalExecutor with discovery→capability→provider→permission→execution→verification→audit.
- **Universal Application Intelligence (Phase E.3):** discovery states, capability profiles, universal providers, interface selector.
- **Blender integration (Phase E.2):** BlenderBridge + BlenderAdapter with approval-gated operations, mock tests.
- **VS Code integration + discovery improvements (Phase E.1):** improved multi-source discovery, VSCodeAdapter with safe file ops.
- **Multi-Application Intelligence foundation (Phase E):** capability discovery, adapter stubs for Blender/Kdenlive/FL Studio/VS Code.
- **Operational Ubuntu Desktop Providers (Phase D.1):** real X11/Wayland/AT-SPI best-effort providers, emergency stop.
- **Universal Desktop Awareness (Phase D):** `nova/gui/` provider abstraction, DesktopObserver, GUIController (approval-gated), mock/X11/Wayland/AT-SPI providers. Tests.
- **Security hardening pass:** token weakness rejection, backup verification + rollback, audit backup metadata, response size limits, plugin default-token guard.
- **Godot integration (Phase B):** `nova/apps/godot/` (bridge client, adapter), `nova/tools/godot.py` tool registration, Godot EditorPlugin under `godot_plugin/`. Bridge binds 127.0.0.1:47821 with bearer auth. Tests: bridge, adapter.
- **Application Awareness foundations (Phase A):** `nova/apps/` package with `ApplicationAdapter` interface, `ApplicationRegistry`, centralized `PermissionEngine` (read-only auto, gated modifications/execution/destructive), and append-only `AuditLog` (JSONL). Config sections `[permissions]`, `[audit]`, `[apps]` added. Tests: permissions, audit, registry.
- **Animated thinking spinner in `nova chat`:** while a real model request is in flight, the terminal shows a spinner beside a randomly chosen status message on a single line. The status rotates every 1-2 seconds and never immediately repeats the previous message. When the request finishes or errors, the animation stops cleanly, the final status stays visible on its own line, and NOVA's response (or the `[real backend unavailable]` / `[context too large]` error) prints on the next line. Shown only for real `llama-server` requests on a real TTY — never for the stub backend and never on piped output. Existing tool status messages and error handling are preserved.
- Add a read-only filesystem listing tool and connect its registered schema to real llama-server tool calls in `nova chat`. NOVA validates calls against the registry, executes at most one tool round, sends observations back for a final response, and prevents mock model responses from executing tools. The direct `nova files` command remains available. File contents are never read and tool paths stay under the trusted project root.
- Clarify that mentions of the NOVA/project/root folder mean the already-selected project root, map the root's friendly name to `.`, and show in chat whether a tool actually ran or failed.
- Restore the orchestrator prompt-building methods required by the in-progress session/context changes and avoid duplicate inference when collecting a streaming response.

## [M1-B] — 2026-10-03

### Added
- **Real local inference online.** Runtime: official llama.cpp prebuilt `llama-server` v0.5.0-dev (build b11379) extracted **user-space** to `tools/llama.cpp/llama-b11379/` (no sudo, no system packages; source build skipped because `cmake` is unavailable). Model: `models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` from `unsloth/Qwen3-4B-Instruct-2507-GGUF` — 2,497,281,120 bytes, **sha256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` verified against Hugging Face's authoritative `X-Linked-Etag`**, GGUF v3 metadata confirmed (arch `qwen3`, name `Qwen3-4B-Instruct-2507`, `general.file_type=15` = MOSTLY_Q4_K_M, 4.02 B params, Q4_K/Q6_K tensor mix).
- **Server configuration (measured on target hardware):** `-c 4096 -np 1 -t 4 -b 1024 -ub 512 -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port 8080`. Chosen from benchmarks: 4 threads beat 8 (tg128 11.1 vs 8.7 t/s), `-np 1` avoids the default 4-slot 16k KV, q8_0 KV saves ~300 MB.
- **Benchmarks (measured, not estimated):** startup → `/health 200` in 5 s · prompt processing pp512 = 35.4 t/s · generation tg128 = 11.1 t/s @ t4 · live chat ≈ 10 t/s · streaming first token ≈ 0.7 s · server RssAnon ≈ 2.0 GB (ctx4096; ctx2048 saves ~150 MB) · system available ≈ 2.3 GB during generation · CPU 200–270 %.
- **Config integration:** `config/nova.toml` now ships `brain = "llama-server"` + `[models.llama_server] enabled = true`; switching back to the mock is `brain = "stub"` (no code change). Full start command documented in README/ARCHITECTURE/config comments.
- **Failure honesty in CLI chat:** a dead real backend prints `[real backend unavailable]` + recovery guidance and **never** substitutes mock text (unit-tested with a dead port).
- **Optional integration tests** (`integration_tests/test_real_brain.py`, outside `tests/` so the default suite never needs the server): health, non-mock generation, trivial answer, progressive streaming, orchestrator end-to-end — 5/5 passing against the live model, auto-skip when the server is down.
- **Docs:** README (start procedure, measured benchmarks, RAM/limitations, switching), ARCHITECTURE (M1-B runtime + honesty invariant), ROADMAP (M1-B checked), CHANGELOG.
- `.gitignore`: `tools/` and `models/` excluded (runtime + weights are never committed).

### Changed
- `tests/test_config.py::test_default_config_file_loads` and `tests/test_llama_server.py::LlamaServerConfigTests.test_defaults` updated: the shipped config now declares the real brain, and built-in-default assertions moved to a config without `[models.llama_server]`. No tests deleted; default suite **87/87 passing**.

### Known limitations
- Interactive `nova chat` buffers full responses (client streaming verified but not yet wired into the REPL); no NOVA-side context budgeting; server lifecycle fully manual; 8 GB RAM means one model resident at a time.

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
