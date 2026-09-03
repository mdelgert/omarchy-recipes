import os
import tempfile
import unittest
from pathlib import Path

from omarchy_recipes import core
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

    def _recipe_with(self, td, **meta):
        base = {"id": "r", "title": "T", "description": "D", "category": "System"}
        base.update(meta)
        p = Path(td) / "r.sh"
        p.write_text("#!/bin/bash\n" + "".join(f"# @recipe.{k} {v}\n" for k, v in base.items()))
        return parse_recipe(p)

    def test_icon_escape_resolves_to_one_glyph(self):
        """Recipes carry `\\uXXXX`; a literal glyph does not survive round-trips."""
        with tempfile.TemporaryDirectory() as td:
            r = self._recipe_with(td, icon=r"")
        self.assertEqual(r.icon, "")
        self.assertEqual(len(r.icon), 1)

    def test_icon_falls_back_to_the_category_glyph(self):
        """No recipe renders blank, and the fallback lives in the engine so no
        frontend needs its own table."""
        for category, expected in [("System", ""), ("Desktop", "")]:
            with self.subTest(category=category), tempfile.TemporaryDirectory() as td:
                self.assertEqual(self._recipe_with(td, category=category).icon, expected)

    def test_unknown_category_still_gets_a_glyph(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(self._recipe_with(td, category="Wildlife").icon, core.DEFAULT_ICON)

    def test_declared_icon_beats_the_category_default(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._recipe_with(td, category="System", icon=r"")
        self.assertEqual(r.icon, "")

    def test_malformed_icon_is_refused(self):
        """An icon that cannot resolve is worse than none: it renders as a
        blank gap and nothing says why."""
        # A whitespace-only value is deliberately absent from this list: the
        # metadata regex needs a non-space value, so such a line never reaches
        # the parser at all. Lint's `empty-icon` rule is what catches it.
        for bad in ["notaglyph", r"\uZZZZ", "ab", r"\\u12"]:
            with self.subTest(icon=bad), tempfile.TemporaryDirectory() as td:
                with self.assertRaises(RecipeError):
                    self._recipe_with(td, icon=bad)

    def test_every_category_glyph_is_a_single_real_character(self):
        """A blank or multi-char default would silently break every recipe in
        that category at once."""
        for category, glyph in core.CATEGORY_ICONS.items():
            with self.subTest(category=category):
                self.assertEqual(len(glyph), 1)
                self.assertGreater(ord(glyph), 0x20)
        self.assertEqual(len(core.DEFAULT_ICON), 1)

    def test_icon_reaches_normalized_output(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIn("icon", self._recipe_with(td).to_dict())

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
