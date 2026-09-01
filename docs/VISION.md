# Vision: Recipes, not a script launcher

This file protects the larger idea of `omarchy-recipes` from being reduced to a folder of buttons that execute shell files.

## Product thesis

`omarchy-recipes` is a **self-describing, reversible workstation automation system**.

A recipe is portable executable knowledge that can answer:

- What is this change called?
- What does it do?
- Which category does it belong to?
- Which platforms/distributions does it support?
- What inputs does it need?
- What privileges does it require?
- What is the current state?
- What will change?
- Can it be reversed?
- What exact state must be backed up first?
- Was the last execution successful?
- What changed during that execution?
- How can the exact prior state be restored?

The UX should be generated from those declarations rather than manually coded per recipe.

## Desired end state

A user opens Omarchy Recipes and sees something like:

```text
Recipes

System
  ✓ Passwordless sudo
  ○ Screen timeout
  ○ Power settings

Applications
  ✓ Docker
  ○ Development tools

Networking
  ✓ Samba
  ○ NAS mount

Omarchy
  ✓ Custom hotkey
  ○ Monitor layout
```

Selecting a recipe generates its controls from metadata:

```text
Configure Screen Timeout

Sets the idle screen timeout.

Screen timeout
[ 600 ] seconds

Current: 300 seconds
Reversible: Yes
Risk: Low

[ Preview ] [ Apply ]
```

After execution:

```text
History
Sep 1  4:05 PM    300 → 600    success
Aug 28 7:12 PM    900 → 300    success

[ Undo Last Change ]
```

## Core abstraction

```text
Recipe files / collections
          ↓
metadata parser + validation
          ↓
      recipe engine
   ┌──────┼───────┐
   ↓      ↓       ↓
  CLI    TUI   Omarchy GUI
```

Omarchy is the first-class initial frontend, but the recipe engine must not depend on QML or Omarchy internals.

## Recipe lifecycle

A modifying operation should conceptually follow:

```text
INSPECT
  ↓
BACKUP
  ↓
APPLY
  ↓
VERIFY
  ↓
RECORD
```

Undo should follow:

```text
LOCATE SOURCE RUN
  ↓
RESTORE BACKUP / EXECUTE UNDO
  ↓
VERIFY
  ↓
RECORD UNDO RUN
```

## Undo types

Not all changes have the same reversal strategy.

- `restore` — restore backed-up files/state.
- `command` — explicit inverse action, e.g. uninstall a package or disable a service.
- `none` — no automatic undo; UI must warn before apply.

Future versions may support `transaction` and multi-resource snapshots.

## Generated parameter controls

Metadata types should map naturally to UI controls:

- `string` → text field
- `integer` → number input / slider when bounded
- `boolean` → toggle
- `choice` → radio/select
- `path` → path picker
- `secret` → masked input, never logged
- `multichoice` → checklist

The frontend should never need recipe-specific UI code for normal parameters.

## Collections

Long-term, a recipe repository should be a shareable collection:

```text
recipes/
collection.json
README.md
```

Possible future commands:

```text
omarchy-recipes source add <git-url>
omarchy-recipes source update
omarchy-recipes source list
```

This creates an ecosystem closer to a blend of Homebrew formulas, Ansible roles, just recipes, and VS Code extensions — but focused on human-selected workstation changes with explicit reversibility.

## Portability

Plan for metadata such as:

```text
@recipe.platform linux
@recipe.distro arch,ubuntu,debian,fedora
```

Omarchy-specific recipes can declare `omarchy`. Generic recipes should work elsewhere when reasonable.

## Future capabilities (not v1 requirements)

- Native Omarchy dynamic GUI with categories/search/forms/status/history.
- Interactive TUI using Gum or a dedicated TUI library.
- Dry-run/diff adapters for file-based recipes.
- Recipe collections from Git sources.
- Cryptographic signing/trust metadata for collections.
- Dependency declarations and capability checks.
- OS/distro/package-manager adapters.
- Secrets integration without persisting secret values in run logs.
- Automated restore-point testing in disposable VMs/containers.
- Policy modes: only signed recipes, only low-risk recipes, etc.
- Optional remote execution much later; do not design around it now.

## Explicit non-goals for the starter

Do not turn v1 into:

- Ansible.
- A remote orchestration platform.
- A scheduler.
- A dependency solver.
- A package manager.
- A marketplace.
- An arbitrary shell textbox in QML.

First make local recipes predictable, inspectable, reversible, and pleasant to run.
