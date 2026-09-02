# Milestone 2 — AI-Assisted Recipe Authoring & Community Contribution

Status: Planned

## Goal

Allow a user to describe a workstation change in natural language from inside the Omarchy Recipes plugin.

The integrated agent should:

1. Understand the requested change.
2. Inspect the current system when necessary.
3. Detect conflicts or ambiguity.
4. Ask the user for clarification before making unsafe or conflicting changes.
5. Generate a recipe that follows the `omarchy-recipes` authoring specification.
6. Validate the generated recipe.
7. Allow the user to review and test it locally.
8. Allow the user to submit the recipe to:

https://github.com/mdelgert/omarchy-recipes

for potential inclusion in the shared recipe collection.

The larger goal is to make recipe creation collaborative while preserving the project's safety, reversibility, auditability, and portability principles.

---

# Example Workflow

The user opens Omarchy Recipes and selects:

`Create Recipe`

The plugin presents a chat interface:

> What would you like to configure?

The user enters:

> Set my screen saver timeout to 15 minutes.

The agent should:

1. Identify the relevant Omarchy/Hyprland configuration.
2. Inspect the current configuration.
3. Determine which file or service controls the setting.
4. Determine whether the requested change conflicts with another configured behavior.
5. Generate a reversible recipe.
6. Show the proposed recipe and expected changes.
7. Validate it.
8. Allow the user to test it.
9. Offer to save it to their local recipe collection.
10. Offer to submit it upstream.

---

# Conflict Detection

Conflict detection is a required feature.

The agent must not simply generate configuration blindly.

Example request:

> Add a hotkey Super+Enter that launches Firefox.

Before generating the recipe, the agent should inspect the current Omarchy/Hyprland bindings.

If it discovers:

`Super+Enter → Terminal`

the agent should tell the user:

> Super+Enter is currently assigned to your terminal.
>
> Would you like to:
>
> * replace the existing binding
> * choose another shortcut
> * cancel

The agent must not silently overwrite the existing shortcut.

Conflict analysis should happen before the recipe is proposed whenever practical.

---

# Types of Conflicts

The authoring agent should check for relevant conflicts including:

## Keyboard shortcuts

Inspect existing bindings before adding or replacing a shortcut.

## Configuration settings

Determine whether the same configuration key is already defined elsewhere.

## Services

Check whether an existing service performs the same or conflicting task.

## Packages

Check whether the requested software is already installed or whether an alternative package conflicts with it.

## Ports

For services and containers, determine whether required ports are already in use.

## Files

Determine whether the recipe will overwrite or replace existing files.

## Mount points

Verify that a mount location is not already in use.

## Docker/container names

Check whether container names, networks, volumes, or ports already exist.

## Systemd units

Check existing unit names and enabled/running state.

## Environment variables

Check whether variables are already defined and where.

The conflict framework should remain extensible so future recipe types can add domain-specific checks.

---

# Recipe Authoring Agent

Create or extend an agent skill specifically for recipe creation.

Suggested location:

`skills/recipe-authoring/SKILL.md`

The skill remains the authoritative ruleset for AI-generated recipes.

The agent must read this skill before generating a recipe.

---

# Required Recipe Authoring Rules

Generated recipes should follow these principles.

## Inspect first

Before modifying a resource, inspect its existing state.

## Backup first

Existing files must be backed up before modification.

## Preserve absence

If a file did not previously exist, record that state so Undo removes the newly-created file rather than restoring a fake default.

## Reversible by default

Every recipe should implement Undo unless the operation cannot reasonably be reversed.

Irreversible recipes must explicitly declare this.

## Idempotent

Running the recipe repeatedly should not accumulate duplicate configuration or unintended changes.

## Least privilege

Do not run an entire recipe as root merely because one command requires elevated privileges.

## Validate user input

Do not insert untrusted values into shell command strings.

Never use `eval`.

## Preserve existing state

Services, packages, configuration values, permissions, ownership, and enabled/running states should be restored appropriately during Undo.

## Verify

After Apply, verify that the requested state exists.

After Undo, verify that the previous state has been restored.

## Explain

Every recipe should clearly describe:

* what it changes
* what it backs up
* required privileges
* parameters
* potential side effects
* whether Undo is available

---

# Recipe Generation Flow

The recommended internal workflow is:

