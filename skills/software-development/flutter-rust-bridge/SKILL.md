---
name: flutter-rust-bridge
description: "Use for Flutter-Rust bridge generation and API changes."
version: 1.0.0
---

# Flutter-Rust Bridge Engineering

## Use when

Use this skill when a Flutter application calls Rust through
`flutter_rust_bridge` (FRB): changing a bridged function or DTO, regenerating
bindings, reviewing generated output, or diagnosing codegen/build mismatches.

## Principles

- Keep the bridge **app-facing and explicit**. Export small DTOs and functions
  designed for Flutter; do not expose internal stores, core handles, traits, or
  domain graphs merely because codegen can see them.
- Generated bindings are build artifacts, not hand-maintained source. Change
  Rust inputs and generator configuration, then regenerate; never patch
  generated Dart or Rust as the lasting fix.
- Keep expensive or fast-moving state tiered. Prefer explicit summary, detail,
  history, and command channels over one universal snapshot that increases
  bridge traffic and Flutter allocation.
- For durable telemetry, make Rust the sole accounting authority: persist and
  deduplicate at backend lifecycle boundaries, compute effective live totals
  there, and expose presentation-ready DTOs. Flutter must not merge saved and
  live counters, infer epochs, or aggregate endpoint identity locally.
- Treat external links and QR payloads as untrusted input. Validate them before
  dispatching a bridged command; do not let a UI handle or display identifier
  masquerade as a durable cross-device identifier.

## Workflow

1. **Trace the current boundary.** Read the generator helper, its explicit Rust
   inputs, the public Rust API, generated Dart facade, app adapter, consumers,
   and test fakes before editing.
2. **Write a focused red test.** Cover the app-facing behavior or the smallest
   core boundary. Test an absent/invalid value as well as the successful bridge
   value where relevant.
3. **Change the real Rust boundary.** Keep DTOs owned and serializable. Return
   explicit `Option`/`Result` values instead of sentinel strings or invented
   identifiers.
4. **Classify the boundary change before codegen.** An internal Rust domain
   struct may carry new information between native adapter and projection
   without changing any exported `portalis_api` function or FRB DTO. In that
   case, do **not** regenerate merely because a Rust struct changed: confirm
   the generated public surface is unaffected, run the backend and Flutter
   compile/test gates, and keep the generated diff empty. Regenerate only when
   an exported Rust API, bridged DTO, generator input, or FRB version changed.
   For telemetry, keep transport counters (for example native received bytes)
   distinct from verified progress; label the UI by the counter's semantics so
   received-but-unverified bytes are never presented as completed content.
5. **Regenerate when the public boundary changed.** Invoke the repository
   helper from the directory it expects. Review every generated change; retain
   only output attributable to the intentional Rust/public-dependency change.
6. **Normalize generated Rust in the helper.** Some FRB versions emit Rust
   import ordering that fails `cargo fmt --check` despite compiling. Put
   `cargo fmt --all` immediately after codegen in the repository helper, then
   rerun the helper. Never manually format `src/api.rs` and call it fixed.
7. **Update adapter seams and test fakes.** An added repository/gateway method
   requires every fake implementation to implement it, usually with the most
   truthful unavailable/default response. Inspect generated DTO field types:
   FRB collection fields can be typed buffers such as `Uint32List`, so list
   literals are not always accepted in test seed data. A fake must also
   **drive any collaborator it is handed**, not just accept it — see the
   underscore-parameter pitfall below, which is the single most effective way
   to write a regression test that cannot fail.
8. **Verify the combined tree.** Run the focused tests, Flutter analysis and
   suite, the generator, Rust formatting, and the repository Rust acceptance
   gate. Report target-specific build checks honestly when the required SDK is
   unavailable.

## Upgrading the FRB runtime and generator

When the package itself is upgraded, treat the Dart runtime, Rust crate, and
codegen executable as one matched toolchain. Update and regenerate them as a
single operation; do not use dependency overrides to force unrelated
transitive packages merely to silence `pub outdated`. Follow
[`references/matched-version-upgrades.md`](references/matched-version-upgrades.md)
for the exact resolution, generation, review, and verification sequence.

## Diagnosing generator messages

- A codegen diagnostic about duplicate internal type names or skipped
  unsupported internal types is not automatically a release failure. First
  inspect the generated public API and compile the generated Rust.
