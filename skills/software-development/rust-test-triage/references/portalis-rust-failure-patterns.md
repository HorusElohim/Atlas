# Portalis Rust failure patterns

## Storage membership expectation

A first publication automatically inserts the owner into membership. A later
explicit grant adds another user. `list_share_members` returns deterministic
share-first/user-second key order, so an expectation may be `[OWNER, MEMBER]`,
not only the explicitly granted member. Trace `Collections::save_publication`
and `list_members` before changing assertions.

## Sync redb API accidentally made async

redb operations are synchronous. If a storage method contains no await, making
it `async` triggers `clippy::unused_async`. After reverting it to sync, search
all callers and remove stale `.await`; convert affected tests from
`#[tokio::test] async fn` to `#[test] fn` only when no await remains.

## Handshake timeout in client presence test

A test may pass in isolation while failing in the full presence suite. Treat
that as not reproduced in isolation. Re-run the exact suite before calling it
flaky; if context-only failure remains, inspect ephemeral-port reservation,
server bind/rebind lifecycle, and QUIC handshake timing.
