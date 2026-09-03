# Handoff notes: what to carry forward into `omarchy-scripts`

Written from `omarchy-recipes` to seed a new, deliberately simpler project.
The decision behind this document: `omarchy-recipes` grew AI-authoring,
mandatory-shaped undo, conflict detection, and lint-as-a-hard-gate all at
once, and that combination made even a one-line change slow and fragile to
generate. The new project keeps the parts that were genuinely good — the
self-describing header-comment pattern, a stable JSON contract, and a clean
engine/frontend split — and defers everything else (AI authoring, full
backup/restore machinery, mandatory undo) to a later, optional layer.

## What to keep — it worked

### 1. Self-describing header comments (the best idea in this repo)

A script declares what it is in its own comments, so a UI never needs
per-script code:

```bash
# @recipe.id add-passwordless-sudo
# @recipe.title Passwordless sudo for a user
# @recipe.description Adds a sudoers.d entry allowing a user to run sudo without a password prompt.
# @recipe.category Security
```

Source: `docs/RECIPE_SPEC.md` "Required metadata" /
`src/omarchy_recipes/core.py` (`Recipe` dataclass + parser, ~lines 78-243).
Keep this pattern verbatim — required keys: id, title, description,
category. Everything else in that file can be optional in v1.

### 2. Declared parameters, one line each

```bash
# @param hostname string required=true label="Hostname"
# @param mode choice default=balanced choices=performance,balanced,powersave
```

This is what lets a UI generate a form with zero per-script UI code
(`docs/VISION.md`'s "Generated parameter controls" section — string→text,
integer→number, boolean→toggle, choice→select, path→picker). Keep the
type vocabulary small: `string`, `integer`, `boolean`, `choice`, `path`.
Drop `secret` for v1 (it was reserved, never finished, in this repo either).

### 3. A tiny arg-parsing helper, not a framework

`lib/recipe.sh`'s `recipe_parse_args "$@"` turns `--hostname foo` into
`RECIPE_ARG_HOSTNAME=foo`. That's genuinely useful boilerplate-removal and
costs nothing to keep. Keep this helper; you do not need the backup/restore
half of that file for v1 (see "What to leave out" below).

### 4. `check` / `run` as the baseline verbs; `undo` optional per-script

Keep exactly two required verbs:

- `check` — read-only, reports current state.
- `apply`/`run` — does the thing.

Make `undo` genuinely optional, not a mandatory third action every script
must implement. A script with no undo story just doesn't declare one — no
`@recipe.undo` field, no stub function, no "declares undo=none and dies"
ceremony. That ceremony is what made simple scripts feel heavier than they
are. (This is already technically possible in `omarchy-recipes` via
`@recipe.undo none`, but the authoring rules and lint still made every
script *reason about* undo up front — in v1, don't ask a script to reason
about it at all unless it wants to.)

### 5. A one-line, human-readable state report

```bash
recipe_state configured "Timeout: 600 seconds"
```

Cheap, and it's the single thing that made a generated UI show real status
instead of guessing from stdout. Worth keeping even in a minimal version —
it's a tiny convention, not a subsystem.

### 6. Stable, versioned JSON output from day one

`docs/ARCHITECTURE.md` (~line 58): every `--json` response carries a
`schemaVersion` a frontend checks before trusting the rest. This cost
nothing to add early and would have been painful to retrofit. Do this in
v1 even though the UI is simple, because you already know a second frontend
(or v2's AI layer) is coming.

### 7. Engine/frontend separation

The engine (a plain script/small program that discovers, parses, and runs
scripts) never depends on QML; QML never parses script comments itself, it
only reads the engine's normalized JSON. Keep this boundary from the start —
it's what makes "start a CLI now, add a TUI or a chat UI later" possible
without rewriting the core.

### 8. Trust/provenance as one honest field, not a subsystem

`bundled` vs `local` vs `community` (`src/omarchy_recipes/sources.py`) is a
reasonable idea — "did this ship with the project or did I add it" — but
keep it to a single field on discovery, not a multi-tier precedence system,
unless you actually have multiple real sources on day one.

## What to leave out of v1 — this is what made things slow/fragile

### 1. AI authoring as a one-shot, rules-heavy prompt

`src/omarchy_recipes/agent.py`'s `draft()` sends the entire skill file plus
duplicated inline rules (~19 numbered safety rules) in a single prompt, with
no automatic repair loop — a lint failure required the human to manually
re-ask, at a full round-trip cost (the 90+ second delays and repeated
"refused: 4 errors" you hit came from exactly this: unquoted variable
expansions and bare `sudo` calls, requiring a full new generation each retry).

Your own instinct is right: build v2's AI layer *after* you know the bare
model latency floor with no rules attached, then add rules incrementally and
measure again. If/when you do add it, build the auto-repair loop
(feed lint/errors back to the same model call) from the start — don't repeat
this project's mistake of making a human be the retry loop.

### 2. Mandatory backup/restore machinery

`recipe_backup_file`, `recipe_mark_absent`, `recipe_restore_file`
(`lib/recipe.sh`, documented in `docs/RECIPE_SPEC.md`'s "Backup contract")
are well-designed for what they do, but requiring every script author to
reason about them up front is exactly the "too many instructions" problem.
Bring this back later as an opt-in helper library ("skills" layer) for
scripts that specifically want exact-restore undo — most scripts don't need
it; "just run it again" or "no undo" covers a lot of real cases.

### 3. Conflict detection (`omarchy-recipes conflicts`) as a required step

A genuinely good idea (`skills/recipe-authoring/SKILL.md` step 3-4) but it's
infrastructure for *AI-authored* scripts avoiding collisions with each
other and the machine. Don't build it until you have AI authoring; it has no
value for a human writing and running their own script.

### 4. Lint as a hard, blocking gate

Static safety checks (`omarchy-recipes lint`) are useful as *warnings* a
human reads. Making them `refused` failures that block saving — especially
combined with a slow one-shot AI generator — is what produced the
frustrating loop in your screenshot. In v1: lint can print warnings; it
should not be the thing standing between you and running your own script.

### 5. No way to view/edit/delete/run a script directly

This repo's UI never surfaces "here's the file, open it, edit it, delete it,
or drop to a terminal and run `check`/`apply` yourself before trusting the
generated UI." (Confirmed: no such affordance exists in
`omarchy-plugin/RecipeDetail.qml` or `Menu.qml` today.) For v1, make this a
first-class, early feature — you said it yourself: staying close to the
code you already know and trust is the whole point of a v1. A "view file
path / open in $EDITOR / run in a terminal" action should exist before any
generated-form UI polish.

## Suggested v1 shape for `omarchy-scripts`

```text
scripts/                   your own scripts, header-comment metadata only
lib/scripts.sh             recipe_parse_args + recipe_state + nothing else
bin/omarchy-scripts         discover, parse metadata, dispatch check/run,
                            emit versioned JSON, list/view/edit/delete/run
```

No conflict detection, no AI, no mandatory undo, no lint gate — those are
the "skills" layer you bolt on later, once v1 is something you already run
daily and trust.

## Everything else in this repo, for later reference

`docs/VISION.md`, `docs/ARCHITECTURE.md`, `docs/RECIPE_SPEC.md`, and
`skills/recipe-authoring/SKILL.md` remain the fullest write-up of the
harder version of this idea (reversibility, AI-authored safety, trust
model) if/when `omarchy-scripts` grows into wanting them. Nothing here
recommends deleting `omarchy-recipes` — it's the reference for "what the
advanced version looks like," should you want to pull a specific piece back
in once v1 is solid.
