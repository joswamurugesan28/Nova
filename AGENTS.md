# AGENTS.md — Rules for Coding Agents

These rules bind every AI agent working on NOVA. Read ARCHITECTURE.md and ROADMAP.md first.

## Ground rules

1. **Never fake AI.** Mock/stub output must always be labeled (`is_mock=True`, visible warnings). Never present canned or heuristic output as model inference, and never claim a model is running when it is not.
2. **Do not download AI models** or large weights unless the milestone explicitly says so.
3. **No system-wide changes.** Never use `sudo`, never install system packages, never modify files outside the NOVA project directory.
4. **Keep dependencies minimal.** Prefer the standard library. Every new dependency must be justified in pyproject.toml and mentioned in CHANGELOG.md. Do not install artifact libraries (python-docx, python-pptx, openpyxl, reportlab, pandas) until their milestone says so.
5. **Stay modular.** Subsystems communicate through the interfaces in `nova/models/base.py`, `nova/tools/__init__.py`, and `nova/artifacts/registry.py`. Do not hard-wire one subsystem into another; route through the orchestrator/router.

## Workflow

6. **Update ROADMAP.md** when a milestone's scope changes; **update CHANGELOG.md** for every user-visible change (Keep a Changelog format).
7. **Tests are mandatory.** Run `python3 -m unittest discover -s tests -v` before declaring any task complete. New functionality needs new tests.
8. **Commit atomically** with messages in the style of the existing `git log` (imperative, scoped, e.g. `Add model router with stub backend`).
9. **Config over code.** Anything tunable (model ids, paths, persona, limits) belongs in `config/nova.toml`, not hardcoded.

## Architecture guardrails

10. The LLM **decides WHAT** (which artifact to create/modify, which tool to call); specialized modules **perform the HOW** (file operations, tool execution). Never let a format library leak into the orchestrator or vice versa.
11. Artifact operations must respect path safety (`ArtifactEngine.safe_path`) — no writes outside workspace/output.
12. Real backends implement `ModelClient.generate()` and register on the `ModelRouter`; do not bypass the router.
13. The 8 GB RAM budget means one heavyweight model loaded at a time until proven otherwise.

## Definition of done for any task

- [ ] Code follows existing conventions in the package
- [ ] Tests written/updated and all passing
- [ ] CHANGELOG.md updated
- [ ] No fake functionality; mocks clearly labeled
- [ ] Nothing changed outside the project directory
