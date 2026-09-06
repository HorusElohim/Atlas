---
name: architecture-decision-records
description: "Use when implementing or governing ADR-driven architecture."
version: 1.1.0
---

# Architecture Decision Records

## Purpose

Use this skill when a repository treats Architecture Decision Records (ADRs) as
its durable architectural history and the codebase as the current-state map.
It governs creating, implementing, accepting, superseding, and cleaning up
architecture decisions without turning documentation back into a mutable second
source of truth.

## Core model

- **Code is the current-state map.** Inspect the working tree before making
  claims about an implementation.
- **ADRs are frozen history.** Do not rewrite old ADR text to match a later
  refactor; supersede it with a new ADR when the decision changes.
- **The ADR index is the entry point.** Keep its number, title, status, and
  supersession data accurate under the repository's status convention.
- **One architectural decision, one atomic implementation.** Keep structural,
  bridge, generated-binding, test, and changelog changes together when they are
  one behavior change.

## Implementing an ADR

1. Fetch `origin/main`, branch from it, and read both the ADR and its index
   entry before changing code.
2. Translate each Decision and Consequence bullet into verifiable repository
   acceptance criteria. Inspect the actual implementation and test paths; do
   not rely on ADR prose as evidence that work landed.
3. Write the acceptance evidence into the ADR itself, not just into your own
   summary to the user. Add an "Acceptance verification" section listing each
   Consequence bullet next to the specific test name that proves it. This is
   what turns "I believe this works" into a durable, checkable artifact — a
   later session (or the user) can re-run the cited test instead of trusting
   the ADR's prose. Only flip status from `proposed` to `accepted` once every
   bullet has a cited passing test; a bullet with no test is a signal the
   feature isn't actually done, not a documentation gap to paper over.
3. Preserve stable public boundaries. For a bridge refactor, trace generated
   types, application seams, widget consumers, and tests before deleting a
   wrapper or renaming an import.
4. Prefer one explicit test seam over several pass-through interfaces. A
   gateway/facade may expose tiered streams and commands; “one seam” does not
   require collapsing materially different data rates into one oversized
   snapshot.
5. Delete obsolete implementation and documentation in the same change. Do not
   leave compatibility paths, stale mirrors, or dead documents merely to retain
   history.
6. Add/update focused tests first when behavior changes. Run the smallest
   affected suite, then the repository gate before committing.

## Real session pattern: ADR-0016/0017 implementation

**Phase 1 — Discovery & RED tests:**
- Traced `Event::TransferSettled` variant already defined but unused in `events.rs`
- Found the single legitimate completion site: `follow_transfers` in `transfers.rs` where `completed_download` is computed
- Wrote RED test `a_completed_transfer_emits_a_typed_settled_event` subscribing to bus before spawning poller, asserting `TransferSettled{ok:true}` fires
- **Verified RED→GREEN explicitly**: temporarily removed `bus.emit` call → test failed; restored → test passed

**Phase 2 — Implementation with vertical slices:**
- Added `Supervisor::bus_arc()` accessor (since `bus()` returned `&EventBus`, not `Arc<EventBus>`)
- Wired `bus_arc()` through `nexus.rs` call sites and tests
- Added `Nexus::events_bus()` (fixed mutex-guard-across-await bug by cloning `Arc<EventBus>` synchronously before `.await`)
- Added bridge: `AppTransferCompleted` DTO + `watch_transfer_completions()` in `portalis_api.rs`
- Regenerated FRB bindings twice (`./tool/frb_build.sh --codegen-only --force-frb --ai`)
- Full backend suite: 286/286 passing, no regressions

**Phase 3 — Flutter migration (one behavior at a time):**
- Added `watchTransferCompletions()` to `AppRepository` interface
- Rewrote `TransferCompletionNotifier` (49 lines) replacing snapshot-diffing with stream consumption
- Updated `AppController.start()/stop()` to use typed stream
- Updated fake repositories in two test files
- `flutter analyze` passed at each step

**Phase 4 — Command envelope refactor (ADR-0017):**
- Deleted generic `EngineCommand{kind: String, ...}` envelope in Rust and Dart
- Added typed `AppCommand` enum (one variant per operation)
- Migrated all Flutter call sites to specific methods (`importTorrent`, `setCollectionPaused`, etc.)
- Removed hand-written `EngineCommand` Dart class entirely
- Fixed `dart format` drift (6→8 unrelated files each time, reverted via `git checkout --`)

