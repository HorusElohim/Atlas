# PortalisApp Collection Lifecycle — Reference

Concrete detail behind the class-level guidance in `durable-lifecycle-debugging`
and `validated-refactoring`. Portalis is Flutter + Rust (flutter_rust_bridge),
BitTorrent via a vendored librqbit, with a strict zero-copy invariant: the
backend seeds the user's original files and never stages a duplicate.

## Verification gates

Run backend gates from `portalis/rust/backend/` (NOT the repo root — cargo will
not find `Cargo.toml`), and Flutter gates from `portalis/`.

```bash
# portalis/rust/backend/
CARGO_BUILD_JOBS=4 cargo test --lib
CARGO_BUILD_JOBS=4 cargo clippy --all-targets --all-features -- -D warnings
CARGO_BUILD_JOBS=4 cargo fmt --all --check

# portalis/
flutter analyze
flutter test
```

Version bumps are coordinated and required for user-visible change:
`portalis/pubspec.yaml`, `portalis/lib/version.dart` (both `portalisVersion`
and `expectedBackendVersion`), `portalis/rust/backend/Cargo.toml`, its
`Cargo.lock` entry (a `cargo check` refreshes it), plus `CHANGELOG.md`.
A frontend/backend version mismatch is a hard startup failure by design.

## The status bridge — RESOLVED (`e8b8c2f`, backend 0.1.37)

Historically `portalis_api.rs` sent status across FFI as Rust `Debug` output
(`format!("{:?}", collection.status)`) and Dart compared raw literals. The
enum's `Debug` output was the wire contract, so renaming a variant changed app
behavior with no compile error on either side.

This is now an explicit contract in `projection/wire.rs`: every status, nature,
role, friendship, and connectivity value is spelled out by hand in an
exhaustive match, so adding a variant **fails to compile** until its word is
chosen. Dart parses those words once in `CollectionState`
(`lib/features/collections/domain/collection_state.dart`) and the UI uses typed
predicates. Characterization tests pin the current spellings.

Fixing this exposed three comparisons that had silently rotted and could never
match: two tested `'downloading'` and one `'importing'`, neither ever emitted.

**Do not reintroduce `format!("{:?}")` on a bridge-facing enum.** If you add a
`Status` variant, the compiler will stop you in `wire.rs` — that is the point.

## Lifecycle — RESOLVED (`6b94dcb`, schema 10, backend 0.1.39)

Persisted `draft` and `paused` were independent booleans, so unactionable
states were encodable (a paused draft; a resolved import that looked confirmed
because its checkboxes defaulted to selected). Each worker reassembled intent
from those flags separately and they disagreed.

Schema 10 stores one exhaustive discriminant in `StoredCollection.lifecycle`:

```
NativeDraft | NativePublished{activity} | TorrentResolving
TorrentAwaitingSelection | TorrentRequested{activity}
```

`activity` (Running/Paused) exists **only inside the two executable variants**,
so a paused draft is unrepresentable rather than merely guarded against. Engine
observation stays separate and feeds `status_for` alongside the lifecycle.

Notes for future work in this area:

- Selected entries stayed in their own table; they are *not* folded into
  `TorrentRequested`. Selection is data, authorization is the lifecycle.
- Resolution now projects as `Preparing`, not `Draft`. Draft means "waiting on
  the person"; resolving is active work. It becomes Draft
  (`TorrentAwaitingSelection`) once the file list lands.
- `PublishDraft` is **refused** for every torrent variant — only
  `DownloadSelection` may authorize acquisition. This was the one real hole an
  independent review caught, and it is now pinned by a falsified test in
  `a_torrent_source_resolves_into_a_selection_then_downloads_it`.
- An unknown discriminant byte decodes as `Malformed`, never a silent default.

## Durable schema migration (the schema 9 → 10 pattern)

Worth copying whenever a redb-backed record changes shape:

1. **Read and convert before `begin_write()`.** `collections_from_schema_nine`
   returns fully-converted rows; `prepare()` then writes them and the version
   stamp in one transaction. A crash mid-migration leaves the old store intact
   at the old version — there is no half-migrated state.
