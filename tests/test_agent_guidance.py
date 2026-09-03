"""Every rule that can refuse a draft must be written where the model reads it.

Three generated recipes were refused in this project for a rule nobody had told
the authoring agent:

    @recipe.privilege sudo    the accepted values were never listed
    bare `sudo`               the no-terminal constraint was never mentioned
    @param name type=string   the grammar was never shown

Each was a fair guess against the documentation that existed, and each cost a
full multi-minute generation before the engine rejected it.

These tests close the pattern rather than the instances. `SKILL.md` is fed to
the model on every authoring call and is the only place it learns the rules, so
adding a new way to reject a draft now fails here until the rule is explained
there. The assertions run against the engine's own definitions, so they cannot
drift: extend `VALID_TYPES` or add an ERROR lint rule and this suite fails
until the guidance follows.
"""

import unittest
from pathlib import Path

from omarchy_recipes import core, lint

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "recipe-authoring" / "SKILL.md"
AGENT = ROOT / "src" / "omarchy_recipes" / "agent.py"

# Vocabularies the parser validates a declared value against, and rejects the
# recipe over. Every member has to appear in the rules the model is given,
# because "one of a fixed set" is unguessable by definition.
ENFORCED_VOCABULARIES = {
    "@recipe.privilege": core.VALID_PRIVILEGE,
    "@recipe.undo": core.VALID_UNDO,
    "@recipe.risk": core.VALID_RISK,
    "@param <type>": core.VALID_TYPES,
}

# VALID_STATES is deliberately absent: an unrecognised `recipe_state` value is
# normalised to "unknown" rather than refused, so it cannot cost a generation.

# Each rule that can refuse a draft, mapped to wording in SKILL.md that tells
# the model how to avoid it. Asserting on the wording rather than merely on the
# rule name means deleting the guidance fails here too, not just forgetting to
# add it.
GUIDANCE = {
    "pipe-to-shell": "curl-pipe-shell",
    "eval": "Never eval user input",
    "rm-rf-broad": "Recursive delete of a root or home path",
    "world-writable": "World-writable permissions",
    "disables-security": "Disabling a security control",
    "embedded-credential": "hard-coded credential",
    "bare-sudo": "recipe_sudo",
    "missing-shebang": "#!/usr/bin/env bash",
    "missing-action": "`check`, `apply`, and `undo`",
    "write-without-backup": "recipe_backup_file",
    "empty-icon": "@recipe.icon",
    "recipe-arg-case": "RECIPE_ARG_HOSTNAME",
    "recipe-arg-without-parse": "recipe_parse_args",
}

# Refusals that are not the model's to avoid, so guidance would be noise.
NOT_THE_MODELS_FAULT = {
    # Bash's own parser disagreeing is reported verbatim; there is no project
    # rule to state.
    "syntax-error",
    # An unreadable file is an I/O problem, not something a draft can cause.
    "unreadable",
    # Raised for every metadata violation, each of which is already covered by
    # ENFORCED_VOCABULARIES above or by its own dedicated rule.
    "invalid-metadata",
}


def error_rules() -> set[str]:
    """Every lint rule id that reports at ERROR severity.

    Read from the module rather than listed here, so a new rule is picked up
    automatically instead of relying on someone remembering this file.
    """
    from_table = {rule for rule, severity, _, _ in lint.DANGEROUS if severity == lint.ERROR}
    # The structural checks build their findings inline rather than in the
    # table, so they are recovered from the source.
    import re
    inline = set(re.findall(r'Finding\("([a-z-]+)",\s*ERROR', AGENT.parent.joinpath("lint.py").read_text()))
    return from_table | inline


class VocabularyGuidanceTests(unittest.TestCase):
    def test_every_accepted_value_is_written_down(self):
        # Matched as `value` in backticks, which is how the rules write a
        # literal. A bare substring search passes on prose: "user", "root",
        # "low" and "path" all occur in ordinary sentences, so deleting the
        # privilege guidance entirely still looked documented — verified by
        # deleting it and watching the loose version stay green.
        rules = SKILL.read_text()
        for field, values in ENFORCED_VOCABULARIES.items():
            for value in sorted(values):
                with self.subTest(field=field, value=value):
                    self.assertIn(
                        f"`{value}`", rules,
                        f"{field} accepts {value!r} and the engine refuses anything else, "
                        f"but SKILL.md never names it as a literal")

    def test_the_draft_prompt_states_them_too(self):
        """The prompt is built around SKILL.md and repeats the hard rules.

        A model that skims the skill still sees these, and they are the ones
        that have actually been guessed wrong.
        """
        source = AGENT.read_text()
        requirements = source[source.index("Hard requirements"):][:2500]
        for field in ("@recipe.privilege", "@recipe.undo", "@recipe.risk", "@param"):
            with self.subTest(field=field):
                self.assertIn(field, requirements)


class RefusalGuidanceTests(unittest.TestCase):
    def test_every_error_rule_is_explained(self):
        rules = SKILL.read_text()
        for rule in sorted(error_rules() - NOT_THE_MODELS_FAULT):
            with self.subTest(rule=rule):
                phrase = GUIDANCE.get(rule)
                self.assertIsNotNone(
                    phrase,
                    f"lint rule {rule!r} refuses a draft but nothing tells the model how to "
                    f"avoid it. Explain it in SKILL.md and map it in GUIDANCE, or add it to "
                    f"NOT_THE_MODELS_FAULT with a reason.")
                self.assertIn(
                    phrase, rules,
                    f"SKILL.md no longer contains the guidance for {rule!r} ({phrase!r})")

    def test_the_registry_has_no_stale_entries(self):
        """A mapping for a rule that no longer exists is guidance nobody needs."""
        known = error_rules()
        for rule in sorted(GUIDANCE):
            with self.subTest(rule=rule):
                self.assertIn(rule, known, f"GUIDANCE maps {rule!r}, which is no longer a lint error")
        for rule in sorted(NOT_THE_MODELS_FAULT):
            with self.subTest(rule=rule):
                self.assertIn(rule, known, f"NOT_THE_MODELS_FAULT lists {rule!r}, which is not a lint error")

    def test_the_check_actually_catches_an_undocumented_rule(self):
        """Guard the guard: a check that cannot fail is worse than none.

        Without this, GUIDANCE quietly covering everything by accident would
        look identical to the check working.
        """
        undocumented = "a-rule-nobody-documented"
        self.assertNotIn(undocumented, GUIDANCE)
        self.assertNotIn(undocumented, NOT_THE_MODELS_FAULT)


if __name__ == "__main__":
    unittest.main()
