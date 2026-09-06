---
name: rust-test-triage
description: "Use for Rust test failures; preserve exact suite context."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rust, testing, debugging, flaky-tests, regression]
    related_skills: [systematic-debugging, shared-dev-host-safety, test-driven-development]
---

# Rust Test Triage

Use for Rust workspace test failures, especially when the user wants concise
output or when a failure may be flaky, stale, or caused by a recent refactor.

## Workflow

1. **Run the exact reported command first.** Preserve the original package,
   test target, suite, thread count, setup, and environment. A narrower test is
   useful only as a diagnostic follow-up, never as proof that the reported
   failure is fixed.
2. **Bound evidence.** Capture the failing test, relevant source range, recent
   commits touching the path, and the final test summary. Avoid dumping an
   entire workspace log.
3. **Trace before changing.** For assertion mismatches, locate the assertion,
   the producer of the returned value, and recent changes. Check implicit side
   effects and deterministic ordering. In storage tests, verify automatic
   membership/ownership effects and key ordering before changing expectations.
4. **Classify accurately.** If an isolated rerun passes, report “not reproduced
   in isolation” and rerun the original suite before calling it flaky. Preserve
   the suite's concurrency and lifecycle when validating a suspected race.
5. **Make the smallest root-cause change.** If behavior is intentional and the
   assertion is stale, update only that focused expectation. Do not alter
   production behavior to satisfy an outdated test.
6. **Verify proportionally.** Run the focused test, then the relevant package
   `cargo fmt --all --check` and `cargo clippy -p <package> --all-targets
   --all-features -- -D warnings`. Run broader checks when resources permit;
   state skipped checks honestly.
7. **Before push**, fetch/rebase origin, rerun affected checks if the rebase
   touched the same area, then push and verify the remote commit.

## Minimal-output mode

When the user requests token efficiency, use terse tool commands and bounded
output. The final handoff should contain only:

- root cause;
- file and line/region changed;
- exact verification result;
- commit/push status;
- broader checks not run.

Do not narrate every investigation step or present an isolated green test as a
resolved suite failure.

## Common patterns

### Stale expectation after an intentional side effect

Trace the write path and compare the expected collection with the actual table
ordering. Update the expectation and add a short assertion message explaining
the intentional side effect, such as automatic owner membership.

### Handshake or timing failure

First rerun the exact suite. Then run the test in isolation to compare. If only
parallel/contextual execution fails, investigate lifecycle, address reservation,
shutdown, and retry behavior; do not immediately label it a product bug.

### Compile/clippy mismatch after sync/async refactor

Search all callers after changing a method's asyncness. Remove stale `.await`
expressions and update tests from async runtime attributes only when no await
remains. Run clippy with `-D warnings` so unused async and cast lints are not
missed.

### Passes on your platform, fails only on another (macOS/Windows/Linux)

Symptom: a test passes on the host you developed on but fails elsewhere with
a panic touching a real filesystem path outside the repo/temp dir — e.g.
`opens: Identity("replacing \"/Users/.../Library/Application Support/<App>/identity.json\"")`.
Before suspecting platform-specific logic, check whether this test is simply
missing a call every sibling test in the same module makes to redirect
persisted state into a disposable temp directory (e.g. a
`redirect_to_temp()`/`with_temp_state_dir()` helper). A test that omits it
reads/writes the *real* per-OS state directory (`~/Library/Application
Support/...` on macOS, `%APPDATA%` on Windows, XDG dirs on Linux) instead of
an isolated fixture. It can still pass by accident on a CI runner or a fresh
dev machine with no pre-existing state file there, and only fails once a real
file already exists at that path (e.g. from an actual app install) that the
test's atomic-write logic then collides with. Fix: add the missing isolation
call — do not add platform-conditional logic to the test or the production
code. Grep the module for the isolation helper and confirm every other test
in it calls it; the fix is almost always copying that one line.

### Compiler/clippy internal error (ICE) unrelated to your diff

Symptom: `error: the compiler unexpectedly panicked. This is a bug`, a
`clippy-driver`/`rustc` panic, or `query stack during panic` output, on a
crate you did not touch (e.g. a protocol/codegen crate elsewhere in the
workspace) while running a gate for changes in a different crate. This is a
toolchain-level flake, not a defect in your change. Rerun the exact same gate
command once, unmodified. If it passes cleanly on retry, treat that as the
real result and move on — do not narrow scope, downgrade the toolchain, or
write up the ICE as a known issue. Only escalate (report to the user, file
upstream) if it reproduces on a second consecutive run.

## Reference

See `references/portalis-rust-failure-patterns.md` for concise examples from
Portalis storage and client test failures.