**Phase 5 — Projection consolidation (ADR-0017):**
- Identified `nexus/projection/build.rs` as duplicate/parallel projector serving only its own tests — deleted it
- Consolidated all status/entries/byte logic onto canonical `StatusFacts` in `state.rs`
- Fixed cascade of test failures by referencing prior code via `git show b092746:...`
- Added restart-matrix test `a_reopened_owner_collection_with_a_missing_zero_copy_source_hydrates_as_unavailable` → exposed real bug (local sources didn't check file existence) → fixed via `ContentLocation`

**Phase 6 — Acceptance verification in ADR docs:**
- Updated `doc/adr/0016-rust-owned-app-contract.md` and `0017-canonical-production-projection.md`
- Changed status `proposed` → `accepted`
- Checked off each Consequence bullet with cited passing test names
- Updated `CHANGELOG.md` with summary entry

**Phase 7 — Final gate + atomic commit:**
- Backend: `cargo fmt --check`, `cargo clippy --lib --tests -- -D warnings`, `cargo test --lib --test-threads=4` — 275/275 passed (intentional drop from 286 due to deleted `build.rs` tests)
- Flutter: `dart format --set-exit-if-changed lib test`, `flutter analyze`, `flutter test` — 180/180 passed
- Committed and pushed atomically

This vertical-slice approach (one behavior → test → implement → gate → commit) proved far more reliable than horizontal "all tests then all code" and caught real bugs at each unification point.

## Retiring a living specification or plan

When an ADR replaces a central mutable specification with frozen ADRs:

1. Delete the live central design, migration-plan, and explicitly contradicted
   narrative documents named by the decision.
2. Replace every **active** README, source-comment, script, manifest, and doc
   reference with either code-local explanation or the ADR index.
3. Keep historical references in frozen ADRs intact. They record the decision
   context at the time it was made, even if their former paths are gone.
4. Preserve focused feature acceptance notes unless they actually recreate a
   central architecture specification.
5. Search for all retired document names after editing. The only remaining
   references should be intentional frozen-history mentions.

## Flutter/Rust bridge refactors

For a generated Flutter-Rust bridge:

- Use generated bridge DTOs directly as the application data types where they
  already express the backend contract.
- Avoid hand-written field-for-field DTO mirrors and command envelopes.
- A small factory that returns the generated command DTO is acceptable when it
  only supplies mandatory empty fields or converts an input into the generated
  typed buffer; it must not create a second domain model.
- Preserve deliberately tiered contracts such as summary snapshots, selected
  detail streams, and append-only history streams. Packing detail/history into
  every snapshot trades a few wrappers for persistent bridge and memory cost.
- Regenerate bindings whenever a bridged Rust signature or DTO changes, and
  review generated diffs as part of the same atomic change.

### Authority-preserving correction guardrail

Before fixing a stale value, performance issue, unbounded list, or duplicated
state in Flutter, trace the value to its authority first.

- If Rust already owns the count/history/lifecycle/capability, Flutter must
  render the generated fact; do not add a Flutter cache, cap, aggregate, or
  second lifecycle rule. Displaying a Rust DTO field and pluralizing its label
  is presentation, not domain ownership.
- If the generated contract lacks a fact the interface needs, add and test that
  fact in the Rust production projection before changing widgets.
- Retention bounds belong beside backend persistence/measurement. A Dart list
  that merely decodes a bounded Rust stream is not the place to invent another
  retention policy.
- Lifecycle edges such as completion, deduplication, share readiness, and
  command validity belong in typed Rust state/events/commands. Flutter may
  deliver notifications or navigate after a result, but must not become the
  authority.
- Preserve architectural invariants while refactoring: native media stays
  zero-copy, and required HTTPS/UPnP/P2P paths are fixed rather than disabled.
- Test the production constructor/path. Delete isolated builders whose tests can
  pass without exercising the code that ships.
- **Concrete pattern to grep for:** a presentation-layer getter that recomputes
  a count/flag from a *lazily-populated* sub-object (`x.length`, `.isNotEmpty`,
  a detail/child collection) instead of reading the already-present summary
  field for the same fact. This is the single most common form of the
  violation, and it reproduces as "shows 0 / empty / false everywhere" because
  the lazy sub-object is unpopulated in exactly the view (a list row, a
  collapsed card) that never triggered its population. Real example: a
  collection-row subtitle read `media.length` (built only from a subscribed
  detail stream, empty for every list row by design) instead of the sibling
  `entryCount` getter that read the summary snapshot's own authoritative count
  — producing the exact "0 items always" symptom the user reported. The fix is
  a one-line getter swap; the value of tracing it through this guardrail is
  recognizing the *shape* of the bug (wrong-source count, not wrong-value
  count) instead of guessing at off-by-one or serialization causes. When fixing
  this class of bug, write the regression test as: construct the object with a
  populated summary field and an *empty* lazy sub-object (exactly the list-row
  shape), assert the presentation value matches the summary field — then prove
  it by temporarily reverting the fix and confirming the test fails with the
  reported symptom verbatim, not just "fails".

### When a test fails after a typed-contract/refactor migration

A widget/controller test failing right after replacing a string contract with
a generated typed one (or any similar mechanical migration) is very often the
harness asserting a **stale literal** — an old placeholder label, an old enum
spelling, an old wire word — not a real behavioral regression. Distinguish the
two before touching any production code:

- Read the failure message literally: `Found 0 widgets with text "X"` after a
  fixture's status/lifecycle value changed almost always means the fixture
  now legitimately produces a *different*, equally-correct label (e.g.
  `'Preparing'` → `'ResolvingMetadata'` renders `'RESOLVING METADATA'`, not
  `'PREPARING'`). Update the one assertion to the new correct value.
- Do **not** reimplement, rewrite, or add fallback branches to the widget/
  controller just to make an old literal pass again — that is solving a
  problem that does not exist and adds a second code path nobody asked for.
- Minimal-diff is a first-class constraint on this class of task, not merely
  a style nicety: prefer the smallest change that makes the *real* contract
  hold (usually one assertion or one fixture value), and treat any urge to
  "reimplement while I'm in here" as a signal to stop and re-check whether
  the failure is actually a regression at all.

### Turning a broad audit into an ADR program

For a multi-priority architecture program:

1. Create one proposed ADR per coherent workstream, with explicit acceptance
   verification checkboxes. Supersede old decisions in the index; do not rewrite
   their frozen files.
2. Commit and push the ADR set before production edits, so later sessions have a
   durable roadmap.
3. Implement in priority order. Keep one implementation commit per agreed
   priority batch when the owner requests aggregated history.
4. Use RED/GREEN focused tests while developing each slice, but defer expensive
   full-platform gates to the end of the priority batch. Never defer the small
   regression test that proves the current slice.
5. Keep completed slices uncommitted or in clearly separate local commits until
   the agreed aggregate commit is ready; do not claim an ADR `accepted` early.
6. At the batch gate, cite the exact passing tests in every completed ADR,
   update changelog/version/generated bindings as applicable, run aggregate
   verification, then commit and push atomically.
7. **Commit granularity is the owner's call, and it can change mid-program.**
   Default to one commit per agreed batch, but if the owner says something like
   "each ADR you can push" (even after previously agreeing to batch), switch to
   one commit per completed ADR immediately — do not keep batching out of
   inertia. Re-confirm gate scope with them if it's ambiguous which they mean
   for future slices, but the most recent explicit instruction wins.
8. **Working on ADR N+1 while ADR N's implementation is still uncommitted (or
   unverifiable) is fine — keep them physically separated in the working tree.**
   If one ADR's code cannot be verified yet (missing SDK/toolchain on this host,
   waiting on a longer test) but you want to continue to the next ADR, `git
   stash push -m "<label>" -- <paths>` the unverified files before committing
   and pushing the next ADR's work, then `git stash pop` immediately after the
   push. This keeps every pushed commit's diff scoped to exactly what it claims,
   without losing the in-progress work or blocking the rest of the program on
   one unverifiable slice.
