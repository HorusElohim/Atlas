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
- [ ] SSH node transport
- [ ] Hermes native installer and configuration
- [ ] CUDA-enabled llama.cpp deployment
- [ ] Qwen3.8-27B model management
- [ ] systemd services
- [ ] Multi-node inventory and health
- [ ] `atlas run <node> "..."`

## License

Apache-2.0
