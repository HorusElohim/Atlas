# Owner seed lifecycle projection

Use this reference when a P2P collection UI conflates a locally published owner with a receiver import.

## State inputs

Keep these facts independent:

- **role/origin:** locally published owner vs remotely imported receiver;
- **intent:** draft, paused, selected;
- **durability:** original source references and persistent torrent/substrate handle;
- **engine activity:** initializing/source check, live transfer, idle, failed;
- **telemetry:** verified bytes, source-check cursor, uploaded bytes/rate, receiver bytes/rate, peers.

## Projection precedence

1. Draft and paused are explicit user decisions and outrank engine telemetry.
2. A published owner with durable original sources plus a durable torrent handle is `Seeding`, including before its first live engine reading after creation or restart.
3. A receiver with a carried unresolved or incomplete torrent follows receiver `Preparing`/`Downloading` semantics.
4. Verification or source-access failure needs a dedicated actionable error, never permanent generic preparation.

## Byte-accounting rule

`source_check_bytes` is a verification cursor. It may drive a source-verification progress bar, but must not populate the receiver's downloaded/on-disk-byte label. Preserve the actual receiver progress counter separately.

## Presentation matrix

| Scenario | Primary wording | Primary metrics |
| --- | --- | --- |
| Owner source verification | Verifying local source | source-check percentage; optionally source read rate |
| Owner idle/ready | Seeding / local source verified | verified local-source total; sharing readiness |
| Owner active upload | Seeding speed | upload rate, uploaded total, served peers |
| Receiver download | Receiving / downloading | selected total, received bytes, download rate, ETA, source peers |
| Receiver metadata or selection | Preparing / waiting | explicit cause and next action |
| Any failed source/verification | Needs attention | concrete reason and recovery action |

## Regression minimums

- Publish a linked/zero-copy owner and assert `Seeding`, not `Preparing` or `Downloading`.
- Reopen that owner before any live engine telemetry and retain `Seeding`.
- Feed an initializing source-check cursor and assert progress is visible without receiver byte labels.
- Feed upload-only owner activity and assert graph/header says `Seeding`, not `Receiving`.
- Feed a receiver with the same incomplete engine facts and assert receiver terminology remains intact.
