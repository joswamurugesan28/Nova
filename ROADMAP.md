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

### M1-B — real inference (requires explicit approval to download)
- [ ] Install/build `llama-server` (user-space, no sudo)
- [ ] Download Qwen3 4B GGUF (Q4_K_M, Instruct-2507) — **awaiting user go-ahead**
- [ ] Enable `brain = "llama-server"` + `enabled = true`, verify first honest non-mock turn
- [ ] Graceful fallback to stub when the server dies mid-session
- [ ] Streaming responses in the CLI chat
- [ ] Token/context budget management (4k ctx, KV-cache sizing for 8 GB)

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
