"""Static checks a recipe must survive before it is saved or run.

This is the gate between a generated recipe and the disk. An agent may write
anything; what actually lands has to satisfy the same rules a human contributor
would be held to, and the dangerous-construct rules exist because the author of
a recipe is now sometimes a model that will happily produce `curl | bash` if a
README told it to.

Findings are advisory text plus a severity:

* `error`   — refuse to save or run until fixed
* `warning` — allow, but the user has to see it

Nothing here executes the recipe. `bash -n` parses without running, which is
the only way to catch a syntax error before the runner would hit it.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import RecipeError, parse_recipe

ERROR = "error"
WARNING = "warning"


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    line: int = 0
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "severity": self.severity, "message": self.message, "line": self.line, "text": self.text}


# Patterns worth refusing or flagging, with why they matter. Each entry is
# (rule, severity, regex, message). Regexes run per line against the recipe
# body; comments are stripped first so documentation about a hazard is not
# mistaken for the hazard.
DANGEROUS = [
    ("pipe-to-shell", ERROR,
     re.compile(r"\b(curl|wget)\b[^|;]*\|\s*(sudo\s+)?(ba|z|k)?sh\b"),
     "downloads and executes code in one step; fetch, verify, then run"),
    ("eval", ERROR,
     re.compile(r"(^|[;&|(\s])eval\s"),
     "eval turns data into code; the project forbids it outright"),
    ("rm-rf-broad", ERROR,
     re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*[ff]?[a-zA-Z]*\s+(-[a-zA-Z]+\s+)*(/|\$HOME/?\s*$|~/?\s*$|/\*|\"?\$\{?HOME\}?\"?/?\s*$)"),
     "recursive delete of a root or home path"),
    ("rm-unquoted-glob", WARNING,
     re.compile(r"\brm\s+[^|;#\n]*(?<![\"'])\*"),
     "unquoted glob in a delete; a stray space or empty variable changes what it matches"),
    ("recursive-permissions", WARNING,
     re.compile(r"\b(chmod|chown)\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*R"),
     "recursive ownership or permission change; scope it to the exact paths"),
    ("world-writable", ERROR,
     re.compile(r"\bchmod\s+(-[a-zA-Z]+\s+)*(777|a\+rwx|o\+w)\b"),
     "makes a path world-writable"),
    ("disables-security", ERROR,
     re.compile(r"\b(setenforce\s+0|ufw\s+disable|iptables\s+-F|systemctl\s+(stop|disable)\s+\S*(firewall|apparmor|nftables))"),
     "disables a security control"),
    ("embedded-credential", ERROR,
     re.compile(r"(?i)\b(password|passwd|api[_-]?key|secret|token)\s*=\s*[\"']?[A-Za-z0-9/_+\-]{8,}"),
     "looks like a hard-coded credential; recipes must never carry secrets"),
    ("hidden-persistence", WARNING,
     re.compile(r"(crontab\s+-|>>\s*~?[^\s]*/\.(bashrc|zshrc|profile|bash_profile)|systemd/user/[^\s]*\.timer)"),
     "installs something that keeps running later; say so in the description and make undo remove it"),
    ("sudo-whole-script", WARNING,
     re.compile(r"^\s*sudo\s+(bash|sh)\b"),
     "elevates a whole shell; elevate the single command that needs it"),
    # An error, not a warning: a recipe run from the menu has its output
    # captured and no terminal attached, so this does not merely look untidy —
    # it fails outright with "sudo: a terminal is required to read the
    # password", which reads as a broken recipe rather than a missing prompt.
    # Refusing at save time is the only place the author still sees it.
    ("bare-sudo", ERROR,
     re.compile(r"(?<!recipe_)\bsudo\s"),
     "bare sudo cannot prompt when a recipe is run from the menu; use `recipe_sudo <command>`"),
    # Matched against the line with string contents blanked (STRING_BLIND_RULES),
    # so an expansion inside "..." is not seen at all and only a genuinely bare
    # one remains. The previous form looked only at the adjacent characters and
    # flagged `recipe_die "User '$RECIPE_ARG_USERNAME' does not exist"` -- fully
    # quoted -- eight times in one generated recipe.
    ("unquoted-recipe-arg", WARNING,
     re.compile(r"\$\{?RECIPE_ARG_[A-Z0-9_]+"),
     "unquoted parameter expansion; quote it so a value with spaces cannot split"),
    # An error: recipe_parse_args uppercases every name, so a lowercase
    # reference is a variable that is never set, and under `set -u` the recipe
    # aborts on first use. A generated recipe read $RECIPE_ARG_hostname eight
    # times, passed lint, and would have died on Apply — the rule above only
    # matches uppercase, so it could not even see the problem.
    ("recipe-arg-case", ERROR,
     re.compile(r"\$\{?RECIPE_ARG_[a-z]"),
     "parameter variables are uppercased by recipe_parse_args: `--hostname` becomes "
     "`$RECIPE_ARG_HOSTNAME`; this lowercase name is never set and `set -u` aborts the recipe"),
]

# A `case` branch label: an optional `case ... in` prefix, an optional opening
# paren, then the pattern up to `)`.
#
# This used to be `^\s*(check|apply|undo)\)`, which only saw a bare, unquoted
# branch at the start of a line. `"check")` is equally valid bash — and this
# project's own "quote every expansion" rule nudges an author toward it — so a
# perfectly good recipe was reported as having no check, apply or undo branch
# at all, and refused. Three wasted minutes of generation for a working recipe.
CASE_BRANCH_RE = re.compile(r"^\s*(?:case\s+\S+\s+in\s+)?\(?\s*([^()\n;]+?)\s*\)", re.MULTILINE)
ACTIONS = ("check", "apply", "undo")


# `check() {` — a function named for an action. Legitimate as the handler, but
# only if something actually calls it (see DISPATCH_RE).
FUNCTION_DEF_RE = re.compile(r"^\s*(?:function\s+)?(check|apply|undo)\s*\(\)\s*\{", re.MULTILINE)
# A line that hands control to whatever the first argument names — `"$1" "$@"`,
# `"${1:-}" "${@:2}"`, bare `$1`. This is what makes the function form work.
DISPATCH_RE = re.compile(r'^\s*"?\$\{?1[^}\s"]*\}?"?(?:\s|$)', re.MULTILINE)


def _case_actions(text: str) -> set[str]:
    found: set[str] = set()
    for label in CASE_BRANCH_RE.findall(text):
        for alternative in label.split("|"):
            word = alternative.strip().strip("\"'").strip()
            if word in ACTIONS:
                found.add(word)
    return found


def _function_actions(text: str) -> set[str]:
    return set(FUNCTION_DEF_RE.findall(text))


def actions_declared(text: str) -> set[str]:
    """Which of check/apply/undo the runner's `recipe.sh <action>` would reach.

    Two shapes count. A `case` branch — `check)`, `"check")`, `('check')`,
    `check|status)` — is read from the label, so quoting and alternation are
    fine. A function named for the action counts too, but only when the file
    also dispatches on `$1`; a generated recipe defined all three functions and
    then simply ended, which the runner executes as a silent no-op that reports
    success. Definitions with nothing calling them are the broken case, not an
    alternative style.
    """
    found = _case_actions(text)
    functions = _function_actions(text)
    if functions and DISPATCH_RE.search(text):
        found |= functions
    return found
WRITE_RE = re.compile(r"(recipe_atomic_write|>\s*\"?\$\{?target|tee\s|sed\s+-i|>>\s*\"?\$)")
BACKUP_RE = re.compile(r"(recipe_backup_file|recipe_mark_absent)")


# Rules that are about *commands*, so text inside a string literal must not
# trip them: `echo "run sudo first"` is prose, and `"…$RECIPE_ARG_X…"` is the
# quoted form the unquoted-expansion rule exists to recommend. These rules are
# matched against the line with string contents blanked out. Everything else
# still sees the full line -- embedded-credential in particular needs the
# string contents, since that is where the credential is.
STRING_BLIND_RULES = frozenset({"bare-sudo", "unquoted-recipe-arg"})


def _blank_strings(line: str) -> str:
    """Replace the contents of quoted strings with spaces, keeping the quotes.

    Same-length output, so a match position still maps to the original line.
    Tracks quoting the same way _strip_comments does, and errs the same way:
    toward keeping code visible rather than hiding it.
    """
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                out.append(" ")
                i += 1
                if i < len(line):
                    out.append(" ")
                    i += 1
                continue
            if ch == quote:
                quote = None
                out.append(ch)
            else:
                out.append(" ")
            i += 1
            continue
        if ch in "\"'":
            quote = ch
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_comments(line: str) -> str:
    """Drop a trailing comment so prose about a hazard is not flagged as one.

    Deliberately simple: it tracks quoting well enough for recipe bodies and
    errs toward keeping code rather than hiding it.
    """
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                out.append(ch)
                i += 1
                if i < len(line):
                    out.append(line[i])
                    i += 1
                continue
            if ch == quote:
                quote = None
            out.append(ch)
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1].isspace()):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def lint_text(text: str, path: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()

    for number, raw in enumerate(lines, start=1):
        code = _strip_comments(raw)
        if not code.strip():
            continue
        blind = _blank_strings(code)
        for rule, severity, pattern, message in DANGEROUS:
            target = blind if rule in STRING_BLIND_RULES else code
            if pattern.search(target):
                findings.append(Finding(rule=rule, severity=severity, message=message, line=number, text=raw.strip()[:160]))

    if not text.lstrip().startswith("#!"):
        findings.append(Finding("missing-shebang", ERROR, "recipe must start with #!/usr/bin/env bash"))
    if "set -Eeuo pipefail" not in text:
        findings.append(Finding("missing-strict-mode", WARNING,
                                "add `set -Eeuo pipefail` so a failing step stops the recipe"))

    actions = actions_declared(text)
    # Name the actual defect. "no `check)` branch" told an author whose recipe
    # defined check() but never called it to add a case branch — the wrong fix,
    # and one a retrying model would follow straight into the same refusal.
    undispatched = _function_actions(text) - actions
    for action in ACTIONS:
        if action in actions:
            continue
        if action in undispatched:
            message = (f"`{action}()` is defined but nothing ever calls it; the runner invokes the "
                       f"script as `recipe.sh {action}`, so dispatch on \"$1\" — a `case` on it, or "
                       f"`\"${{1:-}}\" \"${{@:2}}\"` as the last line")
        else:
            message = (f"nothing handles `{action}`; the runner invokes the script as "
                       f"`recipe.sh {action}` and needs a `case` branch for it, or a function it "
                       f"dispatches to on \"$1\"")
        findings.append(Finding("missing-action", ERROR, message))

    # Reading parameters without ever parsing them. recipe_parse_args is what
    # sets RECIPE_ARG_*; without the call every value is unbound. Checked on the
    # comment-stripped body so prose about the variables does not count.
    code = "\n".join(_strip_comments(line) for line in text.splitlines())
    if "RECIPE_ARG_" in code and "recipe_parse_args" not in code:
        findings.append(Finding("recipe-arg-without-parse", ERROR,
                                "reads $RECIPE_ARG_* but never calls `recipe_parse_args \"$@\"`, which is "
                                "what sets them; every value is unbound and `set -u` aborts the recipe "
                                "on first use"))

    if "@recipe.state" not in text and "recipe_state" not in text:
        findings.append(Finding("no-state-report", WARNING,
                                "check does not report a state; call `recipe_state configured|not-configured \"...\"`"))

    if WRITE_RE.search(text) and not BACKUP_RE.search(text):
        findings.append(Finding("write-without-backup", ERROR,
                                "the recipe writes files but never calls recipe_backup_file or recipe_mark_absent"))

    return findings


def lint_metadata(path: Path) -> list[Finding]:
    try:
        recipe = parse_recipe(path)
    except RecipeError as e:
        return [Finding("invalid-metadata", ERROR, str(e))]

    findings: list[Finding] = []
    text = path.read_text(errors="replace")
    if recipe.undo == "none":
        findings.append(Finding("no-undo", WARNING,
                                "declares undo=none; the UI will warn before applying, so make sure that is honest"))
    elif "undo)" in text and "recipe_restore_file" not in text and recipe.undo == "restore":
        findings.append(Finding("undo-without-restore", WARNING,
                                "declares undo=restore but never calls recipe_restore_file"))
    # A warning, never an error: every recipe written before icons existed has
    # none, and the engine already falls back to the category glyph, so this
    # is a nudge toward a better one rather than a defect. A *malformed* icon
    # is caught earlier, by parse_recipe, and lands as invalid-metadata above.
    icon_values = [v.strip() for v in re.findall(r"^\s*#\s*@recipe\.icon\b(.*)$", text, re.M)]
    if not icon_values:
        findings.append(Finding("no-icon", WARNING,
                                f"declares no @recipe.icon, so the UI draws the {recipe.category} "
                                f"category default; pick one as a \\uXXXX escape and confirm it "
                                f"renders rather than trusting the codepoint"))
    elif not any(icon_values):
        # The metadata regex needs a value, so a bare `# @recipe.icon` line is
        # not merely empty — it is invisible to the parser. Say so, rather than
        # reporting the icon as simply absent and leaving the author looking at
        # a line that is right there in the file.
        findings.append(Finding("empty-icon", ERROR,
                                "@recipe.icon has no value, so it is ignored entirely; "
                                "give it a \\uXXXX escape or remove the line"))
    if recipe.risk == "high" and recipe.undo == "none":
        findings.append(Finding("high-risk-irreversible", WARNING,
                                "high risk and no undo; say plainly in the description what cannot be reversed"))
    return findings


def lint_syntax(path: Path) -> list[Finding]:
    """Parse the script without running it."""
    try:
        proc = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [Finding("syntax-uncheckable", WARNING, f"could not run bash -n: {e}")]
    if proc.returncode == 0:
        return []
    detail = (proc.stderr or "").strip().splitlines()
    return [Finding("syntax-error", ERROR, detail[0] if detail else "bash reported a syntax error")]


def lint(path: Path) -> dict[str, Any]:
    """Full report for one recipe file."""
    try:
        text = path.read_text(errors="replace")
    except OSError as e:
        return {
            "path": str(path),
            "findings": [Finding("unreadable", ERROR, f"could not read: {e}").to_dict()],
            "errors": 1, "warnings": 0, "ok": False,
        }

    findings = lint_text(text, path) + lint_syntax(path) + lint_metadata(path)
    errors = [f for f in findings if f.severity == ERROR]
    warnings = [f for f in findings if f.severity == WARNING]
    return {
        "path": str(path),
        "findings": [f.to_dict() for f in findings],
        "errors": len(errors),
        "warnings": len(warnings),
        # The gate: a recipe with any error is not saved and not run.
        "ok": not errors,
    }
