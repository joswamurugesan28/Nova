"""Tests for nova.config: TOML loading, defaults, validation, env override."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nova.config import (
    ConfigError,
    PersonalitySettings,
    Settings,
    load_settings,
    with_overrides,
)


class LoadSettingsTests(unittest.TestCase):
    def test_default_config_file_loads(self) -> None:
        settings = load_settings()
        self.assertEqual(settings.app_name, "NOVA")
        self.assertIn(settings.config_path.name, "nova.toml")
        # M1-B: the real llama-server brain is the configured default;
        # "stub" remains available by editing config/nova.toml (no code change).
        self.assertIn(settings.models.brain, ("stub", "llama-server"))
        self.assertTrue(settings.models.llama_server.enabled in (True, False))
        self.assertIn(settings.logging.level, ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))

    def test_explicit_path_loads_and_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "custom.toml"
            cfg.write_text(
                '[app]\nname = "NOVA-test"\n'
                '[logging]\nlevel = "DEBUG"\n'
                '[models]\nbrain = "qwen3-4b"\n',
                encoding="utf-8",
            )
            settings = load_settings(cfg)
            self.assertEqual(settings.app_name, "NOVA-test")
            self.assertEqual(settings.logging.level, "DEBUG")
            self.assertEqual(settings.models.brain, "qwen3-4b")

    def test_missing_explicit_path_raises(self) -> None:
        with self.assertRaises(ConfigError):
            load_settings("/nonexistent/nova-config.toml")

    def test_invalid_toml_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "broken.toml"
            cfg.write_text("this is [not valid toml", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_settings(cfg)

    def test_invalid_log_level_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "badlevel.toml"
            cfg.write_text('[logging]\nlevel = "LOUD"\n', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_settings(cfg)

    def test_env_var_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "env.toml"
            cfg.write_text('[app]\nname = "from-env"\n', encoding="utf-8")
            old = os.environ.get("NOVA_CONFIG")
            os.environ["NOVA_CONFIG"] = str(cfg)
            try:
                settings = load_settings()
            finally:
                if old is None:
                    os.environ.pop("NOVA_CONFIG", None)
                else:
                    os.environ["NOVA_CONFIG"] = old
            self.assertEqual(settings.app_name, "from-env")


class SettingsHelpersTests(unittest.TestCase):
    def test_with_overrides_returns_modified_copy(self) -> None:
        base = Settings()
        tweaked = with_overrides(base, personality=PersonalitySettings(name="OTHER"))
        self.assertEqual(base.personality.name, "NOVA")
        self.assertEqual(tweaked.personality.name, "OTHER")

    def test_with_overrides_rejects_unknown_field(self) -> None:
        with self.assertRaises(ConfigError):
            with_overrides(Settings(), bogus={})

    def test_relative_paths_resolve_under_project_root(self) -> None:
        from nova.config import PROJECT_ROOT

        settings = Settings()
        self.assertTrue(str(settings.logging.path).startswith(str(PROJECT_ROOT)))
        self.assertTrue(settings.artifacts.output_path.is_absolute())


if __name__ == "__main__":
    unittest.main()
