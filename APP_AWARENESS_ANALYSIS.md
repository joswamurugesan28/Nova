# NOVA Application Awareness System — Analysis & Proposal

Status: **Analysis only. Awaiting approval before implementation.**

## 1. Existing architecture analysis

NOVA is a modular personal AI assistant built around a single orchestrator pipeline:

- `nova/core/orchestrator.py` — turn pipeline: memory → personality prompt → router → (optional one tool round) → memory. Depends only on interfaces.
- `nova/models/` — `ModelClient` ABC, `ModelRouter`, `ModelFactory`; backends: `StubModelClient` (mock), `LlamaServerClient` (real, Qwen3 4B via llama.cpp). Real inference online (M1-B).
- `nova/personality/`, `nova/memory/` — config-driven persona + bounded short-term buffer.
- `nova/tools/` — `ToolRegistry` (allow-list), `ToolExecutor` with `EventBus`, read-only `filesystem.list_files` confined to a trusted project root. At most one tool round per turn.
- `nova/artifacts/` — `ArtifactEngine` facade + `ArtifactRegistry` (extension→handler), path safety via `safe_path()`, zero format handlers yet (M3).
- `nova/vision/`, `nova/speech/` — placeholders (M2).
- `nova/cli.py` — `chat`, `routes`, `artifacts`, `config`, `version`, `files`, `model status`.
- Config: `config/nova.toml` (TOML, stdlib), all tunables there. Logging: `nova.*` namespace rotating file + console.

Key invariants: LLM decides WHAT, modules do HOW; subsystems talk via interfaces only; no system-wide changes; one heavyweight model at a time; mocks labeled `is_mock=True`; path safety rejects escapes.

## 2. Current capabilities

- Conversational chat with real local LLM (Qwen3-4B, CPU) + honest mock fallback.
- Bounded context budgeting, short-term memory.
- Personality/style injection.
- Read-only filesystem listing tool (confined root, no content reads, hidden dirs skipped).
- One tool round per turn, validated against registry; mock responses cannot trigger tools.
- Artifact engine skeleton with path safety and lifecycle contract (no handlers yet).
- EventBus lifecycle events (tool.started/completed/failed/rejected, observation.received).
- CLI diagnostics (model status, config, routes).
- Test suite (stdlib unittest).

## 3. Missing capabilities (for Application Awareness)

- No concept of "application" or "project" domain objects; filesystem tool is generic.
- No GUI observation / desktop interaction layer.
- No permission engine (read-only auto vs approval-gated modifications).
- No audit log (events are in-memory only; no persistent append-only log).
- No application-specific adapters (Godot, Blender, Kdenlive, FL Studio, VS Code).
- No communication bridge to external editors (localhost/IPC).
- No editor plugin scaffolding.
- No scene/node/script inspection, no controlled editing, no run/debug control.
- No approval workflow in CLI/UI.
- No sandboxing beyond path safety.

## 4. Proposed integration architecture

Introduce an **Application Awareness Layer** (`nova/apps/`) that sits beside tools/artifacts and routes through the orchestrator, never hard-wiring into other subsystems.

```
nova/
├── apps/
│   ├── __init__.py
│   ├── base.py            # ApplicationAdapter ABC (interface)
│   ├── registry.py        # ApplicationRegistry (discover/attach adapters)
│   ├── permissions.py     # PermissionEngine (centralized)
│   ├── audit.py           # AuditLog (append-only)
│   ├── godot/
│   │   ├── __init__.py
│   │   ├── adapter.py     # GodotAdapter implements ApplicationAdapter
│   │   ├── bridge.py      # localhost HTTP bridge client (talks to plugin)
│   │   ├── project.py     # project detection, file ops (via tools/artifacts)
│   │   └── scenes.py      # scene tree / node / script inspection
│   ├── blender/           # future stubs
│   ├── kdenlive/
│   ├── flstudio/
│   └── vscode/
├── gui/                   # GUI access subsystem (desktop observation/interaction)
│   ├── __init__.py
│   ├── observer.py        # read-only screen/window inspection
│   └── controller.py      # approval-gated interaction
```

Core abstractions:

- `ApplicationAdapter` interface: `detect_project()`, `inspect()`, `list_resources()`, `read_script(path)`, `modify_script(...)` (approval-gated), `run_project()`, `debug()`. Each app implements HOW; orchestrator/LLM decides WHAT via tool schemas.
- `PermissionEngine`: centralized policy. Operations classified into `READ_INSPECT` (auto), `FILE_MODIFY`, `SCENE_MODIFY`, `EXECUTE`, `DESTRUCTIVE` (approval required). Exposes `check(op) -> PermissionDecision` + `request_approval(op, context)` for interactive confirmation. Config-driven allow-lists and thresholds in `config/nova.toml`.
- `AuditLog`: append-only JSONL under `logs/audit.jsonl`, recording every app/tool action with timestamp, actor (model/user), operation, target, decision, result. Rotating, tamper-evident-ish (hash chain optional later).
- `Bridge`: localhost HTTP (127.0.0.1, configurable port) between NOVA and editor plugins. Godot EditorPlugin exposes endpoints: project info, active scene, scene tree, selected node, script read/write, run/debug. NOVA never starts the editor; like llama-server, manual start.
- GUI access: separate read-only observer + approval-gated controller; platform-specific (Ubuntu/X11/Wayland) behind interface; initially read-only inspection only to keep scope minimal and safe.

