---
name: flutter-ui-redesign
description: "Use for screenshot-driven Flutter UI redesigns."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [flutter, dart, ui, ux, widget-tests, responsive-design]
    related_skills: [test-driven-development, validated-refactoring, requesting-code-review]
---

# Flutter UI Redesign

## Purpose

Use this skill when a user asks to refresh, modernize, or replace a Flutter widget's visual presentation, especially when they provide a screenshot or describe a desired layout. The goal is a working, tested product change—not a speculative mockup or a pixel-copy of the reference.

## When to Use

Use this skill for screenshot-driven Flutter redesigns, layout hierarchy changes, dense list-to-card transformations, responsive presentation work, or any user-visible widget refresh that must preserve existing domain semantics and automated coverage.

## Workflow

1. **Capture the product contract**
   - Translate the user's visual request into information hierarchy, state behavior, density, and responsive requirements.
   - Use the screenshot as evidence of the current problem, not as an instruction to copy unrelated chrome or exact pixels.
   - Preserve domain semantics: reported/untrusted data must not look verified, and active/idle indicators must reflect real state.

2. **Inspect before editing**
   - Read the target widget and trace its model/domain inputs, formatters, theme tokens, design primitives, and neighboring widget tests.
   - Reuse existing card/surface components, spacing conventions, typography, colors, and byte/rate formatters.
   - Search all usages before renaming or removing a widget; update tests that intentionally pin the old presentation.

3. **Write the visible-behavior test first**
   - Add a focused widget test for the new user-visible contract before production edits.
   - Assert required content, labels, state cues, and canonical formatting at a realistic narrow width.
   - Prefer semantic assertions such as identity/address/metric labels and LIVE versus idle behavior. Avoid asserting private widget names, incidental tree depth, exact padding, or implementation-only colors.
   - Run the focused test and confirm it fails for the intended missing behavior, not because of a typo or broken fixture.

4. **Implement a vertical slice**
   - Build the smallest complete presentation slice that satisfies the test.
   - Keep the model unchanged unless the requested UI exposes a real missing domain value.
   - For dense data, prefer a stable bounded card: identity/header first, secondary metadata beneath it, then a small responsive metric grid.
   - Make long names and addresses ellipsize safely; ensure metrics remain readable on phone-width constraints.
   - Keep visual activity cues honest: a nonzero measured rate may be LIVE; zero-rate connected peers remain visible but quiet.
   - **Extend a shared primitive before building a parallel one-off widget.** A small polish request (e.g. "give paused/error badges a distinct look") is usually an optional parameter on the existing shared component (`StatusBadge(icon: ...)`), not a new bespoke badge widget for that one call site. Grep every existing usage of the primitive first so the new parameter defaults to the old behavior everywhere else.
   - **Derive a type/kind from an existing domain registry, not a new hand-written map.** If the codebase already classifies content (a `MediaFormats`/file-extension registry, a status-lifecycle enum, etc.), route the new icon/color/label decision through that registry's existing resolver instead of writing a second `switch` that can drift from it. Fall back to the previous generic glyph when the registry has nothing to classify yet (e.g. metadata unresolved).
   - **Add interactive detail as an additive overlay, not a painter rewrite.** To let a person reveal exact values on a `CustomPainter` chart (tap/press-and-drag tooltip), wrap the existing paint call in `GestureDetector` + `Stack` and keep the painter itself untouched; compute the nearest sample from gesture-local position with a linear/binary search over the same points array the painter already receives. This keeps the chart's default (unpressed) rendering byte-for-byte identical and confined the change to one new stateful wrapper widget.
   - **Responsive tile density:** wrap a `GridView`'s `build` in `LayoutBuilder` and vary only `maxCrossAxisExtent` by a width breakpoint (e.g. phone-cap unchanged, a larger cap past ~640px). Cheaper and safer than a fixed column count, and keeps the phone-width behavior provably unchanged.

5. **Refine without weakening semantics**
   - Sort live records by useful activity only when that ordering is already supported by the domain values.
   - Keep verified contacts visually distinct from anonymous or self-reported engine observations.
   - Do not replace a canonical formatter with a one-off string format merely to satisfy a brittle screenshot expectation.
   - Update stale tests when they assert the retired visual contract; preserve tests for behavior and trust boundaries.

6. **Verify and ship**
   - Run `dart format` on changed Dart files.
   - Run the focused widget test, then `flutter analyze`, then the full `flutter test` suite.
   - Run `git diff --check` and inspect the diff/stat for unrelated changes.
   - For a user-visible release change, update the changelog and coordinated frontend/backend version metadata when that is the repository convention; run the version-consistency test.
   - Before committing, sweep for leftover Flutter/Dart processes and shared-host resource leaks.
   - Commit only intended files and push when the user's project workflow expects completed work to be shipped.

## Design Heuristics

- **Hierarchy over decoration:** the user should identify what a record is before reading its measurements.
- **Group related facts:** totals belong together; current rates belong together; status belongs in the header.
- **Bound the record:** cards create scan-friendly units and prevent a long list from becoming a terminal dump.
- **Use one accent meaningfully:** reserve strong color/glow for active transfer state; keep idle state legible but subdued.
- **State the trust boundary:** self-reported client names are metadata, not verified identities.
- **Design for the smallest supported width:** desktop whitespace must not be the only layout that works.

## Common Pitfalls

- Copying screenshot coordinates instead of understanding the user's information hierarchy.
- Keeping a log-like row layout because an old test asserts its exact text style or color.
- Showing a peer's client string as if it were a person or verified contact.
- Calling a peer active merely because it is connected; activity requires a nonzero measured rate.
- Adding a second formatter or visual token set instead of reusing the existing design system.
- Testing only a desktop-sized widget and discovering overflow on phone layouts later.
- Stopping after a focused test while leaving analyze, full tests, version checks, or build processes unverified.

## References

- `references/flutter-peer-card-redesign.md` — validated card layout, trust labeling, test assertions, and verification notes from a real collection-detail redesign.
