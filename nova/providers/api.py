from __future__ import annotations
from .base import Provider


class APIProvider(Provider):
    name = "api"

    def __init__(self, permissions, audit=None, base_url="", token=""):
        super().__init__(permissions, audit)
        self.base_url = base_url
        self.token = token