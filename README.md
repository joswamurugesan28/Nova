# NOVA — Neural Operations & Vision Assistant

NOVA is a modular personal AI assistant that can **converse, remember, use tools, and create/modify real work files** (DOCX, PPTX, XLSX, PDF, CSV, images) — running locally on consumer hardware.

**Status: M1-B — real local inference ONLINE.** NOVA's brain runs on
`llama.cpp llama-server` + **Qwen3-4B-Instruct-2507 (GGUF, Q4_K_M)** on
the CPU. The mock `stub` backend remains a one-line config switch away.

## Design goals

- **Modular**: every subsystem (brain, vision, STT, TTS, artifacts) plugs in behind one interface and can be replaced independently.
- **Honest**: mock output is always marked (`is_mock=True`) and the CLI shows a warning banner. NOVA never presents canned text as model inference, and a failed real request is reported as a failure — never silently replaced by fake output.
- **CPU-first**: tuned for Ubuntu Linux, AMD Ryzen 3 7320U (4C/8T), 8 GB RAM.
- **Artifact-producing**: NOVA creates and modifies user work files, not just answers questions.

## Models

| Role | Model | Status |
|---|---|---|
| Brain | **Qwen3-4B-Instruct-2507, GGUF Q4_K_M** (unsloth) | ✅ online (M1-B) |
| Vision | Qwen3-VL 4B | M2 |
| STT | Whisper | M2 |
| TTS | AI4Bharat IndicF5 | M2 |

## Project layout

```
NOVA/
├── config/nova.toml        # configuration (TOML, stdlib-parsed)
├── logs/                   # runtime logs incl. llama-server.log (gitignored)
├── models/qwen3/           # MODEL WEIGHTS (gitignored, 2.50 GB)
│   └── Qwen3-4B-Instruct-2507-Q4_K_M.gguf
├── tools/llama.cpp/        # llama.cpp runtime (gitignored)
│   └── llama-b11379/llama-server
├── nova/                   # the Python package
│   ├── cli.py              # command-line entry point
│   ├── config.py           # settings loading + validation
│   ├── logging_setup.py    # rotating file + console logging
│   ├── core/orchestrator.py# turn pipeline wiring everything together
│   ├── models/             # ModelClient interface, router, factory,
│   │                       #   stub + llama-server backends
│   ├── personality/        # dynamic personality engine (prompt assembly)
│   ├── memory/             # short-term context buffer
│   ├── tools/              # tool registry (LLM tool-calling comes later)
│   ├── artifacts/          # ARTIFACT ENGINE: engine, registry, workspace,
│   │   │                   #   templates, output
│   ├── vision/             # placeholder (M2: Qwen3-VL)
│   └── speech/             # placeholder (M2: Whisper, IndicF5)
├── tests/                  # unit suite (never needs the server)
├── integration_tests/      # optional real-model tests (skip if server down)
└── AGENTS.md ARCHITECTURE.md ROADMAP.md CHANGELOG.md
```

## Getting started

Requires Python ≥ 3.11 (stdlib only — zero dependencies).

```bash
python3 -m nova version        # print version
python3 -m nova config         # show effective configuration
python3 -m nova routes         # show model routing table
python3 -m nova model status   # check llama-server reachability (never starts it)
python3 -m nova chat           # interactive chat (real Qwen3 brain by default)
```

Chat commands: `/help` `/memory` `/routes` `/clear` `/exit`

### Starting the brain (manual — NOVA never starts it for you)

```bash
tools/llama.cpp/llama-b11379/llama-server \
  -m models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf \
  -c 4096 -np 1 -t 4 -b 1024 -ub 512 -ctk q8_0 -ctv q8_0 \
  --host 127.0.0.1 --port 8080
```

Verify: `python3 -m nova model status` → `Status: RUNNING (HTTP 200)`.

### Model backends

| Backend | Status | Notes |
|---|---|---|
| `llama-server` | **working (default)** | Real inference via HTTP/OpenAI API (`nova/models/llama_server.py`) |
| `stub` | working (fallback) | Honest mock, labeled everywhere, zero dependencies |

```
ModelClient
├── LlamaServerClient    (M1-B, real Qwen3 over HTTP)
├── StubModelClient      (fallback, is_mock=True)
└── future backends      (Ollama, vision, STT, TTS)
```

**Switching back to the mock:** set `brain = "stub"` in
`config/nova.toml` — no code changes needed. With `brain = "llama-server"`
and the server down, chat reports `[real backend unavailable]` and
**never** substitutes mock text as an answer.

## Measured performance (this machine, 2026-10-03)

llama.cpp b11379 prebuilt, CPU-only, `-t 4 -c 4096 -ctk q8_0 -ctv q8_0`:

| Metric | Measured |
|---|---|
| Startup (launch → /health 200) | **5 s** |
| Prompt processing (llama-bench pp512) | **35.4 t/s** @ 4 threads (35.3 @ 8) |
| Generation (llama-bench tg128) | **11.1 t/s** @ 4 threads vs 8.7 @ 8 → **4 threads wins** |
| Generation (live NOVA chat) | ~10 t/s steady |
| First token (streaming) | ~0.7 s |
| Server RAM (RssAnon, idle) | ~2.0 GB (ctx 4096); ctx 2048 saves only ~150 MB |
| System RAM during generation | ~2.3 GB available of 6.5 GB |
| CPU during generation | 200–270 % (4 threads) |

## Known limitations & RAM constraints

- **8 GB total (6.5 Gi visible), swap active** — one heavyweight model at a
  time; do not load a second model alongside the server.
- Weights are mmap'd (page cache, reclaimable); server anon memory ≈ 2 GB;
  server's own swap footprint ≈ 45 MB.
- 4B Q4 model quality: fine for chat/summarization; tool-calling and long
  reasoning are limited (M4 will add constrained decoding).
- Streaming is supported by the client and verified, but interactive
  `nova chat` still buffers full responses (CLI streaming = future work).
- Server lifecycle is fully manual (by design): start, stop, restart = you.

## Running tests

```bash
python3 -m unittest discover -s tests -v           # unit tests, no server needed
python3 -m unittest discover -s integration_tests -v  # optional; skips if server down
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — approved component architecture
- [ROADMAP.md](ROADMAP.md) — milestones M0…M5
- [AGENTS.md](AGENTS.md) — rules binding all coding agents
- [CHANGELOG.md](CHANGELOG.md) — change history
