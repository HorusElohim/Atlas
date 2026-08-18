---
name: shared-dev-host-safety
description: "Safe builds on shared/limited hosts; rebase before push."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [builds, resource-management, git, ci, collaboration, oom, cleanup]
    related_skills: [systematic-debugging, github-pr-workflow, subagent-driven-development]
---

# Shared Dev-Host Safety

Practices for doing real development work (builds, tests, git pushes) on a
host or repo you don't fully control alone: a resource-constrained machine
that also runs long-lived production services (e.g. a Hermes gateway/dashboard
on an edge box), or a git branch other agents/contributors are actively
pushing to. The common failure mode is collateral damage — you starve a
neighboring service, or you silently overwrite someone else's concurrent work
— because you optimized only for "did my task succeed."

## 1. Building on a memory/resource-constrained host

**Trigger:** the host has limited RAM (check `free -h` — no swap and a few GB
total is a red flag), and/or it runs other always-on processes you didn't
start (systemd --user services, daemons, a dashboard/gateway).

- Before a heavy build (large dependency trees: Rust workspaces with
  crypto/network/db crates, monorepo builds, ML training), check `free -h`
  and `df -h /` first to establish a baseline.
- Prefer scoped commands over whole-workspace ones: `cargo check` before
  `cargo build`, `cargo test -p <crate>` before `cargo test --workspace`,
  `pytest tests/module` before the full suite. Only escalate to the
  full/workspace command once you have a reason to believe it's needed.
- Cap build parallelism explicitly on constrained hosts: `CARGO_BUILD_JOBS=2`,
  `--test-threads=1` or `2`, `make -j2`, etc. Don't rely on the tool's default
  parallelism, which is usually tuned for a dedicated CI runner, not a shared
  edge box.
- Run heavy/long builds via a **background** process (not foreground), so an
  interrupted turn doesn't leave you guessing whether it's still running —
  poll or wait on it in follow-up calls instead of blocking.
- **A linker/compiler death with no application-level error is very likely
  resource exhaustion, not a code regression.** Signature: `collect2: fatal
  error: ld terminated with signal 9 [Killed]`, a process just vanishing, or
  an unexplained timeout with no compiler diagnostic. Confirm via
  `dmesg | tail -30 | grep -iE "oom|killed"` and `free -h` before writing this
  up as a bug in the change you just made. Retry the *same* command with
  reduced parallelism/scope to confirm — don't immediately blame the diff.
- Don't retry the full heavy command in a loop hoping it succeeds — each
  attempt risks starving the host's other services further. If a scoped/
  lower-parallelism run already gives you enough confidence (clean
  `check`/`clippy` + passing per-crate/per-module tests), that combination is
  legitimate verification; you don't have to reproduce the exact CI command
  locally on a host that can't safely run it.

## 2. Post-task resource leak sweep

**Do this after any task that spawned background processes, heavy builds, or
tests — every time, not just when something looked wrong.** A task isn't
finished until the host is back to a clean, quiet state.

```bash
# 1. No stray build tooling left running
ps aux | grep -E "rustc|cargo|/usr/bin/ld|^cc |node|python.*build" | grep -v grep

# 2. Every background/process-tool session you spawned is exited, not running
#    (check via the process/background-job listing tool, not just ps)

# 3. Long-lived services you don't own are still alive and responsive
ps aux | grep -E "<the service process names>" | grep -v grep

# 4. Memory/disk are back to baseline, no lingering pressure
free -h
df -h /

# 5. Scratch files are gone
rm -f /tmp/<scratch-logs-you-created>
```

If you killed anything to free resources mid-task, re-verify after the kill
that nothing you needed (services, the user's other work) got caught in the
blast radius — `pkill -f <pattern>` with a loose pattern can match more than
you intended.

## 3. Rebase onto origin before every push, not just the first

**Applies whenever a branch has more than one active contributor** (other
agents, CI bots, teammates) — assume it does unless you know otherwise.

```bash
git fetch origin
git log --oneline origin/<branch> -3        # see what's new upstream
git rebase origin/<branch>                   # stash first if you have uncommitted edits
```

Do this immediately before `git push`, even if you rebased earlier in the
same session — new commits can land upstream between your rebase and your
push, especially on a repo other agents are actively working. After a
non-trivial rebase (upstream touched files you also changed), re-run your
verification (build/check/test) on the combined tree before pushing — a
clean rebase (no conflicts) does not guarantee the merged result still
compiles or behaves correctly. Concretely: an "unused dependency" cleanup
removed a crate right as a concurrent commit added a new use of it in the
same file; the rebase applied cleanly but the build then failed, and the fix
was to re-add the dependency after inspecting what the new upstream commit
actually needed (`git show <sha> --stat` to see what it touched).

## 4. Auditing a large/unfamiliar codebase before proposing design changes

When asked to plan or redesign something in a codebase you don't have full
context on (especially one with signs of multi-agent churn — duplication,
abandoned parallel implementations, stale docs), don't try to read everything
yourself serially. Dispatch parallel, narrowly-scoped, **read-only** subagents
via `delegate_task`, one per facet, each with:

- explicit context about the project, the suspected problems, and any
  concrete leads to check (e.g. "this README mentions a directory that isn't
  in the actual workspace members — verify it")
- an `output_schema` so every subagent returns comparable structured findings
  (module map, duplication findings, dead/orphaned code, overengineering
  signals, top risks) instead of free-form prose you have to re-parse
- an explicit read-only constraint ("do NOT modify any files")

Good facet split for a client+server or frontend+backend app with history to
mine: (1) backend/service code, (2) frontend/client code, (3) git history
archaeology (`git log --oneline --all --graph`, deleted files, churn
hotspots, changelog narrative) to find abandoned pivots and residue left
behind. Synthesize their structured results into one findings document
yourself before proposing any design — don't let a subagent's audit double as
the design proposal; keep those two steps separate so the user can validate
facts before design opinions enter the picture.
