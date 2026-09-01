// Native Omarchy Recipes menu scaffold.
//
// IMPORTANT: Before implementing this file, read docs/OMARCHY_PLUGIN.md and
// inspect the CURRENT built-in Omarchy menu/plugin examples. Omarchy's Quattro
// APIs are evolving; the engine contract is intentionally stable while this
// frontend is developed against a real Omarchy installation.
//
// Desired data flow:
//   omarchy-recipes list --json
//             -> category/search model
//   omarchy-recipes info <id> --json
//             -> generated parameter controls
//   omarchy-recipes check/run/undo/history
//             -> status, execution output, history
//
// Do NOT parse recipe comments here. Do NOT execute arbitrary recipe source
// text from QML. Invoke the external runner with argv through current
// Quickshell process APIs.

import QtQuick

Item {
  // Placeholder entry point so the repository expresses the intended Omarchy
  // manifest contract without pretending an untested native UI is production
  // ready. The first GUI PR should replace this Item with the current Omarchy
  // menu base/lifecycle component and validate it with qmllint on Omarchy.
}
