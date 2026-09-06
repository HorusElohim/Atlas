# Flutter macOS build warnings

Use when `flutter build macos` warns about Swift Package Manager (SPM) plugin support or an Xcode `Run Script` phase with no outputs.

## Separate the warning classes

1. **Plugin SPM support** belongs to each dependency maintainer. A successful `pod install` means CocoaPods still works; the warning is about Flutter's future default.
2. **An unnamed script phase with no outputs** is app-project configuration. Locate the exact `PBXShellScriptBuildPhase` by its `shellScript`, not the generic displayed name.

## SPM compatibility workflow

- Inspect the locked plugin versions and run `flutter pub outdated`; do **not** make a major version jump merely to silence the warning.
- Check Flutter's current SPM documentation and the plugin's current metadata/release notes for actual SPM adoption.
- If a required plugin lacks SPM support, retain CocoaPods explicitly until all required plugins support SPM:

  ```yaml
  flutter:
    config:
      enable-swift-package-manager: false
  ```

- Comment this as a temporary compatibility choice. Remove the opt-out only after live verification that every required plugin supports SPM.

## Rust/Cargo script-phase workflow

A Cargo build depends on a dynamic Rust source/dependency graph that Xcode cannot safely enumerate with a short static output list. If the phase must execute every Xcode build, declare that intentionally instead of inventing incomplete outputs:

```text
alwaysOutOfDate = 1;
name = "Build Rust backend";
```

Cargo remains incremental, so the invoked script need not rebuild unchanged crates. Use a normal output dependency only when the phase has complete, reliable inputs and outputs; otherwise stale embedded backend artifacts are worse than the extra incremental invocation.

## Verification

1. `flutter pub get` must accept the project configuration.
2. Run `flutter analyze` and focused/full Flutter tests as appropriate.
3. On a macOS host, run `flutter build macos --release` and confirm the warnings are gone while CocoaPods integration still succeeds.
4. Do not claim macOS build verification from a non-macOS host.