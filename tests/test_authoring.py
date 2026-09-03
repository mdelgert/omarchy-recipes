"""Tests for the Milestone 2 authoring foundation.

Conflict tests inject canned inspection data rather than reading the machine,
so they assert the checking logic and pass on a bare CI box. The few tests that
do touch the system only assert the shape of the answer, never its content.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from omarchy_recipes import agent, authoring, conflicts, contribution, core, inspection, lint, sources
from omarchy_recipes.core import RecipeError, scan
from omarchy_recipes.inspection import DomainResult

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "omarchy-recipes"

GOOD_DRAFT = """#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id drafted-note
# @recipe.title Drafted note
# @recipe.description Writes a note into a demo directory.
# @recipe.category Examples
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @param note string required=true default="hi" label="Note"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

action="${1:-}"
shift || true
recipe_parse_args "$@"
target="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo/note.txt"

case "$action" in
  check)
    if [[ -f "$target" ]]; then recipe_state configured "set"
    else recipe_state not-configured "no note yet"; fi ;;
  apply)
    if [[ -e "$target" ]]; then recipe_backup_file "$target"; else recipe_mark_absent "$target"; fi
    printf '%s\\n' "${RECIPE_ARG_NOTE}" | recipe_atomic_write "$target"
    recipe_summary "note set" ;;
  undo)
    recipe_restore_file "$target"; recipe_summary "restored" ;;
  *) recipe_die "expected action check|apply|undo" ;;
esac
"""


class WorkspaceTestCase(unittest.TestCase):
    """Redirects the user workspace and config into a temporary directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.workspace = base / "workspace"
        self.config = base / "config"
        self.state = base / "state"
        self.home = base / "home"
        self.home.mkdir()
        self.env = {
            "HOME": str(self.home),
            "OMARCHY_RECIPES_HOME": str(self.workspace),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_STATE_HOME": str(self.state),
        }
        self._saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def cli(self, *args, stdin=None):
        merged = os.environ.copy()
        merged.update(self.env)
        return subprocess.run([str(CLI), *args], cwd=ROOT, env=merged, text=True,
                              input=stdin, capture_output=True)


class SourceTests(WorkspaceTestCase):
    def test_sources_are_ordered_by_trust(self):
        names = [s.name for s in sources.sources(ROOT)]
        self.assertEqual(names, ["bundled", "local", "community"])
        self.assertTrue(sources.source_for("bundled", ROOT).reviewed_upstream)
        self.assertFalse(sources.source_for("local", ROOT).reviewed_upstream)
        self.assertFalse(sources.source_for("community", ROOT).reviewed_upstream)

    def test_discovery_does_not_create_the_workspace(self):
        scan(ROOT)
        self.assertFalse(self.workspace.exists(), "browsing recipes must not create directories")

    def test_saved_recipe_is_discovered_as_local(self):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        recipes, _ = scan(ROOT)
        drafted = next(r for r in recipes if r.id == "drafted-note")
        self.assertEqual(drafted.source, "local")
        self.assertTrue(drafted.authoring["generated_with_ai"])
        self.assertFalse(drafted.authoring["reviewed"])
        self.assertFalse(drafted.to_dict()["reviewed_upstream"])

    def test_a_local_recipe_cannot_shadow_a_bundled_id(self):
        shadow = GOOD_DRAFT.replace("drafted-note", "example-config-value")
        local_dir = sources.source_for("local", ROOT).path
        local_dir.mkdir(parents=True)
        (local_dir / "shadow.sh").write_text(shadow)

        recipes, problems = scan(ROOT)
        # The behaviour is what matters: the bundled recipe wins, the local one
        # is not used, and the user is told which file is being ignored.
        winner = next(r for r in recipes if r.id == "example-config-value")
        self.assertEqual(winner.source, "bundled")
        self.assertEqual(len([r for r in recipes if r.id == "example-config-value"]), 1)
        reported = [p for p in problems if "example-config-value" in p["error"]]
        self.assertTrue(reported, problems)
        self.assertIn(str(local_dir / "shadow.sh"), reported[0]["path"])


