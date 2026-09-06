---
name: cross-platform-qr-import
description: "Use for Flutter camera QR import flows across platforms."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [android, ios, macos, windows, linux, web]
metadata:
  hermes:
    tags: [flutter, qr, camera, deep-links, torrents, cross-platform]
    related_skills: [flutter-rust-bridge, systematic-debugging, test-driven-development]
---

# Cross-platform QR import flows

## When to use

Use when a Flutter application needs to scan QR codes containing deep links,
magnet URIs, invitations, or other app-routable payloads and then start an
existing import/download workflow across mobile and desktop targets.

## Design principles

- Keep QR decoding in the Flutter/platform layer unless the wire format itself
  changes. Do not add a bridge method merely to open a camera or decode text.
- Treat every scanned value as untrusted input. Validate the scheme, host, and
  payload before sending an import command to Rust or another backend.
- Reuse one import path for OS deep links, pasted links, and camera scans. The
  camera must not create a parallel flow with different ownership, selection,
  or download semantics.
- Distinguish received content from local content. A QR from another device
  must invoke import/download behavior, never local publication or seeding.
- Preserve zero-copy rules: scanning and importing metadata must never copy,
  clone, hard-link, or stage source media.

## Implementation workflow

1. **Trace the existing path first.** Locate the Share/add-source entry point,
   the QR generator, the deep-link receiver, the validated link parser, and the
   receiver-side command that starts selected content. Reuse those seams.
2. **Add the menu action to the existing source sheet.** This keeps Home and
   embedded layouts consistent and makes the action discoverable beside files,
   folders, and pasted magnets.
3. **Wrap the scanner in a route/future.** The scanner screen should return one
   validated payload after the first successful detection, stop/dispose its
   controller, and close cleanly on cancel.
4. **Support compatibility formats deliberately.** If older QR codes contain
   raw magnets while current codes contain an app URI, normalize both into the
   same validated magnet value before import.
5. **Start the existing receiver workflow.** For a torrent-like collection,
   import the magnet, wait for metadata through the detail stream, then send
   `downloadSelection` for selected entries. Do not call `publishDraft`.
   Once metadata resolves, keep the collection in explicit selection mode:
   render selectable file entries and a visible Download action. Do not route
   the resolved receiver through a completed/read-only collection presentation.
   Selection changes must remain staged locally until the user presses Download;
   the command must contain exactly the selected entry indices.
6. **Declare native permissions.** Add camera permission declarations and
   human-readable usage descriptions for Android, iOS, and macOS. On targets
   without camera support, keep the menu action visible if desired but show a
   recoverable availability/error state rather than crashing.
7. **Test the seam, not hardware.** Add a focused widget test asserting the
   Share/add-source sheet exposes the scan action. Keep parser tests for valid,
   invalid, and compatibility payloads. For a resolved torrent, also assert
   that file-selection controls and the Download action are present, that
   deselection is staged without starting acquisition, and that pressing
   Download forwards exactly the selected indices. Hardware camera and native
   permission behavior require device validation and must be reported
   separately.
8. **Verify efficiently.** Run `dart format`, the focused Flutter test,
   `flutter analyze`, and the full Flutter suite. FRB regeneration is not needed
   when no bridged Rust signature or DTO changes.

## Reference

- `references/portalis-qr-import.md` — Portalis-specific scanner, deep-link,
  permission, and receiver-flow details from a validated implementation.

## Pitfalls

- Adding a scanner that returns a process-local collection handle instead of the
  durable magnet/link payload.
- Importing a scanned QR through the local Share/publish path, which can make a
  receiver try to seed content it does not own.
- Duplicating validation in the scanner callback and deep-link receiver; keep
  one authoritative parser and call it from both paths.
- Forgetting to stop and dispose the camera controller after the first scan or
  when the route is popped.
- Claiming all-platform camera support based only on Flutter tests. Analyze and
  widget tests do not prove native camera permissions, plugin support, or a
  physical scan on every target.
