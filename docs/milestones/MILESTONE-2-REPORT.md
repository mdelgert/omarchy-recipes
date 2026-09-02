# Milestone 2 — AI-Assisted Recipe Authoring & Community Contribution

Status: **complete.** All 17 acceptance criteria are implemented and were
exercised against a live Omarchy session.

The spec's security boundary decides how this milestone is built:

```text
Natural language → Agent → Proposed Recipe → Validator → User Review → Runner → System
```

Everything in that chain except the agent itself is provider-independent, so it
lives in the engine where it can be tested without a model and cannot be
bypassed by one. The agent turns a request into a draft and a list of resource
claims; it never runs a modifying command, and nothing it produces reaches the
disk without passing `lint`.

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
| 1 | Create Recipe chat interface | done — `CreateRecipe.qml`, reached by `Ctrl+N` or the row above the list |
| 2 | User describes a change in the UI | done |
| 3 | Agent reads the authoring skill | done — the skill is fed to the model on every call and ships with the plugin |
| 4 | Agent inspects local configuration | done — `inspect` |
| 5 | Conflicts detected before generation | done — `conflicts`, run by the engine on the agent's claims |
| 6 | Conflicts require explicit resolution | done — Generate stays disabled until a resolution is chosen, and the engine refuses to draft anyway |
| 7 | Agent generates recipe metadata and logic | done — `agent plan` then `agent draft` |
| 8 | Recipe passes repository validation | done — `lint` gates the save |
| 9 | User can preview the generated recipe | done — the full Bash is shown before saving |
| 10 | Test/apply with the standard runner | done — a generated recipe applies and undoes like any other |
| 11 | Undo supported when practical | done — lint refuses a write without backup |
| 12 | Save the recipe locally | done — `create` |
| 13 | UI distinguishes local from bundled | done — a `local · ai` badge in the list, and "AI-generated, not reviewed" in the detail view |
| 14 | GitHub contribution workflow | done — `contribute`, previewed from the detail view |
| 15 | Branch/PR rather than direct writes | done — protected branches refused |
| 16 | Duplicates checked before submission | done — in `conflicts` and again in `contribute` |
| 17 | Safety guarantees intact | done — 75 engine tests, 21 QML tests |

## Verified end to end

Against a live Omarchy session, using the spec's own worked example:

1. `Ctrl+N` opens **Create a recipe**.
2. "Add a hotkey Super+Enter that opens Firefox" → the agent proposes the
   change, asks three clarifying questions, and the engine reports
   **"SUPER + RETURN is already assigned to Terminal"** with
   `replace existing / choose another shortcut / cancel`.
3. **Generate recipe is disabled** until one is chosen.
4. Choosing `replace existing` enables it; the generated recipe explicitly says
   it replaces the terminal binding "as requested".
5. The recipe passes validation, the Bash is shown in full, and saving stores it
   in the local collection.
6. The saved recipe opens in the normal detail view, badged
   **"Created on this machine · AI-generated, not reviewed"**, with its state
   read by `check` and Apply/Undo available.
7. **Contribute…** previews the branch, the file copy, and the commit.

The agent correctly wrote for `~/.config/hypr/bindings.lua` rather than the
`bindings.conf` of older Omarchy releases, because the `config-files` inspector
tells it which files actually exist.

## Known limitations

- **Authoring is slow.** A plan takes roughly a minute and a draft two to three,
  and the UI simply says "Thinking…" / "Writing the recipe…" for the duration.
  Streaming the model's output would fix the feel; it needs the same
  line-by-line plumbing as streaming recipe output.
- **`contribute --push` is implemented but only dry-run tested.** Branch,
  commit, and the generated PR body are exercised; opening a real pull request
  against the canonical repository was not, because doing so would have created
  an actual PR on your repository without asking.
- **One turn, not a conversation.** The agent asks clarifying questions and
  they are shown, but there is no way to answer them and re-plan — you refine
  the request and ask again. A real back-and-forth is the obvious next step.
- **Resolutions are keyed by resource type.** Two blocking conflicts of the
  same type would share one decision. No current checker produces that, but the
  key should become per-resource before one does.
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

1. **Streaming.** Both the agent's output and a running recipe's output are
   captured rather than streamed. It is the largest remaining gap in how the
   whole thing feels.
2. **A real conversation.** Answer the agent's clarifying questions and re-plan,
   instead of rewriting the request.
3. **Recipe-declared resources.** `@recipe.resource keybinding SUPER+RETURN`
   would let conflict detection work against installed recipes, not just drafts
   — and would let the browser warn that two recipes fight over the same key.
4. **Finish the push path.** Test `contribute --push` against a scratch fork,
   including `gh repo fork` when the contributor lacks write access.
5. **Secret parameters.** Still the outstanding safety item from Milestone 1.
