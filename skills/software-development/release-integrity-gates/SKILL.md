---
name: release-integrity-gates
description: "Use when hardening release gates. Verify releases."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [release, ci, generated-code, signing, dependencies, adr, versioning]
    related_skills: [architecture-decision-records, flutter-rust-bridge, ci-quality-gates]
---

# Release Integrity Gates

## Purpose

Use this class-level skill when a project needs to turn release assumptions into
fail-closed, repeatable checks: generated bindings, dependency advisories and
licenses, coverage, signing, platform metadata, version synchronization, or
worktree hygiene. The deliverable is a working gate backed by local execution,
not a CI configuration that has never been exercised.

## Core model

- Treat generated code, dependency policy, coverage scope, signing material,
  platform metadata, and version files as release inputs.
- Keep the application source of truth in code and the architectural decision in
  the ADR; acceptance evidence belongs in the ADR and cites real checks.
- Make release failures explicit and fail-closed. A missing production key must
  not silently create an artifact that is merely debug-signed.
- Distinguish configured hosted-platform jobs from platform builds actually run
  on the current machine.
- Keep implementation and release/version bumps in separate commits when the
  owner requests a dedicated version commit.

## Workflow

1. Read the ADR and index entry, inspect current CI/actions/scripts, and list
   each acceptance bullet as a concrete command or static assertion.
2. Run the existing gates before editing. Capture only concise status/tail output
   for successful commands; preserve full logs only for failure diagnosis.
3. For generated bindings, pin the code generator to the exact runtime version,
   force regeneration in a clean checkout, and fail if tracked generated files
   change. An incremental stamp is an optimization, not proof of freshness.
4. For Rust dependency policy, enable explicit advisories, bans, licenses, and
   sources policy. Add only licenses discovered and reviewed in the dependency
   graph; rerun the policy after each addition. Do not leave the entire policy
   commented out merely because transitive dependencies have multiple versions.
5. For signing, require release material before building, install it only for
   the build, verify the resulting artifact's certificate against the configured
   key, and remove credentials in an `always` cleanup step. Keep debug sideload
   builds under a separate command/name.
6. Replace template publisher/copyright metadata in every native platform
   resource that ships it. Search all platform directories after editing.
7. Synchronize application version, backend crate version, lockfile, runtime
   compatibility constants, and changelog heading in one release change. Search
   for stale old versions. Replace literal version assertions with package
   metadata (`env!("CARGO_PKG_VERSION")` or the canonical app source).
8. Add acceptance evidence to the ADR only after every implementation criterion
   has a check. If a hosted SDK is unavailable locally, say so; do not mark its
   build as locally passed. A configured CI matrix is policy, not execution.
9. Run the complete local gates, inspect `git diff --check` and status, commit
   the ADR implementation, push it, then create and push the separately requested
   version commit. Verify the final tree is clean.

## Verified Portalis pattern

For a Flutter/Rust project, the useful split is:

- Frontend gate: `flutter analyze`, `flutter test`, then
  `tool/frb_build.sh --codegen-only --force-frb --ai` followed by a tracked-file
  drift check.
- Backend gate: `cargo fmt --all --check`, clippy with warnings denied, audit,
  cargo-deny advisories/bans/licenses/sources, workspace tests, and coverage.
- Android action: fail when release keystore/password inputs are empty, build,
  compare APK signer SHA-256 with the keystore certificate, and always remove
  signing files.
- Version commit: bump `pubspec.yaml`, Rust `Cargo.toml`/`Cargo.lock`, Dart
  compatibility constant, and changelog together; make handshake/version tests
  derive expected values from package metadata.

See `references/portalis-adr-0018-checklist.md` for the concrete acceptance
matrix and the known limitation that Apple/Windows release jobs require hosted
SDK runners.

## Pitfalls

- Adding a CI step that was never run locally; configuration is not verification.
- Enabling a license gate with a blanket allow-list and no rerun against the
  actual lockfile.
- Treating a nonzero policy warning or unlicensed upstream package as silently
  reviewed; record the exact remaining warning.
- Letting a release action default to debug signing when secrets are absent.
- Updating only `pubspec.yaml` and leaving the Rust crate, lockfile, or startup
  compatibility constant stale.
- Running a full-tree formatter and accidentally committing unrelated drift.
- Dumping complete successful test/CI logs into the working context. Prefer the
  tail and a pass/fail summary; replay full output only when diagnosing failure.
- Claiming iOS/macOS/Windows release success from Linux when the required SDK is
  absent.
