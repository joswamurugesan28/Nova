"""NOVA command-line interface.

Commands:
    nova chat       interactive REPL (default when no command given)
    nova routes     show model routing table
    nova artifacts  show Artifact Engine status
    nova config     print effective configuration
    nova version    print version

M0 honesty guarantee: if any response comes from the mock backend the
CLI prints a clear warning that no real inference occurred.
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
from nova.personality import PersonalityEngine
from nova.tools import ToolRegistry

MOCK_BANNER = (
    "!! MOCK MODEL BACKEND ACTIVE - NO REAL AI INFERENCE IS HAPPENING. !!\n"
    "!! Responses are canned placeholders (see nova/models/stub.py).    !!"
)


def build_orchestrator(settings: Settings) -> Orchestrator:
    """Wire the M0 component graph from configuration."""
    router = ModelRouter.with_stub()
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
    print(f"{settings.app_name} v{settings.app_version} (M0 scaffold)")
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

        result = orch.handle(user_input)
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
    return 0


def cmd_version(args: argparse.Namespace, settings: Settings) -> int:
    print(f"NOVA {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nova",
        description="NOVA - Neural Operations & Vision Assistant (M0 scaffold)",
    )
    parser.add_argument("--config", metavar="PATH",
                        help="path to a TOML config file (default: config/nova.toml)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("chat", help="interactive chat (mock backend in M0)")
    sub.add_parser("routes", help="show model routing table")
    sub.add_parser("artifacts", help="show Artifact Engine status")
    sub.add_parser("config", help="print effective configuration")
    sub.add_parser("version", help="print version")
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
        "version": cmd_version,
    }
    return handlers[command](args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