class AuthoringTests(WorkspaceTestCase):
    def test_save_writes_an_executable_recipe(self):
        result = authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        self.assertTrue(result["saved"], result)
        path = Path(result["path"])
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK), "the runner executes recipes directly")

    def test_a_draft_cannot_declare_itself_reviewed(self):
        claimed = GOOD_DRAFT.replace(
            "# @recipe.risk low", "# @recipe.risk low\n# @recipe.reviewed true\n# @recipe.generated-with-ai false")
        result = authoring.save(ROOT, "drafted-note", claimed)
        body = Path(result["path"]).read_text()
        self.assertIn("@recipe.reviewed false", body)
        self.assertIn("@recipe.generated-with-ai true", body)
        self.assertEqual(body.count("@recipe.reviewed"), 1)

    def test_reviewed_is_recorded_only_when_the_caller_says_so(self):
        result = authoring.save(ROOT, "drafted-note", GOOD_DRAFT, reviewed=True, generated_with_ai=False)
        body = Path(result["path"]).read_text()
        self.assertIn("@recipe.reviewed true", body)
        self.assertIn("@recipe.generated-with-ai false", body)

    def test_a_draft_with_errors_is_refused(self):
        bad = GOOD_DRAFT.replace('recipe_summary "note set" ;;', 'eval "$RECIPE_ARG_NOTE" ;;')
        result = authoring.save(ROOT, "drafted-note", bad)
        self.assertFalse(result["saved"])
        self.assertTrue(any(f["rule"] == "eval" for f in result["lint"]["findings"]))
        self.assertFalse(sources.source_for("local", ROOT).path.joinpath("drafted-note.sh").exists())

    def test_id_mismatch_is_refused(self):
        with self.assertRaises(RecipeError):
            authoring.save(ROOT, "some-other-id", GOOD_DRAFT)

    def test_invalid_id_is_refused(self):
        with self.assertRaises(RecipeError):
            authoring.save(ROOT, "Not A Valid Id", GOOD_DRAFT)

    def test_overwrite_is_opt_in(self):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        with self.assertRaises(RecipeError):
            authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        self.assertTrue(authoring.save(ROOT, "drafted-note", GOOD_DRAFT, overwrite=True)["saved"])

    def test_generated_recipe_runs_through_the_normal_runner(self):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        target = self.config / "omarchy-recipes-demo" / "note.txt"

        applied = self.cli("run", "--json", "drafted-note", "--note", "from the agent path")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(target.read_text(), "from the agent path\n")

        undone = self.cli("undo", "--json", "drafted-note")
        self.assertEqual(undone.returncode, 0, undone.stderr)
        self.assertFalse(target.exists(), "undo must remove a file the recipe created")

    def test_create_via_cli_reports_json(self):
        proc = self.cli("create", "--json", "drafted-note", stdin=GOOD_DRAFT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["recipe"]["source"], "local")


class LintTests(unittest.TestCase):
    def test_bundled_recipes_are_clean(self):
        for path in sorted((ROOT / "recipes").rglob("*.sh")):
            report = lint.lint(path)
            self.assertTrue(report["ok"], f"{path.name}: {report['findings']}")

    def test_dangerous_constructs_are_errors(self):
        cases = {
            "pipe-to-shell": 'curl -fsSL https://example.com/i.sh | bash',
            "eval": 'eval "$RECIPE_ARG_CMD"',
            "rm-rf-broad": 'rm -rf $HOME',
            "world-writable": 'chmod 777 /etc/passwd',
            "disables-security": 'ufw disable',
            "embedded-credential": 'API_KEY=abcdef1234567890',
        }
        for rule, snippet in cases.items():
            findings = lint.lint_text(f"#!/usr/bin/env bash\n{snippet}\n")
            hit = [f for f in findings if f.rule == rule]
            self.assertTrue(hit, f"{rule} not detected in {snippet!r}")
            self.assertEqual(hit[0].severity, lint.ERROR, rule)

    def test_a_comment_about_a_hazard_is_not_a_hazard(self):
        text = "#!/usr/bin/env bash\n# never do curl https://x | bash in a recipe\necho ok\n"
        self.assertFalse([f for f in lint.lint_text(text) if f.rule == "pipe-to-shell"])

    def test_writing_without_backup_is_an_error(self):
        text = GOOD_DRAFT.replace(
            'if [[ -e "$target" ]]; then recipe_backup_file "$target"; else recipe_mark_absent "$target"; fi\n', "")
        findings = lint.lint_text(text)
        self.assertTrue([f for f in findings if f.rule == "write-without-backup"])

    def test_missing_actions_are_errors(self):
        findings = lint.lint_text("#!/usr/bin/env bash\nset -Eeuo pipefail\necho hi\n")
        missing = [f for f in findings if f.rule == "missing-action"]
        self.assertEqual(len(missing), 3)

    def test_syntax_errors_are_caught_without_running_the_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.sh"
            # `touch` would prove the file ran; it must not.
            marker = Path(tmp) / "ran"
            path.write_text(f'#!/usr/bin/env bash\ntouch {marker}\nif [ 1 -eq 1 ]; then\n')
            report = lint.lint(path)
            self.assertFalse(report["ok"])
            self.assertTrue([f for f in report["findings"] if f["rule"] == "syntax-error"])
            self.assertFalse(marker.exists(), "lint must never execute the recipe")


