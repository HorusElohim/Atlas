# macOS mobile_scanner camera startup

## Symptom

The app shows `QR scanning not available on this device` on macOS even though the
machine has a camera. This can happen when the app performs a separate
availability probe before presenting the scanner.

## Root cause

`mobile_scanner` 4.x supports macOS through AVFoundation, but its controller
defaults to `CameraFacing.back`. The macOS native implementation maps that to
`AVCaptureDevice.Position.back` and searches for a built-in wide-angle camera.
The built-in Mac camera is exposed through the front/unspecified path, so the
probe can fail with no camera found. A second probe controller also adds a
separate permission/startup lifecycle that can reject a valid real scanner
surface.

## Working pattern

- Select the macOS-compatible camera facing explicitly when constructing the
  controller; retain the normal back-facing default on Android/iOS.
- Do not gate the scanner route on a second `isAvailable` controller probe.
  Present the real scanner and let its startup/error stream report failures.
- Stop and dispose the controller after the first decoded payload and when the
  scanner route is popped.
- Declare camera usage permissions in every native target that can invoke the
  scanner:
  - Android: `android.permission.CAMERA`
  - iOS: `NSCameraUsageDescription`
  - macOS: `NSCameraUsageDescription`

## Verification

Flutter widget tests can verify that the Share/add-source sheet exposes the
scanner action, and `flutter analyze`/`flutter test` validate the Dart seam.
They cannot prove native camera startup. On macOS, rebuild the app, allow
Portalis under System Settings → Privacy & Security → Camera, and perform a
physical scan. Xcode `DTDeviceKit` messages about a connected passcode-locked
iPhone are unrelated when the target is macOS.
