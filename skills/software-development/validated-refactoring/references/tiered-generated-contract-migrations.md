# Tiered Generated-Contract Migrations

Use this when a Flutter/Rust (or similar) client has generated bridge DTOs plus handwritten presentation/domain wrappers.

## Decision pattern

Keep one fakeable gateway/facade, but retain the backend's natural read tiers:

- app-wide summary stream (`AppSnapshot`)
- selected-resource detail stream (`AppDetail`)
- append-only or incremental history stream
- generated command DTO (`AppCommand`)

Do **not** force detail and history into a global summary snapshot merely to obtain one stream. That increases bridge traffic, rebuild fan-out, and retained UI memory. The single seam is the gateway interface, not a single oversized read model.

## Safe migration order

1. Add a direct generated-type test that fails because a widget still expects a wrapper.
2. Name and move the gateway seam; make test fakes implement it.
3. Move the selected detail/history subscriptions into the route or screen state that owns their lifetime. Accumulate append-only history there with an explicit bound.
4. Change presentation inputs together: summary widgets accept generated summaries; selected screens accept summary + detail; media widgets accept generated entries.
5. Replace handwritten command envelopes with the generated command DTO. A factory may populate compulsory empty fields but must not introduce another command class.
6. Replace wrapper-only tests with behavior tests using generated values.
7. Delete wrappers and scan the entire client tree for imports, type names, and conversion functions before calling the migration complete.

## Truthfulness rules

- Display only peer/history facts the generated contract actually supplies. Do not retain a synthetic departed-peer history to preserve an old visual treatment.
- If the bridge supplies aggregate piece state but no per-entry ranges, keep aggregate progress rather than inventing file-relative activity.
- Display extensions and bounded decoded history are acceptable derivations; persistent mirror DTOs are not.

## Verification

Run formatter, analyzer/type checker, focused direct-contract tests, then the complete client suite. For cross-layer repos, also run the project acceptance gate. Confirm the wrapper scan returns zero references and inspect the deletion/rename diff before commit.
