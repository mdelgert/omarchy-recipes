import os
import tempfile
import unittest
from pathlib import Path

from omarchy_recipes.core import RecipeError, discover, get_recipe, parse_recipe, validate_values


ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
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

    def test_missing_metadata_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.sh"
            p.write_text("#!/bin/bash\n# @recipe.id bad\n")
            with self.assertRaises(RecipeError):
                parse_recipe(p)


if __name__ == "__main__":
    unittest.main()
