# QR import handoff debugging

Use this when a Portalis QR import resolves metadata but does not download.

## Boundary evidence

The receiver path should produce these events in order:

```text
import accepted
resolve started/completed
collection detail contains entries
DownloadSelection accepted with non-empty entry indexes
acquire started
substrate handle persisted
```

A sender log with `torrent resolve complete` only proves metadata inspection.
The decisive next check is the receiver-side `DownloadSelection` command. If it
is absent, the bug is in QR/deep-link handling, UI handoff, or detail delivery;
do not debug peer reachability yet.

## Detail-stream rule

Portalis' collection detail projection is a live subscription owned by the
opened collection route. Automatic QR download must use that route-owned stream
(or a backend transaction that owns the complete transition). Starting a second
background `watchDetail` waiter before navigation can race or replace the
screen's subscription and leave the receiver stuck after metadata resolution.

Manual magnet imports must remain selection-only. Only the explicitly
identified QR collection flow may confirm the resolved default selection
automatically. Guard the trigger against duplicate listener notifications and
retry only while metadata has not yet produced a non-empty selected set.

## Product wording

Use receiver-facing wording such as `Portalis collection import` and
`Portalis collection scanned successfully`, not generic `Torrent import` or
`Peer hints scanned successfully`. The label should reflect the user's intent
without changing the underlying torrent protocol semantics.

## Verification

When the native iOS/Android build cannot run on the host, still run the pure
Dart tests, analyzer, Rust formatting, and backend tests. Report physical-device
verification separately; do not claim a native build passed without the native
SDK/toolchain.
