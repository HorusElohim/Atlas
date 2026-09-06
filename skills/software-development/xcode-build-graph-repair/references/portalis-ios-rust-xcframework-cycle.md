# Portalis iOS: Rust XCFramework dependency cycle (worked case)

Branch `future-v0.7.0`, repo `PortalisApp`, file
`portalis/ios/Runner.xcodeproj/project.pbxproj`. Fixed in commit
`🐛 fix: break iOS Xcode dependency cycle`.

## Symptom

Every entry point failed identically — `./tool/run.sh ios --release --device Atlas`,
`./tool/build.sh ios --release`, and bare `flutter run -d Atlas --release`:

```
Error (Xcode): Cycle inside Runner; building could produce unreliable results.
→ Command: ProcessXCFramework
    portalis/ios/Frameworks/backend.xcframework
    portalis/build/ios/Release-iphoneos/backend.framework ios
○ That command depends on command in Target 'Runner': script phase "Build Rust (iOS)"
```

Trigger was a `cargo clean` (removed 20556 files, 6.7GiB) which deleted
`ios/Frameworks/backend.xcframework`. That directory is gitignored
(`portalis/.gitignore:72: ios/Frameworks/*`) and never tracked, so with the artifact
gone Xcode had to evaluate the real graph. The cycle was latent, not introduced by
the upgrade the user suspected.

## The defect in the project file

The Runner native target's `buildPhases` contained both:

- `A1B2C3D71A2B3C4D5E6F7081 /* Build Rust (iOS) */` — runs
  `bash "$SRCROOT/Runner/build_rust_ios.sh"`, which ends with
  `xcodebuild -create-xcframework ... -output ios/Frameworks/backend.xcframework`
- the linked + embedded reference `A1B2C3D51A2B3C4D5E6F7081 /* backend.xcframework */`
  (in `Frameworks`, in `Embed Frameworks` with `ATTRIBUTES = (CodeSignOnCopy, )`)

Producer and consumer in one target.

## Objects added (UUID family `A1B2C3E*`)

| UUID | isa | purpose |
|---|---|---|
| `A1B2C3E01A2B3C4D5E6F7081` | `PBXAggregateTarget` | `RustBackend`, sole phase = the moved `Build Rust (iOS)` |
| `A1B2C3E11A2B3C4D5E6F7081` | `XCConfigurationList` | for RustBackend |
| `A1B2C3E21/E31/E41...` | `XCBuildConfiguration` | Debug / Release / Profile |
| `A1B2C3E51A2B3C4D5E6F7081` | `PBXContainerItemProxy` | proxyType 1 → RustBackend |
| `A1B2C3E61A2B3C4D5E6F7081` | `PBXTargetDependency` | added to Runner `dependencies` |

Each aggregate configuration carries:

```
CODE_SIGNING_ALLOWED = NO;
CODE_SIGNING_REQUIRED = NO;
IPHONEOS_DEPLOYMENT_TARGET = 15.0;
PRODUCT_NAME = RustBackend;
SDKROOT = iphoneos;
SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
```

`IPHONEOS_DEPLOYMENT_TARGET` matters: `build_rust_ios.sh` reads it and re-exports it
into `CARGO_TARGET_AARCH64_APPLE_IOS_RUSTFLAGS` as `-C link-arg=-miphoneos-version-min`.
Dropping it would silently regress the SDK floor for aws-lc-sys / PhotoKit objects.

Also edited: `A1B2C3D71A2B3C4D5E6F7081` removed from Runner `buildPhases`;
`A1B2C3E01A2B3C4D5E6F7081` added to `PBXProject.targets`.

## Verified result

`Runner.xcscheme` already had `buildImplicitDependencies = "YES"`, so no scheme change
was needed. `scripts/dump_xcode_targets.py` output after the edit:

```
RustBackend | PBXAggregateTarget | deps: []
    - PBXShellScriptBuildPhase Build Rust (iOS)
RunnerTests | PBXNativeTarget    | deps: ['Runner']
Runner      | PBXNativeTarget    | deps: ['RustBackend']
    - Check Pods Manifest.lock / Run Script / Sources / Frameworks
    - Resources / Embed Frameworks / Thin Binary
    - [CP] Embed Pods Frameworks / Sign Embedded Frameworks
```

Balance + dangling-ref check clean (only `97C146E51CF9000F007C117D`, the `mainGroup`,
flagged — a known false positive of the heuristic).

## Constraints honored

Per the user's standing requirement, UPnP port forwarding and HTTPS/P2P remained
enabled; the framework stayed linked, embedded with `CodeSignOnCopy`, and covered by
the `Sign Embedded Frameworks` phase. Nothing was disabled to make the cycle resolve.

## Not validated

No Xcode on the Linux host and none on atlas-gpu-01 either — the fix was reported as
structurally verified but *unbuilt*, with the DerivedData wipe plus rebuild handed to
the user on their Mac.
