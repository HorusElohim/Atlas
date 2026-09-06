---
name: shell-workflow-verification
description: "Use for strict-mode developer and AI shell wrappers."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [bash, shell, scripts, wrappers, flutter, cargo, ai-output, verification]
    related_skills: [shared-dev-host-safety]
---

# Shell Workflow Verification

Use this skill when creating, consolidating, or debugging developer-facing or
AI-facing shell wrappers around builds, tests, generators, or app launchers.
The goal is a script that works in both interactive developer mode and concise
AI mode without hiding failures or corrupting arguments.

## Workflow

1. **Inventory before replacing scripts.** List the script directory and search
   the repository for every script name. Preserve specialized platform/codegen
   scripts unless the unified wrapper demonstrably replaces their behavior.
   Remove only confirmed legacy wrappers, and update stale documentation and
   comments in the same change.

2. **Define the CLI contract.** Keep platform, clean, build profile, device,
   dry-run, and forwarded tool arguments distinct. Document defaults and give
   examples for the no-argument path, a platform override, and a device path.

3. **Use strict mode safely.** `set -euo pipefail` is appropriate, but every
   optional array must be guarded before expansion. This includes parsed
   positional arrays and intermediate arrays passed from one wrapper to another:

   ```bash
   if [[ ${#ARGS[@]} -gt 0 ]]; then
     COMMAND_ARGS+=("${ARGS[@]}")
   fi
   ```

   Do not test only populated examples; invoke the exact default command, since
   an empty initialized array can still trigger `nounset` in Bash wrapper code.
   See `references/bash-strict-mode.md` for the reusable checklist.

4. **Separate status from subprocess output.** One-line lifecycle messages such
   as cleaning, resolving, building, running, and success should remain visible
   in both developer and AI modes. In AI mode, buffer only verbose Cargo/Flutter
   (or equivalent) subprocess output: discard it on success, replay it in full
   on failure, and return the subprocess's original exit code. Do not replace
   full error output with a generic summary.

5. **Make run wrappers build first.** A run helper should invoke the build helper
   with the same platform/profile/clean/forwarded options, wait for it to finish,
   and only then launch the target. Avoid duplicate platform-native build logic
   when Flutter, Xcode, Gradle, or a retained specialized helper already owns it.

6. **Verify without unintended side effects.** Run shell syntax checks and
   dry-run checks for the default path, each supported platform family, clean,
   device forwarding, and AI mode. Use a temporary fake subprocess to verify
   that success is concise and failure replays complete output with the original
   status. Do not launch a real app merely to test argument parsing.

7. **Finish safely.** Run `git diff --check`, inspect the deletion list, update
   docs/changelog, rebase immediately before pushing, push, verify the remote
   SHA, and confirm a clean worktree.

## Pitfalls

- A guard added to the build wrapper does not protect arrays parsed separately
  by the run wrapper; audit every expansion in both scripts.
- `--dry-run` must not accidentally invoke dependency resolution, cleaning, or
  app launch. It should print commands instead.
- AI-mode capture must not swallow stderr on failure or normalize the exit code.
- A script with a similar name may still be specialized. Delete it only after
  checking repository references and documenting the replacement.
- Do not treat dependency update notices from package managers as build errors.

## Reference

- `references/bash-strict-mode.md` — strict-mode array, capture, and test
  patterns for build/run wrappers.
