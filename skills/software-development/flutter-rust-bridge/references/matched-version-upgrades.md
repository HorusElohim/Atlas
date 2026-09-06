# Matched FRB runtime upgrades

Use this when updating Flutter Rust Bridge itself rather than an app-facing DTO.

## Invariant

Keep these three versions identical:

1. Dart `flutter_rust_bridge` in `pubspec.yaml`;
2. Rust `flutter_rust_bridge` in the backend `Cargo.toml` and lockfile;
3. installed `flutter_rust_bridge_codegen` used to emit tracked bindings.

A Dart-only or Rust-only change can compile part of the project while failing at runtime because generated bindings enforce the codegen/runtime version match.

## Safe sequence

1. Run `flutter pub outdated` and distinguish direct/resolvable upgrades from transitive SDK or parent-package constraints. Do not force transitive overrides merely to remove an informational notice.
2. Pin the same FRB release in Dart and Rust, then run `flutter pub get` and `cargo update -p flutter_rust_bridge --precise <version>`.
3. Install the matching generator (`cargo install flutter_rust_bridge_codegen --version <version> --locked --force`) and verify `flutter_rust_bridge_codegen --version`.
4. Force the repository-owned generator helper once. Review the generated diff: version markers, generated `api.rs`, and generated Dart facade files are expected; handwritten bridge APIs should not change unless the upgrade requires it.
5. Run the helper again without force to prove its fingerprint/stamp behavior is stable.
6. Run formatter, Flutter analysis/tests, Rust workspace tests, and each affected native platform build. Treat parser notices about private, non-exported types as diagnostics only after the public generated boundary compiles and tests pass.

## Release hygiene

For projects that version the native backend separately, update the frontend release, backend package version, compatibility expectation, lockfile entry, and changelog in one atomic commit with the dependency and generated artifacts.
