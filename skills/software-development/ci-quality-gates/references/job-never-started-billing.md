# Job never started: billing / account-level blocks (not a code failure)

A red CI check whose job **died in a few seconds with zero steps executed** is
almost never a code or workflow failure. This is the case where a user
reasonably suspects "the summary job is broken / it can't find the artifact"
— and the workflow code is actually fine.

## Signature

- The check shows `fail`, but the job's `started_at` and `completed_at` are
  seconds apart (e.g. `21:05:25` → `21:05:28`) with **zero steps** (`n_steps: 0`).
- `gh run view <run_id> --log-failed` returns **`log not found: <job_id>`** —
  there is no log because the job never ran. This is the tell that the usual
  "read the log" path is a dead end.
- Every OTHER job in the same run is green.

## Where the real cause lives: the check-run annotations API

The cause is account/runner-level and is surfaced only via the **check-run
annotations**, not the workflow logs:

```bash
# 1. find the check-run id for the failed job
gh api "repos/<owner>/<repo>/actions/runs/<run_id>/jobs" \
  -q '.jobs[] | select(.name=="<JobName>") | .id'

# 2. the real cause is in the annotations
gh api "repos/<owner>/<repo>/check-runs/<check_run_id>/annotations"
```

One recurring `message` there:

> "The job was not started because recent account payments have failed or your
> spending limit needs to be increased. Please check the 'Billing & plans'
> section in your settings"

That is a GitHub **Billing & plans** block on the account, not anything in the
repo.

## Fix

- Owner checks GitHub Settings → **Billing & plans** (expired card / exhausted
  spend limit / failed payment).
- Then `gh run rerun <run_id> --failed`.
- Do NOT "fix" the workflow, its `needs:` graph, its permissions, or its
  summary/artifact logic to chase a red that was never a code failure.

## Distinguish from the adjacent cases

- **Rate-limit infra failure** (see Pitfalls in SKILL.md): the job *does* start
  and run for ~1-2 min before dying at a setup action. Here the job never
  starts at all (zero steps). Different failure, same "not your code" family.
- **`skipped` conclusion** on the job: a `needs:` dependency didn't succeed, so
  it never qualified to run. That's a legitimate DAG outcome, not a billing
  block — check the annotations to confirm which it is.

## Verifying the workflow code was actually fine (before concluding "billing")

To close the loop and rule out the code path the user suspects, run the
exact extraction commands from the workflow against the real files locally:

```bash
# e.g. the "Extract app version" step's regexes
grep -m1 '^version:' <workdir>/pubspec.yaml | awk '{print $2}'
awk -F'"' '/^version\s*=\s*"/ {print $2; exit}' <workdir>/rust/backend/Cargo.toml
```

If those produce sane values, the version/summary logic is not the problem.
