# Choosing a Bridge Tier for New Data

The SKILL.md principle "keep expensive or fast-moving state tiered" decides
*where* newly exposed data crosses the bridge. Getting this wrong is not a
correctness bug — it is a performance bug that only appears under load, so it
is worth deciding deliberately rather than defaulting to the snapshot.

## The decision

Ask two questions about the new data:

1. **How often does it change?**
2. **How many screens need it?**

| Change rate | Consumers | Tier |
|---|---|---|
| With user action | Any list/row | **Summary snapshot** |
| Every engine poll | One screen | **Dedicated call or stream** |
| Every engine poll | Every row | Reconsider — usually a derived aggregate belongs in the summary, details do not |
| Append-only, grows | One screen | **Its own incremental stream** (send only what the subscriber has not seen) |

The failure mode is putting fast-moving detail in the summary tier. A snapshot
is rebuilt and marshalled for *every* consumer; adding a field that changes
twice a second means every collection row in a list re-renders twice a second
to serve one screen that happens to want it.

## Worked example: per-peer transfer stats

Swarm peer stats (bytes up/down, live rates, client name) change every 500 ms
poll and are shown on exactly one screen.

- **Rejected:** adding `peers: Vec<AppPeer>` to the collection summary. Correct,
  and it would have rewritten every collection list item every tick.
- **Chosen:** a standalone `peers() -> Vec<AppCollectionPeer>` call, invoked by
  the one screen that displays them.

The count (`transfer.peers: u16`) stays in the summary, because a row does want
to say "3 peers" — a cheap scalar aggregate, not the per-item detail.

## Flat pairs beat nested maps across the bridge

When an item belongs to a parent, return a flat pair rather than a nested map:

```rust
pub struct AppCollectionPeer {
    pub collection: u32,
    pub peer: AppPeer,
}
```

The same peer address may be connected for two collections. Those are two
distinct connections, and a flat list represents that honestly; a
`HashMap<address, peer>` would silently collapse them and force the UI to
invent a merge rule.

## Polling a call-tier value from a Flutter screen

A call-tier value needs a refresh strategy in the widget. Two triggers, both
necessary:

```dart
@override
void initState() {
  super.initState();
  unawaited(_load());
  // The engine reporting anything can change who is connected; without this
  // the screen lags the rest of the app by up to one full interval.
  AppControllers.engine.addListener(_load);
  _timer = Timer.periodic(_refresh, (_) => unawaited(_load()));
}

@override
void dispose() {
  AppControllers.engine.removeListener(_load);
  _timer?.cancel();
  super.dispose();
}
```

**Pitfall — `notifyListeners()` in the poll's error path.** A failed poll is not
a state change worth rebuilding the app for, and if the poll was kicked off
during a build (`initState`), notifying listeners throws
`setState() ... called during build`. Record the error on the controller and
return an empty result; let the next successful poll speak.

**Pitfall — seeded/offline controllers.** Give the controller a debug seed for
the new call, exactly as the existing stream tiers have one. A widget test must
never reach the real bridge, or it discovers the native library is missing at
whatever moment something happens to subscribe.

## Test fakes

Every new method on the repository interface breaks every fake implementing it.
Grep for implementers before regenerating and add the most truthful
unavailable/default response (`async => const []`), not a fabricated value.
