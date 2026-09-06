# Portalis QR LAN Bootstrap

## Validated Contract

A Portalis collection QR is a two-layer value:

```text
portalis://import?magnet=<URL-encoded magnet>
```

The inner magnet needs both:

```text
xt=urn:btih:<40-hex-info-hash>     # content identity
x.pe=<private-LAN-IP>:<bound-port> # direct rendezvous
```

The `xt` value alone explains the observed iPhone state “Waiting for this torrent's file list” with zero peers: it says what content is wanted but offers no seeder endpoint. Same Wi-Fi is reachability, not discovery.

## Sender Path

- The sender exposes a share URI only after its substrate has a persisted torrent handle.
- Read the actual port using `librqbit::Session::tcp_listen_port()` after the engine session exists.
- Enumerate non-internal, private IPv4 addresses with `network-interface`.
- Combine each address with the actual bound port, deduplicate, cap at 64, and encode as repeated `x.pe` magnet parameters.
- Do not use the configured listener range or hard-code port 6881.

Relevant seam:

- `portalis/rust/backend/src/nexus/torrent.rs`: `magnet_for_share`, `local_peer_hints`, interface-to-peer conversion.
- `portalis/rust/backend/src/nexus/core/nexus.rs`: `share_uri` combines the persisted info-hash and live peer hints.

## Receiver Path

1. Decode and validate `portalis://import`.
2. Preserve its full inner magnet, including `x.pe`.
3. `peer_hints_from_source` parses endpoint hints.
4. `inspect_source` / `acquire_selection` merge source hints into librqbit `initial_peers`.
5. Receiver resolves metadata, then sends `downloadSelection`; it must never send `publishDraft`.

Relevant seam:

- `portalis/lib/app/collection_link.dart`
- `portalis/lib/app/collection_link_receiver.dart`
- `portalis/rust/backend/src/nexus/core/torrents.rs`
- `portalis/rust/backend/src/nexus/torrent.rs`

## Regression Coverage

- Share magnet encodes direct hints and receiver parser reconstructs them.
- Peer advertisements exclude loopback/public addresses and use the listener's actual port.
- Collection-link import dispatches `importTorrent → downloadSelection`, never publication.
- Torrent UI calls its process-local identifier **Local handle**, not info hash.

## Device Check

A QR scanned before the sender rebuilds lacks `x.pe` and cannot be repaired in place. Rebuild/restart the sender, generate a fresh QR, then scan it on the receiver. Accept iOS Local Network permission when requested.

## Zero-Copy Constraint

QR bootstrap stores only a content identifier and endpoint metadata. The Mac continues seeding original source locations. Mobile gallery/files sources must remain platform-native references and be read through native random-access adapters, never copied into cache or staging files.