```text
User request
     |
     v
Intent analysis
     |
     v
System inspection
     |
     v
Conflict detection
     |
     +---- conflict ----> ask user
     |
     v
Generate recipe
     |
     v
Static validation
     |
     v
Recipe preview
     |
     v
Dry run / check
     |
     v
User approval
     |
     v
Apply locally
     |
     v
Verify
     |
     v
Save recipe
     |
     v
Optional community submission
```

The AI should not skip directly from natural-language request to execution.

---

# Chat UI

Add a recipe-authoring interface to the Omarchy plugin.

Conceptually:

```text
Omarchy Recipes
──────────────────────────

Recipes
Create Recipe
History
```

Selecting `Create Recipe` opens:

```text
Create a Recipe

Describe what you want your system to do.

┌──────────────────────────────────────────┐
│ Add a hotkey that opens Firefox          │
└──────────────────────────────────────────┘

[ Ask Agent ]
```

The interface should support a conversational flow.

Example:

```text
User
Add a hotkey Super+Enter that opens Firefox.

Agent
Super+Enter is already assigned to your terminal.

Choose an action:

[ Replace Terminal Binding ]
[ Pick Another Shortcut ]
[ Cancel ]
```

After resolving the conflict:

```text
Agent
I can create this recipe:

Title
Open Firefox with Super+F

Category
Omarchy / Hotkeys

Changes
~/.config/hypr/bindings.conf

Backup
Existing configuration will be preserved.

Undo
Supported

[ View Recipe ]
[ Test ]
[ Save ]
```

---

# Recipe Preview

Before execution, the user should be able to review:

* generated metadata
* generated Bash
* files affected
* commands executed
* packages installed
* privilege requirements
* detected conflicts
* backup behavior
* undo behavior

The generated Bash should never be hidden from the user.

This supports the project's principle:

AI-authorable, human-auditable.

---

# Local Recipe Workspace

Generated recipes should initially be stored separately from trusted/bundled recipes.

Suggested directory:

`~/.config/omarchy-recipes/recipes/local/`

Possible categories:

```text
recipes/
  bundled/
  local/
  community/
```

A generated recipe should not automatically become a trusted bundled recipe.

---

# Validation Pipeline

Before a generated recipe can be saved or executed, run:

```bash
omarchy-recipes validate <recipe>
```

Validation should eventually include:

* metadata schema validation
* required actions present
* valid parameter definitions
* valid recipe ID
* duplicate recipe ID detection
* shell syntax checking
* unsafe construct detection
* undo declaration
* backup declaration where applicable

Potential future validation tools may include ShellCheck, but the core architecture should not depend on one external service.

---

# AI Safety Checks

The authoring agent should flag suspicious generated behaviors such as:

* `curl ... | bash`
* `wget ... | sh`
* downloading executable code without verification
* `rm -rf` with broad paths
* recursive permission changes
* disabling security controls
* replacing system configuration wholesale
* unbounded glob deletion
* `eval`
* shell interpolation of untrusted input
* modifying unrelated user files
* embedding credentials or tokens
* creating hidden persistence mechanisms

The user should receive a warning if these patterns are necessary for a legitimate recipe.

---

# Community Contribution

After a recipe has been created and tested locally, the user may choose:

`Submit to Community`

The plugin should prepare a contribution to:

`mdelgert/omarchy-recipes`

The preferred workflow should use normal GitHub contribution mechanics.

A community contribution should not directly push to the maintainer's main branch.

Preferred process:

```text
generated recipe
      |
      v
validate
      |
      v
tests
      |
      v
fork / branch
      |
      v
commit recipe
      |
      v
open pull request
      |
      v
maintainer review
```

This preserves repository review and prevents the community authoring feature from becoming arbitrary remote code execution into the canonical collection.

---

# Contribution Skill

Create a separate agent skill:

`skills/recipe-contribution/SKILL.md`

This skill should teach an agent how to contribute a recipe to the canonical repository.

It should cover:

1. Validate the recipe.
2. Verify metadata.
3. Verify backup and Undo.
4. Check recipe naming conventions.
5. Check for an existing equivalent recipe.
6. Run recipe tests.
7. Add tests when appropriate.
8. Update documentation if necessary.
9. Create a focused commit.
10. Create a branch.
11. Fork when the contributor does not have write access.
12. Open a pull request.
13. Include a structured PR description.

---

# Pull Request Template

Generated recipe pull requests should include:

## Recipe

Recipe ID:

Title:

Category:

## Purpose

What problem does this recipe solve?

