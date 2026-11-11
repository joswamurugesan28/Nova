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
import itertools
import random
import sys
import threading
import time

from nova import __version__
from nova.artifacts import ArtifactEngine
from nova.config import Settings, load_settings
from nova.core import Orchestrator
from nova.core.context_budget import ContextOverflowError
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
from nova.tools.executor import EventBus, ToolExecutor
from nova.tools.filesystem import register_filesystem_tools
from nova.tools.desktop import register_desktop_tools

MOCK_BANNER = (
    "!! MOCK MODEL BACKEND ACTIVE - NO REAL AI INFERENCE IS HAPPENING. !!\n"
    "!! Responses are canned placeholders (see nova/models/stub.py).    !!"
)

#: Status messages shown beside the spinner while a real model runs.
STATUS_MESSAGES = [
    "Thinking…",
    "Putting the “pro” in procrastination",
    "Thinking. Allegedly.",
    "Overthinking, as usual",
    "Confidently buffering",
    "Brain cell loading",
    "Stalling with style",
    "One neuron working",
    "Processing-ish",
    "Expertly delaying progress",
    "Almost having a thought",
    "Pretending to compute",
    "Delaying with purpose",
    "Making this complicated",
    "Vaguely doing math",
    "Dramatic pause initiated",
    "Loading questionable wisdom",
    "Reasoning-adjacent activity",
    "Precision-ish computing",
    "Calculating… very slowly",
    "Summoning fake urgency",
    "Consulting the tiny oracle",
    "Asking the hamster council",
    "Herding the digital cats",
    "Negotiating with the pixels",
    "Counting the imaginary gears",
    "Polishing a suspicious thought",
    "Searching the idea drawer",
    "Calibrating the sarcasm",
    "Consulting the cosmic paperwork",
    "Rebooting the thinking cap",
    "Mapping world dominance",
    "Bombaclating",
    "Making this sound intentional",
    "Rotating the problem",
    "My brain’s buffering",
]

#: Braille spinner frames, cycled to animate the single status line.
SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

#: Seconds the spinner waits between redraws while a request is in flight.
SPINNER_TICK_S = 0.08
#: Minimum/maximum seconds between status-message rotations.
STATUS_MIN_S = 1.0
STATUS_MAX_S = 2.0


def _stdout_is_tty() -> bool:
    """True only when stdout is a real terminal.

    Guarded with ``hasattr`` so capture streams (e.g. ``io.StringIO`` used
    in tests) that lack ``isatty`` never crash the CLI.
    """
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _select_status(previous: str | None) -> str:
    """Pick a random status message, never the same as ``previous``.

    Used by the thinking spinner so the status rotates without immediately
    repeating the message currently on screen.
    """
    candidates = [message for message in STATUS_MESSAGES if message != previous]
    return random.choice(candidates)


class _ThinkingSpinner:
    """Animated single-line status shown while a real model request runs.

    The spinner lives on one terminal line (carriage return, no newline) and
    rotates its status message every 1-2 seconds. It only draws on a real
    TTY; stub backends and piped output stay quiet.
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous: str | None = None
        self._last_message: str | None = None

    def start(self) -> None:
        """Begin animating on stdout. No-op when stdout is not a TTY."""
        if not _stdout_is_tty():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        spinner = itertools.cycle(SPINNER_CHARS)
        next_switch = time.monotonic() + random.uniform(STATUS_MIN_S, STATUS_MAX_S)
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_switch:
                self._last_message = _select_status(self._previous)
                self._previous = self._last_message
                next_switch = now + random.uniform(STATUS_MIN_S, STATUS_MAX_S)
            if self._last_message is None:
                # Wait for the first status selection before drawing.
                self._stop.wait(SPINNER_TICK_S)
                continue
            char = next(spinner)
            if _stdout_is_tty():
                sys.stdout.write(f"\r\033[2K{char} {self._last_message}")
                sys.stdout.flush()
            self._stop.wait(SPINNER_TICK_S)

    def stop(self, leave_final: bool = True) -> None:
        """Stop the animation.

        When ``leave_final`` is true and a status was drawn, the final status
        is left visible on its own line (terminated with a newline) so the
        response or error prints on the next line. Otherwise the line is
        cleared.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if not _stdout_is_tty():
            return
        if leave_final and self._last_message is not None:
            sys.stdout.write(f"\r\033[2K{self._last_message}\n")
        else:
            sys.stdout.write("\r\033[2K")
        sys.stdout.flush()


def build_orchestrator(settings: Settings) -> Orchestrator:
    """Wire the NOVA component graph from configuration (M1-A)."""
    router = build_router(settings.models)
    memory = ShortTermMemory(max_entries=50)
    personality = PersonalityEngine(settings.personality)
    artifacts = ArtifactEngine(settings.artifacts)
    artifacts.ensure_directories()
    tool_registry = ToolRegistry()
    register_filesystem_tools(tool_registry, settings.project_root)
    register_desktop_tools(tool_registry)
    return Orchestrator(
        router=router,
        personality=personality,
        memory=memory,
        tool_registry=tool_registry,
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
        spinner = None
        try:
            if not isinstance(brain, StubModelClient):
                spinner = _ThinkingSpinner()
                spinner.start()
            result = orch.handle(user_input)
        except ContextOverflowError as exc:
            if spinner is not None:
                spinner.stop(leave_final=True)
            print(f"[context too large] {exc}\n")
            continue
        except LlamaServerError as exc:
            if spinner is not None:
                spinner.stop(leave_final=True)
            # M1-B honesty rule: a failed real request is reported as a
            # failure. NOVA never silently swaps in the mock.
            print(f"[real backend unavailable] {exc}")
            print("NOVA did NOT fall back to the mock. Start llama-server "
                  "(see README 'Starting the brain') or set brain = \"stub\" "
                  "in config/nova.toml.\n")
            continue
        if spinner is not None:
            spinner.stop(leave_final=True)
        label = "nova(mock)" if result.is_mock else f"nova({result.model_id})"
        for observation in result.metadata.get("tool_observations", []):
            if observation.get("ok"):
                print(f"[tool ran: {observation.get('tool')}]")
            else:
                print(f"[tool error: {observation.get('error')}]")
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


def cmd_files(args: argparse.Namespace, settings: Settings) -> int:
    """Run the explicit filesystem tool loop (no model decision is implied)."""
    registry = ToolRegistry()
    root = args.root or settings.project_root
    register_filesystem_tools(registry, root)
    events = EventBus()
    events.subscribe("tool.started", lambda event: get_logger("tools").info(
        "tool started name=%s", event.data["tool"]))
    executor = ToolExecutor(registry, events)
    try:
        result = executor.execute(
            "filesystem.list_files", path=args.path,
        )
    except (OSError, ValueError) as exc:
        print(f"filesystem tool failed: {exc}", file=sys.stderr)
        return 1
    print(f"Files under {result['root']}:")
    for entry in result["entries"]:
        print(f"- {entry['path']} ({entry['size']} bytes)")
    if not result["entries"]:
        print("(no visible files)")
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
    files = sub.add_parser("files", help="list files through the read-only filesystem tool")
    files.add_argument("path", nargs="?", default=".", help="directory relative to project root")
    files.add_argument("--root", metavar="PATH", help="project root boundary (defaults to NOVA project)")
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
        "files": cmd_files,
    }
    return handlers[command](args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
