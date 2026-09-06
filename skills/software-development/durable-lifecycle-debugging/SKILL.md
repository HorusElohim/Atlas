---
name: durable-lifecycle-debugging
description: "Use for durable restart and async lifecycle debugging."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, ios, android]
metadata:
  hermes:
    tags: [debugging, persistence, rehydration, async-workers, state-machines]
    related_skills: [systematic-debugging, test-driven-development, cross-platform-p2p-debugging]
---

# Durable Lifecycle Debugging

## Use when

Use when an item works before restart but loses an action afterward, a second or later item remains in `Preparing`/`Pending`, or an asynchronous worker appears to stop progressing after a partial failure.

This skill complements `cross-platform-p2p-debugging`: use that skill for sender/receiver network boundaries, and this one for durable intent, worker admission, restart recovery, and UI projection.

## Core model

Separate three layers explicitly:

1. **Durable intent** — what the user asked for, persisted before asynchronous work.
2. **Durable completion identity** — the stable external handle proving admission and attribution.
3. **Projection** — transient list/detail/UI state while entries and engine readings rehydrate.

A revision number, display name, item count, or status string is not automatically a completion marker. Prefer the authoritative completion identity: a torrent/substrate handle, remote record ID, job ID, or equivalent stable identity.

## Investigation workflow

1. **Build a red seam test first.** Reproduce the exact symptom with the smallest state: for example `draft=false`, revision present, completion handle absent. Watch it fail before changing production code.
2. **Trace the durable state machine.** Record transitions for intent accepted, worker started, external admission, completion identity persisted, projection refreshed, and failure.
3. **Separate producer and consumer paths.** In a sender/receiver system, inspect publication/source preparation independently from metadata resolution/acquisition. A placeholder such as `Torrent import` does not identify the failing side.
4. **Find the authoritative marker.** Determine which persisted value proves that the external operation is actually attributable and complete. Base pending-work predicates on that marker, not on a convenient revision or UI field.
5. **Make incomplete states recoverable.** If intent exists but completion identity is missing, the item remains pending. An explicit idempotent retry command must wake the worker even if a draft flag has already been cleared.
5a. **Check for a sibling worker that already solved this failure class.** When one async worker (e.g. a publisher/producer loop) has no retry-with-backoff or failure-status surfacing, search the same codebase for the paired worker on the other side of the same system (e.g. the receiver/consumer loop) before designing a fix from scratch. These systems are frequently built in pairs and one side gets the retry ladder, status enum wiring, and backoff-map bookkeeping first; the fix is usually to mirror that exact pattern (same backoff constants, same `HashMap<Key, u32>` failure counter, same `HashMap<Key, Instant>` retry-deadline map, same existing status variant) into the under-built sibling rather than inventing a new one. Reusing an existing status (e.g. a generic `RetryingMetadata`) is preferable to adding a new enum variant when the existing one's label already reads correctly for the new failure site.
6. **Make worker wakes hints, not truth.** Notifications should trigger a scan of durable state. Coalescing is safe when scans are authoritative; ignored closed/full send errors are not. Preserve notifications arriving while work is active.
7. **Instrument boundaries.** Log the durable item key and external identity at start, admission, durable completion, and failure. Never log credentials, source paths, or media contents.
8. **Verify projections independently.** A published item should retain valid actions while detail/list state catches up. If an action is valid but its URI/handle is not ready, show a preparation result rather than hiding the action solely because a transient count is zero.
9. **Run the full gate.** Run the focused red→green test, the backend suite, frontend tests/analyzer, formatting, and then real restart/device validation when the issue is platform-specific.

## Restore fidelity

Restarting is not just "start the work again" — it must reconstruct the item **as the original operation built it**. Three failures recur, and all three are invisible to a unit test that only asserts the item came back.

1. **Same storage location.** If creation chose an explicit output/metadata directory (commonly keyed by a stable identity such as an info hash), rehydration must pass that same location. Leaving it unset lets the engine fall back to a generic default — a download folder, a session root — so a restored item reports paths that nothing ever wrote, and two items sharing a display name can overwrite each other's state there.

