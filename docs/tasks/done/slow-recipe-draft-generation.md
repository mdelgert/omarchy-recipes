# Task: Investigate and fix slow recipe-draft generation (90+ seconds for trivial requests)

Status: Done
Type: bug
Roadmap link: v0.2 — usable interaction

## Goal

Generating a recipe for a simple, one-liner request (e.g. "change hostname")
takes a predictable, reasonable amount of time — not 90+ seconds — or, if the
floor is genuinely set by the AI provider's own cold-start/tool-use overhead
and can't be reduced, the user gets visible progress instead of an opaque
multi-minute hang.

## Context / current behavior

`src/omarchy_recipes/agent.py` is the only part of the authoring path that
calls out to an AI provider (module docstring, ~lines 1-19): two stateless
calls, `plan(request)` then `draft(request, plan, findings)`, each a fresh
subprocess invocation of the configured provider CLI (`claude`, `copilot`, or
`codex`), each with its own `DEFAULT_TIMEOUT = 240` seconds (~line 32). Two
things worth measuring, not assuming, before changing anything:

1. **Two full round trips per request.** `plan` and `draft` are separate
   provider calls (per the module docstring), each paying whatever the
   provider CLI's own startup/tool-use overhead is — for a one-liner request
   this might dominate the total time regardless of prompt size.
2. **Fixed inspection scope regardless of request complexity.** `cli.py`'s
   `agent plan` handling defaults to gathering four inspection domains —
   `config-files`, `keybindings`, `packages`, `services` (~line 369 in
   `cli.py`) — every time, even for a request like "change hostname" that
   doesn't plausibly need keybinding or package inspection.
   `inspect_packages()`/`inspect_services()` in `inspection.py` (~lines
   126-153) shell out to package-manager/systemd queries that are not free.
   `skills/recipe-authoring/SKILL.md` is also fed to the model on every call
   (`agent.py` docstring, ~line 18) — worth confirming its size isn't itself
   a meaningful chunk of prompt-processing time.

This task is explicitly a **measure-first** task: don't guess which of the
above (or something else entirely, e.g. the provider CLI's own subprocess
startup cost) is the dominant factor before changing behavior.

## Scope

1. Add timing instrumentation (temporary, or a `--verbose`/debug flag that
   stays) around: inspection gathering, prompt construction, and each
   provider subprocess call (`plan` and `draft` separately) in the `agent
   plan` / `agent draft` CLI path.
2. Reproduce the reported slowness with a concrete, simple request (e.g.
   "change hostname") against at least one real configured provider, and
   record where the ~90+ seconds actually goes.
3. Based on measured findings, implement the highest-leverage fix. Candidates
   to evaluate against the actual measurements (do not implement all of
   these blindly):
   - Only gather inspection domains actually relevant to the request, or let
     `plan`'s own output narrow what `draft` needs, instead of a fixed
     four-domain default for every `agent plan` call.
   - Avoid re-doing work between `plan` and `draft` that only needs to happen
     once per request.
   - Surface incremental progress/output to the user (e.g. stream provider
     output as it's produced, or emit a status update before/after each
     phase) if the floor turns out to be unavoidable provider latency, so a
     90-second wait is not indistinguishable from a hang.
4. Document the measured baseline and the fix's effect (before/after timing)
   in this task's Report section.

## Out of scope

- Switching default providers or changing which providers are supported.
- Any change to the recipe execution (`check`/`run`/`undo`) path — this is
  authoring-time only.
- Caching or persisting provider responses across different requests (a
  cache keyed on identical repeated requests could be a reasonable future
  idea, but don't fold it into this bug fix without first confirming
  round-trip count, not caching, is the actual bottleneck).
- Rewriting `skills/recipe-authoring/SKILL.md`'s content — only its size/cost
  as prompt input is in scope to *measure* here, not to rewrite for style.

## Acceptance criteria

- [x] timing breakdown captured for a real "change hostname"-style request,
      showing where the ~90+ seconds is spent
- [x] a concrete fix implemented based on that breakdown (reduced inspection
      scope, reduced round trips, and/or visible progress reporting —
      whichever the measurement points to)
- [x] measured improvement (or, if the floor is unavoidable provider
      latency, visible progress feedback added) demonstrated with before/
      after numbers in the Report section
- [x] existing `agent plan`/`agent draft` behavior and output contract
      otherwise unchanged (still two stateless calls returning the same JSON
      shape, unless the investigation justifies changing that — call it out
      explicitly in the Report if so)
