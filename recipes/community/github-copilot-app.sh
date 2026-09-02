#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id github-copilot-app
# @recipe.title Install the GitHub Copilot desktop app
# @recipe.description Installs the GitHub Copilot desktop app (https://docs.github.com/en/copilot/concepts/agents/github-copilot-app) from the AUR package github-copilot-app-bin, using whichever AUR helper is already on PATH (paru or yay). The helper runs non-interactively, so the PKGBUILD is not presented for review; AUR content is user-submitted, and this is a -bin package that fetches an upstream prebuilt binary. If no AUR helper is present the recipe changes nothing and exits non-zero. It does not sign in to GitHub, store any token, write to ~/.config/github-copilot, install the gh or copilot CLI or any editor extension, and it does not touch Hyprland config, keybindings, the Omarchy menu, autostart, or any .desktop file (the package ships its own). Undo removes the package only if this recipe was the one that installed it, and leaves its dependencies in place.
# @recipe.category Development
# @recipe.platform linux,omarchy
# @recipe.distro arch
# @recipe.privilege mixed
# @recipe.undo command
# @recipe.risk medium
# @recipe.tags github,copilot,aur,desktop
# @recipe.generated-with-ai true
# @recipe.reviewed false
# @param package string default="github-copilot-app-bin" label="AUR package" description="Package that ships the GitHub Copilot desktop app. Change this only if the package has been renamed in the AUR."

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

action="${1:-}"
shift || true
recipe_parse_args "$@"

DEFAULT_PACKAGE="github-copilot-app-bin"
STATE_NAME="github-copilot-app.state"
DOC_URL="https://docs.github.com/en/copilot/concepts/agents/github-copilot-app"

package="${RECIPE_ARG_PACKAGE:-$DEFAULT_PACKAGE}"

# A pacman-style package name and nothing else. The value is only ever handed to
# pacman or the AUR helper as a single argv element, never assembled into a
# command string, so it cannot become shell syntax.
valid_package_name() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9@._+-]{0,127}$ ]]
}

have_pacman() { command -v pacman >/dev/null 2>&1; }

package_installed() { pacman -Qi "$1" >/dev/null 2>&1; }

package_version() { pacman -Q "$1" 2>/dev/null | awk '{print $2}' || true; }

# Omarchy ships yay; paru is the other common choice. Only helpers already on
# PATH are used -- this recipe never installs or configures a helper itself.
find_aur_helper() {
  local candidate
  for candidate in paru yay; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

case "$action" in
  check)
    if ! valid_package_name "$package"; then
      recipe_note "Not a valid package name: $package"
      recipe_state not-configured "invalid package name requested"
      exit 0
    fi

    if ! have_pacman; then
      recipe_note "pacman is not on PATH; this recipe only supports Arch-based systems such as Omarchy"
      recipe_state not-configured "pacman not found; cannot install $package here"
      exit 0
    fi

    if package_installed "$package"; then
      recipe_state configured "$package $(package_version "$package") is installed"
      exit 0
    fi

    helper="$(find_aur_helper || true)"
    if [[ -z "$helper" ]]; then
      recipe_note "No AUR helper (paru or yay) found on PATH; apply will stop without changing anything until one is installed"
    else
      recipe_note "Would install $package with $helper"
    fi
    recipe_state not-configured "$package is not installed"
    ;;

  apply)
    valid_package_name "$package" || recipe_die "not a valid package name: $package"
    have_pacman || recipe_die "pacman is not on PATH; this recipe only supports Arch-based systems such as Omarchy"
    ((EUID != 0)) || recipe_die "run this recipe as your normal user; AUR helpers refuse to build as root and will elevate the pacman step themselves"

    recipe_require_runtime
    state_file="${OMARCHY_RECIPES_RUN_DIR:?}/${STATE_NAME}"

    # Record who owns the package before touching anything, so undo removes only
    # what this recipe installed even if a later step fails.
    if package_installed "$package"; then
      printf '%s\t%s\n' "preexisting" "$package" > "$state_file"
      recipe_summary "Already installed: $package $(package_version "$package")"
      recipe_note "$package was already installed; nothing to change. Undo will leave it in place."
      exit 0
    fi

    helper="$(find_aur_helper || true)"
    [[ -n "$helper" ]] || recipe_die "no AUR helper found on PATH; install paru or yay (for example 'sudo pacman -S --needed yay') and run this recipe again"

    "$helper" -Si "$package" >/dev/null 2>&1 \
      || recipe_die "$helper could not look up '$package' -- the package may have been renamed or removed from the AUR, or there is no network. Confirm the current name at https://aur.archlinux.org and re-run with --package <name>. App docs: $DOC_URL"

    printf '%s\t%s\n' "installed-by-recipe" "$package" > "$state_file"

    recipe_note "Installing $package with $helper; the AUR build is non-interactive and the pacman step will ask for sudo"
    "$helper" -S --needed --noconfirm "$package"

    package_installed "$package" \
      || recipe_die "$helper exited successfully but $package is not installed; nothing was left half-configured, re-run after checking the helper output above"

    recipe_summary "Installed $package $(package_version "$package")"
    recipe_note "Installed $package. Launch the GitHub Copilot app from your application launcher and sign in there -- this recipe stores no credentials."
    recipe_note "Setup and usage: $DOC_URL"
    ;;

  undo)
    : "${OMARCHY_RECIPES_SOURCE_RUN_DIR:?undo requires the apply run it reverses}"
    state_file="${OMARCHY_RECIPES_SOURCE_RUN_DIR}/${STATE_NAME}"

    have_pacman || recipe_die "pacman is not on PATH; cannot remove a package here"
    [[ -f "$state_file" ]] \
      || recipe_die "the apply run recorded no install state at $state_file; refusing to remove a package that may have been installed before this recipe ran. Remove it manually with 'sudo pacman -R $DEFAULT_PACKAGE' if you are sure."

    IFS=$'\t' read -r recorded_state recorded_package < "$state_file" || true
    [[ -n "${recorded_package:-}" ]] || recipe_die "install state file is unreadable: $state_file"
    valid_package_name "$recorded_package" \
      || recipe_die "install state records an invalid package name; refusing to act on it: $recorded_package"

    case "${recorded_state:-}" in
      preexisting)
        recipe_summary "Left $recorded_package installed"
        recipe_note "$recorded_package was already installed before this recipe ran, so it is left exactly as it was"
        exit 0
        ;;
      installed-by-recipe) ;;
      *) recipe_die "unrecognised install state '${recorded_state:-}' in $state_file" ;;
    esac

    if ! package_installed "$recorded_package"; then
      recipe_summary "$recorded_package is not installed"
      recipe_note "$recorded_package is already gone; nothing to remove"
      exit 0
    fi

    removed_version="$(package_version "$recorded_package")"
    sudo pacman -R --noconfirm "$recorded_package"

    if package_installed "$recorded_package"; then
      recipe_die "pacman exited successfully but $recorded_package is still installed"
    fi

    recipe_summary "Removed $recorded_package $removed_version"
    recipe_note "Removed $recorded_package. Dependencies it pulled in were left installed on purpose; 'pacman -Qdtq' lists orphans if you want to review them."
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
