# Portalis zero-copy source publication

## Invariant

Source media is referenced, never duplicated. A torrent may hash and read source bytes in bounded piece buffers, but Portalis must not create a persistent cache file, copy, hard link, or clonefile representation of selected media.

## Adapter shape

Use `ContentLocation` as the portable abstraction and a referenced torrent storage adapter as the single publisher path:

- filesystem paths: direct positioned reads from the original file;
- iOS Photos: `phasset://` identifiers read via PhotoKit;
- Android: enable `content://` only after a native MediaStore/SAF random-access adapter exists. Do not enable a picker that returns a cache path as a workaround.

The private torrent/session directory may contain metadata only. Live torrent projections retain the original source path, so previews and media views do not point at a staged directory.

## Descriptor ordering

A referenced storage admission can require the `.torrent` descriptor while the session is opening the torrent. Compute the info hash with metainfo, persist the descriptor/source record under that hash, then call `add_torrent`. On admission failure, remove that record. Return/retain descriptor metadata without treating it as source media.

## Validation checklist

1. Add a focused regression that creates referenced metainfo from an original filesystem source and proves the descriptor/source record is present before session admission.
2. Run `cargo fmt --all` and `cargo check` with no warnings.
3. Search the publisher for forbidden source-layout mechanisms such as `hard_link`, `clonefile`, `link_sources`, and cache/staging directories.
4. Run `./tests/nexus.sh` and Flutter analysis/tests.
5. Attempt an affected mobile target check when the Android/iOS SDK/compiler exists; report missing toolchains as environment blockers, never as proof that cache copies are acceptable.
