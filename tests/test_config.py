import json
import os
import tempfile
import unittest
from pathlib import Path

from omarchy_recipes.core import RecipeError


class ConfigTests(unittest.TestCase):
    """Config storage and retrieval tests."""

    def setUp(self):
        # Create a fresh temp directory for each test
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = os.environ.get("OMARCHY_RECIPES_HOME")
        os.environ["OMARCHY_RECIPES_HOME"] = self._tmp.name
        # Clear cached modules to ensure fresh imports with new env var
        import sys
        for mod in ["omarchy_recipes.config", "omarchy_recipes.sources"]:
            sys.modules.pop(mod, None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("OMARCHY_RECIPES_HOME", None)
        else:
            os.environ["OMARCHY_RECIPES_HOME"] = self._saved
        self._tmp.cleanup()

    def _config(self):
        # Import config (modules were cleared in setUp)
        from omarchy_recipes import config
        return config

    def test_load_defaults_when_missing(self):
        """Load returns defaults when config file doesn't exist."""
        cfg = self._config()
        data = cfg.load()
        self.assertEqual(data["agent"]["provider"], "claude")
        self.assertIsNone(data["agent"]["models"]["claude"])
        self.assertIsNone(data["agent"]["models"]["copilot"])
        self.assertIsNone(data["agent"]["models"]["codex"])

    def test_save_and_load(self):
        """Config is persisted and reloaded correctly."""
        cfg = self._config()
        data = cfg.load()
        data["agent"]["provider"] = "copilot"
        data["agent"]["models"]["copilot"] = "gpt-4"
        cfg.save(data)

        loaded = cfg.load()
        self.assertEqual(loaded["agent"]["provider"], "copilot")
        self.assertEqual(loaded["agent"]["models"]["copilot"], "gpt-4")

    def test_get_returns_value(self):
        """Get retrieves config values by dotted path."""
        cfg = self._config()
        data = cfg.load()
        data["agent"]["provider"] = "codex"
        cfg.save(data)

        self.assertEqual(cfg.get("agent.provider"), "codex")

    def test_get_raises_on_missing_key(self):
        """Get raises when key path doesn't exist."""
        cfg = self._config()
        with self.assertRaises(RecipeError):
            cfg.get("agent.nonexistent")

    def test_set_provider(self):
        """Set stores a new provider value."""
        cfg = self._config()
        cfg.set_value("agent.provider", "copilot")
        self.assertEqual(cfg.get("agent.provider"), "copilot")

    def test_set_model_for_provider(self):
        """Set stores a model for a specific provider."""
        cfg = self._config()
        cfg.set_value("agent.models.claude", "claude-opus-4")
        self.assertEqual(cfg.get("agent.models.claude"), "claude-opus-4")

    def test_set_model_to_null(self):
        """Set can store null (provider picks its own)."""
        cfg = self._config()
        cfg.set_value("agent.models.codex", None)
        self.assertIsNone(cfg.get("agent.models.codex"))

    def test_set_rejects_unknown_provider(self):
        """Set rejects unknown provider names."""
        cfg = self._config()
        with self.assertRaises(RecipeError) as cm:
            cfg.set_value("agent.provider", "unknown-llm")
        self.assertIn("unknown provider", str(cm.exception))

    def test_set_rejects_unknown_key(self):
        """Set rejects unknown config keys."""
        cfg = self._config()
        with self.assertRaises(RecipeError) as cm:
            cfg.set_value("agent.secret_token", "abc123")
        self.assertIn("unknown config key", str(cm.exception))

    def test_set_requires_full_model_path(self):
        """Set requires dotted path for models."""
        cfg = self._config()
        with self.assertRaises(RecipeError) as cm:
            cfg.set_value("agent.models", "something")
        self.assertIn("agent.models.<provider>", str(cm.exception))

    def test_config_path_respects_omarchy_recipes_home(self):
        """Config path uses OMARCHY_RECIPES_HOME when set."""
        cfg = self._config()
        self.assertEqual(
            str(cfg.config_path()),
            os.path.join(self._tmp.name, "config.json"),
        )

    def test_merge_with_defaults(self):
        """Loading preserves unknown keys but fills in missing defaults."""
        cfg = self._config()
        config_file = cfg.config_path()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        # Write a minimal config
        config_file.write_text('{"agent": {"provider": "codex"}}\n')

        loaded = cfg.load()
        self.assertEqual(loaded["agent"]["provider"], "codex")
        self.assertIn("models", loaded["agent"])
        self.assertIsNone(loaded["agent"]["models"]["claude"])


if __name__ == "__main__":
    unittest.main()
