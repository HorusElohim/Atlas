# Summary-vs-Detail Regression Pattern

## Symptom

A collection list row displayed `0 items`, while the backend snapshot already reported a nonzero entry count.

## Data-flow diagnosis

- The list constructed a collection view with `detail: null` by design.
- The domain model exposed `entryCount` from the summary (`AppCollection.entries`).
- The row subtitle instead computed its count from `media.length`.
- `media` is detail-backed, so it was empty for every summary-only row.

## Minimal regression

Construct a collection view with `entries: 3`, `detail: null`, and assert the presentation subtitle is `3 items`. Also assert `media` is empty so the test proves the summary-only path is being exercised.

## Durable fix

Use `entryCount` for the row aggregate. Keep `media` for detail-dependent thumbnails, file labels, and per-file state. Do not force detail subscriptions onto every list row.

## Verification

Run the focused regression, the full feature test file, and static analysis. A passing detail-only test is insufficient because it bypasses the failing summary path.
