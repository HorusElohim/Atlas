# Dual magnet handling and librqbit 9 upgrades

## Preserve both import paths

Portalis has two independent rendezvous paths and changes must be additive:

- App-owned `portalis://import?magnet=...` links must preserve the complete
  inner magnet, including repeated `x.pe` direct-peer hints. Do not replace or
  regress the existing `decode_peer_hint` logic.
- Ordinary `magnet:?xt=...` links must retain DHT, `tr=` tracker, and `x.pe`
  discovery. They may additionally use a validated `xs=` `.torrent` metadata
  descriptor.

Test both forms independently. A passing `xs` test does not prove that the QR
path still supplies `initial_peers`, and a passing QR test does not prove that
ordinary magnets resolve metadata without a seeder endpoint.

A receiver message such as “waiting for this torrent's file list” means
metadata discovery has not completed; it is not yet a payload-transfer failure.
Log the boundary values: source peer hints, supplied peer hints, and the
selected metadata source.

## Safe `xs=` fallback

For a magnet with `xs=https://host/name.torrent` (or HTTP):

1. Accept only HTTP(S) URLs whose path ends in `.torrent`.
2. Fetch descriptor metadata only; do not fetch media payload bytes.
3. Parse the descriptor and verify its BTv1 info-hash equals the magnet's
   `xt=urn:btih:...` value.
4. Pass the verified descriptor bytes to the engine for inspection and later
   selected-file acquisition.

Keep normal DHT/tracker/direct-peer discovery as the fallback when no usable
`xs` exists.

## Vendored librqbit major upgrades

For a vendored, patched engine:

1. Inspect git history of the vendor directory to isolate Portalis patches
   before replacing upstream source.
2. Fetch the target crate into a scratch Cargo project and compare source trees
   before committing to the jump.
3. Replace the vendor tree wholesale, then re-apply only the isolated patches.
4. Read the new `SessionOptions` and metainfo types directly. In librqbit
   9.0.1, flat options moved into `listen`, `connect`, and `dht` sub-configs;
   `Session::tcp_listen_port()` became `announce_port()`; metainfo names and
   file iterators became infallible methods; `TorrentMetaV1.info` uses
   `WithRawBytes`.
5. Match every related dependency and feature to the vendored crate's own
   manifest. In this upgrade, reqwest 0.13 uses the `rustls` feature instead
   of `rustls-tls`, and librqbit companion crates moved to 9.0.1.
6. If an upstream setting disappears, document the compatibility behavior
   explicitly. librqbit 9 removed `defer_writes_up_to`; preserving the setting
   in the app while leaving it inert is preferable to silently pretending it
   still affects the engine.
7. Validate with the full project gate, not only `cargo build`: backend tests,
   protocol tests, coverage, Flutter analysis/tests, and a live network test
   for the real magnet when possible.

The Portalis 9.0.1 migration passed 215 backend tests, 90 protocol tests,
coverage, Flutter analysis, and 123 Flutter tests. The exact Cosmos Laundromat
magnet resolved six files through its live `xs` descriptor after the upgrade.
