# Received-media gallery rebind checklist

Use this when an incoming P2P collection automatically exports completed images/videos to a native photo library while preserving its torrent identity.

## Per-entry transition

```text
verified torrent entry
→ native gallery import (copy first if no cross-store transaction exists)
→ persist `phasset://…` / `content://…`
→ rebind the SAME descriptor/info-hash to hybrid storage
→ remove the app-local received file
```

Never trigger from network-fetched bytes; use the engine's hash-verified per-file completion. Persist after each native import result before processing the next entry.

## Hybrid storage contract

- Gallery-backed entries: random-read only, for resume/verification/seeding.
- Filesystem-backed entries: random-read **and write**, so unselected or unsupported files can be selected/downloaded later.
- Store every descriptor file in torrent order, with its declared length.
- Persist an explicit `allow_missing_files`/equivalent flag for receiver records: an unselected filesystem file may not exist at restart, and rehydration must use the declared descriptor length instead of failing metadata/stat validation.
- Preserve selected-file indices when replacing the live torrent's storage.

## Failure handling

- If gallery import fails or permission is denied, leave the source in app storage and retry only on a later verified state transition.
- If the native import succeeds but durable persistence/rebind fails, retain the app-local source. Do not delete it.
- Delete the local source only after the new native reference is persisted and the torrent rebind succeeds.
- A direct PhotoKit/MediaStore move is safe only with a durable operation journal that can recover the native asset identifier after process death.

## iOS notes

- Add `NSPhotoLibraryAddUsageDescription` for automatic exports.
- Request add-only Photos authorization for export; a separate read capability may still be needed by a source picker or random-access adapter.
- Verify with a signed build on a physical iPhone: permission granted/denied, photo + video, mixed collection, restart, later selection of an unselected file, and resumed seeding from the Photos asset.
