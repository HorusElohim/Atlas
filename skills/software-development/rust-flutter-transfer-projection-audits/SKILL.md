---
name: rust-flutter-transfer-projection-audits
description: "Use when auditing Rust-Flutter transfer data."
---

# Rust-to-Flutter Transfer Projection Audits

Use this skill when a Rust-backed Flutter application appears to forward too much transfer data, rebuilds rich state frequently, or needs a safe projection/performance refactor.

## Procedure

1. Establish a clean baseline before editing:
   - check branch and worktree status;
   - record test counts, clippy/analyzer state, and lockfile revisions;
   - identify the exact hot poll interval and the failing or expensive command.
2. Trace the data end to end:
   - engine/library stats and API calls;
   - Rust accounting and persistence;
   - Rust domain/projection constructors;
   - generated bridge types;
   - concrete Dart controllers and widgets.
3. Build a field-consumer table. Classify every field as summary UI, detail UI, Rust accounting, or genuinely unused. Never remove a field merely because the low-level DTO has no direct Dart references.
4. Separate three concerns without changing semantics:
   - one Rust sampling pass reads engine facts;
   - Rust reducers calculate rates, history, persistence, readiness, and events;
   - projections publish compact summaries and watched detail snapshots.
5. Keep genuinely UI-used capabilities intact. Per-file progress, piece maps, peer rows, and current down/up rates remain available when their screens render them.
6. Move work, not information:
   - keep counters and peer samples in the hot Rust accounting path;
   - build file paths, piece runs, bitmaps, and rich peer rows only for active detail subscribers;
   - coalesce unchanged summary/detail publications;
   - persist newly observed or changed peers, not unchanged idle rows.
7. Measure before and after: engine API calls per tick, poll duration, clone/allocation volume where available, bridge publication size/count, and detail refresh cost. Preserve the existing transfer scheduler and zero-copy media behavior unless a separate benchmark justifies changing them.
8. Add focused regression/contract tests for both retained UI behavior and the new collection boundary. Run the project gate, full Rust tests, Flutter analyze/tests, and dependency checks before committing.

## Portalis-specific tracing pattern

For Portalis, inspect:

```text
Substrate::holdings()
  → TorrentInfo
  → Holdings
  → Detail / CollectionState
  → AppDetail / AppSnapshot
  → collection detail, piece frame, peers, transfer graph, activity rail
```

The current UI genuinely uses:

- per-entry downloaded bytes and resolved paths;
- packed piece state;
- connected peer rows and peer rates;
- collection progress, status, ETA, live peer count, and aggregate down/up rates.

Raw peer addresses and fetched/uploaded counters are Rust accounting inputs, not direct UI contracts, but they must remain available for rates, history, persistence, and events.

## Architecture rule

Prefer a Rust-owned transfer store with one compact sampling/accounting pass, a latest-value summary projection, and request/subscription-driven detail projections. Do not route scheduling, piece selection, rate calculation, or media bytes through Flutter.

## Pitfalls

- Trace derived/generated projections and concrete widgets before declaring a field unused; low-level DTO searches miss indirect consumers.
- Do not confuse "the UI uses detail data" with "every torrent must pay the detail-construction cost every poll"; preserve the detail stream while making its production subscription-aware.
- Do not optimize by slowing the rate sampler until chart/history semantics and transfer accounting are measured; sampling frequency and UI publication frequency can be decoupled.
- Do not use a cache without an explicit revision/invalidation rule; stale piece maps and peer rows are correctness bugs, not acceptable performance tradeoffs.
- Keep peer persistence change-aware, but always record a newly observed peer so a connect-and-disconnect interval is not lost.
- Do not infer that a generated bridge class is used just because it exists; find the actual application/widget reads, and do not infer that a Rust field is unused just because Flutter never sees it directly.
- When testing a fork regression, validate clean upstream and each atomic commit with persistent exit-status records; a failed checkout or a command that remained on the previous revision is invalid evidence.
