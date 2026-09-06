# Vendored crates: feature unification and re-export repair

Notes from repairing a vendored `librqbit` fork inside a Flutter+Rust app.
Two distinct traps, both of which look like ordinary compile errors and are
cheap to fix once recognised, expensive to fix by trial and error.

## 1. Don't add a direct dep on a crate the vendored library already pulls in

The app crate needed `Sha1`/`ISha1`. The obvious move is to add the crate that
defines them to `Cargo.toml`:

```toml
# WRONG
sha1w = { package = "librqbit-sha1-wrapper", version = "9.0.1",
          default-features = false, features = ["sha1-ring"] }
```

This built nothing and failed with:

```
error[E0428]: the name `Sha1` is defined multiple times
error[E0080]: evaluation panicked:
              too many features were enabled, only one of them can be enabled:
              - `feature = "sha1-crypto-hash"`
              - `feature = "sha1-ring"`
```

**Why.** Cargo unifies features across the whole graph. The vendored library
already depended on that crate and selected the *other* mutually-exclusive
feature through its own default feature set (`default-tls` →
`sha1w/sha1-crypto-hash`). Adding a second direct dependency with
`sha1-ring` turned on made both active at once, tripping the crate's own
`assert_cfg::exactly_one!` guard. The error names the features, not the
dependency edge that introduced them, so it reads like a local mistake.

**Fix.** Do not take the direct dependency at all. Re-export the symbol from
the vendored crate you already depend on, and let its existing feature
selection stand:

```rust
// vendor/librqbit/src/lib.rs
pub use sha1w::{ISha1, Sha1, ISha256, Sha256};
```

```rust
// app crate
use librqbit::{ISha1, Sha1};
```

**Rule.** When a vendored library already depends on a crate, reach the
symbol *through* the library. A direct dependency is a second opinion about
feature selection, and mutually-exclusive-feature crates fail loudly when two
opinions disagree. Check `cargo tree -i <crate>` before adding the dep: if the
vendored library is already an inbound edge, re-export instead.

Corollary: the same applies to `[patch.crates-io]` entries. Patching a crate
you don't otherwise need pulls it into the graph with *your* feature flags.

## 2. Repair a broken re-export surface by reading, not by rebuilding

After an interrupted edit, the vendored crate's `lib.rs` was missing module
visibility and re-exports for several symbols. The tempting loop is:

```
cargo build → fix one `unresolved import` → cargo build → fix the next → ...
```

This is very slow: each missing symbol is only revealed once the previous one
resolves, and a vendored crate can easily be a dozen symbols short. Worse, a
symbol may be missing for two different reasons (module is private vs. no
`pub use`), and the error text is the same.

**Do this instead.** Once you suspect the module tree itself is damaged, stop
building and read:

```sh
# What does the crate actually expose today?
grep -n '^pub mod\|^mod\|^pub use' vendor/<crate>/src/lib.rs

# Where do the symbols the call site wants actually live?
grep -rn 'pub struct Id20\|pub trait ISha1' vendor/<crate>/src/ \
       ~/.cargo/registry/src/*/<crate>-*/src/
```

Then fix every `mod` / `pub use` line in **one** edit and rebuild once.

**Also check the wrapped crate, not just the wrapper.** A vendored library
often re-exports its own dependency's types under its own path
(`librqbit_core::hash_id::Id20` surfacing as `librqbit::Id20`). Before
concluding a symbol doesn't exist, grep both the crate you're importing from
and the crate it wraps. Registry sources under
`~/.cargo/registry/src/index.crates.io-*/` are readable and are the ground
truth for what the upstream version actually exports.

## 3. Verifying the repair

A vendored-crate change is invisible to the app's own test suite until it
compiles, so run the gates in widening order and don't skip the middle one:

```sh
cargo build                      # the vendored crate compiles at all
cargo clippy --lib -- -D warnings # no new warnings from the re-exports
cargo fmt --check                 # FRB/codegen import ordering drift
cargo test --lib                  # behaviour unchanged
```

`cargo fmt` is not optional here: repairing imports by hand reliably produces
ordering that `cargo fmt --check` rejects, and that failure will otherwise
first appear in CI.

## Reading a piped build result honestly

`cargo build 2>&1 | tail -60` reports the **exit code of `tail`**, so a failed
build can present as `exit_code: 0`. Judge the run by its text (`error[E....]`,
`could not compile`), or drop the pipe when the status actually matters.