1a. **An engine's own "use the OS default path" helper can be platform-hostile.** Many embedded engines/libraries (databases, torrent clients, caches) offer "leave this config unset and I'll pick a sensible OS directory" via a crate like `directories`/`ProjectDirs`, which typically resolves through `HOME`/`XDG_*` environment variables. A sandboxed mobile app process (Android in particular — no real passwd/home entry) does not have those set, so every construction that relies on the guess fails identically and immediately, before any of the engine's own state machine runs. The failure surfaces as a generic, symptom-free stall (e.g. every publish/resume/session-start retries forever with no partial progress) that looks exactly like a per-item persistence bug but is actually a startup-time config bug blocking the *entire* engine. Recognize the log signature — something like `cannot determine project directory for <namespace>.<component>` — and fix it the same way as case 1 above: point the config explicitly at the app's own already-platform-safe state directory instead of leaving it for the library to guess. **Check for more than one call site.** The same library frequently has multiple independent subsystems (e.g. DHT persistence and session/store persistence in a torrent engine) that each call the same underlying guessing helper with a different component name. Fixing one surfaces the identical failure one line later under the next subsystem's name — grep the vendored/dependency source for every call site of the guessing helper (e.g. `grep -rn "get_configuration_directory\|ProjectDirs::from"` across the whole dependency tree, not just the file that logged the first error) and fix all of them together rather than discovering them one retest cycle at a time.

2. **Rebuild from retained references, not by identity.** A resume path that re-adds by external identity (magnet, URL, remote ID) asks the network for content the device already holds. For a zero-copy system this is also a correctness violation: it materializes a second copy of media the user already owns. Look up the retained source record and rebuild from it; fall back to identity only when no record exists.
3. **Restore stopped, then let the reconciler start things.** Add restored work in its paused/inactive form and let the idempotent reconciler assert stored intent. Starting everything at restore and pausing moments later means bytes move during the gap for something the user explicitly stopped.

**Contain per-record failures.** A restore loop that propagates the first error with `?` abandons every later item. One moved or deleted source then leaves an unrelated share unseeded, and the log names only the first casualty. Restore each record inside its own result, log the identity plus the reason, and continue.

## Recover by converting into an existing lifecycle branch, not by adding a new one

When durable state can go bad in a way nothing currently detects — most
commonly, a zero-copy owner's local source file is deleted, moved, or renamed
out from under an active seed — the instinct is to add a new status
(`SourceMissing`, `Unseedable`, ...) and a new UI branch to explain it. Resist
that. If the system already has a lifecycle path that produces the correct
end behavior for "known content, no local bytes, waiting on the network" —
usually the ordinary receiver/download path — convert the broken record into
that shape and let the existing worker that already knows how to resolve and
acquire it pick it up. No new status, no new UI, no new capability-matrix
row to keep in sync.

The conversion is a small, mechanical data rewrite: clear the fields that
identified this device as the owner/seed (local source list, and the
session/substrate handle if one exists), write whatever durable record the
sibling "fresh import" path expects (e.g. a magnet built from the collection's
own already-known content identity), carry over any already-known metadata
(file list, descriptor) so the receiving worker skips straight to the later
stage instead of re-resolving from scratch, and wake that worker. Do this on
a periodic sanity tick (stat every source, independent of and in addition to
whatever poll interval the transfer/telemetry worker already runs on — the
transfer poller only hears from the substrate about torrents it actively
carries and says nothing about whether the referenced files still exist).

Every use case this recovery reasoning needs to cover, and why each resolves
without special-casing once the rule above is applied:

- **One of several sources missing, not all.** Treat the same as all missing
  — a torrent generated from a partial local set is not the torrent any peer
  already holds, so the whole collection re-fetches from whoever else has it.
- **Renamed/moved vs. genuinely deleted.** Indistinguishable by a stat call,
  and correctly so — this device no longer has the bytes at the path it
  promised, for whatever reason.
