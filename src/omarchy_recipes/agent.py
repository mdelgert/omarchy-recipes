"""Turning a natural-language request into a recipe draft.

This is the only part of the authoring path that talks to an AI provider, and
it is deliberately the *least* trusted part. It gets facts and returns text; it
never runs a modifying command, and nothing it returns reaches the disk without
passing `lint` first.

Two calls, each stateless:

    plan(request)                  → intent + the resources it wants to touch
    draft(request, plan, findings) → the recipe text

Between them the engine runs conflict detection, and the user resolves anything
blocking. That ordering is the point: the agent proposes, the engine checks, the
user decides.

Providers are adapters over a single `complete(prompt) -> str` operation, so
swapping Claude for another model changes nothing about the rules. The rules
live in `skills/recipe-authoring/SKILL.md`, which is fed to the model on every
call and is version-controlled with the project rather than with the provider.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core import RecipeError

DEFAULT_TIMEOUT = 240

# Tools the model must not have while authoring. It is being asked to write
# text, not to operate the machine; inspection reaches it as data in the prompt.
DENIED_TOOLS = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch", "Task"]


@dataclass
class Provider:
    name: str
    command: list[str]
    available: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.available, "reason": self.reason}


def _claude_argv(model: str | None) -> list[str]:
    argv = ["claude", "-p", "--output-format", "json"]
    if model:
        argv += ["--model", model]
    # Variadic flag: keep it last so it cannot swallow another argument.
    return argv + ["--disallowedTools", *DENIED_TOOLS]


def _codex_argv(model: str | None) -> list[str]:
    argv = ["codex", "exec", "--skip-git-repo-check"]
    if model:
        argv += ["--model", model]
    return argv


def _copilot_argv(model: str | None) -> list[str]:
    argv = ["copilot", "-p"]
    if model:
        argv += ["--model", model]
    argv += ["--output-format", "json"]
    # Restrict tool access the same way Claude does
    argv += ["--deny-tool", *DENIED_TOOLS]
    return argv


PROVIDER_ARGV: dict[str, Callable[[str | None], list[str]]] = {
    "claude": _claude_argv,
    "codex": _codex_argv,
    "copilot": _copilot_argv,
}


def providers() -> list[Provider]:
    out = []
    for name, builder in PROVIDER_ARGV.items():
        argv = builder(None)
        found = shutil.which(argv[0])
        out.append(Provider(
            name=name,
            command=argv,
            available=bool(found),
            reason="" if found else f"{argv[0]} is not installed",
        ))
    return out


def default_provider() -> str:
    from . import config
    # Resolution order: env var > config > first installed provider
    override = os.environ.get("OMARCHY_RECIPES_AGENT")
    if override:
        return override
    try:
        configured = config.get("agent.provider")
        return configured
    except RecipeError:
        pass
    for provider in providers():
        if provider.available:
            return provider.name
    return "claude"


def resolve_model(provider: str | None = None) -> str | None:
    """Get the configured default model for a provider.

    Resolution order: explicit model > env var > config > None (provider picks).
    """
    from . import config
    p = provider or default_provider()
    try:
        configured = config.get(f"agent.models.{p}")
        return configured
    except RecipeError:
        pass
    return None


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply.

    Models wrap JSON in prose or fences more often than not. Rather than
    demanding perfection from the model, take the first balanced object and let
    the schema check below decide whether it is usable.
    """
    raw = str(text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()
    start = raw.find("{")
    if start < 0:
        raise RecipeError("the agent did not return JSON")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw)):
        ch = raw[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:index + 1])
                except ValueError as e:
                    raise RecipeError(f"the agent returned malformed JSON: {e}") from e
    raise RecipeError("the agent returned an unterminated JSON object")