- It becomes a correctness problem if the ambiguous or skipped type is present
  in an exported function or DTO. Fix the public boundary—rename/contain the
  internal type or define a dedicated app-facing DTO—rather than suppressing
  diagnostics or exposing internals as opaque solely to hide a message.
- A generator run is successful only when it exits zero **and** the generated
  bindings compile through the repository's normal Rust/Flutter gates.

## Verification checklist

```sh
# From the Flutter package root
./tool/frb_build.sh
flutter analyze
flutter test

# From the Rust workspace root, or use the repository acceptance helper
cargo fmt --all --check
cargo test --workspace --all-targets --all-features
```

Follow any repository-specific integration/coverage script as the final gate.

## Native opaque-source adapters

When a native picker hands the app an opaque, permission-scoped source instead
of a filesystem path, preserve that identifier across Flutter and implement the
reader at the Rust platform-storage boundary. Never repair the boundary by
copying media into an app cache or by requesting picker byte data. See
[`references/android-no-copy-source-adapters.md`](references/android-no-copy-source-adapters.md)
for the Android Storage Access Framework and JNI descriptor pattern.

## Pitfalls

- A Flutter platform plugin (`path_provider`, file pickers, etc.) that *names*
  a path is not promising the path already exists on disk. `getTemporaryDirectory()`
  on macOS can report a sandboxed `Library/Caches/<bundle id>/` directory before
  anything has created it; writing straight into it throws `PathNotFoundException`
  in production while working fine in dev (where the directory was already
  warmed by an earlier run). `directory.create(recursive: true)` before the
  write is the textbook fix and it does make the mocked unit test pass — but
  it is not guaranteed sufficient on every real device/OS combination in
  practice (observed: a user still hit the same `PathNotFoundException` on a
  real macOS install after this fix shipped and passed its test). When the
  data being written already exists as a real file somewhere the app itself
  controls and already exposes (e.g. a log file the backend already wrote to
  a known path), the more robust fix is to **skip the defensive copy
  entirely** and hand the share/consumer API the original file's path
  directly — one less directory-existence assumption to get wrong, not a
  second copy that can go stale or fail for reasons the mock can't reproduce.
  Reach for `create(recursive: true)` only when there genuinely is no
  existing on-disk original to point at instead. See
  [`references/platform-plugin-path-mocking.md`](references/platform-plugin-path-mocking.md)
  for reproducing this class of bug in a fast unit test via a mocked
  `PathProviderPlatform.instance`, without a device or a full widget test —
  and for when that test passing is not the end of the investigation.
