import os
import tempfile
import unittest
from pathlib import Path

from omarchy_recipes.core import RecipeError, discover, get_recipe, parse_recipe, validate_values


ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    """Discovery now walks the user's own collections as well as the bundled
    tree, so these have to redirect the workspace. Without it the suite passes
    or fails depending on what the developer happens to have authored locally —
    which is exactly how this started failing."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = os.environ.get("OMARCHY_RECIPES_HOME")
        os.environ["OMARCHY_RECIPES_HOME"] = self._tmp.name

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("OMARCHY_RECIPES_HOME", None)
        else:
            os.environ["OMARCHY_RECIPES_HOME"] = self._saved
        self._tmp.cleanup()

    def test_discovers_example(self):
        recipes = discover(ROOT)
        ids = [r.id for r in recipes]
        self.assertIn("example-config-value", ids)

    def test_metadata_normalizes(self):
        r = get_recipe(ROOT, "example-config-value")
        self.assertEqual(r.category, "Examples")
        self.assertEqual(r.undo, "restore")
        self.assertEqual(r.risk, "low")
        self.assertEqual(r.parameters[0].choices, ["performance", "balanced", "powersave"])
        self.assertEqual(r.parameters[0].default, "balanced")

    def test_parameter_validation(self):
        r = get_recipe(ROOT, "example-config-value")
        values = validate_values(r, {"value": "performance"})
        self.assertEqual(values["value"], "performance")
        with self.assertRaises(RecipeError):
            validate_values(r, {"value": "warp"})

    def test_enum_errors_name_the_accepted_values(self):
        """A bare "invalid privilege 'sudo'" leaves the reader guessing again.

        This is the failure an authoring agent actually hits: `sudo` is the
        natural guess for privilege, and the message has to be enough for a
        human or an agent to correct it without reading the engine source.
        """
        cases = [
            ("privilege", "sudo", ["mixed", "root", "user"]),
            ("undo", "revert", ["command", "none", "restore"]),
            ("risk", "critical", ["high", "low", "medium"]),
        ]
        for key, bad, expected in cases:
            with self.subTest(key=key):
                meta = {"privilege": "user", "undo": "none", "risk": "low"}
                meta[key] = bad
                with tempfile.TemporaryDirectory() as td:
                    p = Path(td) / "r.sh"
                    p.write_text(
                        "#!/bin/bash\n"
                        "# @recipe.id r\n# @recipe.title T\n"
                        "# @recipe.description D\n# @recipe.category System\n"
                        + "".join(f"# @recipe.{k} {v}\n" for k, v in meta.items())
                    )
                    with self.assertRaises(RecipeError) as cm:
                        parse_recipe(p)
                message = str(cm.exception)
                self.assertIn(repr(bad), message)
                for value in expected:
                    self.assertIn(value, message)

    def test_missing_metadata_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.sh"
            p.write_text("#!/bin/bash\n# @recipe.id bad\n")
            with self.assertRaises(RecipeError):
                parse_recipe(p)


if __name__ == "__main__":
    unittest.main()
