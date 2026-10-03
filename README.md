# NOVA — Neural Operations & Vision Assistant

NOVA is a modular personal AI assistant that can **converse, remember, use tools, and create/modify real work files** (DOCX, PPTX, XLSX, PDF, CSV, images) — running locally on consumer hardware.

**Status: M0 (scaffold).** All model backends are stubs. No AI inference happens yet — every mock response is explicitly labeled as such.

## Design goals

- **Modular**: every subsystem (brain, vision, STT, TTS, artifacts) plugs in behind one interface and can be replaced independently.
- **Honest**: mock output is always marked (`is_mock=True`) and the CLI shows a warning banner. NOVA never presents canned text as model inference.
- **CPU-first**: tuned for Ubuntu Linux, AMD Ryzen 3 7320U, 8 GB RAM.
- **Artifact-producing**: NOVA creates and modifies user work files, not just answers questions.

## Planned models (not yet integrated)

| Role | Model | Milestone |
|---|---|---|
| Brain | Qwen3 4B | M1 |
| Vision | Qwen3-VL 4B | M2 |
| STT | Whisper | M2 |
| TTS | AI4Bharat IndicF5 | M2 |

## Project layout

```
NOVA/
├── config/nova.toml        # configuration (TOML, stdlib-parsed)
├── logs/                   # runtime logs (rotating, gitignored)
├── nova/                   # the Python package
│   ├── cli.py              # command-line entry point
│   ├── config.py           # settings loading + validation
│   ├── logging_setup.py    # rotating file + console logging
│   ├── core/orchestrator.py# turn pipeline wiring everything together
│   ├── models/             # ModelClient interface, router, stub backend
│   ├── personality/        # dynamic personality engine (prompt assembly)
│   ├── memory/             # short-term context buffer
│   ├── tools/              # tool registry (LLM tool-calling comes later)
│   ├── artifacts/          # ARTIFACT ENGINE: engine, registry, workspace,
│   │   │                   #   templates, output
│   ├── vision/             # placeholder (M2: Qwen3-VL)
│   └── speech/             # placeholder (M2: Whisper, IndicF5)
├── tests/                  # stdlib unittest suite
└── AGENTS.md ARCHITECTURE.md ROADMAP.md CHANGELOG.md
```

## Getting started

Requires Python ≥ 3.11 (stdlib only — no dependencies to install for M0).

```bash
python3 -m nova version       # print version
python3 -m nova config        # show effective configuration
python3 -m nova routes        # show model routing table (all stub in M0)
python3 -m nova artifacts     # show Artifact Engine status
python3 -m nova chat          # interactive chat (MOCK backend in M0)
```

Chat commands: `/help` `/memory` `/routes` `/clear` `/exit`

## Running tests

```bash
python3 -m unittest discover -s tests -v
```

(or `pytest` if installed — tests are compatible with both.)

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — approved component architecture
- [ROADMAP.md](ROADMAP.md) — milestones M0…M5
- [AGENTS.md](AGENTS.md) — rules binding all coding agents
- [CHANGELOG.md](CHANGELOG.md) — change history
