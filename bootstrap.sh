#!/usr/bin/env bash
set -Eeuo pipefail

ATLAS_GITHUB_USER="${ATLAS_GITHUB_USER:-HorusElohim}"
ATLAS_REPO="${ATLAS_REPO:-Atlas}"
ATLAS_BRANCH="${ATLAS_BRANCH:-stable}"
ATLAS_DIR="${ATLAS_DIR:-$HOME/Atlas}"
ATLAS_SSH_KEY="${ATLAS_SSH_KEY:-$HOME/.ssh/id_ed25519_atlas}"

HTTPS_URL="https://github.com/${ATLAS_GITHUB_USER}/${ATLAS_REPO}.git"
SSH_URL="git@github-atlas:${ATLAS_GITHUB_USER}/${ATLAS_REPO}.git"

INSTALL_HERMES=false
INSTALL_SHELL=false

log() {
    printf '\n\033[1;36mAtlas\033[0m  %s\n' "$*"
}

die() {
    printf '\n\033[1;31mAtlas error:\033[0m %s\n' "$*" >&2
    exit 1
}

run_with_tty() {
    if [[ -r /dev/tty ]]; then
        "$@" < /dev/tty
    else
        "$@"
    fi
}

enable_component() {
    case "${1,,}" in
        ""|none|core|atlas)
            ;;
        1|hermes)
            INSTALL_HERMES=true
            ;;
        2|shell|ohmyzsh|zsh)
            INSTALL_SHELL=true
            ;;
        a|all)
            INSTALL_HERMES=true
            INSTALL_SHELL=true
            ;;
        *)
            die "Unknown bootstrap component: $1"
            ;;
    esac
}

toggle_component() {
    case "$1" in
        1)
            if $INSTALL_HERMES; then
                INSTALL_HERMES=false
            else
                INSTALL_HERMES=true
            fi
            ;;
        2)
            if $INSTALL_SHELL; then
                INSTALL_SHELL=false
            else
                INSTALL_SHELL=true
            fi
            ;;
        *)
            return 1
            ;;
    esac
}

checkbox() {
    if "$1"; then
        printf '[x]'
    else
        printf '[ ]'
    fi
}

show_component_menu() {
    cat > /dev/tty <<'EOF_MENU'

Atlas bootstrap
───────────────
[x] Atlas core  (required)
EOF_MENU

    printf '%s 1. Hermes Agent\n' "$(checkbox "$INSTALL_HERMES")" > /dev/tty
    printf '%s 2. Shell environment\n' "$(checkbox "$INSTALL_SHELL")" > /dev/tty
    printf '      Zsh + Oh My Zsh + Powerlevel10k + MesloLGS NF + Terminator\n' > /dev/tty

    cat > /dev/tty <<'EOF_MENU'

Toggle an item by number. Press Enter to install the selected components.
> 
EOF_MENU
}

select_components() {
    if [[ -n "${ATLAS_COMPONENTS:-}" ]]; then
        local normalized="${ATLAS_COMPONENTS//,/ }"
        local component
        for component in $normalized; do
            enable_component "$component"
        done
        return
    fi

    if [[ ! -r /dev/tty ]]; then
        log "No interactive terminal detected; installing Atlas core only"
        return
    fi

    # Interactive bootstrap defaults to the complete Atlas node experience.
    INSTALL_HERMES=true
    INSTALL_SHELL=true

    while true; do
        show_component_menu

        local selection=""
        IFS= read -r selection < /dev/tty || true
        selection="${selection//,/ }"

        [[ -z "$selection" ]] && return

        local component
        local valid=true
        for component in $selection; do
            if ! toggle_component "$component"; then
                printf '\nUnknown selection: %s (use 1 or 2)\n' "$component" > /dev/tty
                valid=false
            fi
        done

        if ! $valid; then
            printf 'Press Enter to continue...' > /dev/tty
            IFS= read -r _ < /dev/tty || true
        fi
    done
}

if [[ "$(uname -s)" != "Linux" ]]; then
    die "The bootstrap currently supports Linux nodes only."
fi

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=""
elif command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
else
    die "sudo is required when bootstrap is not run as root."
fi

select_components

log "Bootstrap selection: Atlas core$(if $INSTALL_HERMES; then printf ' + Hermes'; fi)$(if $INSTALL_SHELL; then printf ' + Shell'; fi)"

log "Installing system prerequisites"
$SUDO apt-get update
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    ca-certificates \
    curl \
    git \
    gnupg \
    openssh-client \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    wget \
    xz-utils

log "Installing GitHub CLI from the official repository"
$SUDO install -d -m 0755 /etc/apt/keyrings
GH_KEYRING="$(mktemp)"
trap 'rm -f "$GH_KEYRING"' EXIT
wget -qO "$GH_KEYRING" https://cli.github.com/packages/githubcli-archive-keyring.gpg
$SUDO install -m 0644 "$GH_KEYRING" /etc/apt/keyrings/githubcli-archive-keyring.gpg
$SUDO install -d -m 0755 /etc/apt/sources.list.d
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\n' \
    "$(dpkg --print-architecture)" \
    | $SUDO tee /etc/apt/sources.list.d/github-cli.list >/dev/null
