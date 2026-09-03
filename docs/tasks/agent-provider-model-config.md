# Task: Configurable LLM provider/model settings (Claude, Copilot, Codex)

Status: Ready
Type: feature
Roadmap link: v0.2 → agent authoring; also the "configuration/model provider
abstraction" idea in `docs/dev/NEW_FEATURES.md`

## Goal

A user can persistently configure which AI provider and model the recipe
*authoring* agent uses (`omarchy-recipes agent plan` / `agent draft`), instead
of passing `--provider`/`--model` on every call or relying only on the
`OMARCHY_RECIPES_AGENT` environment variable. Support Claude, GitHub Copilot
CLI, and Codex as providers out of the box, in a way that a fourth provider
can be added without touching callers.

This is agent-authoring configuration only. It has nothing to do with what a
*recipe* itself does at apply-time — do not touch `execute()`/`run`.

## Context / current behavior

`src/omarchy_recipes/agent.py` already has a `Provider` abstraction:
`PROVIDER_ARGV` maps a provider name to an argv builder (`_claude_argv`,
`_codex_argv`), `providers()` reports what's installed, and
`default_provider()` picks one via `OMARCHY_RECIPES_AGENT` or falls back to
"claude". There is no persisted configuration — every choice is either an
environment variable or a per-call CLI flag (`agent.py:32-95`,
`cli.py` `agp`/`agl`/`agd` parsers around lines 131-148), and there is no
`copilot` provider yet.

There is currently no config file anywhere in the engine (no `config.py`,
no `~/.config/omarchy-recipes/config.*`) — this task introduces the first
one.

## Scope

1. **Add a `copilot` provider adapter** alongside `_claude_argv` /
   `_codex_argv` in `agent.py`. Research the installed `copilot` CLI's actual
   non-interactive/print flags (a `-p`/`--prompt`-style mode analogous to
   `claude -p` and `codex exec`, plus however it restricts tool/permission
   access — `DENIED_TOOLS` must be enforced the same way it is for Claude) —
   do not guess the flags; verify against `copilot --help` on this machine
   before hardcoding them. Add it to `PROVIDER_ARGV` and to the `complete()`
   output-parsing branch if its output format differs from plain stdout.
2. **Add a config file** at `~/.config/omarchy-recipes/config.json` (or reuse
   the existing config root if `OMARCHY_RECIPES_HOME` already defines one —
   check `core.py`/wherever `OMARCHY_RECIPES_HOME` is resolved before picking
   a path). Minimal shape:
   ```json
   {
     "agent": {
       "provider": "claude",
       "models": {"claude": null, "copilot": null, "codex": null}
     }
   }
   ```
   `models.<provider>` is the default `--model` value used when the user
   hasn't overridden it for that call; `null` means "let the provider pick
   its own default."
3. **Resolution order** for provider: explicit `--provider` flag >
   `OMARCHY_RECIPES_AGENT` env var (keep this for scripting/CI) > config file
   `agent.provider` > first installed provider (existing fallback). Same
   precedence shape for model, per provider.
4. **CLI surface** to read/write the config without hand-editing JSON:
   ```bash
   omarchy-recipes config get agent.provider
   omarchy-recipes config set agent.provider copilot
   omarchy-recipes config set agent.model.claude claude-sonnet-4.5
   omarchy-recipes config show --json
   ```
   Validate the provider name against `PROVIDER_ARGV` keys on `set`; reject
   unknown keys.
5. **Never store secrets in this file.** Provider CLIs (`claude`, `copilot`,
   `codex`) own their own auth/login state; this config only ever holds a
   provider name and a model string. Say so in a code comment, since the next
   temptation will be to add an API key field here.
6. **Surface it in the plugin**, minimally: `RecipeEngine.qml`'s existing
   "which provider will be invoked" read should reflect the configured
   default, not just installed/env state. A dedicated settings UI panel is
   welcome but not required — read `omarchy-recipes config show --json`
   is enough if a full settings screen is out of scope for time.
7. Update `docs/RECIPE_SPEC.md` or `docs/ARCHITECTURE.md` if the JSON
   envelope for `agent providers --json` gains a "configured default" field.

## Out of scope

- Any provider that isn't Claude, Copilot, or Codex (design the abstraction
  so adding one later is a single adapter function + registry entry, but
  don't build a plugin system for it now).
- Storing API keys/tokens.
- Per-recipe (as opposed to global) provider/model selection.
- Changing anything about `check`/`apply`/`undo`/recipe execution.

## Acceptance criteria

- [x] `copilot` provider adapter implemented and reported by
      `omarchy-recipes agent providers --json` when the `copilot` CLI is
      installed.
- [x] `omarchy-recipes config get|set|show` implemented, backed by a JSON
      file under the existing config root convention.
- [x] Provider/model resolution order (flag > env var > config > fallback)
      implemented and covered by a unit test for each of the three
      providers.
- [x] Invalid `config set` values (unknown key, unknown provider name) are
      rejected with a clear error and non-zero exit, not silently written.
- [x] No secret/token field exists in the config schema.
- [x] Engine tests redirect the config path the same way existing tests
      redirect `HOME`/`XDG_CONFIG_HOME`/`OMARCHY_RECIPES_HOME`, so they never
      touch a real user config file.
- [x] `make check` / `make validate` passes.
- [x] `docs/RECIPE_SPEC.md` / `docs/ARCHITECTURE.md` updated if the JSON
      contract changed.

## Testing notes