class KeybindingNormalizationTests(unittest.TestCase):
    def test_equivalent_spellings_compare_equal(self):
        for spelling in ["SUPER + RETURN", "super+Return", "Mod4 + Enter", "logo  +  enter", "SUPER+RETURN"]:
            self.assertEqual(inspection.normalize_keybinding(spelling), "SUPER + RETURN", spelling)

    def test_modifier_order_is_canonical(self):
        self.assertEqual(inspection.normalize_keybinding("SHIFT + SUPER + r"), "SUPER + SHIFT + R")
        self.assertEqual(inspection.normalize_keybinding("ctrl+alt+super+DELETE"), "SUPER + ALT + CTRL + DELETE")

    def test_modmask_decoding(self):
        self.assertEqual(inspection.decode_hypr_modmask(64), ["SUPER"])
        self.assertEqual(inspection.decode_hypr_modmask(65), ["SUPER", "SHIFT"])
        self.assertEqual(inspection.decode_hypr_modmask(0), [])


class ConflictTests(WorkspaceTestCase):
    def snapshot(self, **domains):
        return conflicts.Snapshot({name: DomainResult(name, items=items) for name, items in domains.items()})

    def test_taken_shortcut_blocks_and_offers_choices(self):
        snap = self.snapshot(keybindings=[{"combo": "SUPER + RETURN", "description": "Terminal", "dispatcher": "exec", "submap": ""}])
        report = conflicts.check([{"type": "keybinding", "value": "super+Return"}], ROOT, snap)
        finding = report["findings"][0]
        self.assertEqual(finding["status"], conflicts.CONFLICT)
        self.assertEqual(finding["severity"], conflicts.BLOCK)
        self.assertIn("Terminal", finding["detail"])
        self.assertIn("replace-existing", finding["resolutions"])
        self.assertIn("choose-another-shortcut", finding["resolutions"])
        self.assertTrue(report["requires_user_decision"])

    def test_free_shortcut_is_clear(self):
        snap = self.snapshot(keybindings=[{"combo": "SUPER + RETURN", "description": "Terminal", "dispatcher": "", "submap": ""}])
        report = conflicts.check([{"type": "keybinding", "value": "SUPER + SHIFT + F12"}], ROOT, snap)
        self.assertEqual(report["findings"][0]["status"], conflicts.CLEAR)
        self.assertFalse(report["requires_user_decision"])

    def test_unavailable_inspection_is_unknown_not_clear(self):
        snap = conflicts.Snapshot({"keybindings": DomainResult("keybindings", available=False, error="hyprctl is not installed")})
        finding = conflicts.check([{"type": "keybinding", "value": "SUPER + P"}], ROOT, snap)["findings"][0]
        self.assertEqual(finding["status"], conflicts.UNKNOWN)
        self.assertIn("hyprctl is not installed", finding["detail"])

    def test_installed_package_is_reported(self):
        snap = self.snapshot(packages=[{"name": "docker"}])
        self.assertEqual(conflicts.check([{"type": "package", "name": "docker"}], ROOT, snap)["findings"][0]["status"],
                         conflicts.CONFLICT)
        self.assertEqual(conflicts.check([{"type": "package", "name": "nope"}], ROOT, snap)["findings"][0]["status"],
                         conflicts.CLEAR)

    def test_busy_port_blocks(self):
        snap = self.snapshot(ports=[{"port": 8080, "protocol": "tcp", "address": "0.0.0.0"}])
        finding = conflicts.check([{"type": "port", "port": 8080, "protocol": "tcp"}], ROOT, snap)["findings"][0]
        self.assertEqual(finding["severity"], conflicts.BLOCK)
        self.assertEqual(conflicts.check([{"type": "port", "port": 9999}], ROOT, snap)["findings"][0]["status"],
                         conflicts.CLEAR)

    def test_existing_file_warns_rather_than_blocks(self):
        existing = self.config / "thing.conf"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("x")
        finding = conflicts.check([{"type": "file", "path": str(existing)}], ROOT, conflicts.Snapshot())["findings"][0]
        self.assertEqual(finding["status"], conflicts.CONFLICT)
        self.assertEqual(finding["severity"], conflicts.WARN)
        self.assertFalse(conflicts.check([{"type": "file", "path": str(self.config / "absent")}], ROOT,
                                         conflicts.Snapshot())["findings"][0]["status"] == conflicts.CONFLICT)

    def test_duplicate_recipe_id_is_detected(self):
        finding = conflicts.check([{"type": "recipe", "id": "example-config-value"}], ROOT, conflicts.Snapshot())["findings"][0]
        self.assertEqual(finding["status"], conflicts.CONFLICT)
        self.assertIn("run-existing", finding["resolutions"])

    def test_equivalent_recipe_is_found_by_keyword(self):
        finding = conflicts.check([{"type": "recipe", "keywords": ["example", "numeric"]}], ROOT,
                                  conflicts.Snapshot())["findings"][0]
        self.assertEqual(finding["status"], conflicts.CONFLICT)
        self.assertIn("improve-existing", finding["resolutions"])

    def test_unknown_resource_type_is_not_silently_clear(self):
        finding = conflicts.check([{"type": "wat"}], ROOT, conflicts.Snapshot())["findings"][0]
        self.assertEqual(finding["status"], conflicts.UNKNOWN)

    def test_cli_exits_nonzero_when_a_decision_is_required(self):
        payload = json.dumps({"resources": [{"type": "recipe", "id": "example-config-value"}]})
        proc = self.cli("conflicts", "--json", stdin=payload)
        self.assertEqual(proc.returncode, 3)
        self.assertTrue(json.loads(proc.stdout)["requires_user_decision"])


