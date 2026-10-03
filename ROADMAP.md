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
- [ ] Choose backend (llama-cpp-python vs Ollama) under 8 GB RAM budget
- [ ] Integrate Qwen3 4B (GGUF, quantized) as `TaskType.CHAT` client
- [ ] Config-driven model selection + graceful fallback to stub with clear labeling
- [ ] Streaming responses in CLI
- [ ] Token/context budget management
- [ ] First *real* conversation end-to-end

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
