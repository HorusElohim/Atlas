---
name: cross-platform-rust-refactoring
description: "Use when moving Rust platform adapters safely."
version: 1.0.0
---

# Cross-Platform Rust Refactoring

Use for structural refactors that relocate Android, iOS, desktop, or web-specific Rust code while preserving the app-facing API.

## Design

1. Keep the crate root reserved for public app/bridge boundaries.
2. Group OS framework, JNI, FFI, and native companion sources under a domain-local platform namespace such as `src/<domain>/platform/`.
3. Keep cross-platform abstractions outside the platform namespace. Extract only the OS-specific FFI and adapter details into platform modules.
4. Move native companion sources (Objective-C/C/C++) with their Rust adapter and update all `build.rs` compiler and `rerun-if-changed` paths atomically.
5. Preserve public bridge paths unless the bridge contract is intentionally changing; regenerate bindings whenever scanned Rust API paths change.

## Rust 2024 Compatibility

- Foreign declarations use `unsafe extern "C"`.
- Exported unmangled symbols use `#[unsafe(no_mangle)]`.
- Keep every `unsafe` call localized to a focused adapter function with a fallible, safe Rust interface for the rest of the domain.

## Target Gating

- Gate module declarations, imports, and implementations with the same target predicate.
- Do not leave platform-only imports unconditional: `-D warnings` on another target must stay clean.
- Prefer `#[cfg(target_os = ...)]` around a whole adapter module over scattering platform checks across core workflow code.

## Validation

1. Run formatting and the host test/lint gate first.
2. Run available `cargo check --target <triple>` checks for affected targets.
3. If a cross-target check stops in a dependency/build script because an SDK or compiler is absent, record the exact prerequisite separately from source validation. Do not label the refactor broken without reaching the edited crate.
   - Before concluding the toolchain is genuinely absent, check whether an IDE already vendored it: Android Studio (including the snap package) ships an NDK under its own plugin directory (`/snap/android-studio/<rev>/plugins/android-ndk`) and the Android SDK manager installs versioned NDKs under `~/Android/Sdk/ndk/<version>/`. `rustup target list --installed` reporting `aarch64-linux-android` etc. does not mean a C toolchain is present — that's a separate, independently-installed piece. If `cargo-ndk` (`cargo install cargo-ndk`) and a real NDK directory both exist, export `ANDROID_NDK_HOME`/`ANDROID_NDK_ROOT` to that path and run `cargo ndk -t <abi> build --lib` (or the repo's own `build_rust_android.sh`) to get a **real** cross-compile — not just a `cfg`-gated `cargo build` on the host, which never actually parses/typechecks the platform-gated module. This is worth doing whenever you touch code behind `#[cfg(target_os = "android")]`: the host build silently skips that module entirely, so "builds clean" on the host proves nothing about the gated code.
   - If truly no NDK is available and none can be found, say so plainly rather than asserting the gated module compiles — a `#[cfg]`-excluded file is unparsed by the host build; a diff that only touches such a file is unverified by any local build you actually ran until you either find a toolchain or a CI job does the real cross-compile.
4. Run the project's complete acceptance suite before committing.
5. Confirm the diff contains each source relocation, every build-script path update, and no unintended generated binding churn.

## Portalis Pattern

- `src/nexus/platform/` owns Android JNI and iOS PhotoKit adapters.
- `src/nexus/content_location.rs` remains the portable content-location abstraction and calls the iOS adapter only behind `cfg(target_os = "ios")`.
- `build.rs` remains at the Cargo package root but references native sources inside the Nexus platform directory.
