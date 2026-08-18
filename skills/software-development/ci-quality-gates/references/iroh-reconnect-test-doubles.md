# QUIC/Iroh Reconnect Test Doubles

## Failure pattern

A reconnecting client can hang indefinitely when a mock peer accepts only one connection. If the initial handshake times out under CI load, the supervisor retries against a peer that is no longer accepting. With an effectively unbounded retry policy and a short backoff, the process can spin at high CPU until the CI job timeout.

## Robust helper pattern

Make the peer accept loop reusable:

- Require the handler as `Fn + Send + Sync + 'static` rather than `FnOnce`.
- Store the handler in `Arc`.
- Loop on `endpoint.accept()`.
- Clone per-connection state inside the loop; `watch::Receiver` is cloneable.
- Spawn each connection handler separately so a deliberately blocking or waiting handler does not stop acceptance of later reconnects.

The failing regression test should also have a realistic handshake timeout. Keep the long request timeout if the assertion is specifically that disconnect—not request timeout—finishes the in-flight request.

## Verification discipline

Run the focused regression test first. Then run the complete test target. If the focused test passes but another pre-existing recovery test still fails, report that separately and do not broaden the patch speculatively.
