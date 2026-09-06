---
name: cross-platform-camera-debugging
description: "Use when Flutter camera plugins fail on native targets."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [android, ios, macos, windows, linux, web]
metadata:
  hermes:
    tags: [flutter, camera, permissions, macos, native-debugging, plugins]
    related_skills: [cross-platform-qr-import, systematic-debugging, test-driven-development]
---

# Cross-platform Flutter camera/plugin debugging

## When to use

Use when a Flutter camera, barcode, QR, microphone, or other native plugin
renders its route but fails to initialize hardware, shows a black preview, or
reports an availability error on one platform.

## Core rule

Do not infer native support from Dart compilation or widget tests. Treat the
resolved plugin version, native implementation, platform permissions,
sandbox/entitlement configuration, and physical device behavior as separate
verification layers.

## Workflow

1. **Capture the exact symptom.** Distinguish route/navigation failures,
   permission-denied failures, no-device failures, black textures, and native
   build warnings. Read screenshots and logs for the plugin's own error state.
   Keep unrelated host/device warnings separate; for example, an Xcode
   passcode-locked iPhone service warning is not evidence of a macOS camera
   failure.
2. **Inspect the resolved dependency.** Run `flutter pub deps` and inspect the
   resolved package source under `.pub-cache`. Check the platform plugin
   registration, native camera selection, API defaults, and fallback behavior.
3. **Research current upstream behavior.** Search the package's official docs,
   changelog, source, and issue tracker before writing a workaround. Prefer a
   maintained release that fixes platform behavior over patching a stale version.
   Record the relevant upstream URL and the exact version decision.
4. **Audit native configuration.** Check usage-description keys in each target's
   `Info.plist`/manifest. For sandboxed macOS, check both Debug and Release
   entitlements, including `com.apple.security.device.camera = true` when the
   app accesses cameras. Rebuild after changing entitlements because an old app
   bundle can retain the previous signing/configuration.
5. **Avoid duplicate probes.** A second controller created only to test
   availability can race permissions or select a different camera path than the
   real UI. Prefer opening the actual scanner and routing its startup errors to
   the user, unless the plugin explicitly requires a probe.
6. **Use platform-specific defaults deliberately.** Desktop camera enumeration
   may expose devices differently from mobile. Inspect the native selector
   before choosing `front` or `back`; use the plugin's documented fallback where
   available rather than assuming mobile-facing semantics.
7. **Validate in layers.** Run formatting, static analysis, focused widget/parser
   tests, and the full Flutter suite. Then perform a native build and physical
   camera/scan test on every claimed target. State Linux-only validation and
   native validation separately; never claim a camera fix is complete from
   `flutter test` alone.
8. **Preserve application semantics.** For QR import flows, pass scanned values
   through the existing validated deep-link/magnet parser and receiver workflow.
   Do not create a second import path, publish received media, or copy source
   media merely to make scanning work.

## macOS checklist

- `NSCameraUsageDescription` exists in the macOS Runner `Info.plist`.
- `com.apple.security.device.camera` is true in Debug and Release entitlements.
- The resolved plugin version has a current AVFoundation macOS implementation.
- Camera permission is enabled under **System Settings → Privacy & Security →
  Camera** for the rebuilt app bundle.
- The app is rebuilt after dependency and entitlement changes.
- A real camera preview and physical QR scan are tested on the Mac.

## Native image and media-preview extension

The same layered method applies to native image previews. First trace the
actual source identifier passed by the grid, not just the file extension. On
iOS, Photos-library selections may intentionally use opaque `phasset://<local
identifier>` references rather than filesystem paths. Never pass those values
to `URL(fileURLWithPath:)` or a filesystem image decoder. Branch to PhotoKit's
`PHImageManager` and request a bounded preview, returning encoded bytes to
Flutter in memory. Keep ordinary filesystem paths on the existing ImageIO
path, and preserve zero-copy source ownership: preview generation must not
copy the original asset or write a cache file. See
`references/ios-media-preview.md` for the validated Portalis pattern.

## Common pitfalls

- Treating a package's pub.dev platform badge as proof that a specific release's
  native camera selector works on the target OS.
- Adding only `NSCameraUsageDescription` while forgetting the macOS sandbox
  entitlement.
- Keeping an old preflight availability controller that fails before the real
  scanner can request permission.
- Passing opaque PhotoKit identifiers into filesystem APIs, causing silent
  thumbnail fallback even though full-screen native preview works.
- Returning more than once from asynchronous PhotoKit callbacks; guard the
  Flutter method-channel result if the platform API can deliver degraded and
  final images.
- Reporting unrelated Xcode device-service warnings as the root cause.
- Saying "fixed" after `flutter analyze` and tests pass without a native build
  or physical camera/preview result.

## References

For the Portalis-specific QR import and `mobile_scanner` history, consult the
existing `cross-platform-qr-import` skill and its `references/` files. This
skill intentionally remains class-level so it can guide camera, barcode, and
other native plugin investigations beyond QR imports.
