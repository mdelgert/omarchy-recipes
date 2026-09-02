import os
import sys
import tempfile
import unittest

from omarchy_recipes.core import RecipeError


class AgentProviderTests(unittest.TestCase):
    """Tests for agent provider and model resolution."""

    def setUp(self):
        # Create a fresh temp directory for tests
        self._tmp = tempfile.TemporaryDirectory()
        self._saved_home = os.environ.get("OMARCHY_RECIPES_HOME")
        self._saved_agent = os.environ.get("OMARCHY_RECIPES_AGENT")
        os.environ["OMARCHY_RECIPES_HOME"] = self._tmp.name
        # Clear cached modules
        for mod in ["omarchy_recipes.agent", "omarchy_recipes.config", "omarchy_recipes.sources"]:
            sys.modules.pop(mod, None)

    def tearDown(self):
        if self._saved_home is None:
            os.environ.pop("OMARCHY_RECIPES_HOME", None)
        else:
            os.environ["OMARCHY_RECIPES_HOME"] = self._saved_home

        if self._saved_agent is None:
            os.environ.pop("OMARCHY_RECIPES_AGENT", None)
        else:
            os.environ["OMARCHY_RECIPES_AGENT"] = self._saved_agent

        self._tmp.cleanup()

    def test_providers_list_includes_copilot(self):
        """providers() includes copilot when copilot CLI is installed."""
        from omarchy_recipes import agent
        providers = agent.providers()
        provider_names = [p.name for p in providers]
        self.assertIn("claude", provider_names)
        self.assertIn("codex", provider_names)
        self.assertIn("copilot", provider_names)

    def test_default_provider_prefers_env_var(self):
        """default_provider() prefers OMARCHY_RECIPES_AGENT env var."""
        os.environ["OMARCHY_RECIPES_AGENT"] = "codex"
        from omarchy_recipes import agent
        self.assertEqual(agent.default_provider(), "codex")

    def test_default_provider_uses_config(self):
        """default_provider() falls back to config when env var is not set."""
        from omarchy_recipes import config
        config.set_value("agent.provider", "copilot")
        os.environ.pop("OMARCHY_RECIPES_AGENT", None)

        # Reimport agent to pick up new config
        if "omarchy_recipes.agent" in sys.modules:
            del sys.modules["omarchy_recipes.agent"]
        from omarchy_recipes import agent
        self.assertEqual(agent.default_provider(), "copilot")

    def test_resolve_model_returns_configured_model(self):
        """resolve_model() returns configured model for provider."""
        from omarchy_recipes import config, agent
        config.set_value("agent.models.claude", "claude-opus-4")

        # Reimport to pick up config
        if "omarchy_recipes.agent" in sys.modules:
            del sys.modules["omarchy_recipes.agent"]
        from omarchy_recipes import agent
        model = agent.resolve_model("claude")
        self.assertEqual(model, "claude-opus-4")

    def test_resolve_model_returns_none_when_not_configured(self):
        """resolve_model() returns None when model is not configured (let provider pick)."""
        from omarchy_recipes import agent
        model = agent.resolve_model("claude")
        self.assertIsNone(model)

    def test_resolve_model_uses_default_provider(self):
        """resolve_model() uses default_provider when provider not specified."""
        from omarchy_recipes import config, agent
        config.set_value("agent.provider", "codex")
        config.set_value("agent.models.codex", "custom-model")

        # Reimport
        if "omarchy_recipes.agent" in sys.modules:
            del sys.modules["omarchy_recipes.agent"]
        from omarchy_recipes import agent
        os.environ.pop("OMARCHY_RECIPES_AGENT", None)
        model = agent.resolve_model()
        self.assertEqual(model, "custom-model")

    def test_copilot_argv_builder(self):
        """_copilot_argv() builds correct command line."""
        from omarchy_recipes import agent
        argv = agent._copilot_argv(None)
        self.assertEqual(argv[0], "copilot")
        self.assertIn("-p", argv)
        self.assertIn("--output-format", argv)
        self.assertIn("json", argv)
        self.assertIn("--deny-tool", argv)

    def test_copilot_argv_with_model(self):
        """_copilot_argv() includes --model when specified."""
        from omarchy_recipes import agent
        argv = agent._copilot_argv("gpt-4")
        self.assertIn("--model", argv)
        idx = argv.index("--model")
        self.assertEqual(argv[idx + 1], "gpt-4")

    def test_claude_argv_builder(self):
        """_claude_argv() builds correct command line."""
        from omarchy_recipes import agent
        argv = agent._claude_argv(None)
        self.assertEqual(argv[0], "claude")
        self.assertIn("-p", argv)
        self.assertIn("--output-format", argv)
        self.assertIn("json", argv)
        self.assertIn("--disallowedTools", argv)

    def test_provider_argv_registry(self):
        """PROVIDER_ARGV contains all known providers."""
        from omarchy_recipes import agent
        expected = {"claude", "copilot", "codex"}
        self.assertEqual(set(agent.PROVIDER_ARGV.keys()), expected)


if __name__ == "__main__":
    unittest.main()
