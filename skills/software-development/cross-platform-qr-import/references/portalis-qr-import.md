# Portalis QR import reference

## Validated payloads

The current Portalis QR generator wraps a magnet as:

```text
portalis://import?magnet=<encoded magnet>
```

The parser must require scheme `portalis`, host `import`, and a payload that
passes the existing magnet predicate. The scanner also accepts a raw `magnet:`
value for older QR codes. Normalize both forms to the magnet before dispatch.

## Existing Portalis flow

- `collection_link.dart` owns link wrapping and validation.
- `collection_link_receiver.dart` imports through `importTorrent`, waits for
  detail metadata, and sends `downloadSelection` for selected entries.
- `showAddSourcesSheet` is the shared Home/embedded Share entry point.
- `QrPeerHintScanner` owns the `mobile_scanner` controller and emits the
  normalized magnet after the first detection.

A camera-scanned collection is received content. It must never call
`publishDraft`; that path is only for local files owned by the current device.

## Native declarations

For camera targets, declare:

- Android: `android.permission.CAMERA` in the application manifest.
- iOS: `NSCameraUsageDescription` in Runner `Info.plist`.
- macOS: `NSCameraUsageDescription` in Runner `Info.plist`.

Flutter widget tests and `flutter analyze` do not establish native camera
permission or hardware behavior. Report physical device validation separately.

## Regression shape

The minimum UI regression asserts that the existing add/share source sheet
contains a stable `scanCollectionQr` key and labels the action as importing a
shared collection. Parser tests should separately cover valid Portalis links,
invalid hosts/schemes, and raw magnets.