- [x] tests added/updated for any changed inspection-domain-selection logic
- [x] `make test validate` (or `make check`) passes
- [x] `./bin/omarchy-recipes validate` passes

## Testing notes

- Test with whichever provider CLI is actually installed/configured on this
  machine (`omarchy-recipes agent providers` lists what's available).
- Watch for a regression where narrowing inspection domains causes `plan` to
  miss a real conflict it previously would have caught — a false "no
  conflicts" is worse than a slow response.

## Report

Measured first. The measurement contradicted the task's own leading hypothesis,
so the fix is somewhere else entirely.

### Baseline: where the time actually went

Request "script that changes hostname", provider `claude`, no model pinned:

| Phase | Time |
| --- | --- |
| CLI startup floor | 0.05s |
| Inspection, all four domains | **0.02s** |
| Conflict checking | 0.001s |
| Bare provider round trip (tiny prompt) | 3.07s |
| `agent plan` | 12.37s |
| `agent draft` | **236.03s** |

Two findings:

**Inspection is not the problem.** The task flagged the fixed four-domain
default as a suspect. All four together cost 0.02s against a 0.05s CLI floor —
about 0.02% of a draft. Narrowing them would have bought nothing measurable and
risked the exact regression the testing notes warn about, a false "no
conflicts". **Deliberately not implemented.**

**The draft was failing, not merely slow.** 236s sat against `DEFAULT_TIMEOUT =
240`, and a separate run hit 240.14s exactly and was killed one second from
finishing — surfacing to the user as a failure after four minutes rather than a
slow success. That is the reported bug at its worst.

### Cause: the model was writing far too much

Generation time is dominated by output tokens, and the draft produced **10,938
characters** for a one-setting change. The recipes that ship with this project
run 1,257-8,210 characters; the generated one was larger than any of them and
roughly 4x the median. Padding took the usual forms: capability probes for
tools the system facts already listed, branches for package managers this
machine does not have, and commentary restating the code.

Cross-check: the same draft with `--model haiku` took 55.9s for 2,707
characters. Time tracks output length across models, not prompt size.

### Fix

Nothing about round trips or inspection changed. The draft prompt and
`SKILL.md` now require the shortest correct recipe and name the specific kinds
of padding to omit — argued from auditability rather than speed, since a
300-line script for a one-line change defeats this project's central claim, and
being faster is a consequence.

`plan` and `draft` also got separate timeouts (120s / 420s) instead of one 240s
constant, so a legitimate draft is never killed at the finish line while a hung
plan is still noticed quickly.

A third fix prevents wasted generations rather than slow ones: `SKILL.md` never
showed `@param` syntax and the draft prompt never mentioned it, so a draft was
refused for `@param name type=string` — a fair guess, since every *other*
attribute is `key=value`. Both now show the grammar and the six valid types.
This is the third instance of the same root cause in this project (after
`privilege` values and `recipe_sudo`): the engine enforcing a rule nobody had
written down for the model. Each miss costs a full generation.

### Result

| | Before | After (3 trials) |
| --- | --- | --- |
| Draft time | 236.03s (one run timed out at 240s) | 95.97s, 102.14s, 131.92s |
| Output size | 10,938 chars | 4,739 / 4,576 / 4,120 chars |
| Lint | passed 1 of 2 attempts | clean 3 of 3 |

Roughly **2.1x faster**, output **~58% smaller**, and no timeout failures.
Correctness held: the 147-line result implements all three actions, backs up
both files, restores exactly on undo, uses `recipe_sudo`, declares an icon, and
parses cleanly under `bash -n`.

Honest caveat: trial 3 was the *slowest* run despite the *shortest* output, so
provider-side variance is real and output length is the dominant controllable
factor, not the only one. A floor of roughly a minute remains, which is why the
timing breakdown stays.

### Instrumentation kept

`agent plan --json` and `agent draft --json` now carry a `timings` object
(`inspect`/`model`/`conflicts`/`lint`, plus `chars` for the draft). This is an
additive field, flagged here because the acceptance criteria ask for contract
changes to be called out; `schemaVersion` is unchanged and existing consumers
ignore it. It is kept rather than made temporary so the next report of a slow
draft arrives with its own breakdown instead of needing this investigation
repeated:

```json
"timings": {"inspect": 0.016, "model": 6.503, "conflicts": 0.001, "total": 6.52}
```
