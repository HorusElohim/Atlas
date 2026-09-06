---
name: validated-refactoring
description: "Remove dead code; run gate; tests pass before commit."
trigger: "User asks to remove dead code or refactor with validation requirements."
---

# Validated Refactoring Workflow

A class-level skill for refactoring tasks where the user requires:
1. **Actual dead code removal** - not `#[allow(dead_code)]` or `#[allow(unused_imports)]` suppression
2. **Project-specific validation gate** - run the project's test script (e.g., `./tests/nexus.sh`) before committing
3. **Full test suite pass** - `cargo test` / equivalent must pass
4. **Project commit conventions** - emoji + conventional commits (🐛 fix, ✨ feat, 📚 docs, etc.)

## Core Principles

### Remove, Don't Suppress
- User explicitly rejects `#[allow(dead_code)]` and `#[allow(unused_imports)]` as solutions
- If code is truly unused, **delete it** - including the `#[allow(...)]` attributes
- Only retain `#[allow(dead_code)]` for test-only utilities that clippy falsely flags (and only when deletion would reduce test coverage of production paths)

### Validation Gate is Mandatory
- Identify the project's validation script (often `./tests/*.sh`, `make test`, `just test`, etc.)
- Run it **before** committing - user validates locally too
- Fix all failures before `git commit`

### Directory-Aware Commands
- Cargo commands must run from the crate root (e.g., `portalis/rust/backend/`, not repo root)
- `CARGO_BUILD_JOBS=2` for shared/limited hosts
- `cargo fmt --all` before check/test

## Baseline Before You Touch Anything

Capture and record the full gate state **before the first edit**: test counts, linter state, formatter state.

```
Rust:    226 passed · clippy 2 errors · fmt clean
Flutter: 130 passed · analyze clean
```

Without this you cannot distinguish "my change broke it" from "it was already red." When the gate then fails, confirm attribution by stashing your work and re-running:

```bash
git stash && <gate command>; git stash pop
```

If a failure reproduces on the untouched tree, say so explicitly rather than silently absorbing it. Pre-existing failures inside the area you are already touching are usually worth fixing in the same change — leaving a red gate behind means the next session cannot get a clean baseline either. Report final numbers as a delta against the recorded baseline (`226 → 228`), which is auditable in a way that a bare "all tests pass" is not.

## Freeze the Tree Before an Independent Review

If you dispatch a reviewer subagent (see the bundled `requesting-code-review`),
it will re-run `git diff` itself and read **whatever is on disk when it runs**,
not the diff you pasted into its prompt. Reviews run in the background for a
minute or two, and editing through that window produces a verdict describing a
tree that no longer exists.

Either `git add -A` before dispatching so the review target is a stable index,
or stop editing until the verdict returns.

When a verdict does come back, re-verify each finding against the current tree
before acting — and do it by reading the code, not by trusting your memory of
having fixed it:

- **Already fixed?** Say so explicitly, and cite the current source. Do not
  silently drop the finding; a reader cannot tell "stale" from "ignored."
- **Already fixed but untested?** This is the valuable case. A stale finding
  that names a real hazard you closed minutes earlier usually means the fix has
  **no regression test** — nothing had forced you to write one. Add the test and
  falsify it (below). A reviewer pointing at code you just fixed is still
  telling you something true about your test coverage.
- **Still live?** Fix it, then re-run the gate.

## Audit Every Transition Into an Executable State

When a refactor introduces a typed state machine where one state authorizes real
work (downloading, sending, publishing, charging), the guard on the *obvious*
entry point is not sufficient. Enumerate every command, handler, and migration
path that can write the executable state, and check each one.

The trap is a **generic action that predates the distinction** — a `PublishDraft`
or `Confirm` that was written when "draft" meant one thing, and now silently
promotes a state that requires a different, more specific authorization. It
type-checks, because the state is legal; it is just not the state the user asked
for. Grep for every construction site of the executable variant:

```bash
git grep -n 'ExecutableState\s*{'   # every place it is written
```

Then pin the refusal with a test, and falsify it by removing the guard.

