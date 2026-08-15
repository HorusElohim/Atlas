# Atlas

Atlas turns heterogeneous Linux machines into a distributed Hermes agent fleet.

It keeps **agent execution** and **model inference** separate:

- Hermes runs natively on every Atlas node.
- Capable GPU nodes can provide shared local inference through an OpenAI-compatible endpoint.
- Edge nodes, such as a Jetson Orin Nano, can run Hermes locally while consuming inference from a stronger node.
- Atlas detects node capabilities and converges machines toward the desired configuration.

```text
                         Atlas
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
        atlas-gpu-01             atlas-edge-01
        Ubuntu 24.04             Jetson Orin Nano
        RTX 3090                 JetPack / ARM64
        Hermes                   Hermes
        llama.cpp                     │
        Qwen3.8-27B  ◄──── inference ─┘
```

## Principles

1. **Native first** — Hermes runs directly on the host unless isolation is explicitly useful.
2. **Capability driven** — deployment decisions come from detected hardware, not hostnames.
3. **Reproducible** — dependencies, models, and runtime parameters are pinned deliberately.
4. **Minimal orchestration** — Atlas uses Python and [TheBundle](https://github.com/HorusElohim/TheBundle) instead of growing a second configuration language.
5. **Secure by default** — agent APIs are private to the Atlas network and never intentionally exposed to the public internet.

## Bootstrap a Linux node

A fresh Ubuntu or Jetson Linux machine can join Atlas with one command:

```bash
curl -fsSL https://raw.githubusercontent.com/HorusElohim/Atlas/stable/bootstrap.sh | bash
```

or with `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/HorusElohim/Atlas/stable/bootstrap.sh | bash
```

The bootstrap is idempotent and performs the machine-level setup that must happen before Atlas can manage itself:

1. Updates apt and installs the base build, Git, SSH and Python prerequisites.
2. Installs the official GitHub CLI package.
3. Creates a dedicated Ed25519 key at `~/.ssh/id_ed25519_atlas` when missing.
4. Authenticates GitHub interactively when required and registers the public key with the account.
5. Adds a dedicated `github-atlas` SSH host alias without replacing the machine's normal GitHub SSH configuration.
6. Clones or updates Atlas in `~/Atlas`.
7. Switches the repository remote to the dedicated SSH identity.
8. Creates `~/Atlas/.venv`.
9. Installs Atlas editable into the virtual environment.
10. Runs `atlas inspect`.

The first GitHub authentication may open a browser/device flow. Re-running the bootstrap reuses the existing key, GitHub authorization, checkout and virtual environment.

Optional environment overrides:

```bash
ATLAS_DIR="$HOME/dev/Atlas" \
ATLAS_SSH_KEY="$HOME/.ssh/my_atlas_key" \
curl -fsSL https://raw.githubusercontent.com/HorusElohim/Atlas/stable/bootstrap.sh | bash
```

For unattended machine keys, the bootstrap creates the Ed25519 key without a passphrase by default. Set `ATLAS_SSH_KEY_PASSPHRASE` before running if you explicitly want one.

## Shell setup

Interactive shell customization is opt-in:

```bash
atlas ohmyzsh setup
```

Atlas installs Zsh, Oh My Zsh, Powerlevel10k and the recommended MesloLGS NF font family, preserves the existing `.zshrc`, selects the Powerlevel10k theme, configures GNOME Terminal when available, and makes Zsh the login shell.

Open a new terminal or run:

```bash
exec zsh
```

Then use `p10k configure` to choose the final prompt style.

## Hermes

Install and prepare Hermes natively on a node:

```bash
atlas hermes setup
```

Run diagnostics independently with:

```bash
atlas hermes doctor
```

## Development

Atlas requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

atlas inspect
```

## First milestone

- [x] Atlas package and CLI foundation
- [x] Local hardware inspection
- [x] One-command Linux bootstrap
- [x] Hermes native installer and configuration
- [x] Optional Oh My Zsh + Powerlevel10k environment
- [ ] SSH node transport
- [ ] CUDA-enabled llama.cpp deployment
- [ ] Qwen3.8-27B model management
- [ ] systemd services
- [ ] Multi-node inventory and health
- [ ] `atlas run <node> "..."`

## License

Apache-2.0
