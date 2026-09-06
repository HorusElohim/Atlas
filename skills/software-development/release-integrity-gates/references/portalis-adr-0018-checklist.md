# Portalis ADR-0018 acceptance checklist

## Generated bindings

- Generator and Flutter/Rust FRB runtime are both 2.13.0.
- `tests/frontend.sh` runs forced codegen and fails if tracked output changes.
- A clean local run passed with no generated diff.

## Dependency policy

- `tests/nexus.sh` runs `cargo audit`.
- `tests/nexus.sh` runs `cargo deny check advisories bans licenses sources`.
- `rust/backend/deny.toml` explicitly allows the reviewed dependency licenses,
  including Apache-2.0, MIT, Unicode-3.0, and CDLA-Permissive-2.0.
- Duplicate semver versions remain visible but are allowed because FRB and
  librqbit require incompatible dependency generations.

## Artifacts and metadata

- Android release action requires keystore inputs and compares APK signer
  SHA-256 with the configured keystore certificate.
- Windows `Runner.rc` and macOS `AppInfo.xcconfig` use Portalis metadata rather
  than `com.example` template values.
- Root `.hermes/` is ignored.

## Versioning

- Frontend 1.0.50+60, backend 0.1.50, Dart compatibility constant, and Cargo
  lockfile were synchronized in a dedicated release commit.
- Version-sensitive handshake tests derive the expected value from
  `CARGO_PKG_VERSION`.

## Verification boundary

- Local verified results: Flutter analysis/tests, FRB drift, Rust formatting,
  clippy, audit/deny policy, backend tests, coverage, and Android debug APK.
- Apple/Windows release execution requires hosted SDK runners and must not be
  reported as a local result.
