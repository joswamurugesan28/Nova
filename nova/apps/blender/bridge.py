"""Blender bridge client (localhost)."""

from __future__ import annotations

import json, urllib.request, urllib.error
from typing import Any


class BlenderBridgeError(Exception):
    pass


class BlenderBridge:
    def __init__(self, host="127.0.0.1", port=47822, token="", timeout=5.0):
        self.base_url = f"http://{host}:{port}"
        self.token = token
        self.timeout = timeout

    def _request(self, path, method="GET", payload=None):
        url = self.base_url + path
        data = None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode()
        except Exception as exc:
            raise BlenderBridgeError(str(exc)) from exc
        return json.loads(raw)

    def scene(self):
        return self._request("/scene")

    def objects(self):
        return self._request("/objects")

    def create_object(self, obj_type, name):
        return self._request("/object/create", method="POST", payload={"type": obj_type, "name": name})

    def delete_object(self, name):
        return self._request("/object/delete", method="POST", payload={"name": name})