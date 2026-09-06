# Portalis Iroh Removal Build Workflow

Reference for removing the Iroh-based Nexus control plane while preserving collection crypto on a constrained Jetson host (7.3 GB RAM, no swap).

## Build Constraints
- `CARGO_BUILD_JOBS=2` — cap parallelism to avoid OOM
- `cargo fmt --all` before every `cargo check`
- Scoped commands: `cargo check -p backend --lib` before full test suite
- Background processes for long builds, poll/wait instead of blocking

## Key Workflow Steps
1. **Extract crypto first** — Move `capsule`, `keys`, `verify` modules from `crates/client` to `backend/src/crypto/` with `pub` visibility
2. **Update visibility** — Change `pub(crate)` → `pub` on all types used by public `collections` API (`Recipient`, `SealedFor`, `KeyError`, `ChainError`, `ChainStore`, `Continuity`, `MemoryChainStore`)
3. **Suppress dead-code warnings** — Add `#[allow(dead_code)]` to test-only constructs re-exported publicly (constants, helper fns, `MemoryChainStore`)
4. **Delete transport modules** — Remove `nexus.rs`, `nexus_settings.rs`, `core/service.rs`, `crates/client`, `apps/server`, `crates/server-core`, `crates/storage`, `demo`
4. **Update Cargo workspace** — Drop `iroh` dep, move `x25519-dalek` to `[dev-dependencies]`, remove deleted crate members
5. **Regenerate FRB bindings** — Update `--rust-input` to exclude `crate::nexus_settings`; run `flutter_rust_bridge_codegen generate`
6. **Clean Dart UI** — Delete `ServiceController`, `ServiceRepository`, `nexus_settings.dart`, `service_section.dart`
7. **Version bump** — Flutter `pubspec.yaml` + Rust `Cargo.toml` together per AGENTS.md
8. **Test** — `cargo test -p backend --lib` (208 passed)

## Common Errors & Fixes
| Error | Fix |
|-------|-----|
| `type X is more private than item Y` | Make `X` `pub` and re-export from `crypto` module |
| `unused imports` in re-export module | Add `#[allow(dead_code)]` to source items, or remove unused re-exports |
| `dead_code` on test-only constructs | Add `#[allow(dead_code)]` to constants, helpers, `MemoryChainStore` |
| FRB missing `nexus_settings` | Remove from `--rust-input`, regenerate bindings |
| `x25519-dalek` unresolved in tests | Move to `[dev-dependencies]` in backend `Cargo.toml` |

## Post-Task Sweep (Mandatory)
```bash
ps aux | grep -E "rustc|cargo" | grep -v grep  # no stray builds
free -h                                        # RAM back to baseline
df -h /                                        # disk OK
```