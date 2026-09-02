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

- [ ] `copilot` provider adapter implemented and reported by
      `omarchy-recipes agent providers --json` when the `copilot` CLI is
      installed.
- [ ] `omarchy-recipes config get|set|show` implemented, backed by a JSON
      file under the existing config root convention.
- [ ] Provider/model resolution order (flag > env var > config > fallback)
      implemented and covered by a unit test for each of the three
      providers.
- [ ] Invalid `config set` values (unknown key, unknown provider name) are
      rejected with a clear error and non-zero exit, not silently written.
- [ ] No secret/token field exists in the config schema.
- [ ] Engine tests redirect the config path the same way existing tests
      redirect `HOME`/`XDG_CONFIG_HOME`/`OMARCHY_RECIPES_HOME`, so they never
      touch a real user config file.
- [ ] `make check` / `make validate` passes.
- [ ] `docs/RECIPE_SPEC.md` / `docs/ARCHITECTURE.md` updated if the JSON
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

(fill in when done)
