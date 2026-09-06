# Redundant hashing over a slow platform media reader (iOS PhotoKit / Android MediaStore)

## Symptom cluster (all three together = this issue, not a network problem)

- A collection created from local/gallery media sits in "Resolving Metadata"
  (or equivalent pre-publish status) for a long time (minutes for a
  large video) with no visible progress, looking hung.
- It eventually flips to "Seeding", but the UI then shows a *second*,
  separate "local source verification" progress bar climbing from zero.
- Effective upload/read throughput looks capped far below real LAN speed
  (e.g. ~1.5MB/s) even though sender and receiver are on the same network.

## Root cause

Two independent full-file hash passes run back to back over the same
slow-to-read source:

1. **App-level publish hash** — the app's own torrent-metainfo builder reads
   every byte of each source file (in fixed-size chunks, e.g. 64KB) to
   compute the piece SHA1s that become the torrent's info hash. This is not
   optional — a BitTorrent info hash is defined by these piece hashes, there
   is no way to create a torrent without this pass.
2. **BitTorrent engine's own re-verification** — the moment the freshly built
   torrent is handed to the engine (e.g. librqbit's `add_torrent`), the
   engine has no way to know the data was just verified by the app, so it
   runs its *own* full initial-check pass (`FileOps::initial_check` in
   librqbit terms) with its own separate read buffer, re-hashing every byte
   again before it will seed. This is pass #2, and it is the one showing as
   "local source verification" with its own progress in the symptom above.

Both passes read through the same slow platform accessor — for iOS, that is
`PHAssetResourceManager`/`PHImageManager` via a sequential, single-request
reader (see the app's native photo-reader bridge) that streams an
iCloud-optimized asset at whatever rate iCloud sync gives it, often far below
local disk or LAN speed. Reading the same multi-hundred-MB/GB asset through
that path *twice* before seeding starts is what looks like the app being
"stuck" and then the upload being throttled — it isn't network-bound at all,
it's blocked on the second iCloud/gallery read.

## Fix direction (not a network/buffer-size fix)

- **Eliminate pass #2 for content the app just hashed itself.** BitTorrent
  engines that support persistent/fastresume state (librqbit's
  `BitVFactory` + `fastresume` option) accept a pre-populated "have all
  pieces" bitfield for an info hash *before* the torrent is admitted. If the
  app writes that bitfield itself right after its own hash pass succeeds
  (since it just verified every piece), the engine only spot-checks one
  piece per file instead of re-reading and re-hashing the whole file. This
  collapses two full slow reads into one, and it is honest (not a
  correctness shortcut) because the app really did just verify the content.
- **Increasing the app's own read chunk size** (e.g. 64KB → 1MB+) reduces
  per-call overhead on the slow reader but does not remove the duplicate
  pass — treat it as a secondary, complementary optimization, not the fix
  for the "looks stuck for a minute, then re-verifies again" complaint.
- **Surface progress during the app's own hash pass.** If the app already
  tracks hashing progress internally (bytes hashed so far) but the status
  the UI reads doesn't carry a percentage, wire it through. This fixes the
  *perceived* hang even in cases where the underlying iCloud/gallery read
  genuinely can't be sped up further.

## Diagnostic tell

If you see a UI status transition of
`resolving/publishing (no progress) → seeding (own verification progress
bar climbing)` immediately followed by throttled-looking transfer speed on
a LAN both devices are actually on, suspect this double-hash pattern before
suspecting networking, permissions, or peer discovery. Confirm by checking
whether the publish/hash code path and the torrent engine's admission path
both do a full read of the source content.