class InspectionTests(unittest.TestCase):
    def test_every_domain_answers_with_a_shape(self):
        for name, result in inspection.inspect().items():
            self.assertEqual(result.name, name)
            self.assertIsInstance(result.items, list)
            if not result.available:
                self.assertTrue(result.error, f"{name} unavailable without saying why")

    def test_unknown_domain_is_rejected(self):
        with self.assertRaises(ValueError):
            inspection.inspect(["not-a-domain"])

    def test_secret_environment_values_are_redacted(self):
        os.environ["OMARCHY_TEST_API_TOKEN"] = "super-secret-value"
        try:
            items = {i["name"]: i for i in inspection.inspect(["environment"])["environment"].items}
            entry = items["OMARCHY_TEST_API_TOKEN"]
            self.assertTrue(entry["secret"])
            self.assertEqual(entry["value"], "<redacted>")
        finally:
            os.environ.pop("OMARCHY_TEST_API_TOKEN", None)


if __name__ == "__main__":
    unittest.main()


class ContributionTests(WorkspaceTestCase):
    def prepared(self, **kwargs):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        return contribution.prepare(ROOT, "drafted-note", **kwargs)

    def test_branch_never_targets_a_protected_branch(self):
        plan = self.prepared()
        self.assertTrue(plan["branch"].startswith(contribution.BRANCH_PREFIX))
        self.assertNotIn(plan["branch"], contribution.PROTECTED_BRANCHES)

    def test_bundled_recipe_cannot_be_contributed(self):
        plan = contribution.prepare(ROOT, "example-config-value")
        self.assertFalse(plan["ready"])
        self.assertTrue(any("bundled" in b for b in plan["blockers"]))

    def test_lint_errors_block_a_contribution(self):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        # Corrupt the saved file the way a hand edit after saving might: drop
        # the backup entirely, so the recipe writes without preserving state.
        path = sources.source_for("local", ROOT).path / "drafted-note.sh"
        body = path.read_text()
        backup_line = next(line for line in body.splitlines() if "recipe_backup_file" in line)
        path.write_text(body.replace(backup_line, "    true"))

        report = lint.lint(path)
        self.assertFalse(report["ok"])
        self.assertTrue([f for f in report["findings"] if f["rule"] == "write-without-backup"])

        plan = contribution.prepare(ROOT, "drafted-note")
        self.assertFalse(plan["ready"])
        self.assertTrue(any("lint error" in b for b in plan["blockers"]))

    def test_pull_request_body_covers_the_template(self):
        plan = self.prepared(testing="Applied and undone locally.")
        body = plan["pull_request_body"]
        for heading in ["## Recipe", "## Purpose", "## Changes", "## Backup", "## Undo",
                        "## Compatibility", "## Testing", "## Conflicts", "## AI Generated"]:
            self.assertIn(heading, body)
        self.assertIn("Applied and undone locally.", body)
        # Provenance must be stated honestly, not omitted.
        self.assertIn("Was AI used to generate this recipe? Yes", body)
        self.assertIn("Human reviewed? Not yet", body)

    def test_dry_run_changes_nothing(self):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True).stdout
        result = contribution.submit(ROOT, "drafted-note", dry_run=True)
        after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True).stdout
        self.assertFalse(result["submitted"])
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["steps"])
        self.assertEqual(before, after, "a dry run must not touch the working tree")

    def test_cli_dry_run_reports_the_plan(self):
        authoring.save(ROOT, "drafted-note", GOOD_DRAFT)
        proc = self.cli("contribute", "--json", "drafted-note", "--testing", "ran it")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["branch"], "recipe/drafted-note")


