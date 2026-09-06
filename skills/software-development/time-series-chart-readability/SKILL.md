---
name: time-series-chart-readability
description: Use when a time-series chart is unreadable after idle gaps.
---

# Time-series chart readability

## The failure mode

A chart plots samples on a **linear time axis**: `x = width * (sample.time - start) / (end - start)`.
This is correct when samples are evenly spaced, but breaks down the moment the
sampling has a **long idle gap** in it — a device recorded actively for a
minute, then sat paused/disconnected for hours, then recorded again. On a
linear axis, the entire meaningful burst gets squeezed into a few pixels
beside a mostly-empty multi-hour flat band. The user sees "the graph looks
unreadable" or "the graph is useless after leaving it open overnight" —
that symptom description is the trigger for this skill, even if they never
say "linear axis" or "gap".

Common real-world sources of this pattern: network/transfer rate history,
peer/connection activity, sensor polling with sleep periods, any dashboard
that keeps a ring buffer of samples across app restarts.

## The fix: gap-relative axis compression

Don't scrap the time axis — compress only the outlier gaps, leave normal
spacing untouched. Compute each point's x-axis fraction from a running sum
of per-gap deltas, where each gap is capped at a multiple of the **history's
own median gap** (not a fixed duration):

```dart
/// The x-axis position (0..1) for each point, compressing any gap that is
/// disproportionately larger than this history's typical sample spacing.
List<double> compressedPositions(
  List<Point> points, {
  double capMultiplier = 2,
}) {
  if (points.isEmpty) return const [];
  if (points.length == 1) return const [1.0];

  final gaps = <int>[
    for (var i = 1; i < points.length; i++)
      math.max(0, points[i].at.difference(points[i - 1].at).inMicroseconds),
  ];

  // Use a RELATIVE cap (multiple of median gap), not a fixed Duration.
  // "Normal" spacing differs by an order of magnitude between a live poll
  // (sub-second) and already-aggregated/rolled-up history (minutes) —
  // a fixed cutoff is wrong for one of the two regimes.
  final sorted = [...gaps]..sort();
  final mid = sorted.length ~/ 2;
  final median = sorted.length.isOdd
      ? sorted[mid]
      : ((sorted[mid - 1] + sorted[mid]) / 2).round();
  final threshold =
      median > 0 ? (median * capMultiplier).round() : double.maxFinite.toInt();

  final effective = <int>[0];
  for (final gap in gaps) {
    effective.add(effective.last + math.min(gap, threshold));
  }
  final total = effective.last;
  if (total <= 0) {
    return [for (var i = 0; i < points.length; i++) i / (points.length - 1)];
  }
  return [for (final v in effective) v / total];
}
```

Why relative-to-median rather than a fixed `Duration` cap: a fixed cutoff
only works for one sampling regime. Live polling can be sub-second, but
rolled-up/aggregated history can legitimately have minute-scale gaps that
are NOT idle — a fixed cap would wrongly compress those too. Deriving the
cap from the history's own median gap makes the function correct for both
regimes with the same code, and "uniformly spaced" data (the common case)
passes through completely linear — the compression only ever engages on
genuine outliers.

## Wiring it in — don't forget the interactive layer

If the chart has tap/drag "nearest sample" tooltip behavior, that hit-test
logic almost always duplicates the axis math independently (`elapsed/span`
against pointer x). When you switch the render path to compressed
positions, the interactive nearest-point lookup MUST switch too, or the
tooltip will point at the wrong sample the moment gaps exist. Compute
`compressedPositions` once, feed the same list into both the painter and
the gesture handler's nearest-index search — never let them diverge.

## Testing

Write a unit test for the position function directly (not just a widget
test) with a fixture that reproduces the reported shape: a short burst of
closely-spaced samples, then one sample many hours later. Assert the burst
still occupies a substantial share of the axis (e.g. `> 0.3`), not the
`burst_duration / total_duration` a linear axis would give it. Also assert
the no-op cases: uniform spacing stays exactly linear (`[0.0, 0.5, 1.0]`
for three equally-spaced points), a single point sits at the right edge,
empty input returns empty.

## Round two: compression alone still hides WHEN it stopped

Shipping gap compression is not the end of this feature. Expect a fast
follow-up along the lines of "now I can't tell when the download actually
stopped vs resumed" — and it's a legitimate complaint, not scope creep.
Compression only fixes the axis's use of *space*; the line drawn between
the last real sample before the gap and the first real sample after it is
still a straight interpolation between two arbitrary rates. A transfer
that trailed off and resumed hours later reads as one smooth
decline-then-incline, and there is no way to read the real stop/resume
instant off that slope — the compressed axis makes the *gap* readable but
not the *boundary*.

Fix: splice two explicit zero-value markers around every compressed gap —
one at the real last-active timestamp (tag it e.g. `stopped`), one at the
real next-active timestamp (tag it `resumed`). The line now drops straight
to zero at the genuine stop instant, stays flat across the compressed idle
span, then rises straight back up at the genuine resume instant: a visible
notch instead of a guessed slope. Each marker keeps its own real
timestamp, so the existing tap/drag "nearest sample" interaction (see
above — don't let it diverge from the render path) now answers exactly
when it stopped and resumed for free; just have the tooltip render a
label ("STOPPED"/"RESUMED") instead of a rate when the selected point is
one of these synthetic markers, rather than printing `0 B/s`.

```dart
// Wrap compressedPositions(): walk consecutive points, and wherever the
// gap between them was classified as idle (i.e. capped), insert a
// zero-rate point at each real boundary timestamp before continuing.
// Keep an enum (none/stopped/resumed) on the point type so the tooltip
// can special-case rendering without a magic-zero check.
```

Uniformly-spaced history produces zero markers — this is purely additive
to the idle spans compression already found, never a separate pass over
normal data. Test it the same way: a burst-then-gap-then-resume fixture
asserting both markers appear with the correct real timestamps and sit at
the same axis position as their neighboring real sample; a uniform-spacing
fixture asserting no markers are inserted at all.

## Real implementation reference (Portalis)

In `lib/design/transfer_graph.dart`:

- `compressedPositions()` — relative-to-median gap capping (as above)
- `_compressedAxis()` — returns both positions and `idleAfter` bool list
- `TransferIdleBoundary { none, stopped, resumed }` enum on `TransferPoint`
- `transferChartSeries()` — splices markers, returns `TransferChartSeries { points, positions }`
- `_drawIdleBandLabels()` — draws centered `IDLE <duration>` label in gaps >40px
- `_InteractiveTransferChartState._selectAt()` — uses expanded series positions for hit-test
- `_TransferGraphTooltip` — renders `STOPPED`/`RESUMED` label for boundary markers

Unit tests in `test/transfer_graph_ui_test.dart`:
- `compressedPositions`: burst→12h-gap→resume (asserts `positions[2] > 0.3`), uniform spacing, single point, empty
- `transferChartSeries`: asserts 2 markers inserted with correct timestamps/rates/positions; uniform spacing has 0 markers; single point has 0 markers

This was implemented as a single vertical slice: RED tests for the marker behavior, then the marker-splicing function, then wiring painter + tooltip + hit-test to the expanded series. No horizontal "all tests then all code" — one behavior at a time.
