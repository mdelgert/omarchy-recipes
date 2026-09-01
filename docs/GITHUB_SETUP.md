# GitHub repository setup

Suggested repository name:

```text
omarchy-recipes
```

Suggested description:

> Self-describing, reversible Linux workstation recipes with generated parameters, backups, history, undo, and an Omarchy-native frontend.

Suggested topics:

```text
omarchy linux archlinux automation bash configuration dotfiles quickshell workstation developer-tools
```

Suggested first issues:

1. **Native Omarchy recipe browser** — implement `Menu.qml` against current Quattro APIs.
2. **TUI frontend** — add category/search/parameter prompts using Gum with fallback.
3. **Preview protocol** — design `preview`/`diff` output without mutation.
4. **User recipe paths** — discover repository recipes plus user-owned collections.
5. **Structured check result** — define status JSON for current/desired state.
6. **Secret handling** — complete end-to-end redaction before adding secret-bearing recipes.
7. **First real Omarchy recipe** — add a low-risk user-level setting with tested exact undo.

Recommended branch protection once the project is public: require tests and recipe validation before merge.
