# Task: Report-only diagnostic recipes (network info, curl+JSON, system diagnostics)

Status: Ready
Type: feature
Roadmap link: v0.3 — real recipe library

## Goal

A user can run recipes that only *display* information — hostname/network
info, a pretty-printed JSON response from a `curl` call, and general system
diagnostics — with no confusing "what does Apply even do here?" moment, and a
future recipe author (human or agent) has one documented pattern to copy
instead of reinventing it per recipe.

## Context / current behavior

The recipe lifecycle in `docs/VISION.md` (INSPECT → BACKUP → APPLY → VERIFY →
RECORD) is written for state-mutating recipes. For a recipe that only reads
and displays data, "Apply" doesn't map cleanly onto "change something" — there
is nothing to back up, verify, or undo.

The collection already contains this exact pattern, just not written down
anywhere as a reusable convention:

- `recipes/examples/example-demo-report.sh` — `@recipe.undo none`; `apply`
  re-reads and prints state, with a comment explaining *why* undo is none.
- `recipes/community/error-log-report.sh` — `@recipe.undo restore` (it installs
  a script + menu entry, so that part *is* reversible), but the installed
  script itself is a pure report.

`docs/RECIPE_SPEC.md` documents `undo: none` as an allowed value but never
explains that "this recipe's `apply` is just `check`'s reporting logic run
again, and that's fine" is an intentional, named pattern rather than a recipe
that's missing an undo.

## Scope

1. **Document the pattern** in `docs/RECIPE_SPEC.md` (short new section, e.g.
   "Report-only recipes"), covering:
   - `check` reports current state as usual.
   - `apply` performs the read/query and prints the result via `recipe_note`
     / `recipe_summary`; it does not modify anything.
   - `undo` is declared `none` and must exit non-zero with a clear message
     (matches skill rule already in `skills/recipe-authoring/SKILL.md`,
     mandatory structure item 6) — no backup/restore calls are needed because
     nothing was changed.
   - This is a naming/documentation clarification, not a new action verb:
     the existing `check`/`apply`/`undo` protocol is unchanged.
2. Add a short "safe `curl` usage" note (in `RECIPE_SPEC.md` or
   `skills/recipe-authoring/SKILL.md`, whichever fits better next to the
   existing curl-pipe-shell rule): fixed/validated URL (no unvalidated
   user-supplied URL param passed straight to `curl`), explicit timeout
   (`curl --max-time`), and a clear failure message instead of a silent empty
   result.
3. Add three new recipes under `recipes/examples/` (or `recipes/community/` if
   that fits the existing split better — match whichever existing recipes of
   this shape already live there):
   - `network-info-report` — hostname, IP address(es), default route, DNS
     resolvers. Read-only.
   - `http-json-report` — `curl` a fixed, documented endpoint (e.g. a public
     "what's my IP" JSON endpoint) with a timeout, and pretty-print the JSON
     response (`python3 -m json.tool`, since Python is already a project
     dependency — do not add a `jq` dependency). Handle request failure with a
     clear error, not a crash or silent blank output.
   - `system-diagnostics-report` — kernel version, uptime, CPU/memory/disk
     summary. Read-only.

   All three: `@recipe.undo none`, `check` reports `unsupported` or a trivial
   always-current state (there's nothing to be "configured" or not), `apply`
   prints the report, `undo` fails clearly per the documented pattern.

## Out of scope

- No new action verb or engine/JSON contract change — reuse `check` / `apply`
  / `undo` exactly as specified today.
- No new `@recipe.*` metadata fields or `@param` types.
- No GUI/QML changes.
- No change to `error-log-report.sh` (it already follows the right shape for
  its own case).

## Acceptance criteria

- [ ] `docs/RECIPE_SPEC.md` documents the report-only recipe pattern
- [ ] safe-curl guidance (timeout, fixed/validated URL, explicit failure) is
      documented next to the existing curl-pipe-shell rule
- [ ] `network-info-report`, `http-json-report`, and `system-diagnostics-report`
      recipes added, each passing `omarchy-recipes lint`
- [ ] each new recipe's `undo` exits non-zero with a clear message (no
      backup/restore machinery, since nothing is mutated)
- [ ] `make test validate` (or `make check`) passes
- [ ] `./bin/omarchy-recipes validate` passes

## Testing notes

- Run `check`, `apply` (`run`), and `undo` manually for each new recipe.
- For `http-json-report`, test the failure path (no network / unreachable
  host) and confirm it reports a clear error instead of hanging past its
  timeout or printing blank output.
- Confirm running `apply` repeatedly is safe (pure reads, no side effects) —
  this is the idempotency property that matters for a report-only recipe.

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
