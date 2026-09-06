---
name: bridge-frontend-refactoring
description: "Use when flattening generated bridge DTOs in a frontend."
version: 1.0.0
---

# Bridge Frontend Refactoring

## Purpose

Flatten frontend layers around generated native-bridge DTOs without losing the
performance boundaries or testability designed into the native API.

## Design rule

Use generated bridge types as the frontend data model. Do not mirror them into
hand-written per-feature DTOs merely to rename fields or restate values.

Keep one explicit, fakeable **gateway/facade** between application code and the
bridge. The gateway is the test seam; its public methods may expose multiple
streams when those streams have distinct cost and lifetime models.

## Tiered stream rule

Do not collapse distinct bridge tiers into one global snapshot solely to claim a
single seam. A healthy gateway may expose:

- an app-wide summary snapshot;
- selected-object detail streams;
- append-only history/event streams; and
- generated command dispatch.

This keeps expensive detail and history out of high-frequency global updates.

## Migration workflow

1. **Inventory the data path.** Trace generated DTOs through re-exports,
   feature wrappers, sources/controllers, widgets, viewers, and test fixtures.
2. **Name the one seam.** Replace generic pass-through repository names with a
   gateway name that makes the boundary clear. Keep tests faking that gateway,
   never FFI calls.
3. **Remove command mirrors.** Accept the generated command type at the
   gateway. A pure convenience factory may fill mandatory empty generated
   fields or convert a caller list to a required typed buffer, but must return
   the generated type and hold no state.
4. **Migrate by complete presentation contract.** Convert every consumer of a
   shared wrapper together: list, route, detail, peers, media viewer, and
   tests. Do not convert only a leaf widget if other paths still rely on its
   extensions or derived helpers.
5. **Replace stored wrappers with pure helpers.** Use extensions and stateless
   presentation functions for formatting, status labels, and byte conversions.
   They must not cache or own a second copy of bridge state.
6. **Delete only after the last consumer moves.** Remove feature DTO wrappers,
   adapters, and legacy sources in the same atomic change. Search imports and
   symbols before deletion.

## Validation

- Run the focused controller and widget tests before and after each migration
  slice.
- Run frontend analysis after renames or import moves.
- Run the complete frontend suite before committing the final deletion.
- Regenerate bindings only when a bridged Rust signature or DTO changes; Dart
  presentation-only refactors should not regenerate them.

## Pitfalls

- A reference-only wrapper may avoid bulk copying, but it still obscures data
  flow and adds allocation/churn; do not mistake it for the desired final
  architecture.
- A single gateway is a facade, not necessarily a single data stream.
- Never move expensive selected detail or append-only history into an
  app-global summary snapshot just to simplify a widget signature.
- Do not leave half-migrated contracts in the tree. If a direct-widget change
  breaks unmigrated detail/media paths, revert that incomplete slice and
  regroup the migration around the full shared contract.
