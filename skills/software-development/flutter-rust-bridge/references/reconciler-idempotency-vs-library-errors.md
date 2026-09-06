# Reconciler idempotency when the wrapped library isn't idempotent

## The bug class

A common Rust backend pattern for this codebase: a worker loop re-asserts
stored intent on every poll tick regardless of whether the last tick already
applied it ("pause if the stored state says paused, resume if it says
running"). This is deliberately idempotent by contract — the whole point is
that the reconciler doesn't need to remember what it last did, it just
asserts the truth every pass.

But the underlying library call it wraps is not always idempotent itself.
Example: `librqbit`'s `Session::pause()`/`unpause()` `bail!()` with
`"torrent is already paused"` / `"torrent is already live"` when called on a
torrent already in that state, instead of treating it as a no-op.

Result: every already-settled item (already paused, already running) fails a
fresh call on *every single poll tick, forever*. Nothing user-visible breaks
— the reconciler swallows the error and just retries — but the diagnostics
/ error log fills with a constant stream of `"torrent worker failed ...
torrent is already paused"` noise that buries anything actually worth
seeing. This is exactly the kind of thing a user spots first ("the logs show
errors that just pollute the diagnostics") even when nothing is functionally
broken.

## The fix

Check the live state before calling the library method, and short-circuit
when nothing would change:

```rust
async fn pause_handle(session: &Session, handle: &Arc<ManagedTorrent>) -> anyhow::Result<()> {
    if handle.is_paused() {
        return Ok(());
    }
    session.pause(handle).await.context("pausing torrent")
}

async fn restart_handle(session: &Arc<Session>, handle: &Arc<ManagedTorrent>) -> anyhow::Result<()> {
    if !handle.is_paused() {
        return Ok(());
    }
    session.unpause(handle).await.context("restarting torrent")
}
```

Extract the check into a small function that takes the live handle/session
directly (not the process-global singleton the public API function reaches
for). That's what makes it unit-testable against a *real* instance of the
third-party type without mocking the whole session.

## Testing it for real, not just with a fake

When the third-party library is embedded/vendored (not a network service),
prefer exercising the real state machine over a mock — mocks can silently
agree with a wrong assumption about when the library transitions state.

```rust
#[tokio::test]
async fn pausing_or_restarting_an_already_settled_torrent_is_a_quiet_no_op() {
    let session = librqbit::Session::new_with_opts(..., SessionOptions { dht: None, ..Default::default() }).await.unwrap();
    let collection = create_referenced_collection(session.clone(), ...).await.unwrap();
    let handle = session.get(id).unwrap();

    // Zero-copy/local sources need to finish their initial checking pass
    // before the library's internal state actually reaches Live — pausing
    // mid-check exercises a different code path (Initializing) than the one
    // the bug hit. Poll for the real target state rather than assuming it's
    // immediate.
    for _ in 0..200 {
        if matches!(handle.stats().state, librqbit::TorrentStatsState::Live) { break; }
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    }

    restart_handle(&session, &handle).await.expect("restarting an already-live torrent is a quiet no-op");
    pause_handle(&session, &handle).await.expect("pausing a live torrent pauses it");
    pause_handle(&session, &handle).await.expect("pausing an already-paused torrent is a quiet no-op"); // this is the actual regression
    restart_handle(&session, &handle).await.expect("restarting a paused torrent resumes it");
    restart_handle(&session, &handle).await.expect("restarting an already-live torrent is a quiet no-op");
}
```

Confirmed RED first by temporarily removing the `is_paused()` guard and
rerunning — the test panicked with the exact `"torrent is already paused"`
error text from the reported log, proving the reproduction was real before
trusting the fix.

## Generalizing

Any time a codebase's own contract documents "idempotent: asking for a state
the engine is already in is not an error" for a wrapper function, don't
assume the underlying call actually honors that — grep the vendored/wrapped
library source for the state-transition function and read what it does on
the "already there" branch before trusting the wrapper's doc comment.
