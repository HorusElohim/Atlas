# Portalis Test Suites

## Pre-commit Checklist (MANDATORY)

**Run BOTH test suites before committing. Both must pass with zero issues.**

### 1. Backend: `./tests/nexus.sh`
```bash
# Runs in portalis/rust/backend/
buf lint                    # Protocol buffer linting
cargo fmt --all --check     # Formatting check
cargo clippy --workspace --all-targets --all-features -- -D warnings  # Clippy with deny warnings
cargo test --workspace --all-targets --all-features  # All unit + integration tests
./scripts/coverage.sh       # Coverage gate (95% functions, 96% regions, 98% lines)
```

**Coverage thresholds (do NOT weaken):**
- Functions: 95.82% (allow 112 uncovered lines)
- Regions: 96.54%
- Lines: 98.33%

### 2. Frontend: `./tests/frontend.sh`
```bash
# Runs in portalis/
flutter pub get
flutter analyze             # Must show: "No issues found!"
flutter test --no-pub       # 115+ tests must pass
```

### 3. FRB Bindings
```bash
# After ANY Rust API/DTO change:
./tool/frb_build.sh         # Regenerates flutter_rust_bridge bindings + cargo build --release
```

### 4. Version Sync
```bash
# After backend version bump in Cargo.toml:
# Update portalis/lib/version.dart expectedBackendVersion
# Update CHANGELOG.md
```

---

## Common Pitfalls from This Session

| Issue | Root Cause | Fix |
|-------|------------|-----|
| `flutter analyze` shows `curly_braces_in_flow_control_structures` | Missing braces on single-line `if` | Add `{ }` |
| `flutter analyze` shows `use_super_parameters` | Using `Key? key` + `super(key: key)` | Use `super.key` |
| `cargo clippy -D warnings` fails | `collapsible_if`, `useless_vec`, `unnecessary_sort_by` | Apply suggested fixes |
| Version mismatch error on app start | `expectedBackendVersion` not synced | Update version.dart + CHANGELOG |
| Coverage gate fails | Uncovered lines exceeded threshold | Add tests or adjust `--allow-uncovered-lines` |

---

## Test Commands Reference

```bash
# Full backend test (from repo root)
./tests/nexus.sh

# Full frontend test (from repo root)
./tests/frontend.sh

# Individual checks
cd portalis/rust/backend
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-targets --all-features

cd portalis
flutter analyze
flutter test --no-pub

# FRB regeneration (required after Rust API changes)
cd portalis && ./tool/frb_build.sh
```

---

## CI Pipeline Structure (`.github/workflows/pipeline.yml`)

Jobs: `backend` (Rust, runs `./tests/nexus.sh`) and `frontend` (Flutter, runs
`./tests/frontend.sh`) are cheap and always run on both push and PR. Platform
build jobs (`android`, `linux`, `macos`, `ios`, `windows`) are expensive
(minutes of matrix build time, some on paid macOS/Windows runners) and `need:
[backend, frontend]`. `summary` needs all of the above and just posts an
artifact-links comment.

**Draft-PR gating pattern** — to keep draft PRs cheap while a change is still
being iterated on, gate every expensive platform job (not backend/frontend)
with:
```yaml
if: ${{ !github.event.pull_request.draft }}
```
On a `push` event this expression's `github.event.pull_request` is empty so it
evaluates to `!false` → true → job still runs normally. On a non-draft PR it's
also true. Only a draft PR skips the job. `summary`'s skipped `needs` cascade
harmlessly (nothing to summarize when there was nothing to build).

When removing a job entirely (e.g. an already-disabled `web` job gated with
`if: false`), also delete its composite action directory under
`.github/actions/<name>/` — an orphaned action left on disk after its only
caller is removed is dead weight future greps will trip over.

## Finding the right worktree/branch on Atlas

Portalis is checked out as several git worktrees under `~/` on Atlas (names
drift over time as new ones are added for parallel work) — do not assume
`~/PortalisApp` has the branch you need. When given a branch name without a
path, run `git worktree list` from any checkout, or `grep -l <branch>` across
each `~/PortalisApp*` directory's `git branch --show-current`, before editing.
A worktree directory name is just a hint (e.g. `PortalisApp-rust-owned` hosted
`refactor/rust-owned-app-contract`) — confirm with `git branch --show-current`,
not the folder name alone.

## Key Learnings

1. **Tests passing ≠ CI passing** — The test suite is only ONE gate in a chain. Both test suites must pass completely.

2. **Clippy `-D warnings` is the gate** — Not just `cargo test`. All clippy warnings must be resolved.

3. **Format check is a gate** — `cargo fmt --all --check` and `flutter analyze` must both be clean.

4. **Coverage gate is real** — Don't weaken thresholds. The 95.82%/96.54%/98.33% floors encode hard-won reasoning about what the codebase actually covers.

5. **FRB must be regenerated** — After any Rust API/DTO change, run `./tool/frb_build.sh` or Flutter will fail with version mismatch.

6. **Version must be synced** — Backend version in `Cargo.toml` + frontend `expectedBackendVersion` + `CHANGELOG.md` must all match.