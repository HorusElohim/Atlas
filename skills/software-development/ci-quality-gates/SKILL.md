---
name: ci-quality-gates
description: "Diagnose opaque CI gate failures; make gates self-reporting."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ci, coverage, quality-gates, thresholds, debugging, observability, tooling]
    related_skills: [systematic-debugging, shared-dev-host-safety, test-driven-development]
---

# CI Quality Gates

For the situation where **CI is red but the logs do not say why** — especially
"all tests passed" followed by a bare non-zero exit. Covers finding the gate
that actually failed, the recurring root cause (threshold flags that abort
before printing), and the fix pattern that makes a gate explain itself.

Also covers coverage gates specifically, which are the most common offender.

## 1. The opaque gate failure

**Signature:** the last useful log line is a tool announcing success or writing
an artifact, immediately followed by a bare non-zero exit, with NO diagnostic
in between:

```
test result: ok. 61 passed; 0 failed; 0 ignored
    Finished report saved to /tmp/nexus-coverage.d37Bsv
##[error]Process completed with exit code 1.
```

This is the most confusing CI failure class, because a user reasonably reads
"all tests passed" and concludes CI is broken or lying. It usually isn't — a
*later, separate* gate failed and said nothing.

### Diagnose in this order

1. **Find the full gate chain.** The CI step almost never runs only tests. Read
   the script the workflow invokes (e.g. `./tests/nexus.sh`) and list EVERY
   command in it. A typical chain:
   `proto/lint → format --check → clippy/typecheck -D warnings → test → coverage/threshold gate`.
   Tests passing means gate 4 of 5 passed. Say this explicitly to the user —
   "tests green ≠ CI green" is the crux of their confusion.
2. **Attribute the last line to a tool.** `Finished report saved` is the
   coverage tool, not the test runner. That names the failing gate.
3. **Ask why there is no message.** If a gate exits non-zero and prints nothing,
   the cause is nearly always that the tool's *built-in* threshold flag aborted
   the run before its own summary was rendered — and with a machine-readable
   output format (`--lcov`, `--json`, `--xml`, `--cobertura`) there is no
   summary table to render at all. The check is real; only the reporting is
   missing.

Do NOT conclude "CI is falsely failing" until you've walked the chain. And do
NOT trust `--log-failed` to contain the reason: it often truncates before the
gate's own output, which is precisely why the gate must print its own verdict.

## 2. The fix: move enforcement to where it can explain itself

**Never weaken or delete the threshold to force green.** That destroys a real
signal in order to work around a reporting bug, and it is the exact move that
erodes a codebase's guarantees over time.

Instead, keep the numbers and relocate the enforcement:

- Keep the tool producing its machine-readable export in ONE invocation
  (re-reading a profile a second time often silently re-scopes it — see §4).
- Drop the tool's `--fail-under-*` / `--check` / `--strict` flags.
- Enforce the SAME numbers in a small script that reads the export, prints the
  metrics on **every** run (pass or fail), and on failure names exactly what is
  short and where.

```bash
# BEFORE: fails blind — in file-output mode no summary is ever produced
tool --json --output-path "$report" --fail-under-functions 100 --fail-under-regions 99

# AFTER: identical thresholds, now diagnosable
tool --json --output-path "$report"
python3 "$(dirname "${BASH_SOURCE[0]}")/report.py" "$report" \
  --min-functions 100 --min-regions 99
```

Commit this as a fix in its own right, and say plainly in the message that
thresholds and any ignore/exclude list are UNCHANGED — reviewers must be able
to see you fixed observability, not lowered the bar.

> **A quality gate that fails without naming what it rejects is a defect in the
> gate.** Every future failure costs someone a full local reproduction.

You are in this situation when you catch yourself re-running the gate locally,
crate by crate or module by module, just to learn what CI already knew.

## 3. Validate your own diagnostic tooling before shipping it

A reporting script is itself code that can be wrong — and a *wrong* diagnostic
is worse than none, because it will be believed. Before committing one:

- **Run it against a known-PASS input and a known-FAIL input.** Confirm exit 0
  / exit 1 and that the failure text names real, correct items.
- **Cross-check its output against the tool's own authoritative totals.** If
  your script lists uncovered items while the summary reports 100%, your script
  is wrong — stop and find out why. (This exact contradiction appeared during
  development: a script printed "523 uncovered functions" for a report whose own
  total was 232/232 covered. Cause in §4.)
- Force a failure artificially if you have no failing fixture handy (e.g. pass
  `--min-regions 99.9` against data at 99.24%) to exercise the failure path.
- Syntax-check both halves before pushing: `bash -n script.sh`,
  `python3 -m py_compile report.py`.

Report honestly which checks you actually ran vs. which CI must run for you —
particularly when the full gate cannot run locally (see `shared-dev-host-safety`).

## 4. Coverage gate mechanics

Deep, tool-specific detail lives in `references/coverage-gates.md`, including:

- why a raw function list contradicts the summary totals (per-build
  disambiguators, generic instantiations),
- why re-reading a coverage profile a second time can silently narrow scope to
  one package,
- reading `--json` export structure to name uncovered functions and lines.

Read it before writing any coverage-report script.

## 4b. Prove a regression is yours before fixing it

When a gate fails after your own session's changes, don't assume — diff the
same gate's own "uncovered functions" output between the pre-session commit
and HEAD (`git stash` / `git checkout <path> -- <paths>` to swap trees, same
script, same machine). A clean diff naming only your new closures is proof
you introduced the gap, not pre-existing debt; see
`references/deterministic-async-ticker-tests.md` §1 for the exact commands,
and its §2-4 for testing a background ticker's write path deterministically
once you've confirmed the gap is a real "daemon / infinite loop" case (see
`references/uncovered-line-triage.md`).

## 5. Marginal coverage that differs between CI and local

A local run can pass while CI falls just below a function threshold even with
the same source and test count. Before calling that an infrastructure problem:

1. Fetch the failed CI log and record its authoritative `covered / count` totals.
2. Run the exact repository coverage script locally from its declared workspace
   directory; never substitute `cargo llvm-cov report` or a narrower package.
3. Compare the *short files and generated function families*, not raw mangled
   names. Async worker loops often surface as closure symbols, and scheduling
   can make those branches appear intermittently uncovered.
4. Add a bounded, condition-driven behavioral test for the missing worker path:
   drive the real worker through its injected double, wait for its observable
   state transition with a timeout, and prove shutdown remains prompt. Do not
   add helper-only calls merely to raise the numerator.
5. Re-run the full gate. Aim for a meaningful buffer over the floor, not a
   one-function pass, then run format and the affected lint gate.

This preserves the coverage gate as a signal: the repair is deterministic
execution of a real decision path, never a lower threshold or broader ignore
regex.

### Dead code is a legitimate second lever, distinct from writing a test

