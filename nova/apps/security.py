"""Security helpers for Application Awareness."""

from __future__ import annotations

import secrets
from pathlib import Path


DEFAULT_TOKENS = {"", "nova-dev-token", "changeme", "password"}


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def is_weak_token(token: str) -> bool:
    return token in DEFAULT_TOKENS or len(token) < 16

def rotate_token(path: str) -> str:
    import json
    new = generate_token()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"token": new}))
    return new

def load_token(path: str) -> str:
    import json
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return json.loads(p.read_text()).get("token", "")
    except Exception:
        return ""


def safe_resolve(root: str | Path, target: str) -> Path:
    root_p = Path(root).resolve()
    if not root_p.exists():
        raise ValueError("project root does not exist")
    # reject absolute and traversal
    candidate = (root_p / target).resolve() if not Path(target).is_absolute() else None
    if candidate is None:
        raise PermissionError("absolute paths are not allowed")
    # ensure within root
    try:
        candidate.relative_to(root_p)
    except ValueError:
        raise PermissionError("path escapes project root")
    # symlink escape check
    if candidate.exists() and candidate.is_symlink():
        real = candidate.resolve()
        try:
            real.relative_to(root_p)
        except ValueError:
            raise PermissionError("symlink escapes project root")
    # also ensure no '..' components
    if ".." in Path(target).parts:
        raise PermissionError("path traversal detected")
    return candidate