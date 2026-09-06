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
- **A test binary that segfaults (`Segmentation fault (core dumped)`, exit
  139) with zero test output — not even the first `running N tests` line —
  is very likely test-thread over-parallelism racing for resources, not a
  real regression**, especially right after a clean `cargo build`/`cargo
  test` of a single target succeeded. Before treating it as a bug, retry the
  identical command with explicit `-- --test-threads=4` (or lower) appended;
  a full `cargo test --all-targets --all-features` spawns one thread per
  logical CPU by default, which on a shared host with several async/tokio
  integration tests already using their own thread pools can starve or
  crash the test harness itself even though `free -h` looks fine. If the
  reduced-thread run passes cleanly, that is legitimate verification — no
  need to chase the segfault further.
- **`clippy` (or `clippy-driver`) panicking with "the compiler unexpectedly
  panicked. This is a bug" (an internal compiler error / ICE) on a crate you
  did not touch this session is very likely a transient toolchain flake, not
  a real lint violation.** This has recurred on unrelated crates across
  sessions on this host. Before investigating the named crate, simply retry
  the identical `cargo clippy` invocation once — if it passes cleanly on
  retry, that confirms transience and is legitimate verification; only
  escalate (bisect toolchain version, file upstream issue) if it reproduces
  twice in a row.

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

## 4. Committing one verified fix while unrelated work sits uncommitted

**Trigger:** the working tree has a verified, ready-to-ship fix (e.g. a
security patch that just passed review) alongside a SEPARATE unrelated
change that is still mid-flight and NOT yet verified (e.g. a platform-specific
rewrite you can't build/test on this host, a different feature branch's
draft). You need to commit and push only the verified piece now.

Don't `git add -A` or `git commit -a` here — that silently rides the unverified
work into the same commit under the verified one's cover, and pushes it too.

```bash
git stash push -m "<description> in progress, unverified" -- <path1> <path2>
git add <verified-files>
git commit -m "..."
git fetch origin && git rebase origin/<branch> && git push origin <branch>
git rev-parse HEAD                                   # confirm...
git ls-remote --heads origin <branch> | cut -f1       # ...matches remote
git stash pop                                         # restore the unrelated work
```

Scope the stash to exact paths (`git stash push -- <paths>`), not a bare
`git stash push`, so anything else uncommitted is left alone. Always `git
stash pop` immediately after the push completes — don't leave work stashed
across turns; it's easy to forget it exists and lose track of in-progress
changes.

## 5. `git push` rejected for touching `.github/workflows/*`

**Symptom:** every other file in the commit is fine, but push fails with
`refusing to allow an OAuth App to create or update workflow `.github/
workflows/<name>.yml` without `workflow` scope`, even though `gh auth
status` shows the token as authenticated with `repo`.

This is a GitHub-side restriction independent of `repo` scope: modifying a
workflow YAML file requires the token to also carry `workflow` scope. An
already-logged-in `gh` session needs a scope **refresh**, not a fresh login:

```bash
gh auth refresh -h github.com -s workflow
```

This starts a device-code flow — it prints a one-time code and
`https://github.com/login/device`. It cannot be completed non-interactively:
relay the code and URL to the user, wait for them to approve it in their
browser, then confirm with `gh auth status` (the `scopes:` line must now
include `workflow`) before retrying the push. Running the refresh as a
**background** process is worth it here specifically because the user's
browser confirmation can take a while and an interrupted foreground call
loses the device code — `terminal(background=true)` then `process(action=
'poll')` survives that wait cleanly.

## 6. Editing the same logical file across multiple worktrees of one repo

**Trigger:** the host has more than one checkout of the same project (e.g.
`~/Project`, `~/Project-0003`, `~/Project-feature`), each on a different
branch. `cd <relative-or-remembered-path>` silently lands in the wrong
worktree, and `patch`/`write_file` then create or edit a file in a checkout
you didn't mean to touch — the tool reports success because the path is
valid, it's just the wrong tree.

- Prefer absolute paths for every file operation once more than one worktree
  is in play; don't rely on a shell `cd` you did several calls ago.
- Before editing, confirm you're where you think you are:
  `git rev-parse --show-toplevel` and `git branch --show-current`.
- If a `patch`/`write_file` call reports success against a file you didn't
  expect (e.g. it resolves under a *different* worktree root than the one
  named in your instruction), stop and re-verify with `pwd`/`git status`
  before continuing — don't assume the tool guessed correctly and keep
  layering edits on top.