- A worker/reconciler that re-asserts stored intent on every poll tick
  ("pause if stored paused, resume if stored running", applied unconditionally
  every tick by design) will treat a wrapped third-party library call as
  idempotent only if the library itself treats it that way. Many libraries
  (e.g. `librqbit`'s `pause()`/`unpause()`) instead `bail!`/error on
  "already in that state", so every already-settled item logs a fresh failure
  on *every single tick, forever* — silent to the user but drowning the
  diagnostics log in noise. Fix at the call site: check current state first
  (`if already_in_target_state { return Ok(()) }`) before calling the
  library method, so the wrapper's own idempotency contract holds regardless
  of what the underlying library actually does. Extract the check into a
  small function taking the live handle/session directly (not the
  process-global singleton) so it's unit-testable against a real instance of
  the library without mocking the whole session.
- Converting a bridged DTO from a single struct (string `kind` plus many
  `Option<T>` fields, one envelope for every command) into a tagged Rust enum
  (one variant per command, each carrying only its own required fields) is a
  real ADR-0016-style improvement — it makes invalid combinations
  unconstructible instead of merely validated at runtime. But regenerating FRB
  mid-conversion, while the old struct definition and the new enum variant
  construction syntax coexist, produces a confusing `error[E0223]: ambiguous
  associated type` at the call site (`AppCommand::Variant { .. }` resolves
  against the still-present struct, not the enum) or, after codegen runs
  against half-migrated Rust, downstream `no field \`kind\` on type
  \`AppCommand\`` errors baked into the generated `api.rs`/`portalis_api.dart`.
  Do the conversion in one shot: delete the old struct entirely (including its
  own now-obsolete `into_core`/dispatch logic) in the same edit that adds the
  enum, *then* run `frb_build.sh --force-frb`. Don't try to land the enum
  alongside the still-present struct and regenerate partway through — the
  generator captures whichever type shape it saw at that moment and nothing
  downstream will match it.
- Using a bare crate-wide generator input in a complex crate and accidentally
  traversing internal modules that are not bridgeable.
- Hand-editing generated files after codegen.
- Running `dart format lib test` (or any bare directory argument) to format
  only the files you intentionally touched. It reformats the **entire** tree,
  including every file with pre-existing style drift that nobody had gotten
  around to yet — those show up as unrelated changes in `git status` and, if
  you `git add -A`, ride into your commit under cover of the real change.
  Before committing, diff what `dart format` actually touched against what
  the task touched (`git status --short lib test`) and `git checkout --` any
  file outside your intended change set; stage explicitly rather than with a
  blanket `git add -A` when this has happened. Formatting drift belongs in
  its own dedicated formatting commit if it needs fixing at all.
- Adding a method to the production adapter but forgetting test fakes.
- **A test double that ignores a collaborator parameter makes an entire
  production branch invisible to the suite — and produces regression tests
  that pass with the bug still present.** A fake satisfying the trait with
  `_progress: PublishProgress` (or `_reporter`, `_clock`, `_metrics`)
  compiles, reviews clean, and leaves that collaborator frozen at its
  constructor defaults. Production code guarded on it advancing —
  `if stage != "preparing" { publish_snapshot() }` — is then never reached
  in any test. Observed symptom: a would-be RED test goes GREEN immediately,
  and when you finally do see a failure the values are *too tidy* (a field
  pinned at `0`/`"preparing"`/`[]` while everything around it is real).
  Diagnose by grepping the doubles for `_`-prefixed parameters on the path
  under test **before** rewriting assertions; the defect is in the double,
  not the test. Fix it by making the double walk the same observable
  transitions as the real implementation (e.g. `progress.set_stage("hashing");
  progress.set_stage("seeding");`), then re-run and confirm the test now
  fails for the real reason. Treat an underscore-prefixed parameter in a
  test double as a suppressed observation, not as tidy unused-arg hygiene.
- **A sidecar task spawned to report on an operation must be stopped on
  *every* exit from that operation, not only on shutdown.** The shape:
  spawn a `tokio::interval` ticker that periodically publishes progress into
  the projection, guard its loop solely on a `cancelled` flag, then only set
  that flag in the shutdown branch. On the ordinary success and failure
  paths the ticker outlives the work it describes, which is worse than a
  plain task leak — the completion path clears the progress field
  (`publish_progress = None`) and the surviving ticker writes its final
  snapshot straight back on the next tick, **re-asserting a stale
  "in progress" bar on a finished item forever, once per interval**, plus one
  leaked task per operation. Hold the `JoinHandle` (not `let _ =`) and
  `.abort()` it on success, failure, and shutdown alike. A test that only
  asserts the field is cleared at completion will not catch this: the
  resurrection happens on the tick *after* settling, so the assertion must
  come after a sleep past at least one full interval.
- **FRB maps Rust `u64`/`i64` to Dart `BigInt`, and `BigInt / BigInt` is
  truncating integer division.** Computing a 0..1 progress fraction as
  `processed / total` silently yields `0` for every value below 100%.
  Convert first: `processed.toDouble() / total.toDouble()`. Guard the
  zero-denominator case explicitly (`total <= BigInt.zero`) and return
  `null` rather than `0.0` so the UI can render an indeterminate bar instead
  of a bar that claims 0% — "no total to measure against yet" and "measured,
  and it is zero" are different facts.
- **Adding a field to a struct that is bridged as an FRB DTO (or that feeds
  one, like an internal `CollectionState`/`AppCollection` pair) breaks every
  place that constructs it with struct-literal syntax, not just the
  production path.** The compiler's `E0063: missing field` errors are a
  reliable checklist, but they surface one file at a time as you fix and
  rebuild — cheaper to find them all up front with
  `grep -rn "StructName {" --include=*.rs` (or the Dart equivalent for a
  hand-built domain-side test fixture) before touching the type, so you patch
  every `#[cfg(test)]` fixture, `emit.rs`/projection builder, and
  `portalis_api.rs` test in one pass instead of a build-fix-build loop across
  four-plus files.
- **Repairing a broken vendored crate's public re-export surface (e.g. after
  an interrupted edit to `lib.rs`) is much faster read-first than
  error-driven.** Iterating `cargo build` → fix one `unresolved import` →
  rebuild, one symbol at a time, burns many turns because each fix can reveal
  the next missing re-export only after the previous one resolves. Instead,
  once you suspect the module tree itself is broken, read the crate's actual
  `src/lib.rs` plus the handful of submodules the call site needs
  (`grep -n "^pub " src/*.rs` across the vendor dir) and fix every `mod`/`pub
  use` line for the needed symbols in one edit before rebuilding again. This
  also applies to sibling crates in the same vendor tree that re-export types
  under a different path (e.g. a crate re-exporting a dependency's `Id20`
  under its own name) — check both the crate you're importing from and any
  crate it wraps before assuming a symbol doesn't exist.
