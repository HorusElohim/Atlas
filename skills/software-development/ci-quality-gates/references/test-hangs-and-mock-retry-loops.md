# Long-Running CI Test Hangs & Async Test Double Traps

When a CI job runs for hours without failing or printing errors, it is almost never a normal assertion failure or slow compilation. It is almost always an unbounded retry loop or deadlocked test double.

## 1. Diagnosing Multi-Hour Test Hangs

1. **Check CPU vs I/O State**:
   - High CPU (~95-100% spin): The process is in a tight retry/polling loop or busy-wait, not blocked on an idle await or deadlock.
   - Low/Zero CPU: The process is deadlocked waiting on a lock, channel receiver that never closes, or an unfulfilled future with no timeout.

2. **The Single-Accept Test Double vs Reconnect Supervisor**:
   - **Pattern**: A test spins up a mock peer/server to test a client disconnect or error condition, but writes the mock server to `accept()` only a single incoming connection.
   - **The Failure**: If the client has a retry/reconnect policy (`attempts: u32::MAX`, small backoff) and the initial connection or handshake experiences a transient timeout (common under slow CI runners), the client tries to reconnect. Since the mock server already consumed its single `accept()`, all subsequent reconnect attempts fail immediately or time out.
   - **Result**: The client reconnect supervisor loops forever in a tight retry cycle, consuming 100% CPU and blocking CI for hours.

## 2. Prevention & Fixes

- **Always loop on server/peer test doubles**: Mock servers must accept connections in a `loop { ... }` and spawn worker tasks per connection, matching real server semantics, unless the explicit goal of the test is verifying behavior against a dead socket.
- **Cap retries or apply test-level timeouts**: Tests verifying fault recovery should never configure unbounded retries without wrapping the test body in `tokio::time::timeout` or capping policy attempts.