$SUDO apt-get update
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y gh

log "Preparing Atlas SSH identity"
install -d -m 0700 "$HOME/.ssh"

if [[ ! -f "$ATLAS_SSH_KEY" ]]; then
    ssh-keygen \
        -t ed25519 \
        -f "$ATLAS_SSH_KEY" \
        -N "${ATLAS_SSH_KEY_PASSPHRASE:-}" \
        -C "${USER:-atlas}@$(hostname):atlas"
elif [[ ! -f "${ATLAS_SSH_KEY}.pub" ]]; then
    ssh-keygen -y -f "$ATLAS_SSH_KEY" > "${ATLAS_SSH_KEY}.pub"
fi

chmod 0600 "$ATLAS_SSH_KEY"
chmod 0644 "${ATLAS_SSH_KEY}.pub"

SSH_CONFIG="$HOME/.ssh/config"
SSH_CONFIG_TMP="$(mktemp)"
BEGIN_MARKER="# >>> Atlas GitHub >>>"
END_MARKER="# <<< Atlas GitHub <<<"

if [[ -f "$SSH_CONFIG" ]]; then
    awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
        $0 == begin { skip = 1; next }
        $0 == end { skip = 0; next }
        !skip { print }
    ' "$SSH_CONFIG" > "$SSH_CONFIG_TMP"
else
    : > "$SSH_CONFIG_TMP"
fi

cat >> "$SSH_CONFIG_TMP" <<EOF_SSH

$BEGIN_MARKER
Host github-atlas
    HostName github.com
    User git
    IdentityFile $ATLAS_SSH_KEY
    IdentitiesOnly yes
    HostKeyAlias github.com
$END_MARKER
EOF_SSH

install -m 0600 "$SSH_CONFIG_TMP" "$SSH_CONFIG"
rm -f "$SSH_CONFIG_TMP"

log "Connecting this node to GitHub"
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
    printf 'A GitHub browser/device authentication will start now.\n'
    run_with_tty gh auth login \
        --hostname github.com \
        --git-protocol https \
        --web \
        --scopes admin:public_key
fi

if ! gh api user/keys --paginate >/dev/null 2>&1; then
    printf 'GitHub needs permission to manage your public SSH keys.\n'
    run_with_tty gh auth refresh \
        --hostname github.com \
        --scopes admin:public_key
fi

PUBLIC_KEY_MATERIAL="$(awk '{print $2}' "${ATLAS_SSH_KEY}.pub")"
if gh api user/keys --paginate --jq '.[].key' \
    | awk '{print $2}' \
    | grep -Fqx "$PUBLIC_KEY_MATERIAL"; then
    log "SSH key is already registered with GitHub"
else
    KEY_TITLE="Atlas $(hostname)"
    gh ssh-key add "${ATLAS_SSH_KEY}.pub" \
        --type authentication \
        --title "$KEY_TITLE"
    log "Registered SSH key with GitHub as: $KEY_TITLE"
fi

log "Cloning or updating Atlas"
if [[ -d "$ATLAS_DIR/.git" ]]; then
    git -C "$ATLAS_DIR" remote set-url origin "$HTTPS_URL"
    git -C "$ATLAS_DIR" fetch origin "$ATLAS_BRANCH"
    git -C "$ATLAS_DIR" checkout "$ATLAS_BRANCH"
    git -C "$ATLAS_DIR" pull --ff-only origin "$ATLAS_BRANCH"
elif [[ -e "$ATLAS_DIR" ]]; then
    die "$ATLAS_DIR already exists but is not an Atlas git checkout."
else
    git clone --branch "$ATLAS_BRANCH" "$HTTPS_URL" "$ATLAS_DIR"
fi

git -C "$ATLAS_DIR" remote set-url origin "$SSH_URL"

log "Creating Atlas virtual environment"
VENV="$ATLAS_DIR/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -e "$ATLAS_DIR"

if $INSTALL_SHELL; then
    log "Configuring shell environment"
    run_with_tty "$VENV/bin/atlas" ohmyzsh setup
fi

if $INSTALL_HERMES; then
    log "Configuring Hermes Agent"
    run_with_tty "$VENV/bin/atlas" hermes setup
fi

log "Inspecting this node"
"$VENV/bin/atlas" inspect

printf '\n\033[1;32mAtlas bootstrap complete.\033[0m\n'
printf 'Repository: %s\n' "$ATLAS_DIR"
printf 'Virtualenv: %s\n' "$VENV"
printf 'Activate with: source %q\n' "$VENV/bin/activate"
printf 'Git remote: %s\n' "$SSH_URL"
