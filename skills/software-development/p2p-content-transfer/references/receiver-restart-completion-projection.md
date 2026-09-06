# Receiver completion projection after restart

## Problem class

A receiver can finish a QR/deep-link transfer, close the app, and reopen with verified bytes still present. The new process may rehydrate an old torrent or substrate handle before it obtains a live engine reading. That handle is only a process/session reconciliation hint; it is not evidence that acquisition is currently incomplete.

Projecting `Downloading` or `DownloadRequested` from that handle creates a contradictory UI: completed files paired with an active-receive state.

## Projection rule

Keep durable transfer moments separate from engine liveness:

1. Let explicit durable intent (`Draft`, `Paused`) retain its existing priority.
2. If the current process has a live engine reading, derive status from that reading; it is current evidence.
3. If no live reading exists and a receiver import has a durable completion moment, project it as available/completed.
4. Only then use a carried/rehydrated substrate handle to infer pending work.

Do not apply the durable-completion shortcut to hide a genuine current live reading that reports incomplete verification or acquisition.

## Regression shape

Build the smallest persisted receiver fixture containing receiver/member role, selected imported entries, a persisted substrate/torrent handle, and non-null `started_at`/`completed_at` moments. Open a fresh core instance without injecting a live engine reading and assert the collection is `Available` (or the product's completed state). Run it red against the old projection, then green after the precedence change.

This tests retained lifecycle truth; it is not an absence-only UI test.

## Related checks

- A current live incomplete reading still renders downloading.
- Paused and draft intent still outrank completion projection where the product defines them to do so.
- Reopening does not schedule a second receiver acquisition solely because a stale process-local handle exists.
