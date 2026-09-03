import json
import os
import tempfile
import unittest

from omarchy_recipes import config
from omarchy_recipes.core import RecipeError

# Environment the config layer reads. Saved and restored around every test so a
# developer's own settings are never read and never written.
MANAGED_ENV = ("OMARCHY_RECIPES_HOME", "OMARCHY_RECIPES_AGENT", "OMARCHY_RECIPES_MODEL")


class ConfigTestCase(unittest.TestCase):
    """Redirects the config root at a throwaway directory.

    Mirrors how `test_core.py` redirects `OMARCHY_RECIPES_HOME`: without it the
    suite would read, and `set` would overwrite, the real `config.json`.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = {name: os.environ.get(name) for name in MANAGED_ENV}
        for name in MANAGED_ENV:
            os.environ.pop(name, None)
        os.environ["OMARCHY_RECIPES_HOME"] = self._tmp.name

    def tearDown(self):
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self._tmp.cleanup()


class ConfigTests(ConfigTestCase):
    def test_config_path_is_inside_the_redirected_workspace(self):
        self.assertEqual(str(config.config_path()), os.path.join(self._tmp.name, "config.json"))

    def test_absent_file_is_not_an_error(self):
        """The ordinary state before anything is configured."""
        self.assertFalse(config.config_path().exists())
        data = config.load()
        self.assertIsNone(data["agent"]["provider"])

    def test_unconfigured_provider_is_null_not_a_provider_name(self):
        """Null is what keeps the "first installed provider" fallback reachable.

        Shipping a literal "claude" here would make that fallback dead code and
        break a machine that has codex but not claude.
        """
        self.assertIsNone(config.load()["agent"]["provider"])

    def test_models_has_a_slot_for_every_registered_provider(self):
        from omarchy_recipes import agent
        self.assertEqual(
            set(config.load()["agent"]["models"]),
            set(agent.PROVIDER_ARGV),
        )

    def test_round_trips_through_disk(self):
        config.set_value("agent.provider", "copilot")
        config.set_value("agent.models.copilot", "gpt-5")
        reloaded = json.loads(config.config_path().read_text())
        self.assertEqual(reloaded["agent"]["provider"], "copilot")
        self.assertEqual(reloaded["agent"]["models"]["copilot"], "gpt-5")

    def test_get_reads_a_dotted_path(self):
        config.set_value("agent.provider", "codex")
        self.assertEqual(config.get("agent.provider"), "codex")

    def test_get_rejects_an_unknown_key(self):
        with self.assertRaises(RecipeError) as cm:
            config.get("agent.nonexistent")
        self.assertIn("unknown config key", str(cm.exception))

    def test_singular_model_alias_is_accepted(self):
        """`agent.model.claude` is the spelling the CLI help advertises."""
        config.set_value("agent.model.claude", "claude-sonnet-4.5")
        self.assertEqual(config.get("agent.models.claude"), "claude-sonnet-4.5")
        self.assertEqual(config.get("agent.model.claude"), "claude-sonnet-4.5")

    def test_null_clears_a_setting(self):
        config.set_value("agent.provider", "codex")
        config.set_value("agent.provider", None)
        self.assertIsNone(config.get("agent.provider"))

    def test_partial_file_is_filled_in_from_defaults(self):
        config.config_path().parent.mkdir(parents=True, exist_ok=True)
        config.config_path().write_text('{"agent": {"provider": "codex"}}\n')
        data = config.load()
        self.assertEqual(data["agent"]["provider"], "codex")
        self.assertIsNone(data["agent"]["models"]["claude"])

    def test_corrupt_file_is_an_error_not_a_silent_default(self):
        """A typo in the file must not look like "nothing configured"."""
        config.config_path().parent.mkdir(parents=True, exist_ok=True)
        config.config_path().write_text("{not json")
        with self.assertRaises(RecipeError) as cm:
            config.load()
        self.assertIn("not valid JSON", str(cm.exception))

    def test_load_never_returns_shared_mutable_state(self):
        """Two loads must not alias each other, or one caller edits the next."""
        first = config.load()
        first["agent"]["models"]["claude"] = "mutated"
        self.assertIsNone(config.load()["agent"]["models"]["claude"])


class ConfigRejectionTests(ConfigTestCase):
    """Invalid input is refused before anything reaches the disk."""

    def test_rejects_unknown_provider(self):
        with self.assertRaises(RecipeError) as cm:
            config.set_value("agent.provider", "bogus")
        self.assertIn("unknown provider", str(cm.exception))

    def test_rejects_model_for_unknown_provider(self):
        with self.assertRaises(RecipeError):
            config.set_value("agent.models.bogus", "x")

    def test_rejects_unknown_key(self):
        with self.assertRaises(RecipeError) as cm:
            config.set_value("agent.api_key", "sk-secret")
        self.assertIn("unknown config key", str(cm.exception))

    def test_rejects_unknown_top_level_key(self):
        with self.assertRaises(RecipeError):
            config.set_value("telemetry.enabled", "true")

    def test_rejects_bare_models_key(self):
        with self.assertRaises(RecipeError) as cm:
            config.set_value("agent.models", "something")
        self.assertIn("agent.models.<provider>", str(cm.exception))

    def test_a_rejected_set_does_not_touch_the_file(self):
        config.set_value("agent.provider", "codex")
        before = config.config_path().read_text()
        for key, value in (
            ("agent.provider", "bogus"),
            ("agent.api_key", "sk-secret"),
            ("agent.models", "x"),
        ):
            with self.subTest(key=key):
                with self.assertRaises(RecipeError):
                    config.set_value(key, value)
                self.assertEqual(config.config_path().read_text(), before)


class ConfigSchemaTests(ConfigTestCase):
    """The schema must stay free of anywhere to put a credential."""

    def test_no_secret_shaped_field_exists(self):
        def keys(node, prefix=""):
            if not isinstance(node, dict):
                return []
            found = []
            for key, value in node.items():
                path = f"{prefix}{key}"
                found.append(path)
                found.extend(keys(value, prefix=f"{path}."))
            return found

        banned = ("key", "token", "secret", "password", "credential", "auth")
        for path in keys(config.load()):
            for word in banned:
                self.assertNotIn(
                    word, path.lower(),
                    f"{path!r} looks like credential storage; provider CLIs own auth",
                )


if __name__ == "__main__":
    unittest.main()