class AgentAdapterTests(unittest.TestCase):
    """The adapter's own logic. No provider is invoked: these assert how a
    model's reply is handled, which is exactly where a wrong assumption would
    let malformed output through."""

    def test_providers_are_reported_with_availability(self):
        names = [p.name for p in agent.providers()]
        self.assertIn("claude", names)
        for provider in agent.providers():
            if not provider.available:
                self.assertTrue(provider.reason)

    def test_provider_can_be_overridden(self):
        saved = os.environ.get("OMARCHY_RECIPES_AGENT")
        os.environ["OMARCHY_RECIPES_AGENT"] = "codex"
        try:
            self.assertEqual(agent.default_provider(), "codex")
        finally:
            if saved is None:
                os.environ.pop("OMARCHY_RECIPES_AGENT", None)
            else:
                os.environ["OMARCHY_RECIPES_AGENT"] = saved

    def test_unknown_provider_is_refused(self):
        with self.assertRaises(RecipeError):
            agent.complete("hi", provider="not-a-provider")

    def test_json_is_extracted_from_prose_and_fences(self):
        self.assertEqual(agent._extract_json('{"a": 1}')["a"], 1)
        self.assertEqual(agent._extract_json('Sure!\n```json\n{"a": 2}\n```\nDone')["a"], 2)
        self.assertEqual(agent._extract_json('text before {"a": 3} text after')["a"], 3)

    def test_braces_inside_strings_do_not_end_the_object(self):
        reply = '{"recipe": "case \\"$x\\" in a) echo {} ;; esac", "id": "x"}'
        self.assertIn("esac", agent._extract_json(reply)["recipe"])

    def test_unusable_replies_are_errors_not_silent_empties(self):
        for reply in ["no json here", "", '{"unterminated": ', '{bad json}']:
            with self.assertRaises(RecipeError, msg=repr(reply)):
                agent._extract_json(reply)

    def _lint_recipe(self, extra_meta=""):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "r.sh"
            p.write_text(
                "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
                "# @recipe.id r\n# @recipe.title T\n# @recipe.description D\n"
                "# @recipe.category System\n# @recipe.privilege user\n"
                "# @recipe.undo none\n# @recipe.risk low\n" + extra_meta +
                "case \"${1:-}\" in\n  check) recipe_state configured x ;;\n"
                "  apply) : ;;\n  undo) : ;;\nesac\n"
            )
            return lint.lint(p)

    def test_missing_icon_only_warns(self):
        """Every recipe written before icons existed has none, and the engine
        already falls back, so this must never block them."""
        report = self._lint_recipe()
        findings = {f["rule"]: f["severity"] for f in report["findings"]}
        self.assertEqual(findings.get("no-icon"), "warning")
        self.assertNotIn("no-icon", [f["rule"] for f in report["findings"] if f["severity"] == "error"])

    def test_declared_icon_silences_the_warning(self):
        report = self._lint_recipe("# @recipe.icon \\uf085\n")
        self.assertNotIn("no-icon", [f["rule"] for f in report["findings"]])

    def test_valueless_icon_line_is_an_error(self):
        """A bare `# @recipe.icon` is invisible to the metadata parser, so
        reporting it as merely absent would leave the author staring at a line
        that is right there in the file."""
        report = self._lint_recipe("# @recipe.icon\n")
        findings = {f["rule"]: f["severity"] for f in report["findings"]}
        self.assertEqual(findings.get("empty-icon"), "error")
        self.assertFalse(report["ok"])

    def test_malformed_icon_is_reported_as_invalid_metadata(self):
        report = self._lint_recipe("# @recipe.icon nonsense\n")
        self.assertIn("invalid-metadata", [f["rule"] for f in report["findings"]])
        self.assertFalse(report["ok"])

    def test_shipped_recipes_still_lint_without_icons(self):
        """Adding the field must not break the existing library."""
        for path in sorted((ROOT / "recipes").rglob("*.sh")):
            with self.subTest(recipe=path.name):
                report = lint.lint(path)
                self.assertTrue(report["ok"], f"{path.name}: {report['findings']}")

    def test_action_branches_are_recognised_however_they_are_written(self):
        """`"check")` is as valid as `check)`, and the rules ask for quoting.

        A generated recipe was refused with three `missing-action` errors for
        quoting its case patterns — a working recipe, thrown away after minutes
        of generation, because the check only matched a bare unquoted branch.
        """
        for label, body in [
            ("bare", 'case "$1" in\n  check)\n  apply)\n  undo)\nesac'),
            ("double-quoted", 'case "$1" in\n  "check")\n  "apply")\n  "undo")\nesac'),
            ("single-quoted", "case \"$1\" in\n  'check')\n  'apply')\n  'undo')\nesac"),
            ("leading paren", 'case "$1" in\n  (check)\n  (apply)\n  (undo)\nesac'),
            ("alternation", 'case "$1" in\n  check|status)\n  apply|do)\n  undo|revert)\nesac'),
            ("case on one line", 'case "$1" in check)\n  apply)\n  undo)\nesac'),
            # Functions are a legitimate handler shape -- when something calls them.
            ("functions + dispatch", 'check() { :; }\napply() { :; }\nundo() { :; }\n"${1:-}" "${@:2}"\n'),
            ("functions + bare $1", 'check() { :; }\napply() { :; }\nundo() { :; }\n"$1" "$@"\n'),
        ]:
            with self.subTest(form=label):
                self.assertEqual(lint.actions_declared(body), {"check", "apply", "undo"})

    def test_a_genuinely_missing_action_is_still_caught(self):
        """The looser match must not stop the rule doing its job."""
        for label, body in [
            ("only one branch", 'case "$1" in\n  check)\nesac'),
            ("only prose", 'echo "run check) apply) undo) please"'),
            # The real generated failure: all three functions defined, then the
            # file ends. Nothing dispatches, so `recipe.sh check` runs top to
            # bottom, defines them, and exits 0 having done nothing. Verified
            # by running it -- no output, success. This must stay refused.
            ("functions, never called", 'check() { :; }\napply() { :; }\nundo() { :; }'),
        ]:
            with self.subTest(form=label):
                self.assertNotEqual(lint.actions_declared(body), {"check", "apply", "undo"})

    def test_undispatched_functions_get_a_message_that_names_the_real_fix(self):
        """"no `check)` branch" sends the author to add a case branch. The fix is
        to call the function, and a retrying model follows whatever the message
        says."""
        body = ("#!/usr/bin/env bash\nset -Eeuo pipefail\n"
                "# @recipe.id r\n# @recipe.title T\n# @recipe.description D\n"
                "# @recipe.category System\n# @recipe.privilege user\n"
                "# @recipe.undo none\n# @recipe.risk low\n"
                "check() { recipe_state configured x; }\napply() { :; }\nundo() { :; }\n")
        report = authoring.draft_report(body)
        messages = [f["message"] for f in report["findings"] if f["rule"] == "missing-action"]
        self.assertEqual(len(messages), 3)
        for m in messages:
            self.assertIn("nothing ever calls it", m)
            self.assertIn('"$1"', m)

    def _param_recipe(self, check_body):
        return ("#!/usr/bin/env bash\nset -Eeuo pipefail\n"
                "# @recipe.id r\n# @recipe.title T\n# @recipe.description D\n"
                "# @recipe.category System\n# @recipe.privilege user\n"
                "# @recipe.undo none\n# @recipe.risk low\n"
                "# @param hostname string required=true label=\"Hostname\"\n"
                "case \"${1:-}\" in\n"
                f"  check) shift || true\n  {check_body}\n  recipe_state configured x ;;\n"
                "  apply) : ;;\n  undo) : ;;\nesac\n")

    def test_lowercase_parameter_variable_is_refused(self):
        """recipe_parse_args exports RECIPE_ARG_HOSTNAME. The lowercase name is
        never set, so this passed lint and died on Apply under set -u. A
        generated recipe did exactly this, eight times over."""
        body = self._param_recipe('recipe_parse_args "$@"\n  echo "$RECIPE_ARG_hostname"')
        rules = [f["rule"] for f in authoring.draft_report(body)["findings"]]
        self.assertIn("recipe-arg-case", rules)

    def test_reading_parameters_without_parsing_them_is_refused(self):
        body = self._param_recipe('echo "$RECIPE_ARG_HOSTNAME"')
        rules = [f["rule"] for f in authoring.draft_report(body)["findings"]]
        self.assertIn("recipe-arg-without-parse", rules)

    def test_correctly_read_parameters_are_clean(self):
        body = self._param_recipe('recipe_parse_args "$@"\n  echo "$RECIPE_ARG_HOSTNAME"')
        rules = [f["rule"] for f in authoring.draft_report(body)["findings"]]
        self.assertNotIn("recipe-arg-case", rules)
        self.assertNotIn("recipe-arg-without-parse", rules)

    def test_bare_sudo_is_refused(self):
        """A recipe from the menu has no terminal, so bare sudo cannot prompt.

        It fails with "sudo: a terminal is required to read the password",
        which reads as a broken recipe. Refusing at save time is the last point
        the author still sees it.
        """
        report = authoring.draft_report(
            "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
            "# @recipe.id r\n# @recipe.title T\n# @recipe.description D\n"
            "# @recipe.category System\n# @recipe.privilege root\n"
            "# @recipe.undo command\n# @recipe.risk low\n"
            "case \"${1:-}\" in\n"
            "  check) sudo pacman -Q nano ;;\n"
            "  apply) : ;;\n  undo) : ;;\nesac\n"
        )
        rules = [f["rule"] for f in report["findings"]]
        self.assertIn("bare-sudo", rules)
        self.assertFalse(report["ok"])

    def test_recipe_sudo_is_not_mistaken_for_bare_sudo(self):
        """The helper is the fix, so it must not trip the rule it exists for."""
        report = authoring.draft_report(
            "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
            "# @recipe.id r\n# @recipe.title T\n# @recipe.description D\n"
            "# @recipe.category System\n# @recipe.privilege root\n"
            "# @recipe.undo command\n# @recipe.risk low\n"
            "case \"${1:-}\" in\n"
            "  check) recipe_sudo pacman -Q nano ;;\n"
            "  apply) : ;;\n  undo) : ;;\nesac\n"
        )
        self.assertNotIn("bare-sudo", [f["rule"] for f in report["findings"]])


    def test_privilege_helper_exists_in_the_library(self):
        lib = (ROOT / "lib" / "recipe.sh").read_text()
        self.assertIn("recipe_sudo()", lib)
        # The no-terminal path is the whole point of the helper.
        self.assertIn("pkexec", lib)



    def test_denied_tools_are_last_so_the_prompt_cannot_be_swallowed(self):
        # Builders take the prompt as well as the model: copilot has no stdin
        # mode and carries it in argv. claude ignores it and reads stdin.
        argv = agent.PROVIDER_ARGV["claude"](None, "PROMPT")
        self.assertEqual(argv[-len(agent.DENIED_TOOLS) - 1], "--disallowedTools")
        for tool in ["Bash", "Edit", "Write"]:
            self.assertIn(tool, argv)

    def test_copilot_denied_tools_are_last_and_use_copilot_names(self):
        argv = agent.PROVIDER_ARGV["copilot"](None, "PROMPT")
        self.assertEqual(argv[-len(agent.COPILOT_DENIED_TOOLS) - 1], "--excluded-tools")
        for tool in ["bash", "edit", "create"]:
            self.assertIn(tool, argv)
