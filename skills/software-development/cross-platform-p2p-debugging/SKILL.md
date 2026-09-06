---
name: cross-platform-p2p-debugging
description: "Use for asymmetric mobile/desktop peer-transfer debugging."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, ios, android, linux, windows]
metadata:
  hermes:
    tags: [p2p, bittorrent, flutter, rust, mobile, desktop, networking]
    related_skills: [systematic-debugging, test-driven-development, flutter-rust-bridge]
---

# Cross-Platform P2P Debugging

## Use when

Use when a transfer, metadata lookup, peer bootstrap, QR/deep-link import, or
local-network operation works in one direction or platform but stalls in the
reverse direction.

## Core rule

A successful import is not proof of connectivity. Separate the pipeline into:

1. payload creation (magnet/QR/deep link);
2. payload parsing and validation;
3. sender listener binding;
4. sender interface enumeration and advertised endpoint construction;
5. receiver parsing and peer-hint propagation;
6. metadata inspection;
7. torrent acquisition.

Do not patch transport code until the first failing boundary is identified.

## Workflow

1. **Record the asymmetry.** Test A→B and B→A with the same content and record
   which stage each direction reaches. Preserve the exact UI state and runtime
   logs.
2. **Capture sender evidence.** At share/QR creation, log the live listener port
   and the complete validated advertised peer list. An empty list is a first-class
   result, not an implementation detail.
3. **Capture receiver evidence.** At import and metadata resolution, log the
   source's embedded peer hints and the hints supplied to the substrate. Confirm
   that parsing did not discard, rewrite, or duplicate them.
4. **Check platform prerequisites.** Verify local-network permission, sandbox or
   firewall rules, listener address family, interface visibility, VPN/cellular
   routing, and whether the advertised address is reachable from the receiver.
5. **Use a tight seam test.** Add a regression test for the first failing seam:
   peer-hint encoding/decoding, listener-address selection, interface filtering,
   command propagation, or metadata options. The test should fail before the
   fix and pass afterward.
6. **Change one boundary at a time.** Do not combine a new endpoint algorithm,
   fallback discovery, and UI changes in one patch. Re-run the directional test
   after each change.
8. **Gate sender sharing on runtime truth.** A persisted torrent handle or a
   successful publication through an injected test substrate is not evidence
   that the current librqbit session can seed. Before displaying or generating
   a QR, verify the exact info-hash is loaded in the active session and that its
   listener has a bound port. Fail closed after restart or rehydration failure;
   return an actionable unavailable state instead of a stale magnet.

## Required diagnostics

Use stable, redacted logs with these fields:

```text
share: listener_port=..., advertised_peers=[...]
import: source_peer_hints=[...], supplied_peer_hints=[...]
metadata: result=ok|error, file_count=..., error=...
acquire: peer_hints=[...], result=started|error
```

Never log source paths, credentials, tokens, or media contents. A magnet's info
hash and private LAN endpoint are sufficient for correlation; redact anything
else not needed to diagnose the transport.

## Common hypotheses to distinguish

- **No listener:** sender has no bound port, so QR contains no usable endpoint.
- **Wrong endpoint:** sender advertises a VPN, cellular, virtual, loopback, or
  otherwise unreachable address.
- **Address-family mismatch:** listener binds IPv6-only while the QR advertises
  IPv4, or the reverse.
- **Permission/firewall block:** the endpoint is correct but the platform denies
  local-network or incoming traffic.
- **Hint loss:** the receiver parses `x.pe` but does not pass it to metadata
  inspection or acquisition.
- **Metadata-only failure:** the peer connects, but the substrate cannot obtain
  or parse the torrent descriptor.
