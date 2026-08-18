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
5. **Secure by default** — inference stays local unless broader exposure is explicitly requested.

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

## OpenAI Codex

Atlas can also install and authenticate the OpenAI Codex CLI independently of Hermes. This gives an Atlas node two separate agent paths: Hermes can use local or remote Qwen inference, while Codex uses OpenAI's Codex service.

Install Codex with OpenAI's official standalone installer and start device-code authentication:

```bash
atlas codex setup
```

On a headless machine such as a Jetson, Codex prints a verification URL and one-time code. Open that URL on another device, sign in with ChatGPT, enter the code, and leave the Atlas command running until authentication completes.

Inspect the installed version and login state with:

```bash
atlas codex status
```

Authentication can also be managed explicitly:

```bash
atlas codex login
atlas codex logout
```

To install Codex without starting authentication immediately:

```bash
atlas codex setup --skip-login
```

Atlas uses OpenAI's standalone installer at `https://chatgpt.com/codex/install.sh`, accepts the installer-managed `~/.local/bin/codex`, and exposes that launcher at `/usr/local/bin/codex` when applicable.

## GPU inference

Atlas manages a pinned CUDA build of `llama.cpp` on discrete NVIDIA GPU nodes. The initial model profile targets the official `Qwen/Qwen3.8-27B` checkpoint with a 65,536-token server context.

To build only the pinned CUDA inference engine:

```bash
atlas inference setup
```

For the complete Qwen path, use one command:

```bash
atlas inference qwen setup
```

That command is resumable and performs the complete model lifecycle:

1. validates the NVIDIA GPU and CUDA compiler;
2. installs the required system packages;
3. checks out the Atlas-pinned `llama.cpp` revision;
4. builds both `llama-server` and `llama-quantize`;
5. creates an isolated Python environment for the pinned llama.cpp Hugging Face converter;
6. reads the official Qwen3.8-27B safetensor checkpoint remotely and converts it to BF16 GGUF;
7. quantizes the model to `Q4_K_M` by default;
8. removes the large BF16 intermediate after successful quantization unless `--keep-bf16` is requested;
9. installs and starts the authenticated `atlas-inference` systemd service;
10. waits until the OpenAI-compatible endpoint is healthy.

The conversion requires substantial temporary disk space. Atlas checks for approximately 80 GiB free before starting a fresh BF16 conversion. Existing conversion or quantization artifacts are reused, so an interrupted setup can be run again safely.

For a Qwen server consumed only on the same machine:

```bash
atlas inference qwen setup
```

For another trusted Atlas node on the LAN/VPN, bind inference to a reachable interface:

```bash
atlas inference qwen setup --host 0.0.0.0
```

For explicit public IPv4 exposure, use:

```bash
atlas inference qwen setup --public
```

`--public` sets the listener to `0.0.0.0`, explicitly restarts an already-running `atlas-inference` service so the new bind address takes effect, waits for Qwen to become healthy again, and, when UFW is installed and active, runs the equivalent of `ufw allow 8080/tcp` so the inference port accepts traffic from any source. A different `--port` is handled the same way.

Router/NAT port forwarding is still required for inbound IPv4 Internet traffic when the Atlas host is behind a typical home router. Atlas cannot configure that router automatically.

The generated service uses:

- the stable API model alias `Qwen3.8-27B`;
- the local quantized GGUF through llama.cpp's `--model` path;
- one inference slot for the 24 GB single-GPU profile;
- full GPU layer offload;
- Flash Attention;
- quantized `q4_0` K/V cache;
- a persistent API key stored at `~/.config/atlas/inference/api-key`;
- an OpenAI-compatible server on port `8080` by default.

The llama.cpp endpoint currently uses plain HTTP. API-key authentication protects access to model routes, but it does not encrypt the bearer token in transit. For Internet use, place Atlas behind TLS or use an encrypted VPN/tunnel before sending credentials over an untrusted network.

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

### Delegated-task routing (cheap local model for grunt work)

`atlas hermes connect` sets Hermes' *primary* model (`model.default` / `model.provider`) — use it when Qwen should drive the whole session, e.g. a pure edge node.

If instead you want to keep a paid frontier model (Claude/GPT) as the primary/orchestrator and only route Hermes' delegated subagent work (`delegate_task`, background/mechanical steps) to the free local Qwen, set `delegation.*` separately — Atlas does not manage this yet, do it by hand once per node after `atlas hermes connect` (or independently of it, as long as the `atlas` provider block already exists in `~/.hermes/config.yaml`):

```bash
hermes config set delegation.provider atlas
hermes config set delegation.model Qwen3.8-27B
```

This keeps the primary model untouched; only subagents spawned via delegation use the local Qwen endpoint. Verify the route works with a throwaway delegated task from inside a Hermes chat.

A pre-existing verified GGUF repository can still be deployed directly with the lower-level command:

```bash
atlas inference setup \
  --hf-repo <verified-Qwen3.8-27B-GGUF-repository> \
  --quant Q4_K_M
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
- [x] Interactive bootstrap component selection
- [x] Existing GitHub SSH/agent reuse
- [x] Hermes native installer and configuration
- [x] OpenAI Codex standalone installer + device-auth management
- [x] Optional Oh My Zsh + Powerlevel10k environment
- [x] Pinned CUDA llama.cpp inference implementation
- [x] Automated Qwen3.8 safetensors → GGUF → Q4_K_M pipeline
- [x] Authenticated systemd inference service implementation
- [x] Hermes custom-provider connection implementation
- [x] Explicit public bind + UFW automation
- [ ] Verify Qwen3.8-27B end-to-end on the RTX 3090 node
- [ ] Benchmark Qwen3.8-27B quantizations on the RTX 3090
- [ ] SSH node transport
- [ ] Multi-node inventory and health
- [ ] `atlas run <node> "..."`

## License

Apache-2.0
