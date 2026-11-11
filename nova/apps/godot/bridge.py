"""NOVA-side client for the Godot EditorPlugin localhost bridge."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class GodotBridgeError(Exception):
    pass


class GodotBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 47821,
                 token: str = "", timeout: float = 5.0) -> None:
        self.base_url = f"http://{host}:{port}"
        self.token = token
        self.timeout = timeout

    def _request(self, path: str, method: str = "GET",
                 payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        data = None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_bytes = resp.read(1_048_576 + 1)
                if len(raw_bytes) > 1_048_576:
                    raise GodotBridgeError("response too large")
                raw = raw_bytes.decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise GodotBridgeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc
        except Exception as exc:
            raise GodotBridgeError(str(exc)) from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GodotBridgeError(f"invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise GodotBridgeError("response is not a JSON object")
        return parsed

    def health(self) -> dict[str, Any]:
        return self._request("/health")

    def project(self) -> dict[str, Any]:
        return self._request("/project")

    def scene(self) -> dict[str, Any]:
        return self._request("/scene")

    def scene_tree(self) -> dict[str, Any]:
        return self._request("/scene_tree")

    def selected_node(self) -> dict[str, Any]:
        return self._request("/selected_node")

    def read_script(self, path: str) -> dict[str, Any]:
        return self._request("/script/read", method="POST", payload={"path": path})

    def write_script(self, path: str, content: str) -> dict[str, Any]:
        return self._request("/script/write", method="POST", payload={"path": path, "content": content})

    def create_scene(self, path: str) -> dict[str, Any]:
        return self._request("/scene/create", method="POST", payload={"path": path})

    def run_project(self) -> dict[str, Any]:
        return self._request("/run", method="POST")

    def stop_project(self) -> dict[str, Any]:
        return self._request("/stop", method="POST")