# Zero-copy custom storage and session persistence

## Symptom

A sender can hash/read gallery media and construct a custom referenced storage,
but adding the torrent fails with an error like:

```text
storages other than FilesystemStorageFactory are not supported
```

The UI may then report that the shared link is still preparing because the
caller forgets the torrent after the persistence flush fails.

## Diagnosis

Separate these stages:

1. source adapter can read the original asset;
2. torrent admission and piece verification succeed;
3. generic session persistence can serialize and reconstruct the adapter.

The third can fail even when the first two are correct. Do not treat this as a
reason to copy, clone, hard-link, or stage the media.

## Safe pattern

- Keep the original source reference and descriptor in an application-owned
  linked-source store.
- Add an explicit storage-factory capability such as
  `supports_persistence()`, defaulting to true.
- Mark external-reference factories false.
- Make the generic serializer skip only those factories rather than returning a
  fatal error for the whole torrent admission operation.
- Leave ordinary filesystem torrent persistence unchanged.
- Add a regression test for the capability and for descriptor persistence
  before session admission.

This preserves zero-copy media ownership: only metadata, torrent bytes, source
references, and peer hints are persisted. The storage adapter continues reading
from the original gallery/file location.

## Verification

Run the focused backend torrent tests, then the complete Nexus/backend and
Flutter gates. A successful fix should show a persisted share link/QR for a
fresh gallery collection and no `forget_torrent` immediately after publishing.