## Changes

What files, packages, services, or configuration does it modify?

## Backup

What existing state is preserved?

## Undo

How is the prior state restored?

## Compatibility

Tested on:

* Omarchy version
* Arch version
* relevant package versions

## Testing

Describe how the recipe was tested.

## Conflicts

Describe any known conflicts or interactions.

## AI Generated

Was AI used to generate this recipe?

If yes, which portions were manually reviewed or tested?

---

# Duplicate Recipe Detection

Before suggesting upstream contribution, search the existing recipe collection.

If the user asks:

> Install Docker

and a Docker recipe already exists, the agent should prefer:

* using the existing recipe
* improving the existing recipe
* proposing additional parameters

rather than creating a duplicate.

The agent could say:

> A Docker installation recipe already exists.
>
> Would you like to:
>
> * run the existing recipe
> * modify it for your use case
> * create a new alternative recipe

---

# Recipe Provenance

Begin tracking provenance metadata.

Possible normalized metadata:

```json
{
  "source": "local",
  "authoring": {
    "generated_with_ai": true,
    "reviewed": true
  }
}
```

Do not encode private conversational content in recipe metadata.

Long term, provenance may include:

* repository
* commit
* author
* signature
* review status

This should be designed but not overbuilt during Milestone 2.

---

# Trust Model

The UI should visually distinguish:

## Bundled

Recipes shipped by the canonical `omarchy-recipes` collection.

## Local

Recipes created locally by the user or their agent.

## Community

Recipes obtained from external collections.

Future versions may add:

* verified
* signed
* reviewed
* unreviewed

Milestone 2 only needs enough structure to avoid implying that an AI-generated local recipe has the same trust level as a reviewed upstream recipe.

---

# Agent Provider Architecture

Do not tightly couple the plugin to a single AI provider.

Create an abstraction conceptually like:

```text
RecipeAuthoringAgent
        |
        +-- Claude adapter
        +-- Codex adapter
        +-- future provider
```

Milestone 2 may implement Claude first if it is the practical initial integration.

However, recipe creation logic, system inspection rules, conflict detection, and recipe validation should remain provider-independent.

The authoring skill is part of the repository and should define the behavior independent of the selected model.

---

# Important Security Boundary

The chat frontend should not itself receive unrestricted permission to modify the system.

The desired boundary is:

```text
Natural language
      |
      v
Agent
      |
      v
Proposed Recipe
      |
      v
Recipe Validator
      |
      v
User Review
      |
      v
Recipe Runner
      |
      v
System
```

Not:

```text
Natural language
      |
      v
Agent with unrestricted shell
      |
      v
System
```

Inspection commands may be necessary for conflict detection, but modifying operations should flow through the recipe lifecycle whenever practical.

---

# Acceptance Criteria

Milestone 2 is complete when:

1. The Omarchy plugin has a Create Recipe chat interface.
2. A user can describe a simple workstation configuration change.
3. The authoring agent reads the repository recipe-authoring skill.
4. The agent can inspect relevant local configuration.
5. The agent detects obvious conflicts before generating a recipe.
6. Conflicts require explicit user resolution.
7. The agent generates valid recipe metadata and executable logic.
8. The recipe passes repository validation.
9. The user can preview the generated recipe.
10. The user can test/apply it using the standard recipe runner.
11. The generated recipe supports Undo when practical.
12. The user can save the recipe locally.
13. The UI distinguishes local recipes from bundled recipes.
14. The user can initiate a GitHub contribution workflow.
15. Contribution occurs through a branch/pull request rather than direct writes to the canonical main branch.
16. Duplicate recipes are checked before submission.
17. The project's existing safety and reversibility guarantees remain intact.

---

# Out of Scope

Do not implement yet:

* automatic merging of community recipes
* arbitrary remote recipe execution
* reputation/rating systems
* cryptographic recipe signing
* hosted recipe marketplace backend
* automatic trust of AI-generated recipes
* unrestricted autonomous agent shell access
* remote machine management
* multi-user collaboration server
* cloud synchronization service

These belong to later milestones.

---

# Product Principle

The central idea of Milestone 2 is:

> A user should be able to describe a desired workstation change in plain language and receive a structured, inspectable, reversible recipe — not an opaque command executed by an agent.

The recipe becomes the durable artifact.

The conversation is temporary.

The recipe is reusable, reviewable, shareable, testable, version-controlled, and reversible.
