import contextlib
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from omarchy_recipes import agent, config

PROVIDERS = ("claude", "codex", "copilot")

# A minimal successful reply in each provider's own output format, so complete()
# gets as far as parsing and we can inspect the argv it built.
PROVIDER_REPLY = {
    "claude": json.dumps({"result": "ok"}),
    "codex": "ok",
    "copilot": json.dumps({"type": "assistant.message", "data": {"content": "ok"}}),
}

MANAGED_ENV = ("OMARCHY_RECIPES_HOME", "OMARCHY_RECIPES_AGENT", "OMARCHY_RECIPES_MODEL")


class _Runner:
    """Stands in for subprocess.run and records how the provider was invoked."""

    def __init__(self, stdout: str):
        self.stdout = stdout
        self.argv: list[str] = []
        self.stdin = None

    def __call__(self, argv, **kwargs):
        self.argv = list(argv)
        self.stdin = kwargs.get("input")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout=self.stdout, stderr="")

    def model(self):
        return self.argv[self.argv.index("--model") + 1] if "--model" in self.argv else None


class AgentTestCase(unittest.TestCase):
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

    @contextlib.contextmanager
    def invoked(self, provider, installed=PROVIDERS):
        """Run complete() without launching anything; yields the recorded call."""
        runner = _Runner(PROVIDER_REPLY[provider])
        found = {agent.PROVIDER_ARGV[p](None, "")[0] for p in installed}
        with mock.patch.object(agent.subprocess, "run", runner), \
             mock.patch.object(agent.shutil, "which", lambda cmd: cmd if cmd in found else None):
            yield runner


class ProviderRegistryTests(AgentTestCase):
    def test_all_three_providers_are_registered(self):
        self.assertEqual(set(agent.PROVIDER_ARGV), set(PROVIDERS))

    def test_providers_reports_copilot(self):
        self.assertIn("copilot", [p.name for p in agent.providers()])

    def test_copilot_denials_use_copilots_own_tool_names(self):
        """Regression: Claude's tool names match nothing in copilot's vocabulary.

        Handing copilot `DENIED_TOOLS` would look like a denial while leaving the
        model its shell, because not one of those names exists there.
        """
        self.assertFalse(set(agent.DENIED_TOOLS) & set(agent.COPILOT_DENIED_TOOLS))
        for expected in ("bash", "edit", "create", "web_fetch", "web_search", "task"):
            self.assertIn(expected, agent.COPILOT_DENIED_TOOLS)

    def test_variadic_tool_flag_stays_last(self):
        """A variadic flag that is not last silently eats the next argument."""
        for provider, flag in (("claude", "--disallowedTools"), ("copilot", "--excluded-tools")):
            with self.subTest(provider=provider):
                argv = agent.PROVIDER_ARGV[provider](None, "PROMPT")
                tail = argv[argv.index(flag) + 1:]
                self.assertTrue(tail, "flag has no values")
                self.assertFalse([t for t in tail if t.startswith("-")])