9. **A hand-rolled network allow/deny address policy (SSRF checks, IP range
   validation) is not "done" after one review pass — budget for several.** Real
   case: three independent reviewers of the same public-unicast IP policy each
   found a genuinely new gap in turn (a missing CIDR block, then NAT64/RFC 6052
   addresses embedding a private IPv4 in their low 32 bits, then the deprecated
   IPv4-compatible `::a.b.c.d` form and the RFC 6666 discard prefix). Enumerate
   against the IANA special-purpose address registries rather than memory of
   "the usual ranges", explicitly test every address-embedding form an attacker
   could use to smuggle a blocked destination past the check (IPv4-mapped,
   IPv4-compatible, NAT64/6to4/Teredo), and keep re-reviewing until two
   consecutive rounds add nothing new — not just until the first one passes.

10. **Unifying several independent inline constructions of the same derived
    state behind one shared function is exactly the kind of change that
    surfaces real, previously-silent divergence bugs — expect that, and treat
    each one as a required regression test, not a surprise to work around.**
    Real case: four call sites (startup hydration, `create_collection`,
    `import_torrent`, a live-update refresh) each built a collection's status
    facts via their own inline struct literal; collapsing them into one
    `StatusFacts::from_stored` constructor immediately exposed that one worker
    (`torrents::republish`) was unconditionally overwriting a *different*
    collection kind's (native, non-torrent) live entry count/byte total with
    empty torrent-import data whenever it happened to share a substrate
    handle — a bug invisible before unification because every call site
    silently trusted its own narrow view. When a unification pass makes an
    existing test fail this way, do not "fix the test to match current
    behavior" — the failure is the unification doing its job. Add a guard
    (e.g. an explicit source-kind check before applying torrent-specific
    metadata) and a dedicated regression test asserting the previously-wrong
    field stays correct through the shared path, then move on: one unification
    pass commonly surfaces more than one such bug, so budget for a couple of
    these before the pass is actually done, the same way §9 budgets for
    several address-policy review rounds.

