Scratch inbox for larger/vaguer feature ideas, not yet scoped enough to be a
task. See `docs/AGENT_WORKFLOW.md`. Once an idea is concrete enough to assign,
write it up properly in `docs/tasks/<slug>.md` and remove it from here (or
add it to `ROADMAP.md` first if it's really a whole new phase, not a task).

- Ansible support: scoped as a draft task at
  `docs/tasks/ansible-adapter-for-routine-recipes.md` (optional adapter for
  routine idempotent changes, not a preferred/default format). Still blocked
  on resolving the direct conflict with `docs/VISION.md`'s "Do not turn v1
  into: Ansible" non-goal before it can move to Ready.
- Add "remix of recipes" (composing/forking existing recipes).
- Support a self-hosted / OpenAI-compatible LLM endpoint for AI authoring. The
  provider abstraction and its config file now exist (Claude, Copilot, Codex);
  what is left is an adapter for an endpoint the user hosts themselves.
- Add agent/LLM/prompt defaults in the recipe header, plus manual
  install/uninstall instructions in the header, as documented defaults an
  authoring agent should fill in.
