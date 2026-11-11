# ARCHITECTURE — NOVA v0.1 (approved)

## Overview

NOVA is a pipeline of small, replaceable subsystems glued together by one
orchestrator. Data flows through explicit interfaces only.

```
                       ┌──────────────────────────────┐
     CLI (nova/cli.py) │        core/orchestrator      │
        chat/routes/…  │  turn: memory → prompt → route│
                       └──────┬────────────┬───────────┘
                              │            │
              ┌───────────────▼──┐   ┌─────▼──────────────┐
              │ personality/     │   │ models/router       │
              │ system prompt +  │   │ TaskType → client   │
              │ style injection  │   └─────┬──────────────┘
              └──────────────────┘         │
              ┌──────────────────┐   ┌─────▼──────────────┐
              │ memory/          │   │ ModelClient (ABC)   │
              │ short-term buffer│   │  - chat   (M1 Qwen3 │
              │ (SQLite in M2+)  │   │  - vision (M2 VL)   │
              └──────────────────┘   │  - stt    (M2 Whisp)│
                                     │  - tts    (M2 F5)   │
              ┌──────────────────┐   │  - artifact planner │
              │ tools/registry   │   │  - stub (M0, MOCK)  │
              │ LLM decides which│   └────────────────────┘
              │ tool; registry   │
              │ executes it      │   ┌────────────────────┐
              └──────────────────┘   │ artifacts/ ENGINE   │
                                     │ see below           │
                                     └────────────────────┘
```

## Subsystems

| Subsystem | Location | Responsibility | M0 status |
|---|---|---|---|
| Orchestrator | `nova/core/orchestrator.py` | turn pipeline: memory → prompt → router → memory | working |
| Config | `nova/config.py` + `config/nova.toml` | TOML settings, validation, path resolution | working |
| Logging | `nova/logging_setup.py` | rotating file (`logs/`) + console, namespaced loggers | working |
| Model layer | `nova/models/` | `ModelClient` interface, `ModelRouter`, backend factory, stub + llama-server clients | working — **real inference online (M1-B)** |
| Personality | `nova/personality/` | config-driven system prompt + style injection | working |
| Memory | `nova/memory/` | bounded short-term context buffer | working (in-memory) |
| Tools | `nova/tools/` | model-facing schemas, allow-listed dispatch, and read-only project file listing | one real-model tool round for filesystem listing |
| Artifact Engine | `nova/artifacts/` | create/modify/validate/save work files | skeleton |
| Vision | `nova/vision/` | Qwen3-VL integration | placeholder (M2) |
| Speech | `nova/speech/` | Whisper STT + IndicF5 TTS | placeholder (M2) |
| CLI | `nova/cli.py` | `chat` `routes` `artifacts` `config` `version` | working |

## Model routing

- One logical task = one `TaskType` = at most one registered `ModelClient`.
- The orchestrator only ever calls `router.generate(request)`; backends are
  interchangeable without touching the orchestrator.
- Backend *selection* happens in one place, `nova/models/factory.py`,
  from the `[models]` section of `config/nova.toml`:
  - `brain = "llama-server"` + `[models.llama_server] enabled = true`
    → `LlamaServerClient` (**current default, M1-B — real inference**)
  - `brain = "stub"` → honest mock `StubModelClient` (one-line switch,
    no code change)
  - disabled or unknown backend → **stub fallback with a logged warning**
    (safe by default)
- `nova model status` probes `GET /health` and reports
  `RUNNING` / `NOT RUNNING` — it **never starts or stops a server**.
- Any response with `is_mock=True` is surfaced as such in the CLI and logs.
- For chat requests, registered tool schemas are passed to the real backend.
  A returned call is checked against the registry, executed by `ToolExecutor`,
  and its observation is returned for one final model response. At most one
  tool round is allowed per user turn. Mock responses cannot trigger tools.
- The initial tool, `filesystem.list_files`, is read-only, receives its
  project root from trusted configuration, accepts only a relative subpath,
  and reports names and sizes without reading file contents.
- Chat history is trimmed before sending based on a bounded character count
  with a reserved output allowance. This is approximate and does not replace
  the server's fixed context window.

### Backend implementations

