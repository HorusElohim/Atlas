# Incremental Flutter-Rust bridge builds

Use this pattern when a repository tracks generated FRB bindings and also has
native Rust packaging hooks.

## Fingerprint inputs

Hash the explicit public bridge modules, generator version, generator helper/configuration,
Cargo manifests/lockfile, and any dependency manifest that changes the bridge.
Include every expected generated output in an existence check. Keep the stamp in
an ignored build-state directory such as `.dart_tool/portalis/`.

Regenerate when the stamp is absent, an output is absent, or the fingerprint
changes. Expose explicit `--force-frb` and `--no-frb` controls. Backend-only
changes outside the public bridge boundary should not invalidate codegen.

## Native hooks

Xcode and Gradle can invoke Rust hooks on every build even when Cargo itself is
incremental. Declare Rust source/manifests as inputs and the packaged framework,
XCFramework, or JNI directory as outputs. The hook should also compare artifact
and source timestamps and skip both Cargo and repackaging when unchanged.

Keep Windows on the same bridge input list as Bash. The Windows pipeline should
conditionally generate bindings, build the native DLL incrementally, copy it
beside the Flutter runner, and expose a force-codegen escape hatch.

## Verification

Run the generator once, inspect the generated diff, run it again, and require a
clean no-op. Then run formatter, client analysis/tests, and the backend suite.
A native target build must be reported separately when it cannot be run on the
current host.
