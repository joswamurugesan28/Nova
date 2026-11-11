"""Intelligent interface selection."""

from __future__ import annotations


def select_interface(profile, preferred=("scripting", "api", "cli", "filesystem", "gui")):
    # profile.mechanisms contains available mechanisms
    for mech in preferred:
        if mech in profile.mechanisms:
            return mech
    return None