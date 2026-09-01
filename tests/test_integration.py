import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "omarchy-recipes"


class IntegrationTests(unittest.TestCase):
    def run_cli(self, *args, env=None):
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run([str(CLI), *args], cwd=ROOT, env=merged, text=True, capture_output=True)

    def test_apply_and_undo_exact_absence(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            state = Path(td) / "state"
            config = Path(td) / "config"
            home.mkdir()
            env = {"HOME": str(home), "XDG_STATE_HOME": str(state), "XDG_CONFIG_HOME": str(config)}

            p = self.run_cli("run", "example-config-value", "--value", "performance", env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
            target = config / "omarchy-recipes-demo" / "settings.conf"
            self.assertEqual(target.read_text(), "mode=performance\n")

            p = self.run_cli("undo", "example-config-value", env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertFalse(target.exists())

    def test_apply_restores_previous_contents(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            state = Path(td) / "state"
            config = Path(td) / "config"
            home.mkdir()
            target = config / "omarchy-recipes-demo" / "settings.conf"
            target.parent.mkdir(parents=True)
            target.write_text("custom=user-value\n")
            env = {"HOME": str(home), "XDG_STATE_HOME": str(state), "XDG_CONFIG_HOME": str(config)}

            self.assertEqual(self.run_cli("run", "example-config-value", "--value", "balanced", env=env).returncode, 0)
            self.assertEqual(target.read_text(), "mode=balanced\n")
            self.assertEqual(self.run_cli("undo", "example-config-value", env=env).returncode, 0)
            self.assertEqual(target.read_text(), "custom=user-value\n")


if __name__ == "__main__":
    unittest.main()