- **A hand-written re-implementation of a straightforward transform (e.g.
  clearing padding bits in a `bitvec` bitfield) is a smell if the same crate
  already exposes the operation as a typed method.** Prefer element-by-index
  iteration (`for idx in n..len { bits.set(idx, false) }`) over reaching into
  raw byte storage (`as_raw_slice()`, manual shifts) unless profiling shows
  the difference matters — the raw-storage version is easy to get subtly
  wrong (off-by-one on byte vs. bit indexing, wrong bit order for the crate's
  configured `BitOrder`) and harder to review.
- Treating a process-local backend handle as an importable or shareable ID.
- Claiming an iOS/Android deep-link handoff passed without installing a new
  native build and testing it on the device.
- Bumping the app's release version in only one of several files that must
  move together. A frontend commonly carries the version in more than one
  place — e.g. `pubspec.yaml`'s `version:`, the Rust crate's
  `Cargo.toml`/`Cargo.lock` version, and a Dart constant
  (`expectedBackendVersion`) the app checks against the live backend at
  startup. Bumping `pubspec.yaml` alone leaves the Dart constant stale, so the
  next real device run reports a compatibility mismatch (or silently trusts
  the wrong pair) even though nothing about the actual bridge changed. Grep
  every version-bearing file in the same commit as any version bump, and
  rebuild at least the backend crate afterward to confirm it still compiles
  at the new version before pushing.
