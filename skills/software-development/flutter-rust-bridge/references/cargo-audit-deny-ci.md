# cargo-audit + cargo-deny in CI

## When to add

Only after verifying they pass (or produce manageable issues) locally on the current lockfile. Adding them blindly to CI will surface existing issues and fail the build.

## Local verification first

```bash
cargo install cargo-audit --locked
cargo install cargo-deny --locked

cargo audit
cargo deny check advisories bans sources
```

If any fail, resolve before adding to CI:

- **advisories**: version bump vulnerable deps (`cargo update -p <crate> --precise <version>`)
- **bans** (duplicates): allow-list known transitive duplicates in `deny.toml`
  - Example: `base64`, `hashbrown`, `rand`, `thiserror`, `syn`, etc.
  - These come from deep transitive trees; unifying versions is impractical
- **licenses**: our own crates need SPDX metadata in `Cargo.toml`
  - `backend = 0.1.49` and `portalis-nexus-protocol` lacked `license = "MIT"` etc.
  - Fix by adding `license` field to each workspace crate's `Cargo.toml`
  - Or disable licenses check in CI until done

## deny.toml minimal working config

```toml
[advisories]
# ignore = [{ id = "RUSTSEC-YYYY-NNNN", reason = "..." }]

[bans]
multiple-versions = "deny"
allow = [
  { name = "base64" },
  { name = "block-buffer" },
  { name = "hashbrown" },
  { name = "rand" },
  { name = "rand_chacha" },
  { name = "rand_core" },
  { name = "thiserror" },
  { name = "thiserror-impl" },
  # ...add as discovered
]

[licenses]
# Disabled until all workspace crates have SPDX license metadata
# allow = ["MIT", "Apache-2.0", "BSD-3-Clause", ...]

[sources]
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
```

## Pipeline integration

```bash
# tests/nexus.sh or equivalent
cargo audit
cargo deny check advisories bans sources
```

Only run the subset that passes. License check added later when all crates have metadata.

## Portalis session notes

- `time 0.3.45` had CVE-2026-0009 (DoS via stack exhaustion) — fixed with `cargo update -p time --precise 0.3.47`
- `chacha20 0.10.1` is yanked — fixed with `cargo update -p chacha20` (0.10.2 unyanked)
- ~18 duplicate semver-incompatible crates from transitive deps (librqbit, ring, etc.)
- Our own crates (`backend`, `portalis-nexus-protocol`) missing `license` field → licenses check disabled

## `unmaintained`/`yanked` advisories from an optional feature, not a direct dep

`cargo audit` flags an advisory even when the offending crate arrives only
through a vendored dependency's *feature choice*, not anything the project
imports directly. Before reaching for an `ignore =` entry in `deny.toml`
(which silences the warning without fixing anything), check whether the
dependency exposes an alternative feature that avoids the crate entirely:

```bash
cargo tree -i <flagged-crate>   # shows exactly which feature pulled it in
```

Example: `librqbit`'s `default-tls` feature enables `librqbit-sha1-wrapper`'s
`sha1-crypto-hash` backend → pulls in the unmaintained `crypto-hash` crate
(RUSTSEC-2025-0060). `librqbit` also ships a `rust-tls` feature that instead
enables `sha1-ring` — same library, no `crypto-hash` in the tree at all:

```toml
# Cargo.toml — default_features must be false, or librqbit's own
# `default = ["default-tls", ...]` re-enables the crypto-hash path anyway
librqbit = { path = "../vendor/librqbit", default-features = false, features = ["rust-tls"] }
```

This is almost always preferable to an `ignore =` suppression: it removes the
unmaintained/yanked crate from the dependency tree entirely rather than
telling `cargo audit` to stop reporting it. Verify with `cargo tree -i
<crate>` (should error "did not match any packages") and a clean `cargo
audit` (zero output = zero findings) before committing.

## When to enable licenses

1. Add `license = "MIT"` (or `MIT OR Apache-2.0`) to every workspace crate's `Cargo.toml`
2. Run `cargo deny check licenses` locally — must pass
3. Then add `licenses` to CI `cargo deny check` command

Don't enable prematurely; a failing licenses check blocks every CI run and adds noise.