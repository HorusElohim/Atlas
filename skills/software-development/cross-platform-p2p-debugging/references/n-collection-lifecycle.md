# N-Collection Lifecycle Reference

Use this reference when the first mobile↔desktop transfer succeeds but a second or later collection remains in a generic import/pending state.

## State boundaries

Treat sender and receiver as separate state machines:

```text
sender:
create/edit → durable local sources → publish/hash → torrent admission → seeding/share URI

receiver:
import URI/magnet → durable import → metadata resolve → file selection → acquisition → reconcile
```

A UI label such as `Torrent import` is not evidence of which machine failed. Capture the first missing transition on both sides.

## Required evidence

Correlate every transition with a durable collection key and torrent identity, but never log source paths or media contents:

```text
publisher starting: key, display name, source count, byte total
publisher substrate returned: key, info_hash, descriptor size
publisher completed/failed: key, revision or error
receiver resolve/acquire/reconcile: key, operation, info_hash when known, result/error
```

Interpretation:

- sender never returns an info hash → publication/source hashing/admission failure;
- sender completes with an info hash, receiver never starts resolve → receiver wake/classification failure;
- receiver resolve fails → peer hints/listener/metadata path;
- receiver resolves but acquisition does not start → selection/acquire/reconcile path;
- all transitions complete but UI stays pending → projection/state refresh bug.

## N-collection invariants

- The librqbit session is shared, but collection state, descriptors, handles, metadata namespaces, and transfer projections are per collection.
- A display name is not an identity. Use the computed torrent info hash (or durable collection key before hashing) for metadata/output namespaces.
- Local sources remain direct filesystem/gallery references. Torrent metadata and descriptors may be persisted; media must not be copied, cloned, hard-linked, staged, or cached as a second representation.
- Publication and import work must be durable and restartable. A wake is only a hint to rescan durable state; it must not be the sole location of pending work.
- A worker may process collections sequentially, but a collection created while another is busy must remain observable by the next scan.

## Wake design

For synchronous command boundaries, avoid a bounded `mpsc` wake channel whose `try_send` result is ignored. Prefer a lossless notification primitive such as `tokio::sync::Notify`, or explicitly handle closed/full states. Coalescing duplicate wakes is correct when the worker scans durable state; dropping the only wake because the worker has exited is not.

The worker loop should:

1. wait for a notification or shutdown;
2. scan all durable pending collections/imports;
3. process each pending item independently;
4. leave failures durable and logged with the collection key;
5. return to waiting, preserving notifications that arrived while work was active.

Do not solve this with sleeps, fixed retries, a second singleton session, collection-count-specific branches, or forced resume commands.

## Regression coverage

Add tests for:

- two distinct info hashes with the same display name producing distinct metadata namespaces;
- multiple durable collections being discovered by one scan;
- a notification arriving while another collection is active being observed on the next scan;
- sender publication and receiver metadata/acquisition remaining separate;
- restart/rehydration preserving each collection's identity and direct source references.

Automated tests do not replace a real iPhone↔macOS transfer. Report device validation separately.
