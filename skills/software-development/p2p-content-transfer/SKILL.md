---
name: p2p-content-transfer
description: "Use when P2P sharing needs discovery, QR, or transfer debug."
trigger: "Use when implementing or debugging P2P file/media transfer, QR bootstrap, direct peer hints, LAN discovery, or receiver-side download flows."
---

# P2P Content Transfer

## Purpose

Use this skill for peer-to-peer file or media transfer systems where one device publishes content and another receives it through a QR code, deep link, magnet, descriptor, LAN endpoint, tracker, DHT, or direct connection.

The central rule is to keep **content identity** separate from **rendezvous information**:

- An info-hash or content ID says **what** the receiver wants.
- A peer endpoint, tracker, DHT, or discovery service says **where** the receiver can find a seeder.
- Being on the same Wi-Fi does not provide rendezvous by itself.

## Non-Negotiable Invariants

1. **Zero-copy source ownership** — Never copy, clone, stage, or duplicate source media merely to publish it. Persist only metadata, descriptors, and endpoint hints.
2. **Sender/receiver separation** — A receiver imports and downloads remote content. It must never invoke sender-only publication actions against local sources.
3. **Truthful identity** — Do not label a process-local collection handle as a content hash, or an address as usable unless it is an actual routable endpoint.
4. **Validated bootstrap data** — Treat QR/deep-link inputs as untrusted. Validate scheme, content ID, endpoint address, port, cardinality, and private/public scope before handing them to the engine.

## Debugging Workflow

### 1. Build the transfer map

Write the actual path down before editing:

```text
sender sources → descriptor/info-hash → QR/deep link → receiver parser
→ rendezvous hints → engine initial peers → metadata resolution → selection → download
```

At every arrow, identify the value that crosses the boundary. Do not infer it from UI state.

### 1a. Separate metadata resolution from acquisition

A resolved file list proves only that the receiver learned the descriptor; it does
not prove that a download was requested. Instrument and inspect these boundaries
independently:

```text
import accepted → resolve started/completed → detail contains entries
→ receiver selected a non-empty entry set → DownloadSelection accepted
→ acquire started → substrate handle persisted → bytes move
```

For a report that says “metadata is correct but nothing downloads”, the first
falsifiable check is the log for `DownloadSelection` (or the equivalent
receiver command). If it is absent, do not debug peer connectivity or the torrent
worker yet: the failure is in the UI/link handoff or the detail subscription.
If it is present but acquisition is absent, continue at the backend lifecycle
and worker boundary. Log collection id, entry indexes, lifecycle, and command
acceptance at each boundary; otherwise a backend `resolve complete` line is
misleadingly easy to mistake for a successful transfer.

**Subscription ownership matters.** If the UI has a single active detail
projection/subscription, do not start a second background waiter before opening
the collection route and then let the route replace it. The route's established
detail stream is the authoritative source for displaying metadata and staged
selection. A sender-only log containing only `resolve complete` is not evidence
that the receiver can acquire bytes; inspect the receiver log or add a boundary
log before changing networking.

**Selection remains explicit.** A scanned Portalis collection must resolve into
the same staged selection experience as a manual torrent import: show metadata,
allow selections to change locally, and start only after the person presses
Download. Do not add automatic QR acquisition as a workaround for a missing
handoff; it violates receiver intent and obscures the real failure. Use
receiver-facing wording such as “Portalis collection import” rather than the
generic “Torrent Import” so product intent and command semantics cannot drift.

**Protect source admission from orphan cleanup.** A zero-copy owner torrent can
be admitted to the engine before publication persists its collection handle. An
orphan sweeper must treat a matching durable linked-source record as ownership
through that transaction window; otherwise it can forget the live seeder while
the QR still advertises its endpoint. If ownership lookup fails, preserve the
live torrent and log the uncertainty rather than destructively releasing it.
Regression coverage should assert that an unclaimed linked source is retained,
while an unclaimed torrent with no linked source is still released.

### 2. Diagnose “waiting”, “no peers”, or unresolved metadata

Check in this order:

