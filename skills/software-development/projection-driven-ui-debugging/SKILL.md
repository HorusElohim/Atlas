---
name: projection-driven-ui-debugging
description: "Use when summary UI values are wrong. Trace data authority."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, ui, projections, data-flow, regression-testing]
    related_skills: [systematic-debugging, test-driven-development, flutter-rust-bridge]
---

# Projection-Driven UI Debugging

## Overview

Use this skill when a UI row, card, list, or summary shows a stale, empty, or zero value while a detail screen appears correct. These bugs commonly arise when the summary projection intentionally omits expensive detail data, but presentation code reads the optional detail collection anyway.

**Core principle:** A summary must render aggregate facts from the authoritative summary projection, not infer them from an unloaded detail projection.

## Workflow

### 1. Identify the exact user-visible value

Record the displayed label and the expected value. Distinguish:

- an aggregate known by the summary (entry count, total bytes, state),
- detail-only content (file names, thumbnails, per-file progress), and
- a presentation fallback (zero, empty list, placeholder).

Do not treat a displayed zero as proof that the backend owns zero; it may be a fallback caused by absent detail.

### 2. Trace both projection paths

Follow the value from its backend/domain source to the widget:

1. Locate the summary DTO/model field.
2. Locate the optional detail DTO/model and subscription boundary.
3. Find the adapter/view-model that pairs them.
4. Find the formatter or presentation getter used by the row.
5. Confirm whether the row is built with detail absent by design.

Prefer existing source-of-truth fields over adding a new data fetch. Avoid subscribing every list row to detail just to make an aggregate visible.

### 3. Build a summary-only regression test

Write a tight test that constructs the smallest valid summary with the expected aggregate and explicitly leaves detail absent (`null`, not an empty fabricated detail). Assert the user-visible result, not only an internal field.

The test should demonstrate the bug before the fix. For example, a collection with `entries = 3` and `detail = null` must render `3 items`, not `0 items`.

### 4. Apply the smallest seam fix

Use the authoritative summary field for aggregate labels. Keep detail-backed values detail-backed when they genuinely require detail. Do not fabricate detail entries, copy source media, or alter subscription behavior as a workaround.

### 5. Verify both paths

Run the focused regression test, then the full feature test file and static analysis. Preserve coverage for:

- summary-only rows,
- detail-loaded screens, and
- empty collections.

### 6. Verify the user's actual worktree and build

If the user still sees the old value after a green test, verify execution context before changing the diagnosis:

1. Enumerate relevant worktrees and record each branch, status, and project path.
2. Compare the edited source and test result with the worktree that produced the screenshot or running binary.
3. Check whether the running app must be rebuilt or restarted; an already-launched binary does not contain newly edited Dart/UI source.
4. When multiple worktrees contain the feature, inspect the target worktree's existing changes before porting the fix, then rerun its focused test and analyzer.
5. Report source verification separately from live-app verification.

A passing test in the wrong worktree is not evidence that the user's running app is fixed.

## Common Pitfalls

- Counting `detail.items.length` in a list that intentionally has no detail subscription.
- Replacing a missing value with a hard-coded nonzero fallback.
- Making every row subscribe to expensive detail data to fix one aggregate label.
- Testing only a fully hydrated detail screen, which masks the list-only failure.
- Treat generated bridge DTOs as the place to fix a presentation projection mismatch.
- Add a Flutter-side fallback when the repository's architecture assigns the authoritative fact or aggregation to Rust.
- Assume the currently open checkout is the user's running build when multiple worktrees are present.

## Flutter/Rust Boundary Notes

At a Flutter/Rust boundary, establish ownership before changing code. Persisted facts, aggregation, business rules, and authoritative projections belong in Rust; Flutter should remain a thin binding and presentation layer. Do not add a Dart-side fallback or duplicate projection merely because the UI symptom is visible there.

Verify the generated decoder and the handwritten projection independently. If the summary field is decoded and populated but the row still shows zero, fix the Dart projection/presentation seam rather than regenerating bridge code. Regenerate artifacts only when the bridge contract itself changed. If the summary field itself is zero, trace and fix the Rust hydration/projection path instead.

## Worktree and Build Identity

Before editing or validating a projection bug, record the absolute repository path and branch. When multiple worktrees exist, compare the edited source and test output with the worktree that produced the screenshot or running binary. Never port a UI workaround from one branch to another without first checking the target branch's existing Rust projection and generated bridge state.

## Verification Checklist

- [ ] Exact zero/empty user-visible symptom reproduced.
- [ ] Summary and detail ownership of the value identified.
- [ ] Regression test uses detail absent and fails before the fix.
- [ ] Fix reads the authoritative summary field.
- [ ] Detail-loaded behavior remains covered.
- [ ] Focused tests, feature tests, and analyzer pass.

## Supporting Material

See `references/summary-vs-detail-regression.md` for a concise worked pattern from a Flutter collection-row bug.
