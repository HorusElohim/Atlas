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
