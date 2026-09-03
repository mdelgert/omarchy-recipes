# Roadmap

## v0.1 — trustworthy core

- [x] self-describing Bash metadata
- [x] dynamic recipe discovery
- [x] normalized JSON metadata
- [x] typed parameter validation
- [x] check/apply/undo protocol
- [x] run history and captured output
- [x] file backup + exact restore helpers
- [x] safe demonstration recipe
- [x] agent authoring skill
- [x] Omarchy menu manifest scaffold
- [ ] user recipe directory
- [x] richer validation diagnostics
- [x] explicit recipe protocol version

## v0.2 — usable interaction

- [x] current-state structured JSON contract
- [x] native Omarchy recipe browser
- [x] generated parameter controls
- [x] execution/log view
- [x] history + undo UI
- [ ] TUI command (Gum when available, fallback otherwise)
- [ ] preview/diff action
- [ ] streaming output for long-running recipes
- [ ] secret parameter handling (masked input, redacted logs)

## v0.3 — real recipe library

- [ ] Omarchy hotkey recipe
- [ ] power/idle recipe
- [ ] Docker setup recipe
- [ ] Samba recipe
- [ ] package/service state helper primitives
- [ ] report-only diagnostic recipes (network info, curl+JSON, system diagnostics) — `docs/tasks/report-only-diagnostic-recipes.md`
- [ ] distro/package-manager capability helpers
- [ ] automated VM tests for risky recipes

## Later — shareable ecosystem

- [ ] Git-backed recipe collections/sources
- [ ] collection manifests
- [ ] trust/signature model
- [ ] update/pinning workflow
- [ ] compatibility/capability resolution
- [ ] optional community catalog

Remote orchestration and scheduling are intentionally deferred.
