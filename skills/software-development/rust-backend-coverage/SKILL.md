---
name: rust-backend-coverage
description: "Use when raising Rust backend coverage. Test real behavior."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rust, testing, coverage, llvm-cov, backend, tdd]
---

# Rust backend coverage

Use this skill to raise backend coverage without weakening quality gates or
adding tests whose only purpose is to change a percentage. The target is
meaningful reachable production behavior, with compiler-generated and
unreachable artifacts identified explicitly.

## Workflow

1. Establish the baseline with the repository’s canonical coverage gate. Capture
   only the summary and uncovered-function tail; preserve full logs only when
   diagnosing a failure.
2. Read the source declarations and nearby tests for every reported symbol.
   Raw LLVM names are not source-level functions; demangle or map them back to
   declarations before planning tests.
3. Classify each item:
   - real production API or branch: add a store-backed or integration test;
   - async state-machine/closure symbol: exercise its parent workflow;
   - `cfg(test)`/`cfg(not(test))` duplicate, debug formatter, ignored/platform
     path, or impossible storage-engine error: document rather than fabricate.
4. Add one focused regression test at a real production seam. For workers,
   use deterministic substrate/test doubles, notifications, and shutdown
   signals—not arbitrary sleeps or tests that call private compiler artifacts.
5. Run the focused test first, then the full backend gate with the mandatory
   coverage floor unchanged. Compare both percentage and the raw list; a list
   can grow when tests add async functions even while behavior coverage improves.
6. For a bug discovered by a coverage test, keep the test red before the fix,
   implement the smallest production correction, rerun focused and full gates,
   and document retained behavior.
7. Commit tests and production fixes atomically when they represent one
   behavior, update the changelog for runtime fixes, push, and verify the remote
   SHA and clean tree.

## High-value seams

Prefer these over direct private-function invocation:

- Nexus command/API calls backed by a real temporary redb store;
- publication success/failure/retry and progress transitions through a
  deterministic substrate double;
- torrent metadata resolution and acquisition with persisted descriptors;
- transfer polling with scripted holdings, orphan release, shutdown, and
  durable history;
- detail projection for native and imported entries, including availability;
- schema migration round trips and durable restart behavior.

## Non-negotiable quality

Never lower the 95% backend floor to make a change pass. Never add artificial
sleep-based tests after a user has requested real missing coverage. A passing
coverage number is not proof if the test never ran; verify focused test counts,
full gate output, and the exact production behavior asserted.

See `references/llvm-symbol-triage.md` for the recurring LLVM symbol categories
and the Portalis coverage command pattern.
