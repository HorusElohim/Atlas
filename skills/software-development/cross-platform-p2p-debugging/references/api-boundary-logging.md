# API-Boundary Logging Gate for Cross-Platform P2P

Use this gate whenever a Flutter/mobile-to-desktop or desktop-to-mobile transfer
crosses UI, bridge, Rust/Nexus, and a torrent worker.

## Before committing a diagnostic or corrective patch

Instrument every boundary and keep the logs in the commit when the user needs a
native reproduction:

1. **Flutter entry:** log the operation, normalized input kind, and payload
   length—not the full magnet or source path.
2. **Bridge/API call:** log invocation and returned acceptance ID or collection
   handle.
3. **Core admission:** log `ImportTorrent` and `DownloadSelection`, collection,
   and selected-entry IDs.
4. **Resolver/worker:** log metadata-resolution start, actual peer hints passed
   to the substrate, success with info hash/file count, and the exact error.
5. **State/projection:** log the transition to metadata-ready and the first
   acquisition/progress event.

Use stable tags and correlate events by command ID, collection handle, or info
hash. Do not print credentials, full source paths, media contents, or unnecessary
query fields. An info hash and private LAN endpoint are enough for correlation.

## Hanging operations

A metadata call that can wait forever leaves the UI permanently showing "waiting
for file list" and hides the failing boundary. Add a bounded timeout (30 seconds
is a reasonable starting point), log an explicit timeout error, and propagate the
failure to the UI. A successful TCP probe is not proof that the BitTorrent
handshake, metadata response, or acquisition succeeded.

## Verification gate

Before committing, run:

- Flutter formatter and analyzer;
- focused and full Flutter tests;
- Rust formatter and focused/full backend tests;
- diff whitespace checks.

Then perform the real device-to-desktop and reverse-direction transfer when the
failure is platform-specific. Report automated and native validation separately.