## Persisted observation and aggregate tiers

When an ADR introduces history for live connection/telemetry data, decide the
observation semantics before choosing a table or bridge shape:

1. **Name the authority and boundaries.** Keep measurement, persistence,
   deduplication, and aggregation in the backend. The frontend receives
   already-computed records and renders them; it must not reconstruct history
   from screen lifetime or sum snapshots on its own.
2. **Separate live state from durable history.** Current rates and connections
   belong in a fast selected-detail tier. Durable history is an on-demand,
   lower-rate tier. Do not append historical records to a universal snapshot or
   a high-frequency detail stream merely because one screen displays both.
3. **Persist at semantic lifecycle boundaries.** Choose deliberate facts such
   as confirmed completion or graceful shutdown when those are what the product
   means by a snapshot. Do not write once per poll by default. State plainly
   which termination paths cannot guarantee a flush.

   Sometimes correctness genuinely requires evaluating at poll cadence — e.g.
   an entity (a peer connection) can appear and disappear entirely between two
   lifecycle boundaries, so waiting for completion/shutdown to snapshot it
   loses it. When that happens, keep the *evaluation* at poll cadence but gate
   the *write* on an actual value change (compare a before/after tuple of the
   fields that matter; skip the write when they're equal), exactly like the
   existing before/after sample-ring write-skip. Otherwise "snapshot every
   tick to not lose transient entities" silently turns into "one durable write
   per known entity per poll interval forever," even while the entity is
   completely idle — a real regression that surfaces only under load, not in
   the correctness test that proved the retention fix worked. Write a
   dedicated regression test for the idle case (N ticks with no change → no
   additional writes) alongside the one proving the entity is retained; the
   retention test alone does not catch the write-amplification defect.
4. **Make cumulative counters mathematically safe.** If an engine exposes
   session-scoped counters but the product requires totals across restarts,
   persist a backend runtime epoch plus raw-counter checkpoint. In the same
   epoch, add only the positive unsaved delta; in a new epoch, add the complete
   new raw counter. Treat a counter decrease within one epoch as a new
   connection segment. Test all three cases so repeated snapshots never double
   count.
5. **Aggregate only after selecting one value per source.** For a People-style
   view spanning collections, first choose each collection/endpoint's effective
   stored-or-live value in the backend, then sum those values by exact endpoint.
   This avoids double-counting an active connection already represented by a
   stored checkpoint.
6. **Do not turn endpoints into identities.** An address and a client string
   are observations, not verified people. Scope durable aggregates to the
   exact endpoint and collection; group exact endpoints for a display only
   when that product tradeoff is explicit.
7. **Bound retention and delete with the owner.** Cap per-owner observation
   rows and remove them atomically when the owning collection is explicitly
   deleted. Do not erase them merely because files are removed or a live engine
   session is released.

## Verification

Before commit, verify all of the following that apply:

```sh
# Documentation retirement
# Search for retired document names and inspect every surviving hit.

# Flutter application changes
flutter analyze
flutter test <focused tests>
flutter test

# Rust/backend changes
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-targets --all-features
./tests/nexus.sh
```

Record skipped target-specific checks honestly. A missing SDK or cross compiler
is not proof a platform build passes.

## Pitfalls

- Treating an ADR as a living implementation document and editing it after the
  fact.
- Deleting an ADR's historical path mentions along with the retired files.
- Replacing several low-rate, on-demand streams with one universal snapshot.
- Calling a reference-holding view a deep copy without inspecting its fields.
- Renaming a pass-through seam without updating its test fake and focused
  controller tests in the same change.
- Claiming cross-platform compilation passed when the host stopped earlier for
  a missing SDK or compiler.
