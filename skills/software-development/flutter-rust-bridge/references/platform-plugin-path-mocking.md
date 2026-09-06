# Testing plugin-reported paths without a device

## The bug class

Flutter platform plugins that hand back a path (`path_provider`'s
`getTemporaryDirectory()`/`getApplicationSupportDirectory()`/etc., and
equivalents in file-picker/share plugins) only *name* a location. They do not
guarantee the directory exists on disk yet. On macOS in particular, a
sandboxed app's `Library/Caches/<bundle id>/` can be reported before the OS
or the app has ever created it. Code that writes straight into that path
fails with something like:

```
PathNotFoundException: Cannot open file, path = '.../Library/Caches/com.example/foo.log'
(OS Error: No such file or directory, errno = 2)
```

This is easy to miss in development because an earlier run (or Xcode/flutter
run itself) often already created the directory as a side effect, so the bug
only surfaces for a genuinely fresh install/profile — exactly what a real
user hits and a dev environment usually doesn't.

## The fix

Always `create(recursive: true)` the directory before writing into it. It's
idempotent — a no-op everywhere the directory already exists — so there's no
downside to doing it unconditionally on every write, not just the first one
after install.

```dart
final dir = await getTemporaryDirectory();
await dir.create(recursive: true);
final file = File('${dir.path}/my-export.log');
await file.writeAsString(contents);
```

## Reproducing it in a fast unit test (no device, no widget test)

Mock the plugin's platform interface to report a path that genuinely does
not exist, then call the extracted write function directly. This proves the
exact failure mode from a bug report and proves the fix, without needing a
real device or emulator.

```dart
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:path_provider_platform_interface/path_provider_platform_interface.dart';
import 'package:plugin_platform_interface/plugin_platform_interface.dart';

class _MissingTempDir extends PathProviderPlatform
    with MockPlatformInterfaceMixin {
  _MissingTempDir(this.path);
  final String path;
  @override
  Future<String?> getTemporaryPath() async => path;
}

void main() {
  test('creates its temp directory when the platform reports one that does not exist yet', () async {
    final scratch = Directory.systemTemp.createTempSync('scratch-');
    addTearDown(() => scratch.deleteSync(recursive: true));
    final missing = Directory('${scratch.path}/does-not-exist-yet');
    expect(missing.existsSync(), isFalse); // sanity check the setup itself
    PathProviderPlatform.instance = _MissingTempDir(missing.path);

    final file = await writeShareFile('a line\n'); // the code under test

    expect(missing.existsSync(), isTrue);
    expect(await file.readAsString(), 'a line\n');
  });
}
```

**Prerequisite for testability:** extract the file-write logic into its own
top-level (or `@visibleForTesting`) function separate from the widget/share
call. Testing the whole button-tap-to-share-sheet flow in a widget test is
brittle (no real OS share surface exists in a widget test) and unnecessary —
the actual bug lives entirely in the file-write step.

**Dependency note:** `path_provider_platform_interface` and
`plugin_platform_interface` are usually only pulled in transitively via
`path_provider`. Add them as explicit `dev_dependencies` in `pubspec.yaml` so
`flutter analyze` doesn't flag the test import
(`depend_on_referenced_packages`), and run `flutter pub get` after.

## Proving RED before GREEN

Don't just trust the fix looks right — temporarily remove the
`create(recursive: true)` call, rerun the test, and confirm it reproduces the
reported exception text exactly. Then restore the fix and confirm GREEN. This
is the fast way to get real RED/GREEN proof for an environment-shaped bug
without needing the user's exact OS/sandbox state.

## When the mocked test passes but the user still hits the bug in the field

A passing mocked-plugin unit test only proves the code creates the directory
when `PathProviderPlatform.instance` behaves like the mock. It does NOT prove
the real platform plugin's native implementation behaves the same way on every
OS/sandbox/build combination — plugin registration quirks, federated-plugin
resolution, or platform-specific edge cases in the real `getTemporaryDirectory()`
implementation can still leave a gap the mock can't see. If a user reports the
exact same failure after this fix shipped and the test passed, don't assume
the test was wrong or add a second layer of defensive `create()` calls —
reconsider whether the temp-file copy is necessary at all.

**The more robust fix, when applicable:** if the data being written already
exists as a real file the app itself wrote and already exposes a path for
(e.g. a log the backend continuously appends to at a known, already-displayed
path), skip writing a *second* copy into a plugin-reported temp directory
entirely. Hand the consumer API (e.g. `SharePlus`, a file picker save target)
the *original* file's path directly:

```dart
// Before: copy into a plugin-reported temp dir, then share the copy
final file = await writeShareFile(log); // extra directory-existence assumption
await SharePlus.instance.share(ShareParams(files: [XFile(file.path)], ...));

// After: share the file that's already on disk at a known path
final path = await backend.logPath(); // the backend already wrote here
await SharePlus.instance.share(ShareParams(files: [XFile(path)], ...));
```

This removes the plugin-path-existence dependency altogether rather than
defending against it — one fewer thing that can be wrong in a way a unit test
can't reproduce. Only fall back to the temp-copy-plus-`create()` pattern above
when there is genuinely no existing on-disk original to point at (e.g. the
data is generated in memory and has never touched disk).
