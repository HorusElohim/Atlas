# Flutter Android SDK provider triage

Use when a Flutter Android build fails while configuring or resolving a plugin task with a generic Gradle provider error, for example:

```text
Could not determine the dependencies of task ':some_plugin:compileReleaseJavaWithJavac'.
Cannot query the value of this provider because it has no value available.
```

## Diagnose before changing plugins

The plugin named in the task is often merely the first Android library Gradle configures. Before pinning or upgrading it, verify the SDK platform selected by the app and plugins is complete.

```bash
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:?Set ANDROID_SDK_ROOT or ANDROID_HOME}}"
API=36 # replace with the project compileSdk

test -f "$SDK_ROOT/platforms/android-$API/android.jar"
```

A platform directory without `android.jar` is an incomplete SDK installation and can surface as the generic provider failure above.

## Repair a known-incomplete platform

Only do this when no other Android build is active on the shared host. Reinstall the exact platform, then verify the actual jar:

```bash
SDKMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
yes | "$SDKMANAGER" --sdk_root="$SDK_ROOT" --uninstall "platforms;android-$API"
yes | "$SDKMANAGER" --sdk_root="$SDK_ROOT" "platforms;android-$API"
test -f "$SDK_ROOT/platforms/android-$API/android.jar"
sha256sum "$SDK_ROOT/platforms/android-$API/android.jar"
```

Then rerun the repository's canonical clean release command. Do not conclude a package is incompatible until this precondition has passed.

## If an AGP 9 migration exposes real plugin failures

Once the SDK is sound, upgrade only the first proven incompatible direct/transitive plugin. Regenerate lockfiles and platform registrants through `flutter pub get`; never edit registrants or pub-cache sources by hand. If the plugin changes a Dart API, update only actual call sites, keep direct-path/zero-copy behavior intact, and validate in this order:

1. `flutter analyze`
2. the relevant Flutter tests
3. the canonical clean Android release build
4. artifact existence, size, and checksum

Commit manifest, lockfile, generated registrants, API callers, and changelog together only after all gates pass.