## Falsify New Regression Tests

A test written alongside or after a fix never had a natural RED to observe — the code is already green. Prove it can fail before trusting it: revert only the fixed line, watch the test fail *with a message naming the behavior*, restore the fix.

```bash
cp src/module.rs /tmp/fixed.rs        # keep the good version
# revert ONLY the specific behavior the fix introduced
cargo test --lib my_new_test          # MUST fail, for the right reason
cp /tmp/fixed.rs src/module.rs        # restore
```

A vacuous test is worse than no test: it is a permanent false assurance a future session will trust. The usual cause is **asserting on a value something downstream recomputes or overlays** — the assertion reads correctly even when the thing under test is misconfigured. Ask "what is the earliest observable that only the fix controls?" and assert there.

### When falsification does NOT fail, you learned something — report it

The attempt itself can be vacuous. If you break a layer the test never
executes, the test stays green, and that green looks exactly like "the test is
fine" while actually meaning "the test never covered that layer".

Observed: a test asserting per-peer transfer rates stayed green after the
adapter mapping the upstream library's fields into those structs was inverted —
because the test constructed the structs directly and never ran the adapter.
The arithmetic was pinned; the field mapping was not.

The seam most often uncovered this way is the **thin adapter between a
third-party library and your own domain type**: unit tests build the domain
type by hand, so nothing exercises the translation. That code is invisible to
the suite and only a live run or hand-inspection can confirm it.

So when the test does not go red:

1. Do **not** record it as a successful falsification.
2. Identify which layer the test actually runs versus the one you broke.
3. Extend coverage, or **state plainly in the final report which seam is
   unverified and how you checked it instead** (read against the vendored
   source, live run). An untested seam reported as tested is the same false
   assurance a vacuous test creates — just moved into your summary.

## Before Fixing a "Broken" UI, Find Its Data Source

A screen that renders nothing is not necessarily a rendering bug. Trace the
value backwards to where it is *produced* before touching how it is *displayed*
— the fault is frequently that nothing ever writes the data.

Observed: a "people" screen was reported as displaying incorrectly. The widget
was correct; the projection hardcoded `contacts: Vec::new()` at every
construction site, the store's writer was never called outside tests, and the
command that should have populated it fell through a catch-all
`_ => Ok(None)` arm in the dispatcher. Nothing could ever have appeared.

Cheap checks that separate "renders wrong" from "has no data":

```bash
git grep -n 'field: Vec::new()'      # hardcoded-empty at construction
git grep -n 'fn put_thing\|write_thing'   # is the writer called outside tests?
git grep -n '_ => Ok(None)'          # commands silently swallowed by a catch-all
```

Report the distinction to the user explicitly — "the screen renders correctly,
it has no data source" is a different bug with a different fix and a different
cost, and they may want to scope it differently. Ask before building the
missing pipeline.

Adjacent to this: when data *is* being discarded, check whether the upstream
library already carries the richer value. A call like
`snapshot.peers.into_keys()` throws away everything except the map key; the
per-item stats were there all along. Read the vendored source of the type you
are collecting from before concluding a field is unavailable.

**A "shows 0" bug is often an undercounted data source, not a broken one.**
A User-page stat reading "0 PEOPLE" wasn't a rendering bug — it summed only
one of two live tiers the app already tracked (signed contacts), when the
adjacent People screen counted contacts *and* anonymous swarm connections.
Most users only ever have the second tier, so the count read as 0 for the
common case even though the code was "correct" for what it summed. When a
count/stat looks wrong, find every screen that renders a semantically
similar number and diff what each one actually includes before assuming the
displayed value's formula needs no change.

## Consolidating Near-Duplicate Per-Feature State

When a screen accumulates one boolean + one near-identical open/build method
per drill-down destination (e.g. `_showStorage`/`_openStorage`,
`_showDiagnostics`/`_openDiagnostics`, `_showFormats`/`_openFormats` — three
copies of the same `openNestedScreen(embedded:, showInPlace:, push:)` shape
differing only in which screen they build), this is a mechanical
consolidation, not a design decision to hold a long discussion over:

