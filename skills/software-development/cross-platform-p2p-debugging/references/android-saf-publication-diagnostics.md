# Android SAF publication diagnostics

Use this when an owner-side Android collection remains in `RetryingMetadata`.

## Established architecture

Android publication is already Rust-owned and zero-copy:

```text
picker → content:// URI + lengthBytes → Rust ContentLocation
       → SAF descriptor → Rust metainfo hashing → librqbit admission
```

The iOS PhotoKit reader is a separate native adapter. Do not port its logic
without evidence that Android's SAF descriptor is the failing boundary.

## Minimal evidence to collect

From the Portalis Diagnostics screen, capture only:

```text
publisher starting
Android source length read failed
Android source read failed at offset=... bytes=...
publisher failed
```

Do not include URIs, filesystem paths, passwords, media bytes, or unrelated
Android application logs.

## Interpretation

- `length read failed`: URI permission, provider metadata, or descriptor open.
- `read failed ... Illegal seek` / `ESPIPE`: provider returned a non-seekable
  pipe; add a native sequential read fallback while retaining zero-copy.
- read succeeds but publication fails later: inspect metainfo validation,
  info-hash admission, or session setup.
- no publisher diagnostics at all: inspect lifecycle wake/status projection
  before changing the source reader.

Picker-provided stable length may be authoritative when descriptor `fstat`
returns zero or a conflicting value. This fixes metadata, not non-seekable
random access; those are separate hypotheses and must not be conflated.