def complete(prompt: str, *, provider: str | None = None, model: str | None = None,
             timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run one prompt through the selected provider and return its reply text."""
    name = provider or default_provider()
    builder = PROVIDER_ARGV.get(name)
    if builder is None:
        raise RecipeError(f"unknown agent provider {name!r}; available: {', '.join(sorted(PROVIDER_ARGV))}")
    # Use explicit model, or fall back to configured default
    resolved_model = model or resolve_model(name)
    argv = builder(resolved_model)
    if not shutil.which(argv[0]):
        raise RecipeError(f"{argv[0]} is not installed; set OMARCHY_RECIPES_AGENT to another provider")

    try:
        # The prompt goes on stdin: it is long, it contains newlines, and a
        # variadic flag must never be able to consume it.
        proc = subprocess.run(argv, input=prompt, text=True, capture_output=True,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise RecipeError(f"{name} did not respond within {timeout}s") from e
    except OSError as e:
        raise RecipeError(f"could not run {name}: {e}") from e

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RecipeError(f"{name} failed: {detail[0] if detail else 'no output'}")

    if name == "claude":
        try:
            payload = json.loads(proc.stdout)
        except ValueError as e:
            raise RecipeError(f"{name} returned unreadable output: {e}") from e
        if payload.get("is_error"):
            raise RecipeError(f"{name} reported an error: {payload.get('result') or 'unknown'}")
        return str(payload.get("result") or "")
    elif name == "copilot":
        # Copilot outputs JSONL; extract the assistant message from the stream
        return _extract_copilot_response(proc.stdout)
    return proc.stdout


def _extract_copilot_response(jsonl_output: str) -> str:
    """Extract the assistant's final message from copilot's JSONL output."""
    for line in jsonl_output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "assistant.message":
                content = obj.get("data", {}).get("content", "")
                if content:
                    return content
        except ValueError:
            pass
    raise RecipeError("copilot did not return a valid response")


# ------------------------------------------------------------------ prompts


def _skill_text(root: Path) -> str:
    path = root / "skills" / "recipe-authoring" / "SKILL.md"
    try:
        return path.read_text()
    except OSError as e:
        raise RecipeError(f"cannot read the authoring skill at {path}: {e}") from e


RESOURCE_SCHEMA = """Resource types and the field each expects:

  {"type": "keybinding",  "value": "SUPER + RETURN"}
  {"type": "file",        "path": "~/.config/hypr/bindings.lua"}
  {"type": "package",     "name": "firefox"}
  {"type": "service",     "name": "docker.service"}
  {"type": "port",        "port": 8080, "protocol": "tcp"}
  {"type": "mount",       "path": "/mnt/nas"}
  {"type": "container",   "name": "media-server"}
  {"type": "environment", "name": "EDITOR"}
  {"type": "config",      "key": "decoration:rounding"}
  {"type": "recipe",      "keywords": ["hotkey", "firefox"]}

Always include a `recipe` claim with `keywords` so an existing equivalent
recipe can be found.

Claim ONLY what the recipe will actually create or modify. Do not claim a
resource you merely considered and rejected, and do not claim a shortcut you are
not going to bind — every claim becomes a conflict the user has to resolve, and
one raised over something the recipe never touches is noise that trains them to
click through the real ones. `config` claims must name a real Hyprland option
such as `decoration:rounding`, not a general area.

Write to the config files that actually exist on this machine. The
`config-files` facts above say which are present and in what format — this
Omarchy release may use `.lua` config where an older one used `.conf`. Do not
assume; a recipe that appends to a file nothing reads is worse than no recipe."""


PLAN_SCHEMA = """{
  "summary": "one sentence describing exactly what will change",
  "recipe_id": "lowercase-hyphenated-id",
  "title": "Human readable title",
  "category": "System | Power | Applications | Development | Networking | Storage | Security | Omarchy | Desktop",
  "risk": "low | medium | high",
  "undo": "restore | command | none",
  "resources": [{"type": "keybinding", "value": "SUPER + RETURN"}],
  "questions": ["anything genuinely ambiguous that you cannot decide yourself"],
  "notes": "what you will not touch"
}"""


def plan(request: str, root: Path, *, inspection_data: dict[str, Any] | None = None,
         notes: list[str] | None = None,
         provider: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Ask what the change would touch, before any Bash exists.

    `notes` carries the exchange so far — the agent's questions and the user's
    answers, plus any correction. Each call is still stateless: the whole
    exchange is re-sent, so there is no hidden conversation state to get out of
    step with what the user can see.
    """
    facts = json.dumps(inspection_data or {}, indent=2)[:20000]
    exchange = ""
    if notes:
        joined = "\n".join(f"- {n}" for n in notes)
        exchange = f"""

The user has already told you the following. Treat it as authoritative and do
not ask about it again:

<answers-so-far>
{joined}
</answers-so-far>
"""
    prompt = f"""You are the recipe-authoring agent for `omarchy-recipes`.

Read these rules and follow them exactly. They are authoritative:

<authoring-skill>
{_skill_text(root)}
</authoring-skill>

The user asked for:

<request>
{request}
</request>

Read-only facts about this machine, gathered by the engine:

<system-facts>
{facts}
</system-facts>
{exchange}
Do NOT write a recipe yet. Identify what the change would touch so the engine
can check for conflicts first.

{RESOURCE_SCHEMA}

Reply with ONE JSON object and nothing else:

{PLAN_SCHEMA}
"""
    reply = _extract_json(complete(prompt, provider=provider, model=model))
    if not isinstance(reply.get("resources"), list):
        reply["resources"] = []
    for key in ("summary", "recipe_id", "title", "category"):
        reply.setdefault(key, "")
    reply.setdefault("questions", [])
    return reply


def draft(request: str, root: Path, plan_data: dict[str, Any],
          *, findings: list[dict[str, Any]] | None = None, decisions: dict[str, str] | None = None,
          provider: str | None = None, model: str | None = None) -> str:
    """Ask for the recipe text, after conflicts have been resolved."""
    conflict_text = json.dumps(findings or [], indent=2)[:12000]
    decision_text = json.dumps(decisions or {}, indent=2)

    prompt = f"""You are the recipe-authoring agent for `omarchy-recipes`.

Read these rules and follow them exactly. They are authoritative:

<authoring-skill>
{_skill_text(root)}
</authoring-skill>

The user asked for:

<request>
{request}
</request>

Your own plan for the change:

<plan>
{json.dumps(plan_data, indent=2)}
</plan>

The engine checked your claimed resources and found:

<conflicts>
{conflict_text}
</conflicts>

The user resolved them as follows. Honor these exactly; do not revisit them:

<decisions>
{decision_text}
</decisions>

Write the complete recipe now.

Hard requirements, all enforced by `omarchy-recipes lint`:
- start with `#!/usr/bin/env bash` and `set -Eeuo pipefail`
- declare @recipe.id, @recipe.title, @recipe.description, @recipe.category,
  @recipe.privilege, @recipe.undo, @recipe.risk
- do NOT declare @recipe.generated-with-ai or @recipe.reviewed; the engine stamps those
- implement all three of `check)`, `apply)`, and `undo)`
- `check` must not modify anything, and must end by calling
  `recipe_state configured|not-configured "detail"`
- call `recipe_backup_file` (or `recipe_mark_absent` when the target does not
  exist) before writing any file
- never use eval, never pipe a download into a shell, never embed a credential
- quote every expansion, including "$RECIPE_ARG_*"

Reply with ONE JSON object and nothing else:

{{"recipe_id": "the id", "recipe": "the complete bash script as a JSON string"}}
"""
    reply = _extract_json(complete(prompt, provider=provider, model=model))
    text = str(reply.get("recipe") or "")
    if not text.strip():
        raise RecipeError("the agent returned an empty recipe")
    return text