1. Replace the N booleans with one enum (`enum _Nested { storage,
   diagnostics, formats }`) and a nullable field holding it.
2. Give the enum a `build({required bool embedded, VoidCallback? onBack})`
   method with one `switch (this)` dispatching to each screen's constructor.
3. Collapse the N near-identical `_open*()` methods into one `_open(_Nested
   nested)` taking the enum value.
4. Collapse the N `if (_showX) return XScreen(...)` blocks in `build()` into
   one `if (nested != null) return nested.build(...)`.

This is safe to do without a design review because it changes zero runtime
behavior — same widgets, same navigation, same embedded/pushed branching —
only the state shape and dispatch mechanism shrink. Verify with the existing
gate (`flutter analyze` + the screen's widget tests); a net line reduction
(e.g. -69 lines with identical test results) is the expected signal that the
consolidation was purely mechanical.

## Consolidating Duplicated Settings-Row Widgets

When a settings-style screen has several call sites building the same small
widget shape with only text/callback differing — e.g. N
`Padding(EdgeInsets.fromLTRB(kScreenGutter, top, kScreenGutter, 0),
child: DestinationRow(icon:, title:, subtitle:, onTap:))` blocks, or N
`ValueRow(label:, value:, onTap: () async { final raw = await _edit(...); if
(raw == null) return; await _apply(s.copyWith(field: parse(raw))); })` blocks
for different numeric engine settings — this is the same class of mechanical
consolidation as the drill-down-enum and polling-timer cases above, just for
row-widget construction instead of state/navigation. The trigger is 3+ call
sites repeating the identical wrapper/callback shape, not a single row.

Extract one private helper method per repeated shape:

```dart
Widget _numericRow({
  required String label,
  required String value,
  String? subtitle,
  required String title,
  required int? current,
  required String hint,
  required String helper,
  required ValueChanged<int?> onChanged,
}) => ValueRow(
      label: label, value: value, subtitle: subtitle,
      onTap: () async {
        final raw = await _edit(title: title, current: current?.toString(),
            hint: hint, helper: helper, keyboard: TextInputType.number);
        if (raw == null) return;
        onChanged(raw.isEmpty ? null : _parseInt(raw));
      },
    );
```

Each call site keeps its own label/value/hint/helper text and which
`copyWith(field:)` to call — only the boilerplate (dialog wiring, parse,
null-guard) moves into the helper. This is safe without a design review for
the same reason as the enum/timer cases: zero behavior change, same widgets,
same save path — verify with a widget test that actually drives the flow
(tap the row, `enterText`, tap Save, assert the underlying settings object
changed) rather than trusting that "it compiles" proves the refactor is
behavior-preserving. A net line reduction with an unchanged (or now-larger,
from the new test) pass count is the expected signal.

## Consolidating Duplicated Polling Timers

When several `StatefulWidget`s each hand-roll the same "refresh every N
seconds while mounted" shape — a `Timer? _poll` field, `Timer.periodic(...)`
started in `initState`, `_poll?.cancel()` in `dispose` — this is the same
class of mechanical duplication as the drill-down-enum case above, just for
timers instead of navigation state. Four screens (Storage, Diagnostics, a
User/profile summary, a People/contacts list) independently repeating this
nine-line shape is the trigger, not a one-off timer in a single screen.

Extract a mixin rather than a base class (Flutter screens already extend
`State<T>`, so a base class would force a rewrite; a `mixin PollingState<T
extends StatefulWidget> on State<T>` bolts onto any existing `State`
subclass unchanged):

```dart
mixin PollingState<T extends StatefulWidget> on State<T> {
  Timer? _pollTimer;
  Duration get pollInterval => const Duration(seconds: 2);
  void onPoll(); // implemented by each screen

  void startPolling() {
    onPoll();
    _pollTimer = Timer.periodic(pollInterval, (_) => onPoll());
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
```

Each call site keeps its own `onPoll()` body (which may itself call two
independent async loaders — see the IndexedStack pitfall above about
reloading *all* of them, not just the first) and replaces its manual timer
with `startPolling()` in `initState`. A screen with an *additional* listener
(e.g. also reacting to a change-notifier) keeps that listener registration
separate — the mixin only owns the timer, not every refresh trigger.

Write a small standalone test for the mixin itself (a probe `StatefulWidget`
with the mixin, driving `tester.pump(duration)` to assert it fires
immediately, fires on every tick, and — the one that actually matters —
stops firing and throws nothing once the widget is unmounted). This is
cheaper than re-verifying timer behavior separately in every screen that
adopts the mixin, and it is the one property (no post-dispose `setState`)
that a screen-level widget test is unlikely to exercise on its own.

## Instrumenting a Shared Primitive Instead of Every Call Site

When asked to "make sure logging/diagnostics/telemetry is wired up everywhere
it should be," resist the urge to walk every call site and add a line to
each. Grep for the *shape* of the gap first — e.g. every error-severity
toast/notification call (`grep -rn 'severity: ...Error'`) — and check whether
they all funnel through one shared function. If they do, the fix belongs in
that one function, not at each of the N call sites.

Observed: a user reported a diagnostics log full of noise and asked "can you
be sure we have all the logs where they should be." Auditing surfaced that
uncaught crashes already reached the shareable diagnostics log
(`FlutterError.onError`/`PlatformDispatcher.onError`), but ~15 *caught*
errors shown via an error-severity toast across three feature areas were
shown for a few seconds and then gone — never recorded. Editing 15
`catch (e) { showToast(..., severity: ToastSeverity.error) }` blocks would
have been the literal reading of "make sure every error is logged", but the
actual fix was one hook (`onErrorToast`) called once inside the shared
`showToast()` function itself and wired once in the app's bootstrap — zero
call sites touched, and no future call site can forget it either. This is
the same principle as consolidating duplicated widgets/timers below, applied
to cross-cutting instrumentation instead of duplicated code: find the one
choke point every instance already passes through, and modify it once.

Verify with a test on the shared primitive itself (does calling it with the
relevant flag invoke the hook? does calling it *without* the flag not
invoke it? is an unset hook a no-op rather than a crash?) rather than
spot-checking a handful of call sites — the whole point is that the call
sites don't matter anymore.

## Third-Party Dependency and Platform-Target Fixes

When a platform build fails inside a third-party crate, do not patch the application first. Reproduce the exact target, compare a clean upstream release with the customized fork, and bisect the fork commits with a persistent, fail-fast harness. Treat a failed checkout or missing revision as an invalid test result; never summarize the command as having tested that revision.

For conditional-compilation failures, inspect the dependency source and enumerate the target families explicitly. macOS and iOS are both Darwin but are distinct Rust `target_os` values; if they share an implementation, express that with `cfg(any(target_os = "macos", target_os = "ios"))`, and exclude both from generic Unix code when the API is not available on either target. Validate the host target and, when the Apple SDK is unavailable, use the strongest available cross-target check while clearly reserving final compilation for a Mac with `xcrun`.

Prefer the upstream/fork-first sequence:

1. Prepare the smallest dependency fix and an upstream PR.
2. Integrate it into the maintained fork using an immutable revision.
3. Verify the fork itself with `cargo check --locked` and its focused tests.
4. Update the downstream application lockfile only after the fork merge.
5. Run the application checks and commit only the dependency and lockfile changes.

Cargo `[patch.crates-io]` entries are root-manifest scoped and do not propagate through a dependency consumed by another project. If an application consumes a forked workspace, make the workspace dependency itself point to the fixed source where possible. If external transitive crates still request the published package, add a temporary application-root patch pinned to the same immutable revision and use `cargo tree -i` to verify that registry and git instances have been unified; duplicate versions of a crate containing shared Rust types can produce type mismatches.

Keep the dependency migration separate from unrelated optimization or feature work. Confirm the lockfile’s exact git revisions, run `git diff --check`, and report whether the final platform build was verified locally or remains Mac/device-only.

## Workflow Steps

1. **Inventory dead code**: `git grep -n 'allow(dead_code)\|unused_import'` + usage search
2. **Determine fate**: delete if truly dead, keep with `#[allow(dead_code)]` only if test-only utility
3. **Remove code + attributes**: delete the items AND their `#[allow(...)]` markers
4. **Run validation**: `./tests/nexus.sh` (or project equivalent)
5. **Run full test suite**: `cargo test --workspace` / equivalent
6. **Format**: `cargo fmt --all` (and `dart format .` if Flutter)
7. **Commit**: emoji + type + short message
8. **Choose commit scope before staging**: keep a requested narrow UI refinement in its existing commit only when it remains that same change. If investigation or implementation expands it into a separate capability (for example durable backend storage, a schema migration, bridge API, and new projections), create a new conventional feature commit. Do not amend or force-push merely because the files overlap.
9. **Push**: fetch and rebase on origin first — then push, unless the user has explicitly directed a normal push without rebasing. Do not stop at "committed, shall I push?" when the user expects landed work. If `git fetch` shows upstream has not moved, no rebase is needed and the verification you already ran still holds; say that rather than re-running the whole gate.

## Pitfalls

- **Don't assume** `cargo check` from repo root works - find the `Cargo.toml`
- **Don't suppress** with `#[allow(...)]` unless user explicitly accepts it for test-only code
- **Don't skip** the validation script - user runs it locally and will catch failures
- **Don't forget** FRB regeneration for Flutter/Rust projects after API changes
- **A patch that "succeeds" can still mangle the file.** Replacing a single
  line that is also a natural anchor (a lone `## Heading`, a bare function
  signature) can join it to the following line. The tool reports success; the
  linter reports a pre-existing-looking error. When a patch result looks
  structurally odd, re-read the region immediately and repair by rewriting the
  enclosing block — do not stack another single-line patch on top of a mangled
  one. Prefer anchoring on 2-3 lines of surrounding context.
- **Verify the language level before using modern syntax in tests.** Digit
  separators (`1_048_576`) and similar niceties fail to compile on older Dart
  SDKs with an `--enable-experiment` hint. Match the style already present in
  the file rather than assuming the newest syntax is available.
- **A widget inside an `IndexedStack` (or any always-mounted tab layout) runs
  `initState` before a test's `debugSeed`/data injection has a chance to
  run**, because every tab mounts immediately even though only one is
  visible. A single async load fired from `initState` silently returns
  stale/empty data with no error. Fix: register a listener on the data
  source (e.g. `AppControllers.engine.addListener(...)`) that retries the
  load on every subsequent change — and if the screen loads *multiple*
  independent async values (a summary AND a count, for example), the retry
  callback must reload **all** of them, not just the one already guarded by
  a null-check; a retry that only re-fires the first load leaves the second
  stuck at its `initState`-time (likely wrong) value forever.
- **When adding a new durable write inside an existing frequent poll loop
  (a transfer poller, a health-check tick, anything on a sub-second
  interval), check whether the codebase already has a "write only if
  changed" convention nearby before writing unconditionally.** A fix that
  makes some piece of state durable (e.g. persisting a live peer connection
  so it survives a disconnect) is easy to write as "snapshot it every
  tick" — correct, but it turns one write-per-mover into one write per
  *known* item per tick forever, including fully idle ones. If a sibling
  function already skips the write when the new value equals the last
  written one (grep for the pattern used by the existing sample/history
  writer), mirror that same before/after comparison for the new write
  rather than introducing a second, more expensive persistence style in
  the same module. Keep the "write once unconditionally" case for a
  genuinely new item (first-seen-at this tick) so something that appears
  and disappears within a single tick is still captured — the point is to
  skip *repeats* of unchanged state, not to skip first observations.
- **A Gradle `signingConfig storeFile` path is relative to the app module
  directory (`android/app/`), not the project root (`android/`) — even when
  the properties file that names it was loaded via `rootProject.file(...)`.**
  Writing `storeFile=app/portalis-release.jks` in `key.properties` (mirroring
  where the root-relative properties file itself lives) makes Gradle look for
  `android/app/app/portalis-release.jks` and fail
  `validateSigningRelease` after a full multi-ABI Rust rebuild has already
  run — expensive to discover late. Put the keystore in `android/app/` and
  reference it as a bare filename (`storeFile=portalis-release.jks`); only
  the properties-file *lookup* (`rootProject.file("key.properties")`) is
  root-relative, the `storeFile` value inside it is module-relative.

- **A regression test built by mocking the platform dependency the bug lives
  in can validate a fix that only holds against the mock, not the real
  platform.** A share flow failed with `PathNotFoundException` because
  `getTemporaryDirectory()`'s path didn't exist on disk. The first fix
  (`dir.create(recursive: true)` before writing) was proven with a RED
  test that mocked `PathProviderPlatform` to return a nonexistent
  directory, reproduced the exact error, then went GREEN after the fix —
  every signal said "done." It shipped, and the user reported the *same*
  error still happening on their real device. The mock exercised the
  Dart-side logic correctly but couldn't reproduce whatever the real
  platform plugin was actually doing, so the RED/GREEN cycle validated a
  hypothesis about the failure, not the failure itself. The eventual real
  fix removed the dependency on the flaky platform call entirely — the
  file already existed at a path the app already knew and displayed on
  screen, so sharing it directly (no copy, no temp directory) sidestepped
  the unreliable API rather than trying to make it reliable. **When a bug
  report cites unpredictable platform/OS behavior (temp dirs, file
  pickers, share sheets, permissions), prefer removing the dependency on
  that behavior over hardening a workaround for it — and if you must fix
  it in place, treat a mock-validated GREEN as provisional until the user
  confirms on the real device, not as proof.**
- **A reconciler that asserts stored intent on every poll tick ("should
  this be paused/running/selected right now") needs every call it makes
  to be genuinely idempotent — check the underlying library, don't assume
  it.** A torrent-pause reconciler called `session.pause()`/`unpause()`
  every ~500ms regardless of whether the last tick already applied that
  state. The library treated "already paused" / "already live" as an
  *error* to report, not a no-op — so every already-settled torrent
  logged a fresh failure on every single tick, forever, flooding
  diagnostics with noise that buried real problems. The fix checks
  current state before calling (`if handle.is_paused() { return Ok(()) }`)
  rather than trying to suppress or rate-limit the resulting log lines.
  When you find (or write) a reconciler that re-asserts intent on a fast
  timer, grep for what happens when the target is already in the desired
  state — if the answer is "an error", the reconciler will silently log-spam
  forever once anything reaches steady state, which is easy to miss in
  short-lived local testing but guaranteed in a long-running session.

## Project-Specific Notes (PortalisApp)

- Validation: `./tests/nexus.sh` (runs from repo root, enforces `-D warnings`)
- Cargo dir: `portalis/rust/backend/`
- Commit style: `🐛 fix: ...`, `✨ feat: ...`, `📚 docs: ...`
- FRB regen: `./tool/frb_build.sh` after Rust API changes
- Version bumps: `pubspec.yaml` + `Cargo.toml` + `CHANGELOG.md` — and
  `lib/version.dart`'s `portalisVersion`/`expectedBackendVersion` constants,
  which are a separate source from `pubspec.yaml` and are easy to leave
  stale after a rushed bump (see `distributed-backend-trust` for the full
  version-lockstep discipline).
- Reusable timer-polling mixin already exists at `lib/design/polling.dart`
  (`PollingState`) — reach for it instead of hand-rolling another
  `Timer? _poll` field in a new screen; see "Consolidating Duplicated
  Polling Timers" above.
- Settings screen (`lib/features/settings/presentation/screen.dart`) has
  `_destination()` and `_numericRow()` private helpers for gutter-padded
  destination rows and numeric engine-setting rows respectively — reuse
  them for any new Settings row rather than hand-rolling the
  `Padding(DestinationRow(...))` or `ValueRow` + `_edit()` + parse pattern
  again; see "Consolidating Duplicated Settings-Row Widgets" above.