1. Does the receiver have a valid content ID?
2. Does it have a discovery path: direct peer hint, tracker, DHT, or service lookup?
3. Does the engine receive those hints as its initial peers?
4. Is the sender actually seeding and listening on a bound TCP/UDP port?
5. Is that endpoint reachable from the receiver’s network and platform permissions?

A peer count of zero with an unresolved file list usually means the receiver has identity but no rendezvous path.

**Treat magnet `xs=` as a bounded optional hint.** Many ordinary public magnets
carry an HTTP(S) exact-source URL for the `.torrent` descriptor. It is an
optimization, not the magnet's sole discovery path. Bound that fetch separately
(a few seconds), verify its descriptor info-hash against `xt`, and on timeout,
HTTP error, parse error, or mismatch fall back to the original magnet so DHT,
trackers, and direct peers still run. Also ensure the *whole* metadata operation's
timeout encloses source preprocessing: in Rust, an awaited argument such as
`session.add_torrent(add_torrent_for(source).await?, ...)` is evaluated before a
`timeout(...)` wrapped around the session future, leaving the HTTP fetch
unbounded. Put both awaits inside the timed async block. Never log the full `xs`
URL; it can contain credentials or sensitive query values.

Pin this with deterministic local HTTP tests for both a non-success response and
a server that accepts but never responds, plus an ignored/configurable live test
that exercises an HTTPS exact source and an ordinary tracker/DHT magnet.

### 3. Bootstrap QR imports correctly

For in-person same-LAN sharing, include one or more direct peer hints in the inner P2P descriptor/magnet. Use the sender's:

- actual runtime listener port from the P2P engine;
- non-loopback, private LAN interface addresses;
- validated and bounded endpoint list.

Never derive a peer hint from a configured port range or a hard-coded conventional port. The configured range may not be the port the engine bound.

Wrap the descriptor in an app-owned deep link only for OS routing. Preserve the complete inner descriptor—including peer hints—through decode and validation.

**Advertise both address families, not just IPv4.** A peer-hint builder that
filters interfaces to `is_private()` IPv4 only silently drops every IPv6
address. On an IPv6-only or dual-stack LAN segment the receiver then gets no
usable hint at all and falls back to DHT/trackers — which a private, unlisted
collection has neither. This is the concrete shape of "same network, no
reason" stalls: the devices are reachable, but the QR never said how. Include
routable IPv6 (global/ULA) interfaces alongside private IPv4; deliberately
still exclude link-local IPv6 (`fe80::/10`) since it needs an interface scope
id most peer-hint encodings (`x.pe=`) cannot express, and an unscoped
link-local address is unusable to the receiver anyway.

**Gate QR generation on genuine live-share readiness, not mere presence.** A
torrent existing somewhere in the engine's session table is not proof it can
answer a peer right now — it may still be initializing, or paused, or have zero
usable direct-peer addresses to hand out. A readiness check that only asks
"is this info-hash loaded?" produces a QR that *looks* valid but names a sender
nobody can reach, which surfaces as intermittent "resolving metadata" /
"waiting for sender" on the receiver with no error on either side. Require, all
together, before producing a share QR: a bound listener, the exact torrent
hash loaded, the torrent actually live (not initializing/paused), and at least
one non-empty direct-peer hint. Fail closed (no QR / an explicit unavailable
state) rather than emitting a hopeful one.

### 4. Keep receiver actions receiver-only

A collection QR should follow this sequence:

```text
import remote descriptor
→ wait for metadata/file list
→ select intended entries
→ issue receiver-side download selection
```

It must not call a sender-only `publish`, `publishDraft`, or equivalent action. If manual imports require file selection, use a receiver-specific action label such as “Download selected files,” never “Share.”

### 5. Stage manual selections until explicit download

A receiver selection screen is a local editing surface, not an implicit transfer trigger:

```text
metadata/file list → locally stage checkboxes → explicit Download
                  → one receiver download-selection command → acquisition
```