```
ModelClient                    (the abstraction boundary)
├── LlamaServerClient          REAL inference (M1-B): HTTP/OpenAI-compatible
│                              client for an EXTERNAL llama-server process
│                              (stdlib urllib; health check, non-stream +
│                              SSE streaming, timeouts, typed errors;
│                              is_mock=False — errors raise, never fake)
├── StubModelClient            mock, is_mock=True, fallback (config switch)
├── OllamaClient               future candidate, same interface
└── future backends            vision / STT / TTS clients (M2)
```

**M1-B runtime (measured on target hardware):**

- Runtime: official llama.cpp prebuilt `llama-server` v0.5.0-dev (b11379),
  user-space at `tools/llama.cpp/llama-b11379/` (no sudo, no build —
  `cmake` is absent on this machine, so the official binary was chosen).
- Model: `models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
  (unsloth, GGUF v3, arch `qwen3`, 4.02 B params, 2,497,281,120 bytes,
  sha256 verified against Hugging Face's authoritative X-Linked-Etag).
- Launch: `-c 4096 -np 1 -t 4 -b 1024 -ub 512 -ctk q8_0 -ctv q8_0`
  — 4 threads beat 8 (11.1 vs 8.7 t/s tg128); `-np 1` keeps a single
  4096-token slot (the default 4 slots quadrupled KV for no benefit);
  q8_0 KV saves ~300 MB. Weights are mmap'd → reclaimable page cache.
- NOVA never manages the server lifecycle; `[models.llama_server]`
  config knobs: `enabled`, `base_url`, `model`, `timeout_seconds`,
  `health_timeout_seconds`, `context_size`, `temperature`, `max_tokens`.
- Honesty invariant: when the real backend fails, the CLI reports
  `[real backend unavailable]` and never substitutes mock text.

## Artifact Engine (first-class module)

The LLM decides **WHAT** needs to be created or modified. Specialized
handlers perform the actual **file operations** with dedicated libraries.

```
nova/artifacts/
├── engine.py      # facade: lifecycle, path safety, directory management
├── registry.py    # extension → handler mapping + ArtifactHandler protocol
├── workspace/     # scratch area where artifacts are opened/edited (gitignored)
├── templates/     # reusable templates NOVA instantiates (committed)
└── output/        # finished artifacts delivered to the user (gitignored)
```

Lifecycle every artifact supports:

```
create / open  →  inspect  →  modify  →  validate  →  save
```

`engine.open_file()` keeps the document object in-session, so an existing
artifact can be re-opened, inspected, modified, validated and saved again.

Planned format handlers (installed only when their milestone starts):

| Format | Library | Milestone |
|---|---|---|
| DOCX | python-docx | M3 |
| PPTX | python-pptx | M3 |
| XLSX | openpyxl | M3 |
| PDF | reportlab | M3 |
| CSV | pandas (stdlib `csv` possible earlier) | M3 |
| Images | Pillow | M3 |
| Templates | engine + templates/ | M4 |
| General generated files | stdlib | M4 |

M0 ships **zero format handlers**; requesting one raises
`HandlerNotAvailableError` with an explicit "planned M3+" message — the
engine never fakes file contents.

**Safety**: all artifact paths pass through `safe_path()` which rejects
absolute paths and `..` escapes — writes can only land in
`workspace/` or `output/`.

## Data & control rules

1. LLM decides *what*; modules do *how*. (tools/, artifacts/ follow this.)
2. No subsystem imports another subsystem's internals — only interfaces.
3. All tunables live in `config/nova.toml`; no hardcoded model ids/paths.
4. Everything logs through the `nova.*` logger namespace.

## Target hardware & budget

Ubuntu Linux · AMD Ryzen 3 7320U · 8 GB RAM · CPU-only.
Quantized (GGUF-class) models; one heavyweight model resident at a time;
memory bounded (rolling buffer + future SQLite with pruning).

## Evolution

M0 scaffold ✅ → M1-A llama-server interface ✅ → M1-B local brain online ✅
→ M2 vision/STT/TTS → M3 artifact handlers → M4 expanded LLM-driven tool &
artifact planning → M5 hardening. The initial filesystem tool loop is in place;
see ROADMAP.md for remaining M4 work.
