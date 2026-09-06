# Portalis Add-Media and Receiver Bootstrap Regression

## Findings

Two recurring failures can look like generic P2P waiting:

1. A command variant can be validated and accepted while the command dispatcher silently falls through without changing durable state. For local native collections, trace the full path `Flutter addMedia -> bridge DTO -> Command::AddMedia -> apply_local -> store -> publisher wake`. Test that the selected original paths are persisted, the projection updates, and the publisher is notified. Do not solve this by copying media.
2. Direct peer hints must survive the complete receiver path. Derive hints from the imported source and pass the same set to both metadata inspection and later acquisition. Passing hints only to inspection, or using `PeerHints::default()` for acquisition, produces metadata with a visible Fetch button but zero peers and no transfer.

## Evidence pattern

When debugging a report, distinguish:

- sender QR diagnostics: listener port and advertised private-LAN endpoints;
- receiver state: metadata/file count, pending selection, peer count;
- engine calls: exact source, peer hints supplied to inspect, peer hints supplied to acquire;
- rollback: `forget_torrent` after publication/admission failure.

Apple `view-bridge`/NSXPC rendering messages should not be treated as torrent evidence unless a reproducible picker failure connects them to the source-selection boundary.

## Acceptance checks

- Add-media regression proves the command is not silently accepted and discarded.
- Receiver regression records non-empty `x.pe` hints at both inspect and acquire seams.
- Fresh QR is used for device testing; old QR payloads do not gain later metadata.
- Physical Mac-to-iPhone test confirms peer count becomes nonzero and a selected download starts.
- Source media remains referenced directly; no copy, clone, hard link, staging cache, or duplicate is introduced.
