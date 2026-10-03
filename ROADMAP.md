# ROADMAP — NOVA Milestones

Target hardware: Ubuntu Linux, AMD Ryzen 3 7320U, 8 GB RAM, CPU-only inference.
Rule: a milestone is done only when tests pass, CLI works, and CHANGELOG.md is updated.

## M0 — Scaffold & Architecture ✅ (current)
- [x] Git repository, Python package, `pyproject.toml`, `.gitignore`
- [x] Configuration loading (TOML, stdlib `tomllib`, validation)
- [x] Logging (rotating file → `logs/` + console)
- [x] Core orchestrator (turn loop: memory → personality → router)
- [x] Model interface (`ModelClient`), model router, honest stub backend
- [x] Personality module skeleton (config-driven prompt assembly)
- [x] Memory module skeleton (bounded short-term buffer)
- [x] Tool registry skeleton (register/dispatch, no tools yet)
- [x] **Artifact Engine skeleton** (engine + registry + workspace/templates/output, path safety, no format handlers)
- [x] CLI: `chat` `routes` `artifacts` `config` `version`
- [x] Test suite (stdlib unittest, 59 tests)
- [x] Docs: README, AGENTS, ARCHITECTURE, ROADMAP, CHANGELOG
- **Out of scope:** any real model, any format library, downloads

## M1 — Local brain

### M1-A — llama-server backend interface ✅ (current)
- [x] `LlamaServerClient` implementing `ModelClient` over llama-server's HTTP/OpenAI API (stdlib only)
- [x] Health checking, normal + SSE streaming completion, timeouts, typed error handling (unreachable / timeout / malformed / HTTP error)
- [x] Backend selection in `nova/models/factory.py` (`stub` | `llama-server`, safe stub fallback)
- [x] Config: `[models.llama_server]` (`enabled`, `base_url`, `model`, `timeout_seconds`, `health_timeout_seconds`, `context_size`, `temperature`, `max_tokens`)
- [x] CLI diagnostic `nova model status` (reports RUNNING / NOT RUNNING; **never starts the server**)
- [x] Mock-HTTP test suite (no server, no model required)
- **Explicitly out of scope:** llama.cpp not installed, no model downloaded, no inference benchmarked, no Ollama

### M1-B — real inference ✅ (complete)
- [x] llama.cpp runtime: **official prebuilt `llama-server` v0.5.0-dev (b11379)** extracted to `tools/llama.cpp/llama-b11379/` (user-space; no sudo; source build skipped because `cmake` is missing)
- [x] Model: **unsloth `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`** → `models/qwen3/` (2,497,281,120 bytes; sha256 verified vs HF authoritative etag; GGUF v3 arch `qwen3` confirmed; llama.cpp loads it)
- [x] First real inference: prompts A–D answered by Qwen3, `is_mock=False`, no canned fallback; streaming verified progressive (30 chunks / 2.61 s spread)
- [x] Benchmark: startup 5 s · pp512 35.4 t/s · tg128 **11.1 t/s @ t4 vs 8.7 @ t8** · ctx 4096 costs ~150 MB more than 2048 → keep 4096 · ~2.0 GB server RssAnon · 4 threads selected
- [x] Config: `brain = "llama-server"`, `enabled = true` (switch back to `brain = "stub"` without code changes)
- [x] Failure honesty: chat reports `[real backend unavailable]`, never silently falls back to mock text (tested)
- [x] Tests: default suite 87/87 green (no server required); optional `integration_tests/` suite 5/5 against the real model (auto-skips when server is down)
- [x] Docs updated (README/ARCHITECTURE/ROADMAP/CHANGELOG)
- [ ] Streaming output in interactive `nova chat` (client supports it; CLI buffers full responses)
- [ ] NOVA-side token/context budgeting (server fixed at `-c 4096` for now)
- [ ] Mid-session server-death recovery (restart guidance only)

## M2 — Perception (vision + speech)
- [ ] Qwen3-VL 4B as `TaskType.VISION` (image input path)
- [ ] Whisper STT as `TaskType.STT`
- [ ] AI4Bharat IndicF5 TTS as `TaskType.TTS`
- [ ] Audio capture/playback plumbing for the CLI
- [ ] Persistent memory: SQLite store + retrieval + pruning

## M3 — Artifact handlers (real file creation)
- [ ] CSV handler (pandas or stdlib `csv`)
- [ ] DOCX handler (python-docx)
- [ ] PPTX handler (python-pptx)
- [ ] XLSX handler (openpyxl)
- [ ] PDF handler (reportlab)
- [ ] Image handler (Pillow)
- [ ] Full lifecycle tests: create → inspect → modify → validate → save → re-open
- [ ] Artifact result reporting in CLI

## M4 — Agentic planning (LLM decides, modules execute)
- [ ] LLM tool-calling loop: model chooses tools, registry executes
- [ ] LLM artifact planner: model decides WHAT to create/modify; engine executes
- [ ] Template instantiation
- [ ] General generated-file support (config dumps, scripts, etc.)
- [ ] Tool execution sandboxing + allow-list from config

## M5 — Hardening & UX
- [ ] Session persistence, error recovery, retries with backoff
- [ ] Resource guardrails for 8 GB RAM (one model resident, eviction policy)
- [ ] Packaging/install story, man-page style docs
- [ ] Performance and soak testing on target hardware
