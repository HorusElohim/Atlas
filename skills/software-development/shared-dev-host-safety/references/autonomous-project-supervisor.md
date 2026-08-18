# Autonomous Project Supervisor (hourly cron over a repo)

Pattern for "check the project every hour and act if something needs doing" —
a scheduled agent that reviews dev status, fixes what is unambiguous, and
otherwise reports and stops. Proven end-to-end: its first run diagnosed and
fixed a CI blocker, opened the fix on the branch, and correctly declined to
merge.

## Shape: cheap deterministic probe + LLM that only reasons

Do NOT let the agent rediscover state with a dozen tool calls every tick — it
burns tokens and drifts between runs. Split the job:

1. **A probe script** gathers facts deterministically (no LLM).
2. **The agent** reads that output and decides. Instruct it explicitly to READ
   THE PROBE OUTPUT FIRST and not re-run discovery that duplicates it.

Attach the script as the job's data-collection script so its stdout is injected
into the prompt as context.

## Probe script rules

Emit **stable** output — no timestamps, no random ordering — so hash/diff-based
change detection works and an unchanged tick can be suppressed.

Useful fields for a git+CI project:

```bash
set -uo pipefail          # NOT -e: one failing probe must not kill the report
cd "$HOME/<repo>" || { echo "REPO_MISSING"; exit 0; }

echo "=== BRANCH ===";    git rev-parse --abbrev-ref HEAD
echo "=== HEAD ===";      git log --oneline -1
echo "=== WORKTREE ===";  git status --porcelain | head -20
echo "=== BEHIND/AHEAD vs origin ==="
git fetch origin --quiet; git rev-list --left-right --count origin/<branch>...HEAD
echo "=== OPEN PRS ===";  gh pr list --state open --limit 10
echo "=== PR CHECKS ==="
for pr in $(gh pr list --state open --json number -q '.[].number'); do
  echo "--- PR #$pr ---"; gh pr checks "$pr" | awk -F'\t' '{print $1"\t"$2}'
done
echo "=== LAST CI FAILURE STEP ==="
run=$(gh run list --branch <branch> --limit 1 --json databaseId -q '.[0].databaseId')
gh run view "$run" --json jobs \
  -q '.jobs[] | select(.conclusion=="failure") | .name + " :: " + ([.steps[] | select(.conclusion=="failure") | .name] | join(","))'
echo "=== PLANS/ADRS ==="; ls -1 .hermes/plans/ | tail -10; ls -1 doc/adr/ | tail -20
echo "=== BUILD PROCESSES ==="; pgrep -af 'cargo|rustc|flutter|dart' | grep -v pgrep | head -5 || echo none
echo "=== HOST ==="; free -h | awk '/^Mem:/{print "mem_avail="$7}'; df -h / | awk 'NR==2{print "disk_avail="$4}'
```

**Run it once by hand before wiring it up.** A probe that errors silently makes
every tick useless.

## Prompt contents (cron runs carry NO conversation history)

Bake in everything the agent cannot infer:

- Repo path, branch, remote, owner.
- **Workflow rules**: who validates, who merges, what must be green first.
- **Agreed architectural decisions** so it doesn't relitigate them.
- **Commit/PR conventions** (message format, changelog requirements, version
  syncing, codegen regeneration rules).
- **Host constraints as hard prohibitions**, with the allowed alternative:
  "NEVER run the full workspace test/coverage here — it OOM-kills the linker.
  Use `cargo check`, `cargo clippy`, or `cargo test -p <crate>` with
  `CARGO_BUILD_JOBS=2`."
- **The known current blocker**, if any, plus how NOT to fix it (e.g. "do not
  weaken thresholds to force green").

## Decision ladder with a restraint clause

Give it an explicit ordering, and permission to do nothing:

1. CI red → investigate the specific failure; implement only if the fix is
   unambiguous and small; open/update a PR.
2. CI green and PR open → report it ready, **do NOT merge** (the human
   validates and merges).
3. Nothing in flight, no blocker → do ONE bounded useful thing (write a pending
   ADR, focused code review of recent commits).
4. Next step needs a human design decision → state the question and STOP; never
   guess.

## Hard rules to state explicitly

- Never force-push, never rewrite published history, never merge PRs.
- Always `git fetch` + rebase onto origin before pushing.
- **"Read-only is a valid outcome. If nothing genuinely needs doing, say so in
  two lines and stop — do not invent work."** Without this, an hourly agent
  manufactures busywork.
- Don't leave long-running builds in the background; sweep for stray
  `rustc`/`cargo` processes before finishing.
- Report honestly: never claim a check passed that you did not run. Ask it to
  separate "verified by me, actually run" from "not verified — CI is running
  it", and to flag residual risk.

Scope `enabled_toolsets` to what the job needs (e.g. terminal, file, web,
delegation) to cut per-tick token overhead.

## Delivery pitfall: the job runs fine but the user sees nothing

A job can complete successfully and still appear dead. Check both fields:

```
last_status: ok
last_delivery_error: "no delivery target resolved for deliver=all"
```

`deliver='all'` resolves to nothing when no gateway-connected channel exists
(a desktop/CLI session is not one). Point it at a concrete target — copy the
value from an existing working job (`cronjob action='list'`).

**Past output is recoverable regardless**, so read the last run before assuming
failure:

```
~/.hermes/cron/output/<job_id>/<timestamp>.md
```

That file contains the injected script output, the full prompt, and the
agent's response.

Also note: triggering a manual run can return
`"Job is already being fired by the scheduler; not run again."` — that is
success, not an error; the scheduler already picked it up.
