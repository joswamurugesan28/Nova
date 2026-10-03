"""NOVA command-line interface.

Commands:
    nova chat         interactive REPL (default when no command given)
    nova routes       show model routing table
    nova artifacts    show Artifact Engine status
    nova config       print effective configuration
    nova model status check llama-server reachability (never starts it)
    nova version      print version

Honesty guarantee: if the active backend is the mock stub, the CLI
prints a clear warning that no real inference occurred. The llama-server
backend (M1-A) is a real inference client, but only used when the user
explicitly enables it AND a manually started llama-server is reachable.
"""

from __future__ import annotations

import argparse
import sys

from nova import __version__
from nova.artifacts import ArtifactEngine
from nova.config import Settings, load_settings
from nova.core import Orchestrator
from nova.logging_setup import get_logger, setup_logging
from nova.memory import ShortTermMemory
from nova.models import ModelRouter, TaskType
from nova.models import (
    LlamaServerClient,
    LlamaServerError,
    ModelRouter,
    StubModelClient,
    TaskType,
    active_backend_name,
    build_router,
)
from nova.personality import PersonalityEngine
from nova.tools import ToolRegistry

MOCK_BANNER = (
    "!! MOCK MODEL BACKEND ACTIVE - NO REAL AI INFERENCE IS HAPPENING. !!\n"
    "!! Responses are canned placeholders (see nova/models/stub.py).    !!"
)


def build_orchestrator(settings: Settings) -> Orchestrator:
    """Wire the NOVA component graph from configuration (M1-A)."""
    router = build_router(settings.models)
    memory = ShortTermMemory(max_entries=50)
    personality = PersonalityEngine(settings.personality)
    artifacts = ArtifactEngine(settings.artifacts)
    artifacts.ensure_directories()
    return Orchestrator(
        router=router,
        personality=personality,
        memory=memory,
        tool_registry=ToolRegistry(),
        artifacts=artifacts,
    )


def cmd_chat(args: argparse.Namespace, settings: Settings) -> int:
    orch = build_orchestrator(settings)
    brain = orch.router.resolve(TaskType.CHAT)
    print(f"{settings.app_name} v{settings.app_version} - brain backend: "
          f"{brain.describe()}")
    if isinstance(brain, StubModelClient):
        print(MOCK_BANNER)
    print("Type /help for commands, /exit to quit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return 0

        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            print("bye.")
            return 0
        if user_input == "/help":
            print("commands: /help /memory /routes /clear /exit")
            continue
        if user_input == "/memory":
            for line in orch.memory.to_context():
                print(f"  {line}")
            continue
        if user_input == "/routes":
            _print_routes(orch.router)
            continue
        if user_input == "/clear":
            orch.memory.clear()
            print("memory cleared.")
            continue

        result = None
        try:
            result = orch.handle(user_input)
        except LlamaServerError as exc:
            # M1-B honesty rule: a failed real request is reported as a
            # failure. NOVA never silently swaps in the mock.
            print(f"[real backend unavailable] {exc}")
            print("NOVA did NOT fall back to the mock. Start llama-server "
                  "(see README 'Starting the brain') or set brain = \"stub\" "
                  "in config/nova.toml.\n")
            continue
        label = "nova(mock)" if result.is_mock else f"nova({result.model_id})"
        print(f"{label}> {result.text}\n")


def _print_routes(router: ModelRouter) -> None:
    for task in TaskType:
        if router.has_client(task):
            client = router.resolve(task)
            print(f"  {task.value:<10} -> {client.describe()}")
        else:
            print(f"  {task.value:<10} -> (not registered)")


def cmd_routes(args: argparse.Namespace, settings: Settings) -> int:
    orch = build_orchestrator(settings)
    print("Model routing table:")
    _print_routes(orch.router)
    return 0


def cmd_artifacts(args: argparse.Namespace, settings: Settings) -> int:
    engine = ArtifactEngine(settings.artifacts)
    engine.ensure_directories()
    formats = engine.supported_formats()
    print("Artifact Engine status:")
    print(f"  workspace : {engine.workspace}")
    print(f"  templates : {engine.templates}")
    print(f"  output    : {engine.output}")
    print(f"  handlers  : {', '.join('.' + f for f in formats) if formats else 'none registered yet (planned M3+)'}")
    print("  planned   : docx pptx xlsx pdf csv images templates general")
    return 0


def cmd_config(args: argparse.Namespace, settings: Settings) -> int:
    print(f"config path : {settings.config_path or '(built-in defaults)'}")
    print(f"project root: {settings.project_root}")
    print(f"app         : {settings.app_name} v{settings.app_version}")
    print(f"log level   : {settings.logging.level} -> {settings.logging.path}")
    print(f"personality : {settings.personality.name} ({settings.personality.style})")
    print("models      :")
    for task in TaskType:
        key = "brain" if task is TaskType.CHAT else task.value
        print(f"  {task.value:<10} -> {getattr(settings.models, key)}")
    ls = settings.models.llama_server
    print("llama-server :")
    print(f"  enabled    : {ls.enabled}")
    print(f"  base_url   : {ls.base_url}")
    print(f"  model      : {ls.model}")
    print(f"  timeout    : {ls.timeout_seconds}s (health {ls.health_timeout_seconds}s)")
    print(f"  ctx/temp   : {ls.context_size} / {ls.temperature} (max_tokens {ls.max_tokens})")
    return 0


def cmd_model(args: argparse.Namespace, settings: Settings) -> int:
    """Model backend diagnostics. NEVER starts a server (exit 0=reachable,
    1=not reachable)."""
    if args.model_command != "status":
        print(f"unknown model command: {args.model_command}", file=sys.stderr)
        return 2

    ls = settings.models.llama_server
    client = LlamaServerClient(ls, base_url=args.url) if args.url \
        else LlamaServerClient(ls)
    status = client.check_health()
    state = "RUNNING" if status.healthy else "NOT RUNNING"

    print("Backend: llama-server")
    print(f"URL: {client.base_url}")
    print(f"Model: {ls.model}")
    print(f"Enabled: {'yes' if ls.enabled else 'no'} "
          f"(brain backend: {settings.models.brain}; "
          f"active: {active_backend_name(build_router(settings.models))})")
    print(f"Status: {state} ({status.detail})")
    print("Note: NOVA never starts llama-server automatically.")
    return 0 if status.healthy else 1


def cmd_version(args: argparse.Namespace, settings: Settings) -> int:
    print(f"NOVA {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nova",
        description="NOVA - Neural Operations & Vision Assistant (M1-A)",
    )
    parser.add_argument("--config", metavar="PATH",
                        help="path to a TOML config file (default: config/nova.toml)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("chat", help="interactive chat (mock backend by default)")
    sub.add_parser("routes", help="show model routing table")
    sub.add_parser("artifacts", help="show Artifact Engine status")
    sub.add_parser("config", help="print effective configuration")
    sub.add_parser("version", help="print version")
    model = sub.add_parser("model", help="model backend diagnostics")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    status = model_sub.add_parser(
        "status", help="check whether llama-server is reachable "
                       "(never starts it)"
    )
    status.add_argument("--url", metavar="URL",
                        help="override the configured base URL for this check")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config)
    except Exception as exc:  # config errors are user-facing
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.logging)
    get_logger("cli").info("nova started command=%s", args.command or "chat")

    command = args.command or "chat"
    handlers = {
        "chat": cmd_chat,
        "routes": cmd_routes,
        "artifacts": cmd_artifacts,
        "config": cmd_config,
        "model": cmd_model,
        "version": cmd_version,
    }
    return handlers[command](args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
