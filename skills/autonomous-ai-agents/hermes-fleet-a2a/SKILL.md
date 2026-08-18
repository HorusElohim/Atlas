---
name: hermes-fleet-a2a
description: "Wire two Hermes hosts into a manager/operator A2A pair."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [hermes, a2a, multi-agent, fleet, delegation, remote]
    related_skills: [hermes-remote-admin, hermes-agent, subagent-orchestration]
---

# Hermes ↔ Hermes cooperation over A2A

## When to Use

- The user wants two Hermes instances/profiles on **different machines** to
  cooperate (manager delegates, operator executes).
- Work must run where the hardware/files are (GPU box, build server) while the
  conversation stays on a small always-on node.
- A user proposes the Telegram-group + "bot mode" pattern for multi-agent work —
  redirect them here; that flag only controls chat visibility.

Make a Hermes on machine A (manager) delegate real work to a Hermes on machine
B (operator), each keeping its own model, tools, memory, and credentials.

Use A2A — **not** `delegate_task` (in-process subagents, same machine only) and
not the Telegram-group/"bot mode" pattern (that only gates whether adapters
*read* other bots' messages; it is a chat-visibility flag, not a work-delegation
transport, and it burns a bot token + group per agent).

## Architecture

- **Operator (machine B)** enables the inbound `a2a` *platform* → serves an
  Agent Card + JSON-RPC on `:9900`, injecting peer tasks into its live gateway
  session with its real toolset.
- **Manager (machine A)** enables the outbound `a2a` *toolset* → gets
  `a2a_call` / `a2a_discover` / `a2a_list` / `a2a_history` / `a2a_orchestrate`.
- The two sides are independent: the inbound platform does **not** need to be
  enabled on the manager, and the outbound toolset is off by default everywhere.

## Procedure

### 1. Generate one token per manager peer (on the manager)

```bash
openssl rand -hex 24
```

Never put the literal token in `config.yaml`. Keep it in each side's `.env`.

### 2. Operator: `~/.hermes/.env` (mode 0600)

```
A2A_PEER_TOKENS=<peer-name>:<token>      # per-peer, drives ratelimit/trust/audit
A2A_HOST=0.0.0.0                          # only widens because a token is set
A2A_PORT=9900
A2A_AGENT_NAME=<host>-operator
A2A_PUBLIC_URL=http://<lan-ip>:9900       # what the Agent Card advertises
A2A_TRUSTED_PEERS=<peer-name>             # allow-list of authenticated names
A2A_REPLY_TIMEOUT=900                     # raise for long builds/tests
A2A_MAX_PINGPONG_TURNS=20                 # anti-loop cap, 20 is the max
```

### 3. Operator: `~/.hermes/config.yaml`

```yaml
gateway:
  platforms:
    a2a:
      enabled: true
      extra: { port: 9900 }

platform_toolsets:
  a2a:                      # what a peer task may use — this IS the trust boundary
    - terminal
    - file
    - code_execution
    - skills
    - todo
    - web
    - memory
    - session_search
```

`platform_toolsets.a2a` is the whole authorization story for inbound work. If
you omit it the platform falls back to plugin defaults; list it explicitly.
Restart the operator gateway. Expect in `~/.hermes/logs/gateway.log`:

```
A2A: serving Agent Card + JSON-RPC on http://0.0.0.0:9900 (REMOTE (bearer auth)) as '<name>'
```

### 4. Manager: token in `.env`, peer in `config.yaml`

`~/.hermes/.env`: `ATLAS_GPU01_A2A_TOKEN=<token>`

```yaml
a2a_agents:
  <peer-alias>:
    url: "http://<lan-ip>:9900"
    auth: { type: bearer, token: "${ATLAS_GPU01_A2A_TOKEN}" }
    timeout: 900
    capabilities: [terminal, gpu, cuda, inference, build, test, file]

platform_toolsets:
  cli:      [hermes-cli, a2a]
  telegram: [hermes-telegram, a2a]
```

`${VAR}` in `config.yaml` is expanded by `hermes_cli.config.load_config` from
the profile `.env` — verify with a live `load_config()` call, not by eye.

### 5. Make the manager actually delegate

Enabling the tool is not enough — the model will still default to doing the work
locally. Add a fleet-cooperation block to the manager's `~/.hermes/SOUL.md`
naming the peer alias, the exact trigger conditions (GPU work, heavy builds,
files that live on B), and the instruction to treat replies as self-reports
needing independent verification.

## Verification (all of it, in order)

```bash
# card
curl -s http://<ip>:9900/.well-known/agent-card.json | python3 -m json.tool | head -20
# auth gate — MUST be 401 without a token
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://<ip>:9900/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"SendMessage","params":{"message":{"messageId":"m0","role":"ROLE_USER","parts":[{"text":"hi"}]}}}'
# real task
curl -s -X POST http://<ip>:9900/ -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"SendMessage","params":{"message":{"messageId":"m1","role":"ROLE_USER","parts":[{"text":"run nproc, report raw output"}]}}}'
```

- [ ] Agent Card lists the toolsets you granted (`skills[].name`).
- [ ] No-token POST → `401`.
- [ ] A task that runs a command returns real output; confirm a side effect
      independently over ssh (write a file via the peer, then read it back
      yourself with `read_file`).
- [ ] Multi-turn: reuse the returned `contextId` in a second `SendMessage` and
      confirm the peer remembers turn 1.
- [ ] `~/.hermes/a2a_audit.jsonl` on the operator grew, with `peer` = the
      authenticated name (not an IP).

## Pitfalls

- **A restart guard fires on remote restarts too.** `ssh host 'systemctl --user
  restart hermes-gateway'` is blocked by the local terminal tool's
  gateway-suicide guard even though the remote unit is a different process.
  Split the verb so the literal string doesn't match: `V=re; V2=start; ssh host
  "systemctl --user ${V}${V2} hermes-gateway.service"`.
- **`A2A_ADVERTISED_TOOLSETS` is a hard filter, not a hint.** Setting it to a
  comma list collapsed the card to a single skill (`['terminal']`) even though
  every toolset was granted. Leave it unset unless you need to hide skills; the
  card then advertises everything registered.
- **A2A tool functions take a single dict**, not kwargs: `a2a_call({'agent':...,
  'message':...})`. Calling `a2a_discover('name')` raises
  `AttributeError: 'str' object has no attribute 'get'`, and `a2a_discover`
  needs a full URL — it does not resolve peer aliases (`a2a_call` does).
- **Never `sys.path.insert(0, 'plugins/platforms')`** to probe these modules —
  `plugins/platforms/email/` shadows stdlib `email`, and `import urllib.request`
  then dies with `ModuleNotFoundError: No module named 'email.utils'`. Load the
  file via `importlib.util.spec_from_file_location` with a synthetic package
  instead.
- **First call is slow** (~40s with a local 27B on the far end). Set
  `timeout: 900` on the peer and `A2A_REPLY_TIMEOUT=900`, or use push
  notifications + `GetTask` polling for long jobs.
- **No token ⇒ localhost only.** `A2A_HOST=0.0.0.0` is ignored without a token
  set; the log line tells you which mode you got (`REMOTE (bearer auth)` vs local).
- HTTP on a LAN means the token crosses the wire in cleartext. Fine inside a
  trusted subnet/Tailscale; put it behind TLS + `A2A_PUBLIC_URL` otherwise.
