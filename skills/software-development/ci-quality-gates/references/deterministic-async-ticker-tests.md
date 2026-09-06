# Testing Background Tickers Deterministically (and Proving You Caused a Coverage Regression)

For a spawned `tokio::spawn(async move { loop { interval.tick().await; ... } })`
ticker that periodically writes derived state (progress bars, health snapshots,
reconnection status) into a shared projection. Two problems recur together:
the ticker's write-path closures are invisible to coverage because no test runs
long enough to observe a real tick, and any test that tries via `tokio::time::sleep`
is slow and flaky.

## 1. Prove the regression is yours before you fix it (don't guess)

When a coverage/lint gate fails after a session's changes, do not assume the
uncovered items are pre-existing debt (see `uncovered-line-triage.md`) or
assume they're new — check mechanically:

```bash
git stash                                   # or: git worktree add
git checkout <pre-session-commit> -- <changed paths>
bash tests/nexus.sh > /tmp/baseline.log 2>&1  # run the exact CI script
git checkout <head-commit> -- <changed paths>
git stash pop

sed -n '/Uncovered functions/,/Uncovered lines/p' /tmp/baseline.log > /tmp/base.txt
sed -n '/Uncovered functions/,/Uncovered lines/p' /tmp/ci.log       > /tmp/ci.txt
diff /tmp/base.txt /tmp/ci.txt
```

A clean `diff` naming exactly your new closures (mangled Rust names like
`_RNCNCNCNvNtNt...publish_pending_collections0s1_0Bb_` are fine to leave
mangled — the file path above them is enough to locate the code) is proof, not
a guess. This also stops you from writing tests for unrelated pre-existing
gaps that were never your responsibility this session.

## 2. Give the test double a release gate, not a sleep

Don't add a fixed `tokio::time::sleep(Duration::from_millis(900))` to a test
double to "hold it open long enough for a tick to fire." That is exactly the
pattern a user correction targets ("remove this delay, add real coverage") —
it's slow (seconds per test run), and it's still a race: the delay only needs
to be *probably* longer than one interval, so it stays flaky under CI load.

Instead, add an explicit `tokio::sync::Notify`-gated hold to the double, and a
method the test calls when ready to let it proceed:

```rust
pub(crate) struct Recorded {
    // ...
    hold_while_hashing: Mutex<Option<Arc<tokio::sync::Notify>>>,
}

impl Recorded {
    pub(crate) fn publishing_held(info_hash: String, descriptor: Vec<u8>) -> Self {
        Self {
            publication: Mutex::new(Some((info_hash, descriptor))),
            hold_while_hashing: Mutex::new(Some(Arc::new(tokio::sync::Notify::new()))),
            ..Self::default()
        }
    }
    pub(crate) fn release_publish(&self) {
        if let Some(notify) = self.hold_while_hashing.lock().unwrap().as_ref() {
            notify.notify_one();
        }
    }
}

// in the trait impl the worker actually calls:
progress.set_stage("hashing");
if let Some(notify) = self.hold_while_hashing.lock().unwrap().clone() {
    notify.notified().await;   // waits until the test calls release_publish()
}
progress.set_stage("seeding");
```

## 3. Drive the ticker with a paused, hand-advanced clock — never wall-clock sleep

```rust
#[tokio::test(start_paused = true)]
async fn ticker_reaches_the_projection_mid_publish() {
    // ... start the worker with the held double ...
    tokio::task::yield_now().await;                       // let the publish task register its stage
    tokio::time::advance(Duration::from_millis(600)).await; // past the ticker's 500ms interval
    tokio::task::yield_now().await;                       // let the woken ticker actually run and write

    assert_eq!(projection.stage_for(collection), Some("hashing"));

    substrate.release_publish();   // let the publish finish so cleanup doesn't race teardown
    // ... await final settled state with a real tokio::time::timeout (unaffected by the pause
    //     once the paused runtime's virtual clock is what everything is waiting on) ...
}
```

Requires the `tokio` dev-dependency to enable `test-util` (`features = ["test-util"]`).
This test is instant in wall-clock time (no sleep at all) and deterministic: the
ticker's `interval.tick().await` cannot fire until `tokio::time::advance` moves
the virtual clock past its period, so there is no race window.

## 4. Cover the abort/cleanup path too, not just the write path

A ticker spawned to report on one operation must be aborted on every exit from
that operation (success, failure, AND early-shutdown/cancellation) — not just
the wall-clock-timeout path most people remember. A ticker that outlives its
operation can rewrite state the completion handler just cleared, on its very
next tick, silently resurrecting a stale status forever. Write two tests: one
that proves the ticker's write reaches the projection while genuinely in
flight (this file), and one that proves nothing writes after the operation
ends (`tokio::time::advance` well past several ticker periods post-completion,
assert the field is still cleared).
