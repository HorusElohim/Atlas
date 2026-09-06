# Transfer Timeline Telemetry

Use this reference when a P2P transfer graph must show its whole real timeline without storing or painting every raw sample.

## Contract

| Situation | Representation |
|---|---|
| Core sampled no receive/upload bytes | `ObservedZero` segment on the zero axis |
| Waiting for peers / paused / checking | zero-rate segment with an explicit phase |
| App/backend was not observing | `UnknownGap`; render a break, never zero |
| Completed session | one terminal zero boundary, then stop extending history |
| Live session | backend supplies the current observed endpoint; UI does not use its own wall clock |

## Compact model

Persist append/extendable segments rather than identical periodic rows:

```text
RateSegment {
  started_at, ended_at,
  down_rate, up_rate,
  phase: Receiving | WaitingForPeers | Paused | Checking | Seeding | Completed,
  certainty: Observed | Unknown,
}
```

A phase change always closes the previous segment. A zero-rate tick extends the existing observed-zero segment. A shutdown/restart boundary creates `UnknownGap` unless the core has authoritative coverage for the interval.

## All-history rendering

- Default to the complete retained session; zoom is optional detail.
- Use raw samples for short/recent detail.
- For a broad viewport, return per-time-bucket **first/min/max/last** points (M4-style) for each direction plus mandatory segment boundaries.
- Size the result to the display width (roughly a few extrema per pixel), not to the raw history length.
- This preserves short bursts and zero/gap transitions while keeping bridge traffic and Flutter `CustomPainter` work bounded.

## Research notes

- Grafana treats null values as gaps and exposes connection/disconnection behavior; this supports a deliberate distinction between missing telemetry and an observed zero.
  https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series
- TimescaleDB's gap-fill function creates time buckets but leaves them `NULL` unless an explicit fill policy is applied. Do not automatically fill missing telemetry with zero.
  https://docs.tigerdata.com/use-timescale/latest/hyperfunctions/gapfilling-interpolation/time-bucket-gapfill
- Datashader shows that every-Nth downsampling can erase sharp spikes.
  https://datashader.org/user_guide/Timeseries.html
- M4 is a visualization-oriented aggregation that retains first/min/max/last information per group; its authors report high reduction while preserving the rendered line chart.
  https://www.vldb.org/pvldb/vol7/p797-jugel.pdf

## Regression checklist

- A long observed zero interval occupies its real horizontal duration.
- An unknown interval produces a break/dashed span, not a zero line.
- Completion records one terminal zero and no unbounded trailing samples.
- A short high-rate burst remains visible after all-history aggregation.
- The graph's x-domain is derived solely from backend timestamps.
