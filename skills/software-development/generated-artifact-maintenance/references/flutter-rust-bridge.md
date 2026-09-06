# Flutter-Rust Bridge 2.x regeneration gate

## Validated sequence

Use this sequence in a Flutter application that tracks FRB output and whose
backend workspace is distinct from the Flutter app root.

1. Locate the Rust `Cargo.toml`; run `cargo build` from that workspace, not
   from the Flutter application directory.
2. Run the repository-owned FRB helper from the Flutter app root. Its explicit
   public Rust input list is the bridge contract; do not broaden it to a
   crate-wide scan merely to silence parser notices.
3. Run `cargo fmt --all` inside the Rust workspace directly after FRB
   generation. FRB 2.x can regenerate Rust imports in an order that fails a
   repository format gate even though code generation exits successfully.
4. Review generated Rust/Dart bridge changes and platform registrant changes
   alongside dependency lockfile updates. Do not edit either generated artifact
   manually.
5. Verify both sides: Flutter analysis/tests, Rust build, and the backend
   acceptance/coverage suite.

## Helper pattern

Place the formatter immediately after the code generator and before any native
library build:

```bash
flutter_rust_bridge_codegen generate ...
(cd "$CRATE" && cargo fmt --all)
```

Then rerun the helper itself and the strict format/acceptance gate. Formatting a
single generated file manually is insufficient because the next regeneration
would reintroduce the defect.

## Diagnostics

FRB parser messages about duplicate internal type names, unsupported private
shapes, or lifetime handling need investigation if they affect the exported
bridge. They are not automatically build failures when the explicitly exposed
API regenerates, compiles, and passes its consumer tests. Preserve the messages
in command output; do not add blanket suppression.

A helper named for a target platform is not proof that it cross-compiles. Verify
native macOS/iOS/Android artifacts on that target platform or with an explicit,
configured cross-compilation target before reporting a target build as passed.
