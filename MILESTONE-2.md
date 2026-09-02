# Milestone 2 — AI-Assisted Recipe Authoring & Community Contribution

Status: **engine and rules complete; plugin UI and provider adapter not started.**

The spec's security boundary decides how this milestone is built:

```text
Natural language → Agent → Proposed Recipe → Validator → User Review → Runner → System
```

Everything in that chain except the agent itself is provider-independent, so it
belongs in the engine where it can be tested without a model and cannot be
bypassed by one. That half is done. The chat interface and the model adapter —
the parts that need QML and an AI provider — are not.

## What works now

An agent (or a person) can author a recipe end to end from the command line:

```bash
omarchy-recipes inspect --json keybindings          # read the machine, read-only
echo '{"resources":[{"type":"keybinding","value":"SUPER + RETURN"}]}' \
  | omarchy-recipes conflicts --json                # exits 3 when the user must decide
omarchy-recipes lint --json < draft.sh              # static + AI-safety gate
omarchy-recipes create my-recipe --json < draft.sh  # save to the local collection
omarchy-recipes run my-recipe                       # normal runner, backup and undo
omarchy-recipes contribute my-recipe --testing "…"  # dry-run pull request plan
```

### Recipe sources and trust

Discovery now walks three collections in trust order:

```text
<engine root>/recipes/                        bundled    reviewed upstream
~/.config/omarchy-recipes/recipes/local/      local      written here, by the user or an agent
~/.config/omarchy-recipes/recipes/community/  community  from someone else's collection
```

A lower tier can never take an id a higher tier already claimed. Shadowing
`install-docker` with a generated file would let untrusted code run under a name
the user believes is reviewed, so the collision is reported and the bundled
recipe wins. `OMARCHY_RECIPES_HOME` relocates the workspace; browsing never
creates it.

This also closes the "no user recipe directory" limitation from Milestone 1.

### Provenance the recipe cannot fake

`@recipe.generated-with-ai` and `@recipe.reviewed` are stripped from every draft
and re-stamped by the engine at save time. A recipe declaring itself reviewed
gets `reviewed false` unless the caller passed `--reviewed`. Origin comes from
which directory the file was found in, never from the file's own claim.

### Inspection (`inspect`)

Read-only snapshots for `keybindings`, `packages`, `services`, `ports`,
`mounts`, `containers`, and `environment`, plus a `config` lookup for individual
Hyprland options. Every inspector runs a fixed argv, is bounded by a timeout,
and reports `available: false` with a reason rather than raising — "I could not
look" is never returned as "there is nothing there". Secret-looking environment
values are redacted before they can reach a prompt or a log.

Adding a domain means adding one function to `INSPECTORS`.

### Conflict detection (`conflicts`)

The agent declares what it intends to touch *before* writing any Bash:

```json
{"resources": [{"type": "keybinding", "value": "SUPER + RETURN"}]}
```

Ten resource types are checked: keybinding, file, package, service, port,
mount, container, environment, config, and recipe. Each finding carries a
status, a severity, and concrete `resolutions` the UI can offer — the spec is
explicit that the agent must not pick one itself.

The spec's headline example works against real data: asking about
`super+Return` reports *"SUPER + RETURN is already assigned to Terminal"* with
`replace-existing / choose-another-shortcut / cancel`. Shortcut spellings are
normalized, so `Mod4 + Enter` and `SUPER+RETURN` compare equal.

`requires_user_decision` is set when anything blocking is found, and the CLI
exits **3**, so a caller that ignores the report still cannot barrel past a
conflict.

### Lint and AI safety (`lint`)

The gate between a generated recipe and the disk. Errors refuse the save;
warnings must be shown. It parses with `bash -n` and never executes the recipe.

Errors: `curl | bash`, `eval`, recursive delete of a root or home path,
world-writable permissions, disabling a security control, embedded credentials,
a missing shebang, a missing `check`/`apply`/`undo` branch, and writing files
without `recipe_backup_file` / `recipe_mark_absent`.

Warnings: recursive permission changes, unquoted globs in deletes, hidden
persistence, `sudo bash`, unquoted parameter expansions, `undo: none`, high risk
with no undo, and a `check` that reports no state.

Comments are stripped before matching, so documentation *about* a hazard is not
flagged as one. All four bundled recipes lint clean.

### Contribution (`contribute`)