- Toggling a file before the first download must update only presentation-local staged state. Do not dispatch a receiver command, wake an acquisition worker, or alter a durable selected set from a checkbox tap.
- Render the staged state immediately (including skipped/deselected affordances) so the person can inspect the exact final set.
- The Download button dispatches one complete, sorted selection—not a delta—and is the only action that may start a draft import.
- After a torrent is already running, selection revisions may be sent to the engine so it can reconcile the active transfer. Preserve this distinction between **draft staging** and **live revision**.
- Regression coverage must prove: a checkbox tap emits no command; Download emits exactly one receiver download command with the staged entries; the backend acquires only those file indexes.

### 6. Test before platform handoff

Create deterministic tests before changing implementation:

- share payload encodes direct endpoint hints;
- receiver parser reconstructs the exact endpoint list;
- engine bootstrap receives those peers;
- a collection-link/import flow sends import then download-selection, never publication;
- UI labels local handles, content hashes, and peer state honestly.
- When retiring an unsupported control or API, tests the retained receiver workflow and its invariants rather than merely asserting the retired label or symbol is absent.

Then rebuild both devices and scan a **fresh** QR. Old QR values cannot acquire newly added metadata.

## Received Media Handoff to a Native Gallery

When a receiver's product policy is to place completed photos and videos into the native gallery automatically, model this as a **per-entry durable transition**, never as a collection-level toggle:

```text
verified receiver file → native gallery import/move → durable native reference
→ storage adapter rebinds the same torrent entry → no repeat download on restart
```

1. Trigger only after the engine reports the specific file as hash-verified and complete; never react to fetched/network byte counts.
2. Use an explicit image/video allow-list. Leave unsupported entries (documents, archives, etc.) in Portalis storage even when they share a collection with supported media.
3. Persist the native reference per imported entry (`phasset://<localIdentifier>` on iOS; `content://…` on Android), not merely a boolean that an entire collection was exported.
4. Re-register the **same collection** against a hybrid storage adapter: gallery-backed entries must be random-readable for resume/seeding, while app-folder entries remain writable for future selection/download work.
5. Do not replace a mixed collection with a read-only gallery-only storage factory; that breaks downloads of unsupported or previously unselected entries.
6. Treat PhotoKit/MediaStore completion and durable persistence as a recovery boundary. If the platform move succeeds but Portalis crashes before recording the reference, recovery must reconcile the native asset instead of blindly re-downloading or duplicating it.
7. When the platform API cannot atomically commit both the gallery asset and Portalis' durable reference, import/copy first, persist and rebind the native reference, then remove the app-local source last. Do not use a direct source-file move before the collection has been rebound unless a durable native-operation journal can recover the returned asset identifier.
8. Preserve incomplete receiver intent during a rebind: source records need declared torrent lengths and an explicit allowance for intentionally unselected/missing filesystem files. A hybrid adapter must read gallery references but continue to write filesystem-backed entries when a person selects them later.

See `references/received-gallery-hybrid-storage.md` for the receiver-storage and recovery checklist.

Verify this path on a physical device with: a media-only collection, a mixed media/document collection, denied library permission, interrupted import, app restart, and a subsequent re-download/seed check. A Linux test can validate the durable transition and planner, but cannot validate PhotoKit or MediaStore behavior.

## Transfer Timeline and Telemetry

When presenting P2P receive/upload history, make the transfer core—not the UI clock—the authority for timestamps and inactivity:

1. **Known zero is data.** If the engine sampled an interval and no receive/upload bytes moved, render its actual duration at `0 B/s`.
2. **Unknown is not zero.** App suspension, a backend restart, sampling failure, or pruned/unavailable history must render as a visual gap, never as fabricated inactivity.
3. **Default to the whole retained session.** Do not replace a truthful all-history view with a short live window. Offer zoom as an optional detail view.
4. **Store semantic segments, not repeated zeros.** Extend one `observed-zero`/`waiting`/`paused` segment across identical ticks; preserve phase boundaries and close with a terminal zero at completion.
5. **Render to the viewport budget.** Keep raw recent samples for detail, but serve all-history graphs as first/min/max/last (M4-style) envelope buckets sized to the chart width. Always retain segment boundaries; they carry pause, waiting, and gap semantics.
6. **Never synthesize a `now` sample in Flutter.** The backend must provide the current observed endpoint. A UI-created timestamp can stretch the x-axis and visually compress valid earlier history.