- **A pubspec package listed only under `dependency_overrides:` is not a
  declared dependency** — `dependency_overrides` merely pins the *version* a
  transitive resolution must use; it does not add the package to the app's
  own dependency graph. If Dart code starts `import`ing that package
  directly (e.g. wiring up a plugin that was previously pulled in only
  transitively and left unused, such as `wakelock_plus`), `flutter analyze`
  correctly flags `depend_on_referenced_packages` even though `flutter pub
  get` resolves fine and the plugin is already registered natively
  (`GeneratedPluginRegistrant`/Android's Gradle module) — native
  registration and pubspec dependency declaration are two independent facts.
  Move the entry to `dependencies:` (or `dev_dependencies:` if test-only) the
  moment you start importing it in app code, and only leave a bare version
  constraint in `dependency_overrides` for packages the app never imports
  directly (documented in this repo for AGP/KGP-incompatible transitive Android
  plugins). Re-run `flutter pub get && flutter analyze` after moving it, and
  for an Android-registered plugin specifically, confirm it actually resolves
  on the Gradle classpath with
  `./gradlew :app:dependencies --configuration debugRuntimeClasspath -q | grep <plugin>`
  rather than assuming pubspec resolution implies Gradle resolution.
- **Adding a trait-object field (`Arc<dyn Trait>`) to a struct that derives
  `#[derive(Debug)]` breaks the derive** with `the trait \`Debug\` is not
  implemented for \`(dyn Trait + 'static)\`` — common when threading a
  substrate/adapter handle into a core struct so a method can call back into
  it (e.g. re-kicking a stalled operation from a lifecycle hook).
  **If the trait's own module (or any concrete implementor) sits inside FRB's
  scanned input tree, do NOT reach for the "add `Debug` as a supertrait bound,
  derive it on every implementor" fix** — flutter_rust_bridge_codegen 2.13.0
  scans every struct in an FRB-input file regardless of whether it is actually
  bridged, and a bare `#[derive(Debug)]` on a **unit struct** among those
  implementors (`pub struct Torrents;`) panics codegen with `no entry found
  for key=MirStructIdent(...)` / "struct with unit fields are not supported
  yet" — a failure `cargo build` will never show you, since it's a separate
  tool with a separate, stricter scanner. In an FRB-scanned module the safe
  fix is a **hand-written `Debug` impl on the containing struct** that skips
  just the non-Debug trait-object field via `finish_non_exhaustive()`
  (mirror any existing example in the file, e.g. a sibling
  `DetailSources`-style impl) — leave the trait bound and every implementor
  untouched. Reserve the supertrait-bound approach for structs and traits
  that are genuinely outside FRB's `--rust-input` scan path; even there,
  double-check none of the implementors becomes a unit struct.
  Either way, **`cargo build` succeeding is not proof FRB codegen still
  works** — after any change (even one unrelated to the bridge API, like
  adding a derive) that touches a file inside FRB's scanned input tree,
  actually run the codegen (`tool/frb_build.sh --codegen-only --force-frb`,
  or the repo's equivalent) and confirm it exits 0 with the generated Dart
  diff you expect (empty, if nothing bridged changed) before trusting the
  build is healthy.
- **A background worker that only wakes on an event `Notify` (never on a timer) silently drops errors forever.** A common shape in this class of app: a reconciler loop does `tokio::select! { _ = shutdown.requested() => return, _ = wake.notified() => {} }` and processes durable work scanned from the store each wake. If the per-item operation can fail (e.g. publishing/hashing a locally-selected source through a native platform adapter — PhotoKit, SAF, etc. — which can hit a stalled network fetch, a revoked permission, or a transient read timeout), a bare `Err(error) => { log(...) }` with no retry and no status update leaves that item stuck in its "in progress" projected status **forever**: nothing ever wakes the worker again for it, because nothing changed. The person sees a permanently spinning state with zero feedback. The fix is the same shape used by this codebase's *other* durable worker (the receiver-side metadata resolver, `follow_torrent_imports`): track a `HashMap<key, failure_count>` and `HashMap<key, retry_deadline>`, add a third `tokio::select!` branch that races `sleep_until` the earliest deadline, filter pending work to what's actually due, and on error insert an exponential-backoff deadline (e.g. 5/15/30/60s ladder) *and* push a visible status onto the projection (reuse an existing "retrying" status if one already exists for the mirror-image worker rather than inventing a new one — the same label often reads correctly for both directions). Clear the failure/backoff entry on the next success. When two workers in the same codebase handle the two directions of the same class of operation (publish vs. resolve, upload vs. download), a retry/backoff/status pattern that exists on one side and not the other is very likely a bug on the side missing it, not an intentional asymmetry — check the sibling worker before assuming silence is fine.
- **Adding CI quality gates without first checking they pass locally.** Before
  adding `cargo audit` or `cargo deny` to the pipeline, run them locally on the
  current lockfile — they will likely surface existing issues (vulnerable
  dependencies, license mismatches, duplicate semver-incompatible versions)
  that must be resolved (version bumps, allow-lists, config) or the CI will
  fail. In this session, `cargo audit` found `time 0.3.45` (CVE-2026-0009),
  fixed by `cargo update -p time --precise 0.3.47`. `cargo deny check bans`
  surfaced ~18 duplicate semver-incompatible crates from transitive deps
  (base64, hashbrown, rand, thiserror, etc.) — addressed via an allow-list
  in `deny.toml` rather than trying to unify versions. `cargo deny check
  licenses` failed on our own crates (`backend`, `portalis-nexus-protocol`)
  lacking SPDX metadata — licenses check was disabled in CI config with a
  TODO comment. Only enable the subset that passes (`advisories`, `bans`,
  `sources`) until license metadata is added to all workspace crates.

- **A `tokio::spawn` called from inside an FRB-exposed function panics with "there is no reactor running, must be called from the context of a Tokio 1.x runtime" — and if that call sits inside a lock guarding the app's whole runtime handle, the panic poisons the lock and bricks every subsequent FRB call, not just the one that spawned.** flutter_rust_bridge invokes a plain (non-`async`) exported function from its own synchronous worker thread pool, which has no Tokio reactor attached — this is true even for a function that is otherwise perfectly ordinary, like a lifecycle hook (`set_active(bool)`) that decided to fire off a best-effort background task. The natural first fix — "fire-and-forget, `tokio::spawn` it so the caller doesn't have to await" — panics on every single invocation in production while passing every existing test, because `#[tokio::test]` always provides a working reactor and therefore can never reproduce this failure mode; a green test suite here proves nothing about the real constraint. Worse, if the spawn happens while holding a `std::sync::Mutex` that gates the single global runtime handle (`static RUNTIME: OnceLock<Mutex<Option<Core>>>`, locked by nearly every FRB call), the panic poisons that mutex — and if the lock accessor treats poisoning as fatal (`.lock().map_err(|_| "poisoned".to_owned())` instead of `.lock().unwrap_or_else(PoisonError::into_inner)`), the app is bricked for its entire remaining lifetime: every later call, including unrelated ones like a share/QR action, fails with the same "lock was poisoned" error until the user force-kills and relaunches. Fix both layers: (1) never call `tokio::spawn` directly from a function FRB can invoke synchronously — instead hold a `tokio::sync::Notify` field, call `notify.notify_one()` (which needs no runtime) from the sync entry point, and do the actual async work on an existing supervised background worker that already runs `tokio::select! { _ = shutdown.requested() => return, _ = notify.notified() => {} }` on the app's real runtime, mirroring however the app already wakes its other background reconcilers; (2) make every lock reachable from an FRB entry point recover from poisoning via `PoisonError::into_inner()` rather than surfacing poisoning as a permanent error, matching whatever convention the rest of the codebase already uses for its other locks — a panicked holder left the guarded data in whatever state it panicked in, not corrupted, so refusing to ever touch it again is strictly worse than recovering.

## Release build tuning (Rust profile + Android R8)

A Flutter+Rust bridge crate is easy to ship with Cargo's dev-grade release
defaults (no LTO, `codegen-units=16`, unstripped) and an Android build that
never shrinks/minifies, because neither omission produces a build failure —
only a bigger, slower artifact nobody notices until asked to look. See
[`references/release-build-tuning.md`](references/release-build-tuning.md) for
the verified `[profile.release]` settings (and why `panic = "abort"` is unsafe
here specifically because FRB's generated handler relies on unwind-based
panic catching), the `minifyEnabled`/`shrinkResources` + `proguard-rules.pro`
recipe, the specific R8 failure it causes (`Missing classes` on Play Core's
deferred-component classes that the Flutter engine references unconditionally)
and its fix, and the fat-APK-vs-`--split-per-abi`/`.aab` tradeoff for a crate
built for multiple Android ABIs.

## Reference

- `references/release-build-tuning.md` — Rust `[profile.release]` tuning safe
  for an FRB app, Android R8 minify/shrink setup and its Play Core
  `-dontwarn` fix, and the fat-APK ABI-bundling tradeoff.
- `references/generated-output-hygiene.md` — compact notes on formatting FRB
  output and reviewing generator diagnostics.
- `references/choosing-a-bridge-tier.md` — deciding whether new data belongs in
  the summary snapshot, a dedicated call, or its own stream; flat parent/child
  pairs; polling a call-tier value from a Flutter screen without
  `setState`-during-build.
- `references/generated-collection-types.md` — handling FRB typed collection
  fields and keeping repository test seams truthful after a DTO change.
- `references/platform-plugin-path-mocking.md` — testing code that writes into
  a plugin-reported directory (path_provider and similar) without a device,
  by mocking the plugin's platform interface to reproduce the exact
  not-yet-created-directory failure mode, and what to do when that fix isn't
  enough in the field.
- `references/reconciler-idempotency-vs-library-errors.md` — when a worker
  reconciler re-asserts stored intent every tick but the wrapped third-party
  library call isn't itself idempotent (bails on "already in that state"),
  flooding the diagnostics log; the state-check-first fix and how to test it
  against the real vendored library.
- `references/vendored-crate-feature-unification.md` — why adding a direct
  dependency on a crate the vendored library already pulls in can break the
  build with a mutually-exclusive-feature assertion, and the resolution order
  for repairing a vendored crate's public re-export surface.
