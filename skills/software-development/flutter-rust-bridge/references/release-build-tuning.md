# Release build tuning for a Flutter + Rust (FRB) app

Both halves of this stack ship with defaults tuned for development speed, not
for what actually goes to a user's device. Neither omission fails a build —
that's exactly why they go unnoticed until someone measures binary size or
download time.

## Rust `[profile.release]`

If the crate's `Cargo.toml` has no `[profile.release]` section at all, Cargo
uses its own defaults: `codegen-units = 16` (parallel but less optimized),
no LTO, no stripping, `panic = "unwind"`. Add:

```toml
[profile.release]
lto = true            # cross-crate inlining, smaller & faster
codegen-units = 1      # trade compile time for runtime speed
strip = true           # drop debug symbols from the shipped binary
# panic = "abort" deliberately NOT set — see below
```

**Do not set `panic = "abort"` in an FRB app.** flutter_rust_bridge's
generated handler (`frb_generated_default_handler!()` and friends) relies on
Rust's unwind-based panic catching (`catch_unwind`) internally to convert a
panic inside any single bridged call into a catchable Dart-side error rather
than crashing the whole native process. `panic = "abort"` removes that safety
net: any one bad `unwrap()` or out-of-bounds index anywhere in the bridged
surface then takes down the entire app instead of failing one operation. This
is a correctness regression, not just a missed optimization — skip it even
though it's the usual size/speed lever for other Rust binaries.

Verify after the change: `cargo test --release` (not just `cargo test`) to
exercise the new profile's actual codegen, and confirm the built `.so`/`.dylib`
is stripped (`file`/`nm` shows no debug symbols) and noticeably smaller.

## Android R8 minify + shrink

`android/app/build.gradle`'s `release` block frequently has no
`minifyEnabled`/`shrinkResources` at all — R8 never runs, so the release APK
ships every class and every resource from every dependency verbatim.

```groovy
buildTypes {
    release {
        minifyEnabled = true
        shrinkResources = true
        proguardFiles getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro"
    }
}
```

Most of what a Flutter app needs is already covered automatically and does
**not** need duplicating in `proguard-rules.pro`:
- Every plugin AAR ships its own `consumer-rules.pro`, merged in by AGP
  regardless of the app's own proguard file.
- `proguard-android-optimize.txt` already keeps every `native`-annotated JNI
  method by class-member signature — covers flutter_rust_bridge's Rust\<->Dart
  call resolution without an explicit rule.

### The one failure this reliably causes: Play Core "Missing classes"

Enabling minify on a Flutter app that has **no** Play Core / dynamic-feature-
delivery dependency fails with something like:

```
Missing classes detected while running R8. ...
com.google.android.play.core.splitinstall.SplitInstallManager
com.google.android.play.core.splitcompat.SplitCompatApplication
...
```

The Flutter engine's `io.flutter.embedding.engine.deferredcomponents`
package references Google Play Core's dynamic-feature classes
unconditionally, whether or not the app actually uses deferred components.
Since there's no play-core dependency in `pubspec.yaml`/`build.gradle` to
keep those classes real, R8 can't resolve the reference and refuses to
finish. This is a known, widely-hit Flutter/R8 interaction with no code fix
on the app's side — the standard resolution is a `-dontwarn`:

```proguard
-dontwarn com.google.android.play.core.**
```

Add this to `proguard-rules.pro` alongside a broad `-keep class io.flutter.**
{ *; }` (the embedding classes get reached by name from native code R8's
call-graph analysis can't see) and the app's own package if the FRB glue
looks anything up by name rather than pure JNI linkage.

Verify by actually building: `flutter build apk --release` must complete
through `minifyReleaseWithR8` successfully, not just compile — this failure
only appears at the R8 step, after everything else has already succeeded.

## Fat APK vs. per-ABI / app bundle

A Rust crate built for multiple Android ABIs (`aarch64`, `armv7`,
`x86_64` — typical CI matrix) means `android/app/src/main/jniLibs/<abi>/`
ends up with a native lib per ABI. `flutter build apk --release` with no
further flags bundles **all** of them into one "fat" APK; a real device only
ever uses one. Verified example: a 159.7MB fat APK contained 33 `.so` files
across 3 ABIs for one Rust crate + a media library.

Two fixes, pick based on the distribution channel:
- **Play Store**: `flutter build appbundle` — Play delivers only the
  matching ABI's slice per install automatically.
- **Direct sideload**: `flutter build apk --split-per-abi` — produces one
  APK per ABI; the sideload/download page then needs one link per device
  architecture instead of a single universal link.

This is a real ~2–3x per-device download-size win and is independent of
the R8/profile changes above — apply it separately since it changes the
distribution artifact shape (documentation/download instructions need to
name the right file per architecture).
