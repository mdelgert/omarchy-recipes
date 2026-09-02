Scratch inbox for larger/vaguer feature ideas, not yet scoped enough to be a
task. See `docs/AGENT_WORKFLOW.md`. Once an idea is concrete enough to assign,
write it up properly in `docs/tasks/<slug>.md` and remove it from here (or
add it to `ROADMAP.md` first if it's really a whole new phase, not a task).

- Add Ansible support for scripts, where it makes sense
  (https://github.com/ansible/ansible) — note: `ROADMAP.md` currently
  defers remote orchestration; revisit whether this fits the "Later" phase
  or contradicts it before scoping a task.
- Add "execute bash script and show results" examples: show IP address, open
  ports, logs and other diagnostics, maintenance scripts.
- Add icons to recipes.
- Add "remix of recipes" (composing/forking existing recipes).
- Add a configuration/model provider abstraction for AI authoring: Claude,
  Copilot, Codex, or a self-hosted LLM.
- Add a curated list of good example recipes for Omarchy.
- Add agent/LLM/prompt defaults in the recipe header, plus manual
  install/uninstall instructions in the header, as documented defaults an
  authoring agent should fill in.
