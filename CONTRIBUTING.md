# Contributing

Start by reading `docs/VISION.md`. The project is intentionally more than a script launcher.

For new recipes:

1. Follow `skills/recipe-authoring/SKILL.md`.
2. Put recipes under an appropriate subdirectory of `recipes/`.
3. Use a stable unique kebab-case recipe ID.
4. Declare risk, privilege and undo behavior.
5. Add/update tests for nontrivial parsing or runner behavior.
6. Run `make test validate`.

For frontend work, do not create a second recipe metadata parser. Consume the runner's JSON.
