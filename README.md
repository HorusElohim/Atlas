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

At startup the interactive bootstrap shows a checkbox-style component menu. All optional components are selected by default:

```text
Atlas bootstrap
───────────────
[x] Atlas core  (required)
[x] 1. Hermes Agent
[x] 2. Shell environment
      Zsh + Oh My Zsh + Powerlevel10k + MesloLGS NF + Terminator

Toggle an item by number. Press Enter to install the selected components.
>
```

Enter `1` or `2` to toggle that component on or off. You can also enter multiple numbers such as `1,2`. The menu is shown again with the updated checkboxes after each toggle. Press Enter with no input to confirm and continue. Atlas core is always installed.

The bootstrap is idempotent and the Atlas core performs the machine-level setup that must happen before Atlas can manage itself:

1. Updates apt and installs the base build, Git, SSH and Python prerequisites.
2. Tests the machine's existing GitHub SSH access through its current `ssh-agent` and SSH configuration.
3. If SSH works, reuses it directly.
4. If SSH does not work, uses the public Atlas repository over HTTPS without requesting credentials.
5. Clones or updates Atlas in `~/Atlas`.
6. Creates `~/Atlas/.venv`.
7. Installs Atlas editable into the virtual environment.
8. Installs selected optional components.
9. Runs `atlas inspect`.

GitHub credential enrollment is **never performed by default**. `ATLAS_GITHUB_SETUP` controls the behavior:

- `skip` (default): reuse working SSH access when available; otherwise use public HTTPS. Never request GitHub credentials.
- `auto`: same non-interactive credential behavior as `skip`; retained as a compatibility alias.
- `managed`: explicitly opt into Atlas's dedicated Ed25519 key + GitHub CLI enrollment flow.

For non-interactive or remote deployment, bypass the component menu with `ATLAS_COMPONENTS`. Accepted component names are `hermes`, `shell`, `all`, `none` and their menu numbers:

```bash
ATLAS_COMPONENTS=hermes,shell \
curl -fsSL https://raw.githubusercontent.com/HorusElohim/Atlas/stable/bootstrap.sh | bash
```

Optional environment overrides:

```bash
ATLAS_DIR="$HOME/dev/Atlas" \
ATLAS_COMPONENTS=all \
curl -fsSL https://raw.githubusercontent.com/HorusElohim/Atlas/stable/bootstrap.sh | bash
```

To explicitly ask Atlas to create and enroll its own GitHub key:

```bash
ATLAS_GITHUB_SETUP=managed \
ATLAS_SSH_KEY="$HOME/.ssh/id_ed25519_atlas" \
curl -fsSL https://raw.githubusercontent.com/HorusElohim/Atlas/stable/bootstrap.sh | bash
```

`ATLAS_SSH_KEY` and `ATLAS_SSH_KEY_PASSPHRASE` are used only by the managed GitHub enrollment path.

## Shell setup

Interactive shell customization can also be applied independently:

```bash
atlas ohmyzsh setup
```

Atlas installs Zsh, Oh My Zsh, Powerlevel10k, the recommended MesloLGS NF font family and Terminator, preserves the existing `.zshrc`, selects the Powerlevel10k theme, configures the terminal fonts, makes Terminator the default terminal emulator, and makes Zsh the login shell.

Open a new terminal or run:

```bash
exec zsh
```

Then use `p10k configure` to choose the final prompt style.

## Hermes

Install and configure Hermes natively on a node:

```bash
atlas hermes setup
```

Run diagnostics independently with:

```bash
atlas hermes doctor
```

Hermes is also exposed as `/usr/local/bin/hermes`, so the native command remains usable independently of Atlas.

## GPU inference

Atlas manages a pinned CUDA build of `llama.cpp` on discrete NVIDIA GPU nodes. The initial Qwen profile targets `Qwen/Qwen3.8-27B` with a 65,536-token context window.

First prepare the inference engine on the GPU node:

```bash
atlas inference setup
```

This validates the NVIDIA GPU and CUDA compiler, installs build dependencies, checks out the Atlas-pinned `llama.cpp` revision, and builds `llama-server` with CUDA. It does not download a model unless a GGUF repository is explicitly selected.

Once a verified Qwen3.8-27B GGUF repository is available, deploy it with:

```bash
atlas inference setup \
  --hf-repo <verified-Qwen3.8-27B-GGUF-repository> \
  --quant Q4_K_M \
  --context 65536 \
  --host <trusted-LAN-or-VPN-address>
```

The generated `atlas-inference` systemd service uses:

- the stable API model alias `Qwen3.8-27B`;
- one inference slot for the 24 GB single-GPU profile;
- full GPU layer offload;
- Flash Attention;
- quantized `q4_0` K/V cache;
- a persistent API key stored at `~/.config/atlas/inference/api-key`;
- an OpenAI-compatible server on port `8080` by default.

The default listen address is `127.0.0.1`. For another Atlas node to consume inference, bind the service only to a trusted LAN or VPN address rather than exposing it publicly.

Inspect the service with:

```bash
atlas inference status
```

Print the local API key when you need to provision an agent node:

```bash
atlas inference key
```

Then connect Hermes on an edge node:

```bash
atlas hermes connect http://<gpu-node>:8080/v1
```

Atlas verifies `/v1/models`, prompts for the inference API key without echoing it, and configures Hermes with a named `custom:atlas` provider. You can also supply the key through `ATLAS_INFERENCE_API_KEY` or `--api-key-file`.

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
- [x] Interactive bootstrap component selection
- [x] Existing GitHub SSH/agent reuse
- [x] Hermes native installer and configuration
- [x] Optional Oh My Zsh + Powerlevel10k environment
- [x] Pinned CUDA llama.cpp inference implementation
- [x] Authenticated systemd inference service implementation
- [x] Hermes custom-provider connection implementation
- [ ] Verify CUDA inference on the RTX 3090 node
- [ ] Select and verify a Qwen3.8-27B GGUF artifact
- [ ] Benchmark Qwen3.8-27B quantizations on the RTX 3090
- [ ] SSH node transport
- [ ] Multi-node inventory and health
- [ ] `atlas run <node> "..."`

## License

Apache-2.0