- In nested repositories, keep the build root and Git root explicit. For
  Portalis-like layouts where Cargo.toml is below the Git root, run Cargo
  from the manifest directory (or pass --manifest-path), but stage and
  commit paths relative to git rev-parse --show-toplevel. Verify both roots
  before every combined test-and-commit command; a passing test followed by a
  pathspec failure is a workflow error, not a code failure.
- When the user reports behavior from a running desktop/device build, verify
  that build's source worktree and branch before diagnosing the code. Multiple
  checkouts may contain the same package with different behavior; a correct
  fix in an inactive checkout will not change the visible app. Confirm the
  target worktree with `git rev-parse --show-toplevel` and
  `git branch --show-current`, then rebuild/restart from that exact tree and
  re-test the reported behavior.

- The Hermes desktop project registry and the shell/tool working directory
  are separate pieces of state. After the user identifies the intended
  checkout, inspect the project registry, explicitly switch the chat to the
  matching project (rather than merely relying on `cd`), and verify again with
  both the project primary path and `git rev-parse --show-toplevel` plus
  `git branch --show-current`. For direct file reads, use the verified
  absolute path under that checkout; a stale workspace path can make
  `read_file` appear broken even when the tool is healthy. Do not reconfigure
  or edit a similarly named backup repository to correct an active desktop
  project.

## 7. Headless Android emulator verification

When validating Flutter Android builds on an SSH or display-less Linux host,
follow the evidence-first procedure in
[`references/headless-android-emulator.md`](references/headless-android-emulator.md).
In particular, separate Flutter's launcher behavior from the emulator binary,
require an actual ADB boot before claiming success, and clean stale AVD locks
only after checking for live emulator processes.

## 9. Flutter Android release build fails with an AAR metadata desugaring error

**Symptom:** `flutter build apk --release` (locally or in CI) fails at Gradle,
not at `flutter pub get` or the Rust cross-compile step:

```
* What went wrong:
Execution failed for task ':app:checkReleaseAarMetadata'.
> A failure occurred while executing ...CheckAarMetadataWorkAction
   > An issue was found when checking AAR metadata:
       1.  Dependency ':some_plugin' requires core library desugaring to be
           enabled for :app.
```

This fires whenever a newly added (or upgraded) plugin's Android AAR ships
Java 8+ APIs (`flutter_local_notifications` is a common trigger, but any
plugin touching `java.time`, streams, etc. can do it) and the app module's
`android/app/build.gradle(.kts)` has never turned on desugaring. It is a real
AGP/dependency requirement, not a flaky or environment-specific failure — it
will recur the next time a similar plugin is added if left unfixed.

**Fix**, in the app module's Gradle file:

```gradle
android {
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
        coreLibraryDesugaringEnabled = true   // add this line
    }
}

dependencies {
    coreLibraryDesugaring "com.android.tools:desugar_jdk_libs:2.1.4"
}
```

Both pieces are required — enabling the flag without adding the
`coreLibraryDesugaring` dependency fails with a different error asking for
exactly that artifact. Pin a current `desugar_jdk_libs` version; an ancient
one can itself be rejected by a newer AGP.

**Verify for real, not just "should work":** run the actual
`flutter build apk --release` locally (Android SDK + Rust Android targets
installed, e.g. via `rustup target add aarch64-linux-android` etc.) through to
a produced APK before pushing. `cargo check`/`clippy` passing says nothing
about a Gradle-layer AAR metadata failure — this class of bug is invisible to
every Rust-side check and only a real Gradle assemble catches it. After the
local verify, `./gradlew --stop` to kill the Gradle/Kotlin daemons it starts —
they idle at several hundred MB to a few GB each and outlive the build
(see §2, post-task resource leak sweep).

## 10. Default terminal `workdir` pointing at a nonexistent path

**Symptom:** a `terminal` call with no explicit `workdir` fails immediately
with `bash: line 4: cd: /some/path: No such file or directory` (exit 126),
while the same command with an explicit `workdir` (or run from a prior
session-persisted cwd) succeeds normally. This happens when the backend's
default/session cwd was set from a different project's snapshot (e.g. a
workspace path from an earlier profile or repo) that does not exist on this
host.

- Don't conclude the terminal tool is broken from one bare failure — always
  pass `workdir` explicitly (an absolute path you've already confirmed with
  `git rev-parse --show-toplevel` or similar) once you've seen this once in a
  session; every subsequent call in that session should carry it too, since
  the broken default persists across calls.
- If several tool calls in a row fail identically on unrelated commands right
  after this, re-verify with a trivial diagnostic (`pwd && ls -la`) using an
  explicit `workdir` before assuming a real regression — it is very likely
  the same stale-default-cwd issue repeating, not N independent failures.

## 8. Auditing a large/unfamiliar codebase before proposing design changes

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
