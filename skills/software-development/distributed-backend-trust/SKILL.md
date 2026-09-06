---
name: distributed-backend-trust
description: "Use for frontend/backend trust releases."
version: 1.0.0
---

# Distributed Backend Trust and Release Compatibility

## Use when

Use this skill when a Flutter application ships a native Rust/backend engine,
when frontend and backend versions must remain compatible, or when a distributed
transfer/trust failure crosses Flutter, FFI/FRB, core state, worker, and network
boundaries.

## Core model

- A frontend release version and a backend compatibility version are related but
  distinct identities. Keep both explicit.
- A process-local handle, torrent info hash, peer address, or build artifact path
  is not a release identity and must not be used as one.
- API admission, worker execution, metadata resolution, and remote trust are
  separate facts. Never report a queued command as a completed transfer or a
  compatible backend as a trusted remote peer.
- Host-side tests prove code behavior only. Physical iOS/macOS or Android device
  validation must be reported separately.

## Coordinated release workflow

1. Read repository instructions and locate all version sources.
2. Bump the user-facing Flutter package/build version and the Rust backend crate
   version together.
3. Update the backend package entry in the local `Cargo.lock` and the frontend
   expected-backend compatibility constant.
4. Keep the release version available for user-facing reports, while comparing
   the loaded backend version against the exact expected compatibility version.
5. Emit one startup trust report containing:
   - frontend release version;
   - loaded backend version;
   - expected backend version;
   - explicit `trusted`/`rejected` compatibility result.
6. On mismatch, stop startup and include the same values in the user-visible
   error. This makes stale native libraries and mismatched generated bindings
   diagnosable.
7. Update `CHANGELOG.md` with the coordinated versions and the compatibility
   behavior.

## Distributed-flow diagnostics

Before committing a fix for a cross-component failure, instrument each boundary
in order:

1. Flutter entry and normalized input (log type/length, not secrets or full
   untrusted payloads).
2. Bridge/API request and result (command kind, collection, entry count, handle,
   queued/accepted state).
3. Core command admission and durable-state write.
4. Worker wake, pending-work count, and the exact transition being performed.
5. Metadata/inspection start, peer hints, success info hash/file count, timeout,
   and error.
6. Projection/detail update showing when the file list becomes available.
7. Selection command with selected entry IDs and result.
8. Acquisition start/result and first progress/peer observation.

Use stable, privacy-safe fields: command kinds, IDs/handles, counts, source type
and length, info hashes where appropriate, bounded peer hints, and exact error
reasons. Do not log credentials, secret keys, complete untrusted payloads, or
media contents.

## Verification

Run the smallest relevant checks first, then the broader gates:

```sh
# version consistency: use the repository's actual version sources
flutter analyze
flutter test
cargo fmt --all --check
cargo test --lib
# run the repository's full Rust/Flutter acceptance gates when required
```

If the bridge schema changed, regenerate bindings with the repository helper and
review generated diffs. If only version/reporting code changed, do not create
unrelated generated churn. Before commit, run `git diff --check` and verify the
working tree contains only the intended atomic change.

## Pitfalls

- Updating only the Flutter version or only the Rust version.
- Checking compatibility with a hard-coded value in a second, drifting location.
- Reporting a generic mismatch without actual, expected, and frontend versions.
- Treating a successful bridge command as proof that the asynchronous worker ran.
- Adding network/listener changes before tracing the complete worker path.
- Treating TCP reachability as proof of a successful application-level handshake
  or metadata exchange.
- Treating host compilation/tests as proof of physical iPhone↔macOS transfer.
- Logging complete magnets, credentials, secret keys, or media payloads.

## Related skills

This skill complements the Flutter/Rust bridge workflow; use the bridge skill for
FRB schema/code-generation mechanics and this skill for release identity,
compatibility reporting, and cross-boundary trust diagnostics.
