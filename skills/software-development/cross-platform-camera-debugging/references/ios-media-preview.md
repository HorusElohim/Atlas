# iOS media-preview reference

## Portalis validated pattern

Portalis Photo-library imports preserve source identity as
`phasset://<PHAsset local identifier>`. The media grid's generic HEIC decoder
uses `CGImageSourceCreateWithURL(URL(fileURLWithPath: ...))`, which is correct
for ordinary filesystem files but cannot open that opaque URI. Full-screen
preview already proves the PhotoKit identifier is valid, so the grid must use
the same native ownership path.

Use a native method-channel branch for the `phasset://` scheme:

1. Strip the scheme and fetch the `PHAsset` by local identifier.
2. Ask `PHImageManager` for a bounded `PHImageRequestOptions` preview.
3. Encode only the returned thumbnail (for example JPEG) in memory.
4. Return the bytes to Flutter; never export, copy, clone, or cache the source.
5. Keep filesystem paths on the existing ImageIO thumbnail path.

`PHImageManager.requestImage` may deliver more than one callback depending on
options and network availability. Ensure a Flutter method-channel result is
completed at most once. Validate the actual iOS behavior on a physical device,
because Flutter analyzer and Dart widget tests cannot exercise Photos access,
permissions, or PhotoKit decoding.