2. **A legacy flag may need sibling tables to interpret.** The old `draft` bit
   alone could not distinguish "resolving" from "awaiting selection"; the
   migration reads `TORRENT_IMPORTS` and `TORRENT_IMPORT_ENTRIES` to tell them
   apart.
3. **Fail closed on read errors, tolerate only genuine absence.** `.ok()` on a
   table open swallows corruption and type mismatch as "table missing," which
   silently misclassifies lifecycle. Match explicitly:

   ```rust
   match read.open_table(TORRENT_IMPORTS) {
       Ok(table) => Some(table),
       Err(redb::TableError::TableDoesNotExist(_)) => None,
       Err(error) => return Err(error.into()),
   }
   ```
4. **Bias ambiguity toward the state that requires user action.** A resolved
   legacy draft migrates to *awaiting selection*, never *requested* — the cost
   of being wrong is one extra tap, not an unwanted download.
5. **Falsify the migration test**: flip the mapping to the executable state and
   confirm the test fails.

## Bugs found and fixed (2026-08, `0ff99aa`)

1. **Draft auto-acquire.** `resolve()` writes every entry `selected: true` so
   the selection screen opens populated. `pending_work()` emitted
   `Pending::Acquire` on "entries selected + no substrate_handle" without
   checking `draft`. App open wakes the worker → reopening downloaded a
   torrent that had only been inspected. Fix: skip `Acquire` while `draft`.

2. **Restore pointed at Downloads.** `rehydrate_linked_torrents` left
   `AddTorrentOptions.output_folder` unset, so librqbit fell back to the
   session download dir instead of the info-hash-keyed
   `referenced_metadata_dir` publication had chosen.

3. **Resume re-fetched owned content.** `restart_torrent` re-added by info hash
   (`AddTorrent::from_url`) when the session had dropped the torrent — asking
   the swarm for media the device already holds, a zero-copy violation. Fix:
   look up `linked_source_store::record_for` and rebuild from retained
   references; fall back to identity only when no record exists.

4. **One bad source killed all restores.** The rehydration loop propagated the
   first error with `?`. A moved file left every later collection unseeded.
   Fix: per-record `match`, log identity + reason, continue.

5. **Transfer before pause.** Restored torrents started immediately and were
   paused only by later reconciliation. Fix: add with `paused: true` and let
   the reconciler start what is genuinely meant to run.

6. **macOS had no security-scoped bookmarks.** iOS had
   `NoCopySourcePicker.swift` doing this; macOS had nothing. The sandbox
   revoked access to picked sources at process exit, so the publisher failed
   with `Operation not permitted` and stopped seeding everything. Fix:
   `SecurityScopedSources` (Swift, registered before the first frame so
   bookmarks resolve before the backend starts) + a Dart channel wrapper,
   retained in `pickedFileFrom` — the single chokepoint every desktop pick
   flows through. macOS-only; iOS/Android/Linux/Windows are no-ops.

7. **Files zipped by index.** `to_info` overlaid vault source paths onto engine
   files positionally. Engines order files their own way. Fix: match by name.

## Reading the startup log

```
[torrent] linked torrent rehydration incomplete ...: cannot read source
          "/Users/mark/Downloads/Screenshot ....png": No such file (os error 2)
[nexus]   publisher failed collection ... "Jam Jar": Operation not permitted (os error 1)
```

Three separate bugs in two lines: `os error 2` = source genuinely moved;
`os error 1` = sandbox permission lost (bug 6); and the *second* line failing
because the *first* aborted the loop (bug 4). Do not stop at the first error.

## Test placement notes

- macOS Swift helpers live inside `AppDelegate.swift` (as `HeicPreview` does),
  which avoids a fragile `project.pbxproj` edit for a new file.
- `list_torrents()` uses the process-global session; a test needing a specific
  session must use `session.with_torrents(...)` + `to_info` directly.
- Assert restore location on `api_torrent_details(...).output_folder`, NOT on
  `TorrentInfo.absolute_path` — the latter is overlaid from the vault
  afterwards and reads correctly even when the engine was configured wrongly.
- Dart `expect` takes `reason:` as a named argument, not a third positional.
