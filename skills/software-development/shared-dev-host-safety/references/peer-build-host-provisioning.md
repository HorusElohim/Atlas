# Provisioning a Peer Build Host (Jetson → x86 GPU node)

Concrete transcript of promoting a LAN peer from "inference box" to
"build/test/coverage host", so a constrained edge node stops being the
bottleneck. Generalize the shape, not the hostnames.

## The trigger

The local box (NVIDIA Jetson Orin Nano, 6 ARM cores, 7.3 GB RAM, **no swap**)
could not run the project's real verification: a full-workspace
`cargo llvm-cov` OOM-kills the linker. Consequence — work was being pushed
with CI as the first genuine test, which is exactly the loop worth breaking.

The peer (`atlas-gpu-01`, x86_64, Ubuntu 24.04) turned out to be far better
suited:

| | Jetson (local) | Peer |
|---|---|---|
| Cores | 6 (ARM) | 24 (x86_64) |
| RAM | 7.3 GB, no swap | 31 GB (26 GB free) |
| GPU | — | RTX 3090, 24 GB |

Proof of the payoff: `cargo install cargo-llvm-cov --locked` finished in
**35.27s** on the peer.

## Survey commands (batch these — one round trip each)

```bash
# Hardware + headroom
ssh peer 'nproc; free -h | head -2; df -h /home | tail -1'

# Toolchain presence, one line per tool
ssh peer 'for t in flutter dart rustc cargo git gh clang cmake ninja pkg-config; do
  printf "%-12s " "$t"
  command -v $t >/dev/null 2>&1 && $t --version 2>&1 | head -1 || echo MISSING
done'

# Can I provision unattended?
ssh peer 'sudo -n true 2>/dev/null && echo "passwordless sudo" || echo "PASSWORD REQUIRED"'

# Cargo-installed binaries (things not in apt)
ssh peer 'ls ~/.cargo/bin | tr "\n" " "'
```

`ssh -G <alias>` resolves the effective user/port/IdentityFile when a
`~/.ssh/config` alias exists — quicker than reading the config by hand.

## Pitfall: transient SSH timeout ≠ host down

First `ssh` attempt returned `Connection timed out` on port 22 and a raw
`/dev/tcp` probe reported port 22 closed. A retry seconds later showed port 22
**OPEN** and logged in cleanly. Retry once before declaring a peer unreachable.

## Use the repo's wizard as the dependency source of truth

`PortalisApp` ships `setup/wizard_{linux,darwin}.sh` + `wizard_windows.ps1`.
Two properties made it unrunnable unattended, and neither made it worthless:

- interactive `confirm_yes()` built on `read -r -p`
- opens with `sudo apt-get install ...`, and the peer needed a sudo password

So: **read it, extract its package list, diff against reality.** From its apt
branch (16 packages), 15 were already installed; only `libmpv-dev` was
missing — media playback, irrelevant to build/test/coverage. That turned an
apparent hard block into a one-line note for the user.

```bash
ssh peer 'for p in git curl unzip zip xz-utils file build-essential libglu1-mesa \
  clang ninja-build libgtk-3-dev pkg-config cmake mesa-utils libmpv-dev libepoxy-dev; do
  printf "%-20s " "$p"
  dpkg -l "$p" 2>/dev/null | grep -q "^ii" && echo ok || echo MISSING
done'
```

The wizard's non-sudo half is safe to replicate directly:

```bash
rustup component add llvm-tools-preview
cargo install cargo-llvm-cov --locked
cargo install flutter_rust_bridge_codegen
git clone --depth 1 --branch stable https://github.com/flutter/flutter.git \
  "$HOME/.local/share/flutter"
```

## Verify with the tool's own report

```bash
ssh peer 'export PATH="$HOME/.local/share/flutter/bin:$PATH"; flutter doctor'
# The line that actually matters for desktop work:
#   [✓] Linux toolchain - develop for Linux desktop
ssh peer 'export PATH="$HOME/.local/share/flutter/bin:$PATH"; flutter config --enable-linux-desktop'

ssh peer 'source ~/.cargo/env; cargo llvm-cov --version'   # -> cargo-llvm-cov 0.9.0
```

`flutter doctor` reporting `[!] Android Studio (not installed)` is noise when
the goal is Linux desktop — read the specific line you need, not the summary
verdict.

## The blocker that actually stopped the work: scoped deploy key

Cloning the repo failed on the peer. The diagnosis that matters — **an SSH key
can authenticate successfully and still be denied**, because a GitHub *deploy
key* is scoped to a single repository:

```bash
ssh -i ~/.ssh/id_ed25519_atlas -T git@github.com
# Hi HorusElohim/Atlas! You've successfully authenticated, but GitHub does not
# provide shell access.
```

That greeting names **`Owner/Repo`**, not a username — the tell for a deploy
key. It grants `Atlas` only, so `PortalisApp` returns
`Permission denied (publickey)`. A plain user key greets `Hi <username>!`.

Test every candidate key individually with `-i <key> -T git@github.com` and
read the greeting; do not infer from "one key worked" that the host has
general access. Other paths checked the same way:

- `gh auth status` → not logged in
- HTTPS → `could not read Username for 'https://github.com'` (no credentials)
- generic HTTPS egress → fine (`git ls-remote` against a public repo worked),
  proving the failure was authorization, not network

Escalate to the user with the three real options: `gh auth login` (device
flow), add the key as a deploy key on the *other* repo, or promote it to an
account-level SSH key. See `github-auth` for the mechanics of each.