Dry run by default. It validates, lints, looks for duplicates, and prints the
branch it would create plus a pull request body generated from the recipe's own
metadata following the spec's template. `--commit` branches and commits;
`--push` pushes and opens the PR. Protected branches are refused, and a bundled
recipe cannot be re-contributed.

### Skills

`skills/recipe-authoring/SKILL.md` gained the generation workflow: inspect,
declare resources, stop on conflicts, check for an existing recipe, write, lint,
show the Bash, save, test. `skills/recipe-contribution/SKILL.md` is new and
covers the eight checks before a PR plus the rules (never push to main, one
recipe per PR, never include the conversation, state plainly that AI was used).

## Acceptance criteria

| # | Criterion | State |
| --- | --- | --- |
| 1 | Create Recipe chat interface | **not started** — needs QML |
| 2 | User describes a change in the UI | **not started** — needs QML |
| 3 | Agent reads the authoring skill | done — skill rewritten for generation |
| 4 | Agent inspects local configuration | done — `inspect` |
| 5 | Conflicts detected before generation | done — `conflicts` |
| 6 | Conflicts require explicit resolution | engine done (`requires_user_decision`, exit 3, `resolutions`); UI pending |
| 7 | Agent generates recipe metadata and logic | **not started** — needs the provider adapter |
| 8 | Recipe passes repository validation | done — `lint` + `validate` |
| 9 | User can preview the generated recipe | engine done (`lint` on a draft returns the findings); UI pending |
| 10 | Test/apply with the standard runner | done — verified apply and undo on a generated recipe |
| 11 | Undo supported when practical | done — lint refuses a write without backup |
| 12 | Save the recipe locally | done — `create` |
| 13 | UI distinguishes local from bundled | engine done (`source`, `source_label`, `reviewed_upstream`); UI pending |
| 14 | GitHub contribution workflow | done — `contribute` (push path untested, see below) |
| 15 | Branch/PR rather than direct writes | done — protected branches refused |
| 16 | Duplicates checked before submission | done — `conflicts` type `recipe`, and in `contribute` |
| 17 | Safety guarantees intact | done — 68 tests pass |

## Known limitations

- **No chat UI and no provider adapter yet.** Criteria 1, 2, and 7 are the
  remaining half of the milestone. The engine is deliberately ready for them:
  the adapter's whole job is to turn a request into draft text and resource
  claims, because everything it would otherwise be trusted to get right is
  already enforced elsewhere.
- **The `--push` path is unverified.** `gh` is installed but not authenticated
  on this machine, so branch-and-commit and the generated PR body are tested
  while the actual push and `gh pr create` are not.
- **Conflict coverage is per-resource, not semantic.** The engine can tell you
  `SUPER + RETURN` is taken; it cannot tell you that two recipes configure the
  same idea in different files. That needs recipes to declare the resources they
  touch, which is a natural next step.
- **Lint is pattern-based.** It catches the constructs the spec names and does
  not pretend to be a general shell analyzer. ShellCheck would complement it and
  is deliberately not a dependency.
- **Inspection reflects the running session.** The environment domain shows the
  engine process's variables, not what a login shell would have.

## How to test

```bash
make check     # 68 engine tests, 18 QML logic tests, recipe validation
```

The authoring tests redirect `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, and
`OMARCHY_RECIPES_HOME` into a temporary directory, so they never read or write a
real collection. Conflict tests inject canned inspection data rather than
reading the machine, so they assert the logic and pass on a bare CI box.

Manual, against this machine:

```bash
omarchy-recipes sources
omarchy-recipes inspect keybindings | head
echo '{"resources":[{"type":"keybinding","value":"super+Return"},
                    {"type":"recipe","id":"example-config-value"}]}' \
  | omarchy-recipes conflicts
```

## Next

1. **Provider adapter.** `RecipeAuthoringAgent` with a Claude adapter first
   (`claude`, `codex`, and `opencode` are all on this machine). It reads the
   authoring skill, calls `inspect` and `conflicts`, and returns draft text — it
   never runs a modifying command.
2. **Create Recipe UI.** A chat pane in the plugin, conflict prompts rendered
   from `resolutions`, and the generated Bash shown in full before saving.
3. **Trust badges in the browser.** `source_label` and `reviewed_upstream` are
   already in `list --json`; the browse list needs to show them.
4. **Recipe-declared resources.** `@recipe.resource keybinding SUPER+RETURN`
   would let conflict detection work against installed recipes, not just drafts.
