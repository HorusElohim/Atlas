# Runtime Listener and Trust Report

## Why this matters

A frontend/backend version match proves only compatibility of the loaded release
contract. It does not prove that the live distributed engine initialized. A
BitTorrent session that fails its TCP bind can leave imports queued, local
collections stuck in `Preparing`, and QR sharing apparently available while no
sender can seed or receiver can resolve metadata.

## Required startup sequence

Report these facts separately and in order:

```text
startup: frontend=... backend=... expected_backend=... compatibility=trusted
engine: session=starting listen_range=...
engine: session=listening bound_port=...
engine: worker=ready pending_work=...
```

Only the engine's returned bound port is valid for QR/direct-peer hints. Never
advertise `listen_port_start` merely because it is configured.

## Port-collision recovery

If the engine API accepts one listener port rather than a range, implement the
configured range at the application boundary:

1. Build fresh session options for each candidate port.
2. Try the start port first.
3. Retry the next port only for an explicit address-in-use bind error.
4. Log each rejected candidate and the selected actual port.
5. If all candidates fail, report the complete range and final bind error.
6. Do not silently disable the listener, direct bootstrap, or UPnP.

Fresh options may be necessary when session/connection option types are not
`Clone`; use small local factories rather than mutating or reusing moved values.

## Evidence interpretation

- `queued=true`: local admission only.
- `Preparing`: projection/state only.
- visible QR: an info hash and/or endpoint was rendered; it is not proof of a
  live seeder.
- `Address already in use`: diagnose session startup before peer hints, trackers,
  metadata, or UI selection.
- stale source path errors: correlate to the collection/source that owns them;
  remove or repair stale persisted work, but do not mistake it for a listener
  bind failure.

## Verification

On the target device, rebuild the native backend, restart the app, and require a
log showing the actual bound port before testing QR or directional transfer.
Then verify a simple local collection reaches sending/seeding before testing a
remote receiver. Host tests cannot prove the physical target path.