Tests must cover a known zero interval, an unknown gap, a terminal zero, and a short burst preserved by all-history aggregation. See `references/transfer-timeline-telemetry.md`.

## Owner Lifecycle and Truthful Transfer Presentation

Model **ownership/role** separately from **engine activity**. A published zero-copy owner already owns the original source bytes; an imported receiver does not. Engine startup, rehydration, or source verification must never erase that distinction.

1. Give published owners an explicit `Seeding`/sharing-ready lifecycle state once their durable source references and torrent handle exist. Do not project them as receiver `Preparing` or `Downloading` merely because a live engine reading has not arrived yet.
2. Retain the engine's source-check cursor separately from received/on-disk bytes. While a linked source is being verified, present it as local-source verification progress—not downloaded payload progress.
3. Keep user intent authoritative: `Draft` and `Paused` outrank engine activity. Treat verification failures or unavailable source references as actionable errors, rather than leaving a collection indefinitely in a generic preparing state.
4. Make presentation phase-specific:
   - **owner verifying:** source-verification percentage and local-source wording;
   - **ready/idle seed:** verified local-source total and sharing readiness;
   - **active seed:** uploaded bytes/rate and served peers, labeled seeding;
   - **receiver:** received/selected bytes, receive rate, ETA, and source peers.
5. Add regressions for fresh owner publication, owner restart before the first live reading, source verification, idle seeding, and active upload. Assert both status semantics and UI wording so a receiver-style `0 B of total` display cannot return unnoticed.
6. **Completed receiver restart:** a durable receiver completion timestamp is authoritative during hydration when the live engine has not produced a fresh reading. A persisted, process-local substrate handle alone must not reclassify verified content as `Downloading` or `DownloadRequested`. A current live reading may supersede the durable snapshot if it proves different active work.

See `references/owner-seed-lifecycle-projection.md` for a condensed Portalis-style state/projection checklist and `references/receiver-restart-completion-projection.md` for the receiver restart precedence and regression seam.

## Presenting Peers Without Inventing Identity

A swarm peer carries no signed identity. Its address names a socket, and any
client name it announces is a string it chose. What you *can* vouch for is what
your own engine measured: bytes exchanged and current rates. Build the surface
around that asymmetry.

1. **Never pool verified contacts and anonymous peers into one list.** A person
   whose fingerprint was compared out of band and an address in a swarm are
   different kinds of thing. Give them separate sections with visibly different
   shapes — a stranger must never wear a contact's card, avatar, or verification
   badge.
2. **Lead a peer row with the address**, since it is the only element the
   device can confirm. Render a self-reported client name as an explicit claim
   (`reports qBittorrent 4.6`), never in the identity position.
3. **Do not attribute bytes to people.** Neither engine attributes transfer to a
   signed identity: a collection knows what it moved, not which member consumed
   it. A contact card showing a collection total wearing a person's name is a
   fabricated attribution. Byte figures belong on the connection, where they are
   measured.
4. **Measure peer rates between polls, not over the connection's lifetime.** A
   lifetime average keeps claiming a peer is working long after it went quiet.
   A peer seen for the first time has no prior sample, so it reports no rate
   rather than its whole connection compressed into one tick.
5. **Distinguish the real states.** *Moving* (show rates), *connected but idle*
   (say so — it is common and truthful), and *has exchanged nothing* are
   different. Showing a stale rate for a quiet peer is the same class of error
   as fabricating inactivity in a timeline.
6. **One connection per collection.** The same address connected for two
   collections is two connections; a flat parent/child pair preserves that.
   Merging them invents a single relationship the protocol does not have.

Pin with tests that a connection never renders a verification badge, that an
idle peer says idle rather than showing a rate, and that a self-reported name
appears as reported.

## Platform Considerations

- On iOS, declare local-network usage and handle the permission prompt. Use registered app URL schemes only for opening the app; the P2P engine still needs a real peer endpoint.
- On Android, do not substitute cache-file copies for gallery, MediaStore, or SAF sources. Add native random-access adapters for URI-backed media.
- For native galleries/files, retain platform references and read the original asset in the P2P storage adapter.