When a function/method shows up in the gate's own "uncovered functions"
list, don't reflexively write a test for it — first check whether it has
any real callers at all (`search_files` for its name across the whole
workspace, not just the file it's defined in). A `#[must_use]` accessor or
builder-style constructor with zero call sites anywhere is dead code that
someone forgot to remove, not a genuine gap in test coverage. Deleting it is
both the more honest fix (there is nothing to verify — it's unreachable)
and the one that best serves the codebase (less surface area to maintain),
and it moves the gate's percentage the same direction a throwaway test
would, without adding a test whose only purpose is padding a denominator.
Reserve writing an actual test for functions that DO have real callers but
simply never got one — e.g. a `Debug`/`Display` impl that's used in logging
but never asserted against; that case genuinely deserves a real assertion
on its real behavior, not deletion.

## 6. Script working-directory contracts

Coverage scripts often assume their crate or workspace directory as the current
working directory even when invoked by an absolute path. Before treating a
`cargo locate-project` failure as a coverage failure, read the script and run
it with an explicit `cd <declared-project-root> && ./scripts/coverage.sh`.
Keep its thresholds intact; if it still fails, preserve or explicitly emit its
JSON report and target the uncovered production function—not merely a new test
function, which can raise the denominator without improving the percentage.

## 7. Match the failing run to the checkout before editing

When a user supplies CI log lines without a run identifier, resolve the exact
workflow run, branch, and commit first, then verify the local worktree with
`git rev-parse --show-toplevel`, `git branch --show-current`, and
`git log -1 --format='%H %s'`. Repositories with multiple Portalis worktrees
can otherwise produce a correct fix in an inactive branch while the reported
failure remains unchanged.

For dependency-policy failures, read the invoked script and the policy file
before changing dependencies. If `cargo deny check ... sources` rejects a
pinned Git dependency, add only its repository URL to `[sources].allow-git`
and keep `unknown-git = "deny"`; the lockfile source includes a revision query,
but the allowlist should authorize the reviewed repository rather than one
transient commit. Reproduce the failing `cargo deny` command before the edit
and rerun the complete `advisories bans licenses sources` command afterward.

## 8. Matrix-cost controls and Android ABI scope

When a repository deliberately keeps draft pull requests cheap, gate expensive
platform-build jobs rather than authoritative tests. Leave backend and frontend
test jobs unconditional, and add a job-level condition to release/platform
builds:

```yaml
if: ${{ !github.event.pull_request.draft }}
```

This is safe for push events because `github.event.pull_request.draft` is empty
outside pull-request events. If a summary job depends on skipped platform jobs,
expect it to skip too unless it explicitly handles skipped needs. Do not leave a
dead job behind as `if: false`; remove its workflow block and unused composite
action so the CI surface stays truthful.

For an Android build that must ship only ARM64 (`arm64-v8a`, colloquially
"arm8"), constrain all three layers consistently:

1. setup action: install only `aarch64-linux-android`;
2. native build script: invoke `cargo ndk -t arm64-v8a` only, for debug and
   release;
3. Flutter packaging: use `flutter build apk --target-platform android-arm64`.

Changing only Flutter packaging can still waste time compiling native x86 or
ARMv7 libraries; changing only Rust leaves packaging ambiguous. Remove stale
`armeabi-v7a` and `x86_64` JNI folders before building so an old checkout cannot
package an ABI the current build no longer produces. Validate YAML and shell
syntax before pushing.

## 8. Commit-scope safety with pre-existing staged work

Before committing a focused CI change, inspect both the index and worktree:

```bash
git diff --cached --stat
git status --short
```

Stage explicit paths. If unrelated changes were already staged, do not use a
blanket commit. If they were accidentally included in the just-created local
commit, recover with `git reset --soft HEAD^`, unstage only unrelated paths with
`git restore --staged -- <paths>`, recommit the intended files, and use
`git push --force-with-lease` only when the rewritten commit is your own fresh
remote update. Report the correction honestly and verify final status.

## Pitfalls

- **Don't blame the diff.** A gate that started failing after your change may
  be failing on pre-existing untested code that your change merely made
  reachable — or on infrastructure (see below). Attribute before you fix.
- **Infrastructure failures masquerade as code failures.** A setup action that
  hits an unauthenticated API rate limit (`API rate limit exceeded for
  <ip>`, preceded by `No github_token supplied`) fails the job long before any
  build runs. Fix is to pass the token to that action, not to touch code:
  `with: github_token: ${{ secrets.GITHUB_TOKEN }}`. Tell-tale: the job dies in
  ~1-2 min instead of its usual duration.
- **A container-dependent test can be a flake, not a bug.** `MongoDB replica
  set did not start within 20 seconds` with every other test in the file
  passing is runner timing, not a regression. Re-run before editing test code.
- **Threshold values usually encode hard-won reasoning.** Before touching one,
  read the comments around it — a floor of 99 rather than 100 often documents a
  specific tool artifact. Preserve that rationale in your commit message.
