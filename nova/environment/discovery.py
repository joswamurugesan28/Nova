from __future__ import annotations

import shutil
from nova.apps.discovery import _which_any


def discover_software(names: list[str]) -> dict[str, bool]:
    return {n: _which_any([n]) for n in names}