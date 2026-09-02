# Milestone 1 — Native Omarchy Recipe Browser

Read the repository documentation before making changes, especially:

* `AGENTS.md`
* `README.md`
* `ROADMAP.md`
* `docs/VISION.md`
* `docs/ARCHITECTURE.md`
* `docs/RECIPE_SPEC.md`
* `skills/recipe-authoring/SKILL.md`

Preserve the larger architectural goal described in `docs/VISION.md`.

`omarchy-recipes` is not merely a shell-script launcher. It is intended to become a self-describing, reversible workstation automation system where recipes declare their metadata, parameters, state, backup behavior, apply behavior, and undo behavior, and multiple frontends can dynamically render those recipes.

For this milestone, focus specifically on the **native Omarchy recipe browser**.

## Goal

Create a usable Omarchy plugin UI that dynamically discovers recipes through the existing `omarchy-recipes` engine and displays them in an Omarchy-native menu.

Do not hardcode individual recipes in QML.

The recipe files and runner are the source of truth.

The UI should discover recipes using the CLI/API output, such as:

```bash
./bin/omarchy-recipes list --json
```

and retrieve individual recipe metadata using:

```bash
./bin/omarchy-recipes info <recipe-id> --json
```

## Milestone scope

Implement the following:

1. Native Omarchy plugin menu
2. Dynamic recipe discovery
3. Recipe categories
4. Recipe search/filtering
5. Recipe title and description display
6. Recipe detail view
7. Current recipe status using the existing `check` protocol
8. Dynamically generated parameter controls based on recipe metadata
9. Run/apply confirmation
10. Execute a recipe through the existing runner
11. Display stdout/stderr and success/failure
12. Display recipe execution history
13. Offer Undo when the recipe/run supports it
14. Refresh recipe state after Apply or Undo
15. Handle missing dependencies and malformed recipes gracefully

## Important architectural rules

Keep QML thin.

Preferred architecture:

```text
Omarchy Menu.qml
      |
      v
Omarchy plugin service/controller
      |
      v
omarchy-recipes CLI / structured JSON API
      |
      v
recipe engine
      |
      v
individual recipes
```

Do not duplicate recipe parsing, validation, backup logic, state management, or execution logic inside QML.

Do not directly construct arbitrary shell command strings from user input.

Parameters must continue to flow through the runner's validated argument interface.

Do not use `eval`.

Do not execute arbitrary recipe contents directly from QML.

The frontend should treat the engine as the authoritative boundary.

## Generated controls

The UI should dynamically choose controls from parameter metadata.

At minimum support:

* `string` → text field
* `integer` → numeric field
* `boolean` → toggle
* `choice` → selector
* `path` → text/path field for now

Design this so additional types can be added later without restructuring the UI.

Example recipe metadata:

```json
{
  "name": "timeout",
  "type": "integer",
  "required": true,
  "default": 600,
  "min": 60,
  "max": 7200,
  "label": "Screen timeout"
}
```

should automatically result in an appropriate numeric input.

## Desired UX

The initial menu could conceptually look like:

```text
Omarchy Recipes
────────────────────────────────

Search recipes...

System
  Passwordless sudo
  Configure power settings

Networking
  Configure Samba
  Mount NAS share

Omarchy
  Configure screen timeout
  Add custom hotkey
```

Selecting a recipe should show something like:

```text
Configure Screen Timeout

Configure the display idle timeout.

Status
Configured

Screen timeout
[ 600 ] seconds

Reversibility
✓ Previous configuration will be backed up
✓ Automatic undo is supported

[ Apply ]
```

After execution:

```text
Configure Screen Timeout

✓ Recipe completed successfully

Previous: 300 seconds
Current:  600 seconds

[ Undo Last Change ]
[ View Log ]
```

The exact visuals should follow current Omarchy/Quattro plugin conventions rather than inventing a foreign-looking UI.

## Omarchy research

Before implementing substantial QML:

1. Inspect the current Omarchy plugin development documentation.
2. Inspect current built-in Omarchy plugins, especially the built-in menu implementation.
3. Follow current Quattro component and navigation conventions.
4. Do not assume older Omarchy/QML APIs are still valid.
5. Keep compatibility with the current Omarchy release rather than copying outdated examples.

If the existing scaffold in this repository disagrees with current Omarchy APIs, update the scaffold.

## Security

Remember that Omarchy plugins execute unsandboxed with the user's permissions.

Therefore:

* Treat recipe metadata as untrusted input.
* Treat recipe stdout/stderr as untrusted display text.
* Never construct executable QML/JavaScript from recipe metadata.
* Never interpolate user parameters into a shell command string.
* Never bypass the runner's validation.
* Use least privilege.
* Keep privilege elevation in the engine/recipe layer rather than the UI.
* Never silently run a modifying recipe merely because it was selected.

A modifying recipe must require an explicit Apply/Run action.

## Testing

Before considering the milestone complete:

* Existing engine tests must still pass.
* Add tests for any new engine/API behavior.
* Exercise recipe discovery with multiple categories.
* Exercise malformed metadata.
* Exercise a recipe with no parameters.
* Exercise integer parameters.
* Exercise choice parameters.
* Exercise boolean parameters.
* Exercise failed `check`.
* Exercise failed `apply`.
* Exercise successful apply.
* Exercise history.
* Exercise undo.
* Verify UI state refreshes after apply and undo.

Where practical, keep the UI testable without actually modifying system configuration.

Use the repository's safe example recipes for development.

## Don't expand scope yet

Do NOT build these in Milestone 1:

* community marketplace
* remote recipe sources
* GitHub recipe synchronization
* scheduling
* Ansible integration
* remote machine management
* dependency graphs
* recipe signing infrastructure
* multi-distro package abstraction
* full standalone TUI
* cloud services

Document ideas if needed, but don't implement them now.

## Deliverables

At completion I want:

1. Working native Omarchy recipe browser
2. Clean QML/plugin structure
3. Dynamic rendering from recipe metadata
4. Apply/check/history/undo integration with the existing engine
5. Updated README instructions
6. Updated architecture docs for decisions made
7. Automated tests where appropriate
8. Manual Omarchy testing instructions
9. A short `MILESTONE-1.md` describing:

   * what was implemented
   * architecture decisions
   * known limitations
   * how to test
   * recommended Milestone 2 work

## Working style

Work incrementally.

Before rewriting architecture, understand the code that is already here.

Prefer small, reviewable changes.

Run tests frequently.

Do not remove existing safety or reversibility behavior to make the UI easier.

If you discover that the engine's current JSON/API shape makes a clean frontend difficult, improve the engine API rather than duplicating logic in the frontend.

Start by inspecting the repository and current Omarchy plugin conventions.

Then give me a concise implementation plan and begin Milestone 1.
