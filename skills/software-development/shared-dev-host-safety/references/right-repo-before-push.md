# Right repo before push (multi-repo user)

Pitfall recorded 2026-08-18: user asked to "push the latest commit"; agent
reported "nothing to push" from `~/Atlas` (which really was in sync), but the
actual target was `feat/adr-0002-storage-redb` in the sibling `~/PortalisApp`
repo. User had to correct the target.

## Rule

The terminal CWD is NOT a reliable indicator of which repo the user means.
Before acting on any push/commit request:

1. If the user named a branch, confirm it exists in the current repo:
   `git branch -a | grep <branch>` and `git ls-remote --heads origin <branch>`.
2. If it doesn't exist here, find the owning repo before answering:
   ```bash
   for d in ~/*/; do
     (cd "$d" 2>/dev/null && git ls-remote --heads origin | grep -q "<branch>" && echo "$d")
   done
   ```
3. `cd` there, verify `git log origin/<branch>..<branch>` shows the unpushed
   commit, push, then verify with `git ls-remote origin <branch>` matching
   local HEAD.
4. Never answer "nothing to push" based on one repo's state without checking
   the branch name the user actually mentioned.