Manual:
```bash
omarchy-recipes agent providers --json          # confirm copilot appears
omarchy-recipes config set agent.provider copilot
omarchy-recipes config show --json
omarchy-recipes agent plan "..." --json         # confirm it actually invokes copilot
omarchy-recipes config set agent.provider bogus  # should fail, not write
```

## Report

Implemented. Two defects in the first pass were found only by testing the
provider for real, and both are worth recording because they would each have
shipped silently.

### The copilot adapter had to be rewritten against the real CLI

The first version was written from a plausible reading of `copilot --help` and
never actually exercised. It was wrong twice:

1. **The prompt never arrived.** `copilot -p/--prompt <text>` takes its text as
   a *required argument*, and copilot has no stdin mode at all. The engine
   passes prompts on stdin, so the built argv was
   `copilot -p --output-format json …` — `-p` would have consumed
   `--output-format` as the prompt. Verified: with `-p` last, copilot exits with
   `error: option '-p, --prompt <text>' argument missing`. Every authoring call
   through copilot would have failed.

   Fixed by giving the argv builders the prompt as well as the model, and adding
   `PROMPT_IN_ARGV` for providers with no stdin mode. stdin remains the default
   and is still what claude and codex use; the security note on that choice is
   unchanged for them.

2. **The tool denial denied nothing.** `DENIED_TOOLS` is written in Claude's
   vocabulary (`Bash`, `Edit`, `Write`…). Copilot's tools are named `bash`,
   `edit`, `create`, `web_fetch`, `task`, … — so passing `DENIED_TOOLS` to
   copilot matched zero tools while looking like an applied restriction. The
   model would have kept its shell.

   Fixed with an explicit `COPILOT_DENIED_TOOLS` mapping, and by switching from
   `--deny-tool` (permission-level) to `--excluded-tools`, which is the true
   analogue of Claude's `--disallowedTools`. Verified against ground truth
   rather than the model's self-report, by reading the tool list copilot emits
   in its own JSON stream: **24 tools → 8**, with `bash`, `edit`, `create`,
   `write_agent`, `web_fetch`, `web_search` and `task` all gone. Only read-only
   tools remain (`view`, `grep`, `glob`, `sql`, `skill`, agent readers), which
   matches what `DENIED_TOOLS` leaves Claude. The builtin GitHub MCP server is
   disabled for the same reason `WebFetch` is denied — it reaches the network.

### The config file made the installed-provider fallback dead code

`agent.provider` defaulted to the literal `"claude"`, so `config.get` returned a
provider name even with no config file present. `default_provider()` therefore
never reached its "first installed provider" branch: on a machine with codex but
not claude, the engine would have resolved to claude and then failed with
"claude is not installed" — a regression against existing behaviour.

Fixed by defaulting `provider` (and every model) to `null`, meaning "not
configured". Null is now the documented way to say "let the engine choose", and
is what `config set agent.provider null` restores. Covered by
`test_falls_back_to_the_first_installed_provider`.

### What was built

- `src/omarchy_recipes/config.py` — the engine's first config file, at
  `${XDG_CONFIG_HOME:-~/.config}/omarchy-recipes/config.json`, reusing
  `sources.workspace_root()` so `OMARCHY_RECIPES_HOME` relocates it exactly as
  it relocates the recipe collections. The no-secrets rule is stated in the
  module docstring, where the next person tempted to add an API key will read it.
- `config get|set|show` — `set` validates against `PROVIDER_ARGV` and rejects
  unknown keys *before* touching the disk, so a rejected write leaves the file
  byte-identical (asserted by `test_a_rejected_set_does_not_touch_the_file`).
  `agent.model.<provider>` is accepted as an alias for `agent.models.<provider>`
  because this task's own CLI examples use both spellings.
- Resolution order, for provider and model alike:
  flag > env var > config > fallback. `OMARCHY_RECIPES_MODEL` was added so the
  model has the same shape as `OMARCHY_RECIPES_AGENT`, per the task's "same
  precedence shape for model".
- `agent providers --json` gained a `model` field alongside `default`; both are
  the *resolved* answer, not merely what is installed.

### Testing

- 115 engine tests + 23 QML tests + `validate` — `make check` green.
- Resolution order is asserted for **each** of the three providers, including
  flag-beats-env-beats-config and per-provider model isolation.
- A real `agent plan` call through copilot end to end: returned a valid plan
  whose notes referenced `bindings.conf (does not exist on this machine)`,
  confirming the inspection facts genuinely reached the model.
- The plugin path was exercised for real, not just asserted: `RecipeEngine.qml`
  was driven headless under quickshell against the real CLI, and tracked the
  configured provider (`codex` → `codex`, `copilot` → `copilot`, cleared →
  first installed) and rendered the model when pinned.

### UI

`RecipeEngine.qml` already read `agent providers --json`, so the configured
default flowed through without QML changes. That surfacing was thin, so it now
also shows the pinned model and names the command that changes it, via a new
pure `Model.agentSummary()` helper with QML tests. There is still **no in-GUI
editing** of the setting — the task called a settings panel "welcome but not
required", and that remains the honest gap.

### Not done

- Left in `docs/tasks/`, not moved to `docs/tasks/done/`:
  `docs/AGENT_WORKFLOW.md` step 6 says to move it *once merged*, and this is on
  `dev`.
- No visual check of the plugin in a live session. The plugin is not installed
  on this machine, and installing it writes to `~/.config/omarchy/plugins/` and
  hot-reloads the running shell, so it needs the user's say-so.
