# Magnet `xs=` Fallback and Vendored Engine Upgrades

Addendum to the main SKILL.md debugging workflow, with concrete validation and
upgrade details that are too session-specific for the class-level body.

## The `xs=` exact-source magnet field

A `magnet:` URI's discovery mechanisms are not limited to DHT, trackers, and
`x.pe` direct-peer hints. Many real-world magnets (not just app-generated
ones) also carry:

```
xs=https://example.com/some-file.torrent
```

`xs` points at a `.torrent` metadata descriptor served over plain HTTP(S).
Fetching it needs no DHT response, no tracker announce, and no peer
connection at all — it resolves the file list directly. If a magnet import
hangs at "waiting for file list" despite trackers/DHT being configured and
correct, check for `xs=` in the magnet before assuming the problem is
peer-address/rendezvous related. This is a distinct discovery path from
direct peer hints and is easy to overlook when a P2P debugging session
fixates on peer-hint/LAN-bootstrap logic.

When wiring `xs` support into an engine call path:

- Validate the URL scheme is `http`/`https` and the path ends in `.torrent`
  before fetching — never treat an `xs` value as an arbitrary payload
  source to blindly download.
- After fetching, verify the descriptor's own info-hash matches the
  magnet's `xt=urn:btih:...` before accepting it. This stops a
  compromised or stale `xs` host from substituting different content
  under the same magnet link.
- Treat `xs` as an optional optimization, never a mandatory dependency.
  Bound it independently (a validated implementation used five seconds),
  then fall back to the untouched magnet on timeout, HTTP failure, invalid
  bencode, or hash mismatch so DHT, trackers, and direct peers still run.
- Bound the complete metadata operation as well. In Rust, this is wrong:
  `timeout(T, session.add_torrent(add_torrent_for(source).await?, opts))`.
  The awaited source preparation is evaluated before `timeout` receives
  its future. Use `timeout(T, async { let add = add_torrent_for(source).await?;
  session.add_torrent(add, opts).await })` so a hung HTTP hint cannot leave
  the UI in `ResolvingMetadata` indefinitely.
- Do not log the full exact-source URL. URL user-info and query parameters
  can contain credentials or sensitive tokens; log only the fallback class.
- This is a metadata-only fetch (typically a few KB) — it does not violate
  a zero-copy / no-payload-fetch invariant that governs the actual media
  transfer.
- Regression coverage should use local HTTP servers for two deterministic
  seams: a non-success response (for example 503) and a connection that
  accepts but never responds. Both must return the original magnet path.
- When a bug report names a specific real-world magnet/URL, also run a
  network-gated (`#[ignore]`) test against (1) a working HTTPS exact-source
  magnet and (2) an ordinary public magnet with no `xs`, using DHT/trackers.
  Make the live magnet injectable through an environment variable so the
  probe stays reusable without hard-coding one transient swarm.

## Upgrading a vendored/patched P2P engine fork (e.g. librqbit major bump)

When the engine is vendored (source copied into the repo, not a plain
crates.io/pub dependency) and asked to upgrade across a major version:

1. **Find the real patch first.** `git log --oneline -- <vendor-dir>` and
   diff each vendoring commit against the version before it. Usually only
   one or two commits contain actual behavioral patches on top of the
   plain upstream source — everything else is the untouched vendored tree.
   Isolate exactly those hunks before touching anything else.
2. **Fetch the new upstream version into a scratch Cargo project**
   (`cargo fetch` against a throwaway `Cargo.toml` naming just the new
   version) to pull it into the local registry cache, then `diff -rq` the
   old vendored dir against the new cached version to see the full blast
   radius before committing to the upgrade.
3. **Replace the vendored source wholesale, then re-apply only the
   isolated patch** from step 1 onto the new source. Don't try to
   hand-merge line by line against a diff that predates the version jump.
4. A major bump can restructure internal types the patch depends on (e.g.
   a private field replaced by a wrapper type exposing only single-item
   accessors, no bulk iterator). Add a minimal new `pub fn` accessor on
   the vendored type rather than reaching into internals or reimplementing
   the wrapper's logic.
5. Expect ripple into the consuming crate's own `Cargo.toml`:
   transitively-pinned dependencies (e.g. `reqwest`) may need bumping too,
   and feature names can be renamed across major versions (e.g.
   `rustls-tls` → `rustls`). Check the new vendored crate's own
   `Cargo.toml` for its dependency versions/features as the source of
   truth, not assumption.
6. Session/config option structs are a common source of many small
   compile errors in one pass — flat fields get grouped into nested
   sub-structs (e.g. `disable_dht`/`disable_dht_persistence` →
   `dht: Option<DhtConfig>`; `listen_port_range`/
   `enable_upnp_port_forwarding` → `listen: Option<ListenerOptions>`).
   Read the new struct definition once, map every old field to its new
   home, then fix all call sites in one edit rather than iterating
   error-by-error blindly.
7. If the upgrade removes a setting with no replacement (e.g. a
   deferred-write buffer size knob), don't silently drop the user-facing
   control that fed it — leave it wired through the UI/bridge layer with a
   code comment marking it inert upstream, and say so explicitly to the
   user rather than pretending nothing changed.
8. Standalone per-file lint/patch-tool checks on vendored source can show
   spurious edition-2015 errors (`async fn` not permitted, `let`-chains
   not allowed) when a file is linted outside its crate context — this is
   not a real error. Verify with a full `cargo build` from the crate root
   instead of trusting a single-file lint pass.
