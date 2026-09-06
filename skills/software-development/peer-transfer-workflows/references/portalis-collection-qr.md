# Portalis collection QR receiver

## Role contract

| Role | Allowed work | Forbidden work |
| --- | --- | --- |
| Sender (Mac or mobile with chosen local sources) | Read original source references, hash, publish/seed a torrent, persist metadata/descriptor, show QR | Copy, clone, hard-link, or cache source media for publication |
| Receiver (device scanning the QR) | Validate link, import magnet, resolve descriptor, select entries, acquire/download through the torrent substrate | Invoke `publishDraft`, treat remote source paths as local media, or create a local sharing collection |

## App command map

```text
portalis://import?magnet=…
  → collectionMagnetFromLink
  → EngineCommand.importTorrent(magnet)
  → detail stream resolves AppEntry list
  → EngineCommand(kind: 'downloadSelection', collection, entries)
  → torrent worker acquires selected entries
```

`publishDraft` is sender-only. It is valid for a Native collection containing local source records; it is invalid for the iPhone receiver path.

## UI contract

- Native draft footer: **Share this collection**.
- Torrent import footer: **Download selected files**.
- A link-driven receiver should automatically dispatch the selected-entry download once descriptor metadata is available.
- If resolution fails, leave the imported collection visible with its error; do not redirect to the local source picker or Share action.

## Test seams

- `portalis/test/collection_link_test.dart`: link parser and exact command order (`importTorrent`, then `downloadSelection`, never `publishDraft`).
- `portalis/test/nexus_app_controller_test.dart`: imported torrent UI uses Download wording rather than Share.
- `portalis/rust/backend/src/nexus/core/nexus.rs`: the import and selection state machine.
- `portalis/rust/backend/src/nexus/core/torrents.rs`: descriptor resolution and selected-entry acquisition.

## Validation

```sh
# Flutter package root
flutter analyze
flutter test

# Repository root
./tests/nexus.sh
```

Physical iOS test: install a fresh build, scan a Mac QR, verify the iPhone imports metadata and begins receiver-side transfer; confirm no local sharing/publishing action occurs.
