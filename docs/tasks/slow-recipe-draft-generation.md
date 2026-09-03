# Task: Investigate and fix slow recipe-draft generation (90+ seconds for trivial requests)

Status: Ready
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

- [ ] timing breakdown captured for a real "change hostname"-style request,
      showing where the ~90+ seconds is spent
- [ ] a concrete fix implemented based on that breakdown (reduced inspection
      scope, reduced round trips, and/or visible progress reporting —
      whichever the measurement points to)
- [ ] measured improvement (or, if the floor is unavoidable provider
      latency, visible progress feedback added) demonstrated with before/
      after numbers in the Report section
- [ ] existing `agent plan`/`agent draft` behavior and output contract
      otherwise unchanged (still two stateless calls returning the same JSON
      shape, unless the investigation justifies changing that — call it out
      explicitly in the Report if so)
- [ ] tests added/updated for any changed inspection-domain-selection logic
- [ ] `make test validate` (or `make check`) passes
- [ ] `./bin/omarchy-recipes validate` passes

## Testing notes

- Test with whichever provider CLI is actually installed/configured on this
  machine (`omarchy-recipes agent providers` lists what's available).
- Watch for a regression where narrowing inspection domains causes `plan` to
  miss a real conflict it previously would have caught — a false "no
  conflicts" is worse than a slow response.

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