- **Sender stuck "resolving metadata"/"publishing" indefinitely:** a publish/
  hash worker that only logs a failure and waits for the next external wake
  leaves the collection stuck forever with zero visible progress — see
  `flutter-rust-bridge`'s pitfall on background workers that only wake on
  `Notify` for the retry/backoff/status-surfacing fix (mirror the sibling
  receiver-side worker's pattern rather than inventing a new one).
- **Sender source vanished after publish:** a zero-copy source (local file,
  gallery/PhotoKit asset) later deleted, moved, or renamed leaves the
  collection permanently unseedable unless something periodically re-stats
  every published source — see `durable-lifecycle-debugging`'s "Recover by
  converting into an existing lifecycle branch, not by adding a new one"
  section for the full conversion recipe and edge cases (paused, draft,
  receiver-side collections).
- **Mobile publish looks stuck, then "seeding" but a second local-source
  verification pass runs with its own progress, and upload speed on the same
  LAN is implausibly slow (e.g. ~1.5MB/s):** this is not a network problem.
  It is redundant hashing over a slow platform media reader (iOS PhotoKit
  streaming an iCloud-optimized asset, Android MediaStore, etc.) — see
  `references/redundant-hash-on-slow-media-readers.md` for the double-hash
  mechanism and the fix direction (skip the torrent engine's own
  re-verification pass for content this device just hashed itself).
- **A peer connects, download runs fine, but upload from the seeding side
  stays pinned at 0 B/s the entire session — including two devices on the
  same LAN/Wi-Fi (e.g. iPhone → desktop):** before suspecting choking,
  rate limiting, or a peer-selection bug, check whether the session listener
  is TCP-only. Some peers (or some OS/router paths between two devices on the
  same network) only complete a working connection over uTP
  (BitTorrent's own congestion-controlled UDP transport) even though the TCP
  handshake and metadata exchange succeed enough to show "1 peer" and receive
  data — the asymmetry is real, not a red herring. In a librqbit-based
  backend this is one config line: `ListenerOptions.mode` set to
  `ListenerMode::TcpOnly` instead of `TcpAndUtp`. Switching it on is
  additive — librqbit's stream connector builds the uTP socket automatically
  once the listener creates one, existing TCP peers are unaffected, and it
  needs no new dependency (uTP is already a transitive crate). Rule out the
  cheaper causes first and in this order, since none of them require a code
  change: (1) an explicit upload rate limit set in app settings (defaults to
  unlimited, but confirm), (2) local service discovery / UPnP forwarding
  disabled, (3) on iOS specifically, confirm `NSLocalNetworkUsageDescription`
  **and** a `_xxx._udp` Bonjour service entry are both declared in
  `Info.plist` — UDP traffic is gated behind the local-network permission
  prompt same as TCP, and a missing `_udp` service entry means enabling uTP
  in Rust will not actually take effect on that platform.

## Android publication and SAF source-I/O diagnosis

Android collection publication already uses the shared Rust-owned hashing path:
`create_referenced_metainfo` reads `ContentLocation` sources and creates the
metainfo without copying media through Flutter. Do not duplicate the iOS
PhotoKit hasher merely because Android is stuck in `RetryingMetadata`; first
identify whether the Android-specific SAF reader is failing.

For Android `content://` sources, validate this boundary in order:

1. picker returns a stable non-negative `lengthBytes`;
2. URI permission is persisted for the application context;
3. `openFileDescriptor` succeeds;
4. descriptor metadata/length is usable, with picker length authoritative when
   the provider reports zero or a conflicting value;
5. random-access `read_exact_at` succeeds during Rust hashing;
6. generated metainfo is admitted to the torrent session.

Some `DocumentsProvider` implementations return pipe/proxy descriptors rather
than seekable files. If Rust's `read_exact_at` fails with `ESPIPE`, `Illegal
seek`, or an equivalent error, implement a native sequential SAF-reader
fallback at the Android adapter boundary; never copy the source into Flutter or
an unbounded cache. Add redacted diagnostics containing only the operation,
offset, and byte count, not the URI or media contents. The reusable evidence
matrix is in `references/android-saf-publication-diagnostics.md`.

## Android zero-copy preview and source-I/O boundaries

For Android SAF-backed media, keep the `content://` identifier as the source of
truth and route preview work through a native adapter. Flutter's `Image.file`
and `VideoPlayerController.file` cannot consume a content URI; grid videos
must not create full player instances merely to paint a first frame. Use a
bounded native decoder/cache and keep the full video controller only in the
viewer. Native decode requests need bounded worker concurrency, completed-byte
caching separate from in-flight futures, and lifecycle guards so activity
teardown cannot answer a destroyed Flutter channel or leave an unresolved
future cached forever. See `references/android-zero-copy-preview.md`.

The Rust Android source adapter has a separate resource boundary: do not reopen
an SAF descriptor for every torrent block, but do not retain one descriptor per
source without a process-wide bound. Use a bounded descriptor cache, avoid
holding its global lock across JNI/provider I/O, and preserve the picker length
when a provider reports an unknown zero `fstat` size. Never log the URI or media
path; log only a redacted source event. Keep this adapter behind Android cfg and
compile all Android ABIs after changes; Linux coverage cannot execute it.

## Platform-specific completion and background flow

Before moving a completion step off a transfer loop, map the platform's actual receive path.
receive path. iOS may synchronously import verified files into PhotoKit; that
must be dispatched outside the poller and its blocking FFI call must use a
blocking pool. Android's current flow is different: SAF `content://` URIs are
zero-copy source references, while received torrent bytes go to a filesystem
destination; there is no post-download MediaStore import to move off the
poller. Desktop platforms likewise use filesystem destinations. Do not add an
Android MediaStore copy or foreground service as a speculative analogue: first
prove that such a completion step exists and is the failing boundary. Treat a
future Android MediaStore writer/export as a separate native feature, with
explicit lifecycle, crash-retry, and zero-copy decisions.

When verifying cross-platform changes, run platform-relevant static/build gates
and report only concise tails/status for successful commands. Preserve full
failure output in a file or capture when diagnosing errors; do not flood the
conversation with complete build, coverage, or dependency logs.

## Completed receiver re-sharing

A receiver that reaches 100% must remain an active seeder and re-shareable through
QR, not merely appear `Available` in the projection. Trace this separately from
UI capability flags: `can_share` may be true while the active session has no
live torrent. After any completion-time storage rebind, preserve the exact
info-hash, selected-file intent, `overwrite: true`, and a valid fast-resume
bitmap. Only pre-seed all pieces when every file is selected and has just been
verified; partial selections must not advertise unowned pieces. Keep QR
readiness fail-closed for a missing listener, unloaded/mismatched torrent,
non-live torrent, or empty reachable peer list, but log which prerequisite
failed so "Not ready to share" is actionable rather than guessing or weakening
the gate. Add a regression test that exercises the real receiver-completion
path and then calls the Rust share operation, including the post-restart case
when session rehydration is involved.

## Pitfalls

- Do not infer the root cause from a generic "waiting for file list" screen.
  First classify the observed phase precisely: `ResolvingMetadata` with zero
  peers is bootstrap/metadata resolution, not payload download or gallery save.
- Do not claim a fix covers an adjacent phase merely because it touches the
  same collection. Match the observed state and failing boundary to the
  changed code, then say explicitly what remains unverified.
- Do not treat a QR scanner, deep-link import, or collection-row creation as a
  completed transfer.
- Do not retry speculative listener or IPv4/IPv6 changes without first checking
  the emitted listener and peer-hint diagnostics.
- Do not claim a cross-platform fix from Flutter tests alone; they cannot prove
  native camera, sandbox, local-network, or real peer reachability.
- If a requested ADR is being implemented and a target-platform compiler/build
  failure appears, stop the ADR slice, fix and verify that blocker first, and
  only then resume the ADR. Keep the blocker correction in its own focused
  commit when the user requested dedicated ADR/version commits.
- If the exact runtime logs are unavailable, ask for the smallest evidence set:
  sender share diagnostics, receiver resolution diagnostics, and the exact
  imported magnet with secrets and unrelated query fields removed.
- A QR source length and successful Flutter import prove only payload delivery.
  They do not prove the sender is reachable or that metadata handshake succeeded.
  For a private magnet, confirm the receiver's parsed `x.pe`, the supplied
  `initial_peers`, the sender's bound listener port, and the first connection
  error before changing librqbit transport or Android permissions. A typical
  bare BTIH plus one IPv4 `x.pe` is about 84 characters; treat that as a useful
  sanity check, not as proof of reachability.

## Reference

See `references/directional-transfer-diagnostics.md` for the evidence matrix and
reproduction recipe from a real QR-to-metadata investigation.

See `references/redundant-hash-on-slow-media-readers.md` when a mobile sender
looks stuck resolving/publishing, then shows a second "local source
verification" progress pass, with implausibly slow throughput on a real LAN —
this is a double-hash issue over a slow platform media reader, not a network
problem.