- **Paused when the source disappears.** Leave it alone. A pause is the
  person's decision, not a stall to auto-fix; converting it would silently
  restart something they explicitly stopped. Let the next sanity tick after
  they resume catch it.
- **A draft (never published/shared) whose source disappears.** Leave it
  alone too — nothing has been offered to anyone, so there is nothing for a
  swarm/peer to re-fetch; converting it would try to download content that
  was never published.
- **The receiver side of the same system.** Out of scope by construction —
  a receiver record already has no local source list, so the missing-source
  check never matches it; it already lives on the ordinary download path.

## Cleanup must not outrank the durable record

The most damaging lifecycle bugs are not in the restore path at all — they are in a **cleanup path that couples a session-scoped lifetime to a durable one**. Restore then works perfectly and is undone seconds later.

The pattern: a reaper releases anything the current projection does not claim (`release`, `forget`, `evict`, `prune`, `gc`). That release *also* deletes the durable record — the source references, the descriptor, the path vault. But "unclaimed right now" is not "the user deleted it": during startup a record is routinely unclaimed for a moment while the projection hydrates, and a publish that has not yet written its handle is unclaimed by definition.

Consequences worth recognizing on sight:

- **Self-reinforcing corruption.** Each launch restores correctly, is reaped, loses the real location, and the *next* launch falls back to a default directory — which then gets persisted as if it were the truth. Fallback paths from previous runs appearing in a log (e.g. sources under the app's own download/debug folder) mean the damage is already several restarts deep.
- **Unrepairable by the fix.** Once the only record of a user's original location is gone, correcting the cleanup path does not bring it back. Say so explicitly and separate "new items are fixed" from "existing damaged items must be re-added."

Rules:

- A destructive cleanup belongs on the **explicit user act** (delete the item), never on a transient reconciliation verb. Split them into two functions with names that cannot be confused, and say in the doc comment why the release path deliberately does *not* purge.
- Before deleting any durable record, ask: *can this state occur without the user having asked for anything?* If yes, the deletion is in the wrong place.
- Grep every caller of a purge helper. The dangerous one is usually a periodic worker, not the command handler you were reading.

**Log signature.** Two lines for the same identity in one startup — a restore followed by a release — is this bug, not noise:

```
rehydrated linked torrent <ID> from original sources
...
forget_torrent: info_hash=<ID>
```

Read the *whole* startup log before diagnosing. A single failing line invites a plausible wrong root cause; the restore/release pairing a few lines later is what actually identifies it.

## Sandbox access for zero-copy sources

When the system reads the user's original files rather than copies, the OS permission to read them is itself durable state and must be restored alongside the record.

A sandboxed app (macOS, iOS) may read a user-picked file only for the life of the process that picked it. After a restart the backend gets `Operation not permitted` (`os error 1`) on a path that plainly exists — a signature worth recognizing on sight, and distinct from `No such file or directory` (`os error 2`), which means the source genuinely moved.

- Persist a security-scoped bookmark **at selection time**; the platform cannot mint one for a file it can no longer reach, so deferring until publication is too late.
- Resolve every bookmark **before the backend starts**, since rehydration is often the first thing that reads a source.
- Release bookmarks when an item is deleted, so a removed collection does not hold a permission forever.
- Check platform parity explicitly. One platform having this wired up says nothing about its sibling: verify each target that claims support rather than assuming a shared picker implies shared persistence.
- When testing, choose a source **outside** any directory the app holds a blanket entitlement for (e.g. `~/Downloads`), or that entitlement masks the bug.

## Completion metadata versus ongoing telemetry

Treat download completion as a one-way lifecycle edge, not as the end of all
transfer activity. Persist `completed_at` exactly once when the engine reports
the download complete, and derive `completed_in` only from the fixed
`started_at` and `completed_at` values. Never recompute either value from the
latest history sample.

Keep polling and recording upload/seeding telemetry after completion. The graph
may extend past the completion moment and show current upload rates, while the
completion duration and timestamp remain unchanged. In the frontend, do not use
`!complete && rate > 0` as the only definition of activity; completed torrents
can have upload-only activity. Use a regression test with a fixed completion
moment and a later non-zero upload sample, asserting both immutable completion
labels and visible current upload data. First run it against the old condition
to confirm RED, then apply the smallest change and run the focused and full
suites.

## Checkpoint ephemeral state on every tick, not only at lifecycle edges

A durable snapshot that only writes at completion or shutdown loses anything
that changed and reverted *between* those edges. A peer that connects, moves
bytes, and disconnects mid-transfer — with the collection never finishing and
the app never restarting — leaves no trace if the snapshot write is gated on
`if completed_download { snapshot(...) }` or `on shutdown { snapshot(...) }`.
The fix is to move the snapshot call outside the completion/shutdown
conditional and let it run on the regular poll tick unconditionally (a cheap
upsert per currently-known item, keyed on its exact identity) — the durable
ledger then trails the live one by at most one poll interval instead of being
blind to anything that didn't survive to a lifecycle edge.

Recognize this class of bug by asking, for any "X disappeared" report about a
durable list (peers, connections, sessions, active jobs): *does the write
path that persists X only fire on completion/shutdown/an explicit close
event?* If so, write the RED regression test as two poll readings — item
present, then item absent — with the fake substrate/engine double reporting
no completion and no shutdown between them, and assert the durable store
already has the item by the second reading. That pins the difference between
"missing because it never finished" and "missing because retention itself is
broken."

## Required regression cases

- A published item reopens with its action visible before detail entries rehydrate.
- A partial durable write with revision present and completion handle absent is republished and records the handle.
- Multiple durable items are discovered by one scan, including an item created while another is active.
- Repeating an idempotent publish/retry command does not create a second singleton session.
- Sender publication and receiver acquisition remain separate state machines.
- A resolved-but-unconfirmed draft remains non-acquiring across a full process restart and every unrelated worker wake; default-selected entries are not themselves confirmation.
- A collection persisted as paused is added to a freshly created transport session in its paused state, rather than being started and paused only by later reconciliation. Exercise both ordinary session persistence and custom/zero-copy rehydration paths.
- Original filesystem/gallery references remain direct; metadata/descriptors may persist, but media is never copied, cloned, hard-linked, staged, or cached as a duplicate.
- A restored item reports the storage location the original operation chose, not the engine's default download directory. Assert on the engine's own output/storage field, not on a path a later projection layer overlays.
- A restore pass containing one unreadable source still restores every other record.
- Resuming an item the session has dropped rebuilds it from the retained source references rather than re-fetching by external identity.
- After a full process restart, a sandboxed platform can still read every source it seeds (guards the `Operation not permitted` class).
- Per-file source paths are matched to engine files **by name, not list position** — engines order files their own way, so zipping two lists pairs one file's location with another's name.

## Pitfalls

- Do not hide a broken lifecycle with sleeps, fixed retry counts, forced resume commands, or collection-count-specific branches.
- Do not treat a successful revision write as proof that the external torrent/job was admitted.
- Do not let `draft=false` mean “never retry” when the completion identity is missing.
- Do not infer a UI action’s validity from a transient entry/detail count.
- Do not claim a restart or cross-device fix from unit tests alone; report physical validation separately.
- Do not trust a restore test that asserts only on a value a projection layer overlays after the fact. If a later step rewrites the field from a durable record, the assertion passes even when the engine was configured wrongly. Assert on what the engine itself was handed, and prove the test fails with the fix reverted.
- Do not read a startup log's first error as the whole story. Two adjacent failures — one `os error 2` on a missing source, one `os error 1` on a permission — are usually distinct bugs plus a third that let the first abort the rest.
- Do not kill unrelated long-running processes on shared development hosts while validating.
- Do not accept "the test passes" alone as proof a lifecycle regression test is real. If the fix was written before the test (rather than strict red-then-green), retroactively comment out just the fix's behavioral change (not the whole worker/function — keep it registered and running) and rerun the exact same test; it must fail with a timeout/assertion tied to the removed behavior, not a compile error. Then restore the fix and rerun to confirm green. A test that never demonstrably failed proves nothing about what it's guarding.
