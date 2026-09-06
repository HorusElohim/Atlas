# QR transfer reliability hardening

## Proven failure signature

A receiver that repeatedly logs a 30-second metadata timeout against an `x.pe`
endpoint is not necessarily parsing the QR incorrectly. Check the sender log
first. The decisive failure pattern is:

```text
admitting torrent with live session id=…
forget_torrent: info_hash=…
publisher completed …
share QR … direct_peer_hints=[sender-ip:port]
```

This means orphan cleanup removed a just-admitted zero-copy source torrent
before publication durably stored its collection handle. The QR can then name a
real listener port but no live torrent answers metadata.

## Ownership rule

A durable linked-source record is an ownership claim during publication. Orphan
cleanup must:

1. retain reported torrents whose info hash has a linked-source record;
2. retain rather than release when ownership lookup fails;
3. release only an unclaimed torrent with no durable linked-source record.

Test both the protected publication window and a genuine unclaimed torrent so
cleanup does not become permanently disabled.

## Receiver intent

A scanned Portalis QR must have the same staged selection contract as a pasted
magnet:

```text
import accepted -> metadata resolved -> entries displayed
-> person changes local selection -> explicit DownloadSelection -> acquire
```

Never start acquisition automatically merely because a QR resolved. If a UI
subscription race prevents a background auto-start from firing, remove the
automatic flow; do not violate selection intent to hide the race.

## Resolution/retry design

Keep retry state keyed by collection/info hash, not as one worker-wide delay.
For each failed metadata resolve, retain:

- attempt count;
- next eligible monotonic instant;
- error category/message;
- suppressed-repeat count for diagnostics.

Use capped exponential delays (for example 5, 15, 30, 60 seconds). Pending work
must skip a collection until its own deadline even if an unrelated worker wake
occurs. Clear its retry record immediately after resolve success. Surface
backend-owned state that distinguishes resolving, retrying/waiting for sender,
metadata-ready-for-selection, and user-confirmed downloading; do not overload
all of these as `Preparing`.

## QR readiness and endpoints

Generate a QR only when all conditions are true:

- persisted handle is a valid info hash;
- the local session is actively carrying that exact info hash;
- a TCP listener is currently bound;
- one or more validated non-loopback private LAN endpoints are available.

Advertise the actual bound port for every validated private endpoint, sorted,
deduplicated, and bounded. Do not use a configured range or assumed `6881`.
If readiness fails, return no QR with an actionable local diagnostic reason.

## Client identity

librqbit `SessionOptions.client_name_and_version` controls extended-handshake
client identity. Set it to `Portalis <backend-version>` at session creation and
verify the observed remote client string through a handshake-level harness, not
only an options-construction test.

## Diagnostic fields and device matrix

Log correlation fields at every boundary: collection handle, shortened info
hash, operation (`resolve`, `acquire`, `reconcile`), peer hints, attempt, and
next retry. Emit start/failure/backoff/recovery messages; suppress repeated
identical reconcile/no-op lines.

Physical verification must cover: fresh publish + scan; sender restart;
network/IP change; sender unavailable; denied local-network access; selection
staging before Download; mixed media; and an old QR after sender deletion.
