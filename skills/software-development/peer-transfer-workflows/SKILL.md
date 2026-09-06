---
name: peer-transfer-workflows
description: "Use when a QR/link transfers content between device roles."
version: 1.0.0
---

# Peer Transfer Workflows

## Use when

Use this skill when a QR code, deep link, invite, magnet, descriptor, or similar handoff moves content between devices with distinct **sender** and **receiver** roles. It applies to peer-to-peer, local-network, cloud-assisted, and direct-transfer systems.

## Invariants

1. **Separate roles at the command boundary.** Sender commands publish content the local device owns. Receiver commands import metadata, resolve it, select it, and download it. A receiver must never invoke a sender-only publish command.
2. **Preserve source ownership.** Source media remains at its original sender-side location. Persist descriptors and metadata if needed, but do not copy, clone, or stage source media merely to publish it.
3. **Treat links as untrusted input.** Validate scheme, host/path, payload type, and durable identifiers before dispatching a command.
4. **Do not derive behavior from a UI label.** Trace the actual command sequence and the durable state transition. A mislabeled button can hide a correct command; a familiar label can hide a wrong one.
5. **Distinguish metadata resolution from payload transfer.** A descriptor may need to resolve before a receiver can select/download files. This is a normal asynchronous stage, not a reason to route into local sharing.

## Investigation workflow

1. Capture the exact payload and user-visible outcome.
2. Map the whole path: QR decoder or OS handoff → link parser → app controller → backend command → durable state → worker → UI projection.
3. Write down the allowed sender and receiver command sequences. Identify a receiver-side command that must never appear.
4. Build a tight regression around the command list, not just navigation or toast text.
5. Inspect whether metadata arrival needs a follow-up receiver command to start acquisition.
6. Check that live projections retain original source references rather than exposing a staging directory as media.

## Implementation pattern

```text
sender:   local sources → publish → descriptor/info hash → QR/link
receiver: QR/link → validate → import metadata → resolve descriptor
          → select intended entries → acquire/download
```

For an automatic receive handoff, start the follow-up selection/download only after the descriptor produces a non-empty selectable file list. Keep errors on the incoming collection route; never fall back to a local create/share path.

For a manual receive handoff, label the final action as **Download** or **Receive**, not **Share**, and dispatch a receiver command.

## Regression tests

At minimum, cover:

- valid link → import command with the decoded durable payload;
- resolved file list → selection/download command for the intended entries;
- forbidden sender-only publish command is absent from the receiver sequence;
- incoming UI says Download/Receive, not Share;
- source paths/media bytes are not copied or synthesized during publication;
- invalid/foreign link produces no backend command.

Use streams or a small fake repository to model asynchronous descriptor resolution. Assert command order explicitly.

## Verification

1. Run the focused link/command-sequence regression.
2. Run the focused receiver UI regression.
3. Run app analysis and the complete app test suite.
4. Run the backend acceptance suite when receiver commands cross the app/runtime boundary.
5. Rebuild and install a fresh sender/receiver app build for physical-device handoff testing. Do not report iOS/Android handoff as verified until it was exercised on-device.

## Pitfalls

- Reusing a generic `draft` state for both local publishing and remote receiving without role-aware UI actions.
- Treating an accepted import command as proof that payload transfer has started.
- Automatically copying a gallery/files asset into app cache to satisfy a path-only storage API.
- Encoding a process-local UI handle in a QR code instead of a durable descriptor identifier.
- Retrying a link by invoking publish, because it appears to wake a worker.

## Reference

- `references/portalis-collection-qr.md` — Portalis command map, test seams, and zero-copy constraints.
