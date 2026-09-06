# Flutter/Android Native Gate Diagnosis

Use this reference when a Flutter Android build is red after FRB, Gradle, or
Rust JNI work.

## Stage classification

1. **FRB generation** — duplicate internal names, unsupported arrays, and unit
   structs such as `#[frb(opaque)] struct X;` can be informational when codegen
   exits zero and the exported bridge compiles. Do not hand-edit generated
   bindings or `GeneratedPluginRegistrant.java` to silence them.
2. **Gradle/Java startup** — Java 25 requires Gradle 9.1 or newer to run Gradle.
   Flutter's configured JDK can override `JAVA_HOME`; inspect the JDK Flutter
   actually uses before adding an environment-only workaround. Upgrade the
   wrapper and matching AGP/Kotlin/Flutter integration together.
3. **Rust JNI** — verify each requested ABI independently (`arm64-v8a`,
   `x86_64`, and `armeabi-v7a`). Successful JNI compilation does not prove the
   Java/Kotlin plugin layer is healthy.
4. **Generated plugin registration** — if `GeneratedPluginRegistrant.java`
   references a missing plugin class, trace the locked package version and its
   Android build metadata. The plugin module may not be compiling or its
   Gradle/Kotlin integration may be incompatible. Change the dependency or
   Gradle configuration, then regenerate through Flutter; never make a lasting
   hand edit to the generated registrant.

For AGP 9 migrations, Flutter's built-in Kotlin mode is the preferred path when
supported: set `android.builtInKotlin=true` and remove the app's direct Kotlin
Gradle Plugin application. Keep third-party plugin warnings separate from the
first fatal compiler error, and do not declare the migration complete until the
native APK passes on the target machine and CI.

## Evidence checklist

Record the exact command, Flutter/JDK/Gradle/AGP/Kotlin versions, first failing
Gradle task, and which ABI stages completed. A log showing all Rust ABIs built
but failing at `compileReleaseJavaWithJavac` is a plugin/Android Gradle issue,
not a Rust or FRB issue.

## Portalis session detail

The Android failure sequence was: Java 25 with Gradle 8.14; after upgrading to
Gradle 9.1 and AGP 9.0.1, all three Rust ABIs compiled; the next failure was
`GeneratedPluginRegistrant.java` referencing
`com.mr.flutter.plugin.filepicker.FilePickerPlugin`. The project then migrated
to built-in Kotlin (`android.builtInKotlin=true`, no app-level
`kotlin-android`). The post-migration Mac APK result remains the required
verification before treating that plugin fix as complete.
