# Directional transfer diagnostics

## Evidence matrix

| Stage | Sender-side evidence | Receiver-side evidence |
|---|---|---|
| Share | listener port; advertised `x.pe` endpoints | — |
| Import | — | exact parsed source and source hints |
| Metadata | sender is listening and serving the info hash | supplied hints passed to `inspect`; result/error |
| Acquire | seeding torrent is managed and reachable | `acquire_selection` receives the same hints |

A screen showing an imported collection with zero files means payload ingestion
worked but metadata resolution did not. A zero-peer state is not enough to tell
whether the endpoint was absent, malformed, unreachable, or discarded.

## Reproduction recipe

1. Use one small collection and record its info hash.
2. Test desktop → phone and phone → desktop separately.
3. Capture share logs on the sender and resolution logs on the receiver.
4. Compare the two `advertised_peers` lists and the receiver's
   `source_peer_hints`/`supplied_peer_hints`.
5. Only after the first differing boundary is known, write a seam regression
   test and change one component.

## Redaction

Keep the info hash and private LAN endpoint when they are needed to correlate a
run. Remove source file paths, tokens, credentials, unrelated query parameters,
and media content before sharing logs.