Permission classes and approval matrix:

| Operation class | Auto? | Notes |
|---|---|---|
| Read-only inspection (list/read files, scene tree, node props) | Yes | Logged |
| File modifications | No | Approval required |
| Scene modifications | No | Approval required |
| Terminal commands / project execution | No | Approval required |
| Destructive (delete, overwrite outside workspace) | No | Explicit approval |

Integration with existing pieces:

- New tools registered in `ToolRegistry` (e.g., `godot.inspect_scene`, `godot.read_script`) so LLM can call them; execution goes through `ToolExecutor` and `PermissionEngine` gate.
- Artifact engine handles file writes (path safety) for scripts/resources; modifications require approval token from `PermissionEngine`.
- Audit events published via existing `EventBus` AND persisted by `AuditLog`.
- Config additions under `[apps]`, `[apps.godot]`, `[permissions]`, `[audit]`.

Godot specifics:

- EditorPlugin (GDScript) in a `godot_plugin/` directory (delivered to user to install in their Godot project) exposing a localhost HTTP server with endpoints.
- NOVA side `bridge.py` client using stdlib urllib (consistent with llama-server client).
- Active project detection: bridge reports project path; NOVA validates against allowed roots.
- Scene inspection: active scene, scene tree (nodes, types, properties), selected node.
- GDScript reading + controlled editing (approval-gated, path-safe).
- Project execution & debugging: run project, capture output, stop (approval-gated).

Future apps (Blender, Kdenlive, FL Studio, VS Code) implement the same `ApplicationAdapter` + bridge pattern; registry discovers them. No hard-wiring.

## 5. File structure changes

New (additive, no overwrites):

```
nova/apps/__init__.py
nova/apps/base.py
nova/apps/registry.py
nova/apps/permissions.py
nova/apps/audit.py
nova/apps/godot/__init__.py
nova/apps/godot/adapter.py
nova/apps/godot/bridge.py
nova/apps/godot/project.py
nova/apps/godot/scenes.py
nova/gui/__init__.py
nova/gui/observer.py
nova/gui/controller.py
godot_plugin/                      # Godot EditorPlugin (GDScript) + README
  addons/nova_bridge/
    plugin.cfg
    plugin.gd
    http_server.gd
    ...
docs/APP_AWARENESS_SETUP.md
tests/test_permissions.py
tests/test_audit.py
tests/test_apps_registry.py
tests/test_godot_bridge.py (mock HTTP, no Godot required)
```

Modified (minimal, additive):

- `config/nova.toml` — add `[apps]`, `[apps.godot]`, `[permissions]`, `[audit]` sections.
- `nova/cli.py` — add `apps`, `permissions`, `audit` commands; approval prompts.
- `nova/core/orchestrator.py` — optional `permission_engine`/`audit_log`/`app_registry` params (backward compatible, default None).
- `nova/tools/__init__.py` or new `nova/tools/apps.py` — register app tools when an adapter is attached.
- `ARCHITECTURE.md`, `ROADMAP.md`, `CHANGELOG.md` — document new layer and milestones.
- `README.md` — setup instructions.

## 6. Implementation roadmap (incremental, approval-gated)

Phase A — Foundations (no external app needed):
1. `PermissionEngine` + tests.
2. `AuditLog` (JSONL, append-only) + tests.
3. `ApplicationAdapter` interface + `ApplicationRegistry` + tests.
4. Config sections + CLI `nova permissions`, `nova audit`.

Phase B — Godot bridge (mock-first):
5. `bridge.py` client with mock HTTP tests (mirror llama-server test style).
6. Godot EditorPlugin (GDScript) with localhost endpoints + install docs.
7. `GodotAdapter` implementing adapter: project detection, scene tree, selected node, script read.
8. Register Godot tools in ToolRegistry; approval gate for modifications.

Phase C — Controlled actions:
9. GDScript controlled editing (approval + path safety + artifact engine).
10. Project run/debug control (approval + output capture).
11. Audit integration across all actions.

Phase D — GUI access:
12. Read-only desktop observer (Ubuntu) behind interface.
13. Approval-gated controller (minimal, safe subset).

Phase E — Future apps:
14. Stub adapters for Blender, Kdenlive, FL Studio, VS Code (detect + inspect only).

Each phase: tests pass, CLI works, CHANGELOG updated, no fake functionality. Mocks (bridge tests) clearly labeled and never presented as real.

## Open questions for approval

1. Should the audit log be JSONL under `logs/` or a separate `data/` dir?
2. Should approval be interactive CLI prompt only initially, or also a config allow-list for trusted operations?
3. Port for Godot bridge (suggest 7456) and whether NOVA should ever auto-launch Godot (recommend: never, manual only, consistent with llama-server).
4. Scope of GUI access in first iteration: read-only inspection only (recommended) vs. any interaction.

Awaiting approval to proceed with Phase A.