### Android: rule out engine session startup before chasing per-source I/O

If **every** publish and every resume attempt on Android gets stuck retrying
forever (e.g. `RetryingMetadata`) with no exceptions and no partial progress —
not just the collections that use a particular tricky source — suspect the
torrent engine's *session construction* itself before chasing SAF descriptors,
permissions, or hashing. Many Rust BitTorrent engines (e.g. librqbit) pick a
default DHT/session persistence path via the `directories` crate when the
caller leaves it unset, and that crate resolves through `HOME`/XDG environment
variables. Android app processes never set those (no real home directory or
passwd entry in the sandbox), so the lookup returns `None` and every session
construction fails identically, logging something like `cannot determine
project directory for com.<engine>.<component>`. This surfaces exactly like a
per-source publication failure (same generic retry state) but actually blocks
every collection on the device, because the whole session never comes up.

Diagnose by capturing the engine's own redacted logs (mirror them to Android
Logcat under a stable tag if they are not already visible there) and grepping
for "project directory"/"cannot determine" before assuming a SAF read or
hashing cause. Fix by explicitly pointing the persistence config's file path at
the app's own already-platform-safe state directory (the same one
settings/collections state already uses successfully) instead of leaving it
unset for the library to guess one via environment variables that don't exist
on the platform.

## Verification Checklist

- [ ] Sender is actively carrying/seeding the collection.
- [ ] Sender has a real bound listener port.
- [ ] Fresh QR contains a valid content ID and direct peer hints when using LAN bootstrap.
- [ ] Peer hints include routable IPv6 LAN interfaces alongside private IPv4, not IPv4 only.
- [ ] QR generation checks the torrent is genuinely live (not merely loaded/initializing/paused) before producing an endpoint.
- [ ] Receiver parser preserves the hints.
- [ ] Receiver observes a nonzero peer or a concrete connection error rather than an unexplained wait.
- [ ] Receiver sends download-selection, never sender publication.
- [ ] No media source bytes were copied to make publication/discovery work.
- [ ] Relevant unit, integration, and device tests have passed.

## Common Pitfalls

- **“They are on the same network.”** This is network reachability, not discovery. Carry an endpoint or use an actual discovery mechanism.
- **Hard-coded `6881`.** The P2P engine may bind another available port in its configured range.
- **Raw info-hash QR.** It may identify the swarm without giving a private receiver any route to it.
- **IPv4-only peer hints.** Filtering interfaces to private IPv4 silently drops IPv6, leaving IPv6-only/dual-stack LANs with no usable hint at all — the receiver hangs with no error. Advertise routable IPv6 too (see §3).
- **“Loaded” treated as “ready.”** A torrent present in the session is not necessarily live, unpaused, or reachable. QR generation needs a positive live-share check (listener bound + torrent live + ≥1 peer hint), not just “does this info-hash exist.”
- **Overloading drafts.** A local unpublished collection and a remote unresolved import are different workflows; never reuse sender terminology for receiver actions.
- **Copying to solve permissions.** Staging bytes creates storage and ownership bugs. Fix the native random-access source adapter instead.
- **Testing only parsing.** A valid QR parser proves nothing unless the endpoint reaches engine initial-peer configuration.
- **Re-resolving metadata the receiver already has.** If `inspect`/resolve already returned the immutable descriptor, pass it straight into the acquisition step instead of re-deriving it from the magnet a second time — it costs an avoidable swarm round-trip and adds latency to every QR-initiated download.
- **Treating `xs=` as mandatory or timing only the engine call.** A stale exact-source URL can return errors forever or hang before DHT/trackers are attempted. Bound it, fall back to the original magnet on every failure class, and place source preparation inside the overall metadata timeout rather than awaiting it as a timeout argument.

## References

- `references/portalis-qr-lan-bootstrap.md` — validated Portalis seam, regression cases, and zero-copy constraints.
- `references/qr-reliability-hardening.md` — publication/orphan race evidence, retry-state design, share-readiness gates, and verification matrix.
