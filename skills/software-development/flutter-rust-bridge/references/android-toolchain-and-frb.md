# Android Toolchain and FRB Diagnostics

## Diagnostic split

FRB parser notices and Android packaging failures are separate layers. Messages about duplicate internal names (`Handle`, `Role`), fixed-size arrays (`Cannot parse array length`), or unit structs suggesting `#[frb(opaque)]` are usually non-fatal when the types are outside the explicit `--rust-input` bridge boundary. Confirm that generation reaches `Generate`, `Polish`, and exit 0, then inspect generated public output and run the normal compile/tests before changing internal types.

The actual Flutter Android artifact commands are `flutter build apk` and `flutter build appbundle`; `flutter build android` is invalid. Keep repository wrappers aligned with the CI artifact command.

## Java/Gradle compatibility

Gradle 8.x cannot run on Java 25. Java 25 requires a Gradle 9.1-or-newer line. A Java 25 migration is a coordinated set: update the wrapper, Android Gradle Plugin, and Kotlin plugin according to the installed Flutter tool's compatibility guidance. Do not change only `gradle-wrapper.properties`, and do not assume every Gradle 9.x release is accepted by the selected AGP.

A conservative fallback is JDK 17 selected through `JAVA_HOME`, Flutter's configured JDK, or a repository override such as `PORTALIS_JAVA_HOME`. This is a compatibility fallback, not a reason to abandon a planned Java 25 migration.

## Verification recipe

1. Run the FRB helper and confirm it exits successfully.
2. Inspect generated public Dart/Rust output for the warned types.
3. Run `flutter analyze`, focused bridge tests, and the Rust formatting/check gate.
4. Build Rust JNI libraries for Android.
5. Build the actual release artifact: `flutter build apk --release` or `flutter build appbundle --release`.
6. Repeat on CI with the same Java/Gradle/AGP/Kotlin versions.
7. If upgrading Java 25, first validate the minimum supported Gradle/AGP pair named by Flutter; evaluate newer Gradle versions separately.