class PromptDeliveryTests(AgentTestCase):
    """How the prompt reaches each provider — argv or stdin, never neither."""

    def test_copilot_receives_the_prompt_as_the_value_of_p(self):
        """Regression: `copilot -p` with no value fails outright.

        copilot has no stdin mode, so the prompt has to travel in argv, directly
        after -p where exactly one flag consumes it.
        """
        with self.invoked("copilot") as run:
            agent.complete("WRITE ME A RECIPE", provider="copilot")
        self.assertEqual(run.argv[run.argv.index("-p") + 1], "WRITE ME A RECIPE")

    def test_stdin_providers_get_the_prompt_on_stdin_and_not_in_argv(self):
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                with self.invoked(provider) as run:
                    agent.complete("WRITE ME A RECIPE", provider=provider)
                self.assertEqual(run.stdin, "WRITE ME A RECIPE")
                self.assertNotIn("WRITE ME A RECIPE", run.argv)

    def test_argv_providers_are_not_left_inheriting_stdin(self):
        """An inherited stdin is something the child could block reading."""
        with self.invoked("copilot") as run:
            agent.complete("hello", provider="copilot")
        self.assertEqual(run.stdin, "")

    def test_every_provider_receives_the_prompt_somehow(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                with self.invoked(provider) as run:
                    agent.complete("UNIQUE-MARKER", provider=provider)
                self.assertTrue(
                    "UNIQUE-MARKER" in run.argv or run.stdin == "UNIQUE-MARKER",
                    f"{provider} never received the prompt",
                )


class ProviderResolutionTests(AgentTestCase):
    """flag > OMARCHY_RECIPES_AGENT > config agent.provider > first installed."""

    def test_flag_beats_env_and_config(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                other = next(p for p in PROVIDERS if p != provider)
                os.environ["OMARCHY_RECIPES_AGENT"] = other
                config.set_value("agent.provider", other)
                with self.invoked(provider) as run:
                    agent.complete("x", provider=provider)
                self.assertEqual(run.argv[0], agent.PROVIDER_ARGV[provider](None, "")[0])

    def test_env_beats_config(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                other = next(p for p in PROVIDERS if p != provider)
                config.set_value("agent.provider", other)
                os.environ["OMARCHY_RECIPES_AGENT"] = provider
                self.assertEqual(agent.default_provider(), provider)

    def test_config_beats_the_installed_fallback(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                config.set_value("agent.provider", provider)
                self.assertEqual(agent.default_provider(), provider)

    def test_falls_back_to_the_first_installed_provider(self):
        """Regression: an unconfigured provider must not resolve to "claude".

        With nothing configured and claude absent, the engine has to pick the
        provider that is actually on the machine.
        """
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                only = agent.PROVIDER_ARGV[provider](None, "")[0]
                with mock.patch.object(agent.shutil, "which", lambda c, only=only: c if c == only else None):
                    self.assertEqual(agent.default_provider(), provider)


class ModelResolutionTests(AgentTestCase):
    """flag > OMARCHY_RECIPES_MODEL > config agent.models.<provider> > None."""

    def test_flag_beats_env_and_config(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                os.environ["OMARCHY_RECIPES_MODEL"] = "from-env"
                config.set_value(f"agent.models.{provider}", "from-config")
                with self.invoked(provider) as run:
                    agent.complete("x", provider=provider, model="from-flag")
                self.assertEqual(run.model(), "from-flag")

    def test_env_beats_config(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                config.set_value(f"agent.models.{provider}", "from-config")
                os.environ["OMARCHY_RECIPES_MODEL"] = "from-env"
                self.assertEqual(agent.resolve_model(provider), "from-env")

    def test_config_is_used_when_no_flag_or_env(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                config.set_value(f"agent.models.{provider}", f"{provider}-model")
                with self.invoked(provider) as run:
                    agent.complete("x", provider=provider)
                self.assertEqual(run.model(), f"{provider}-model")

    def test_unset_model_lets_the_provider_choose(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertIsNone(agent.resolve_model(provider))
                with self.invoked(provider) as run:
                    agent.complete("x", provider=provider)
                self.assertIsNone(run.model())

    def test_model_is_per_provider(self):
        """A model set for one provider must not leak into another."""
        config.set_value("agent.models.claude", "claude-only")
        self.assertEqual(agent.resolve_model("claude"), "claude-only")
        self.assertIsNone(agent.resolve_model("codex"))
        self.assertIsNone(agent.resolve_model("copilot"))


class CopilotOutputTests(AgentTestCase):
    def test_takes_the_last_assistant_message(self):
        stream = "\n".join([
            json.dumps({"type": "session.mcp_servers_loaded", "data": {}}),
            json.dumps({"type": "assistant.message", "data": {"content": "first"}}),
            json.dumps({"type": "model.turn_ended", "data": {}}),
            json.dumps({"type": "assistant.message", "data": {"content": "final"}}),
        ])
        self.assertEqual(agent._extract_copilot_response(stream), "final")

    def test_skips_unparsable_lines(self):
        stream = "not json\n" + json.dumps({"type": "assistant.message", "data": {"content": "ok"}})
        self.assertEqual(agent._extract_copilot_response(stream), "ok")

    def test_a_stream_with_no_message_is_an_error(self):
        from omarchy_recipes.core import RecipeError
        with self.assertRaises(RecipeError):
            agent._extract_copilot_response(json.dumps({"type": "model.turn_ended", "data": {}}))


if __name__ == "__main__":
    unittest.main()
