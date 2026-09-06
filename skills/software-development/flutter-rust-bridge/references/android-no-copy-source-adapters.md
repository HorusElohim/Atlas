# Android no-copy document-source adapters

Use this pattern when Flutter must pass user-selected Android media to Rust without staging a duplicate.

## Invariant

The picker may provide metadata and a stable source identifier, but must not request `PlatformFile.bytes`, write a cache copy, or convert the document into an app-owned path. Reading into an already-required piece buffer is distinct from duplicating the source.

## Storage Access Framework flow

1. In the Android host, open `Intent.ACTION_OPEN_DOCUMENT` with `CATEGORY_OPENABLE`, `FLAG_GRANT_READ_URI_PERMISSION`, and `FLAG_GRANT_PERSISTABLE_URI_PERMISSION`. Enable `EXTRA_ALLOW_MULTIPLE` when collections support N sources.
2. For every returned `Uri`, call `takePersistableUriPermission` with the granted read flag. Return only `{name, path: content://…, lengthBytes}` through the Flutter method channel.
3. Gate the Flutter Files UI on a native Android capability. Do not use a generic Dart file-picker path when it materializes data or supplies an app-cache path.
4. Treat `content://` as a first-class Rust `ContentLocation`, not as a filesystem path. With the installed application context, use `ContentResolver.openFileDescriptor(uri, "r")`; transfer the `ParcelFileDescriptor` with `detachFd()` to an owned Rust `File` for the single operation.
5. Open a fresh descriptor for metadata and each positioned read, then close it with the Rust `File`. Use the same random-access range-read method as filesystem sources. Reject providers that cannot expose a required stable length rather than silently copying them.

## Tests and verification

- Flutter unit test: Android exposes the Files capability and translates a `content://` record to the domain source without byte data.
- Native target build: compile all Android ABIs; host-only Rust tests cannot execute Android JNI access.
- Device test is still required: select multiple documents, publish, restart, and confirm the persisted grants remain readable with no media written to app cache.

## Pitfalls

- `ACTION_GET_CONTENT` may yield a transient grant; use `ACTION_OPEN_DOCUMENT` for durable sources.
- Do not hand-edit generated Flutter plugin registrants to repair a picker integration.
- `ParcelFileDescriptor` ownership changes at `detachFd()`; the Rust `File` must own and close that descriptor exactly once.
