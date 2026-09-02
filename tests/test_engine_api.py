"""Tests for the JSON engine API the Omarchy frontend consumes.

Every case runs the real CLI against a temporary root built from
`tests/fixtures/recipes/`, with HOME, XDG_CONFIG_HOME, and XDG_STATE_HOME
redirected into the temporary directory. Nothing here touches the developer's
own configuration or state.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "omarchy-recipes"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "recipes"
SCHEMA_VERSION = 1


class EngineApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / "root"
        (self.root / "recipes").mkdir(parents=True)
        shutil.copytree(FIXTURES, self.root / "recipes" / "fixtures")
        # The engine hands recipes OMARCHY_RECIPES_LIB from the root, so the
        # temporary root needs the real helper library.
        shutil.copytree(ROOT / "lib", self.root / "lib")

        self.home = base / "home"
        self.config = base / "config"
        self.state = base / "state"
        self.home.mkdir()
        self.config.mkdir()
        self.env = {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_STATE_HOME": str(self.state),
            "OMARCHY_RECIPES_ROOT": str(self.root),
        }

    def tearDown(self):
        self._tmp.cleanup()

    # ---- helpers ---------------------------------------------------------

    def cli(self, *args):
        merged = os.environ.copy()
        merged.update(self.env)
        return subprocess.run([str(CLI), *args], cwd=ROOT, env=merged, text=True, capture_output=True)

    def json_cli(self, *args):
        proc = self.cli(*args)
        try:
            payload = json.loads(proc.stdout)
        except ValueError:  # pragma: no cover - only on a real regression
            self.fail(f"non-JSON output for {args}: {proc.stdout!r} {proc.stderr!r}")
        self.assertEqual(payload.get("schemaVersion"), SCHEMA_VERSION, payload)
        return proc, payload

    def apply_typed(self, **overrides):
        values = {"timeout": "600", "mode": "balanced", "enabled": "true", "note": "hi", "directory": str(self.config / "fixture")}
        values.update(overrides)
        args = []
        for name, value in values.items():
            args += [f"--{name}", value]
        return self.json_cli("run", "--json", "fixture-typed", *args)

    @property
    def target(self):
        return self.config / "fixture" / "typed.conf"

    # ---- discovery -------------------------------------------------------

    def test_list_reports_categories_and_skips_malformed(self):
        proc, payload = self.json_cli("list", "--json")
        self.assertEqual(proc.returncode, 0)
        ids = [r["id"] for r in payload["recipes"]]
        self.assertEqual(ids, ["fixture-noparams", "fixture-failing", "fixture-typed"])

        categories = [r["category"] for r in payload["recipes"]]
        self.assertEqual(categories, ["Diagnostics", "Failures", "Fixtures"])

        # The malformed recipe is reported, not silently dropped, and it does
        # not prevent the other three from loading.
        self.assertEqual(len(payload["problems"]), 1)
        self.assertIn("broken-metadata.sh", payload["problems"][0]["path"])
        self.assertIn("missing metadata", payload["problems"][0]["error"])

    def test_validate_fails_on_malformed_recipe(self):
        proc, payload = self.json_cli("validate", "--json")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["problems"]), 1)

    def test_info_exposes_normalized_parameter_metadata(self):
        _, payload = self.json_cli("info", "--json", "fixture-typed")
        params = {p["name"]: p for p in payload["recipe"]["parameters"]}
        self.assertEqual(params["timeout"]["type"], "integer")
        self.assertEqual(params["timeout"]["min"], 60)
        self.assertEqual(params["timeout"]["max"], 7200)
        self.assertEqual(params["timeout"]["default"], 600)
        self.assertEqual(params["mode"]["choices"], ["performance", "balanced", "powersave"])
        self.assertIs(params["enabled"]["default"], True)
        self.assertTrue(params["directory"]["required"])
        # A label is always present so a frontend never has to invent one.
        self.assertEqual(params["timeout"]["label"], "Timeout")

    def test_unknown_recipe_reports_error_as_json(self):
        proc, payload = self.json_cli("info", "--json", "does-not-exist")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not found", payload["error"])

    # ---- parameter validation -------------------------------------------

    def test_integer_parameter_is_range_checked(self):
        proc, payload = self.apply_typed(timeout="10")
        self.assertEqual(proc.returncode, 2)
        self.assertIn(">= 60", payload["error"])

        proc, payload = self.apply_typed(timeout="not-a-number")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must be an integer", payload["error"])

    def test_choice_parameter_rejects_undeclared_value(self):
        proc, payload = self.apply_typed(mode="warp")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must be one of", payload["error"])

    def test_boolean_parameter_round_trips(self):
        proc, payload = self.apply_typed(enabled="false")
        self.assertEqual(proc.returncode, 0, payload)
        self.assertIs(payload["run"]["parameters"]["enabled"], False)
        self.assertIn("enabled=false", self.target.read_text())

    def test_missing_required_parameter_is_reported(self):
        proc = self.cli("check", "--json", "fixture-typed")
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing required parameter --directory", payload["error"])

    # ---- check protocol --------------------------------------------------

    def test_check_reports_declared_state_without_recording_a_run(self):
        _, payload = self.json_cli(
            "check", "--json", "fixture-typed", "--directory", str(self.config / "fixture")
        )
        run = payload["run"]
        self.assertEqual(run["state"], "not-configured")
        self.assertEqual(run["summary"], "nothing written yet")
        # The state markers are stripped from what a frontend displays.
        self.assertNotIn("@recipe.state", run["stdout"])
        # A check must not accumulate run directories: a browser checks state
        # every time a recipe is selected.
        self.assertIsNone(run["run_dir"])
        _, history = self.json_cli("history", "--json", "fixture-typed")
        self.assertEqual(history["runs"], [])

    def test_failed_check_is_reported_as_error_state(self):
        proc, payload = self.json_cli("check", "--json", "fixture-failing")
        self.assertNotEqual(proc.returncode, 0)
        run = payload["run"]
        self.assertEqual(run["state"], "error")
        self.assertEqual(run["status"], "failed")
        self.assertIn("dependency missing", run["stderr"])

    def test_recipe_without_parameters_checks_and_applies(self):
        _, payload = self.json_cli("check", "--json", "fixture-noparams")
        self.assertEqual(payload["run"]["state"], "configured")

        proc, payload = self.json_cli("run", "--json", "fixture-noparams")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["run"]["status"], "success")
        self.assertEqual(payload["run"]["parameters"], {})

    # ---- apply / failure -------------------------------------------------

    def test_successful_apply_records_a_run(self):
        proc, payload = self.apply_typed()
        self.assertEqual(proc.returncode, 0)
        run = payload["run"]
        self.assertEqual(run["status"], "success")
        self.assertEqual(run["summary"], "timeout=600 mode=balanced enabled=true note=hi")
        self.assertTrue(run["run_dir"])
        self.assertEqual(self.target.read_text(), "timeout=600 mode=balanced enabled=true note=hi\n")

    def test_failed_apply_is_recorded_and_leaves_nothing_to_undo(self):
        proc, payload = self.json_cli("run", "--json", "fixture-failing")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["run"]["status"], "failed")
        self.assertIn("refusing to apply", payload["run"]["stderr"])

        _, status = self.json_cli("status", "--json", "fixture-failing")
        self.assertTrue(status["status"]["undo_supported"])
        self.assertFalse(status["status"]["undo_available"])

        proc, payload = self.json_cli("undo", "--json", "fixture-failing")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no successful", payload["error"])

    def test_missing_executable_is_reported_rather_than_crashing(self):
        recipe = self.root / "recipes" / "fixtures" / "fixture-noparams.sh"
        recipe.chmod(0o644)
        proc, payload = self.json_cli("run", "--json", "fixture-noparams")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["run"]["status"], "failed")
        self.assertIn("cannot execute", payload["run"]["stderr"])

    # ---- status, history, undo ------------------------------------------

    def test_status_does_not_execute_the_recipe(self):
        _, before = self.json_cli("status", "--json", "fixture-typed")
        self.assertEqual(before["status"]["runs"], 0)
        self.assertFalse(before["status"]["undo_available"])
        self.assertFalse(self.target.exists())

    def test_apply_then_undo_refreshes_status_and_history(self):
        self.apply_typed(timeout="900")

        # What the UI reads to decide whether to offer Undo.
        _, after_apply = self.json_cli("status", "--json", "fixture-typed")
        self.assertTrue(after_apply["status"]["undo_available"])
        self.assertEqual(after_apply["status"]["runs"], 1)

        _, checked = self.json_cli(
            "check", "--json", "fixture-typed", "--directory", str(self.config / "fixture")
        )
        self.assertEqual(checked["run"]["state"], "configured")

        proc, undone = self.json_cli("undo", "--json", "fixture-typed")
        self.assertEqual(proc.returncode, 0, undone)
        self.assertEqual(undone["run"]["status"], "success")
        self.assertFalse(self.target.exists())

        # After undo the same three reads report the reversed world.
        _, after_undo = self.json_cli("status", "--json", "fixture-typed")
        self.assertFalse(after_undo["status"]["undo_available"])
        _, checked = self.json_cli(
            "check", "--json", "fixture-typed", "--directory", str(self.config / "fixture")
        )
        self.assertEqual(checked["run"]["state"], "not-configured")

        _, history = self.json_cli("history", "--json", "fixture-typed")
        actions = [row["action"] for row in history["runs"]]
        self.assertEqual(actions, ["undo", "apply"])
        applied = next(row for row in history["runs"] if row["action"] == "apply")
        self.assertTrue(applied["undone"])

    def test_undo_replays_the_parameters_of_the_source_run(self):
        # The target path is chosen by a parameter, so undo can only reverse
        # the right file if the engine replays the values the apply used.
        elsewhere = self.config / "elsewhere"
        self.apply_typed(directory=str(elsewhere))
        self.assertTrue((elsewhere / "typed.conf").exists())

        proc, payload = self.json_cli("undo", "--json", "fixture-typed")
        self.assertEqual(proc.returncode, 0, payload)
        self.assertEqual(payload["run"]["parameters"]["directory"], str(elsewhere))
        self.assertFalse((elsewhere / "typed.conf").exists())

    def test_undo_restores_previous_contents_exactly(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text("hand written\n")

        self.apply_typed(mode="powersave")
        self.assertIn("mode=powersave", self.target.read_text())

        self.json_cli("undo", "--json", "fixture-typed")
        self.assertEqual(self.target.read_text(), "hand written\n")

    def test_history_limit_and_log_readback(self):
        self.apply_typed(timeout="600")
        self.apply_typed(timeout="1200")

        _, history = self.json_cli("history", "--json", "fixture-typed", "--limit", "1")
        self.assertEqual(len(history["runs"]), 1)
        latest = history["runs"][0]

        _, log = self.json_cli("log", "--json", "fixture-typed", "--run", latest["run_id"])
        self.assertIn("wrote ", log["stdout"])
        self.assertEqual(log["run"]["run_id"], latest["run_id"])

    def test_log_rejects_a_run_id_that_escapes_the_state_directory(self):
        proc, payload = self.json_cli("log", "--json", "fixture-typed", "--run", "../../etc")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid run id", payload["error"])

    def test_json_flag_after_the_recipe_id_is_refused_clearly(self):
        proc = self.cli("run", "fixture-noparams", "--json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("place --json before the recipe id", proc.stderr)


if __name__ == "__main__":
    unittest.main()
