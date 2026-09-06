# ADR Refactor Review: Pin the Correct Ref

Before deciding whether an ADR-backed refactor is implemented:

1. Confirm the absolute repository path, current branch, worktree status, and the exact commit/ref under review.
2. If the user refers to an updated ADR or feature branch, inspect that ref explicitly with `git branch -a`, `git log --all -- <path>`, `git show <ref>:<path>`, and `git diff <base>..<ref>`.
3. Separate implementation status from ADR governance status. Code may be implemented while the ADR remains `proposed` pending owner validation.
4. For structural refactors, verify the target tree and rename/delete diff, not only the current checkout's file names. A clean current worktree says nothing about another branch.
5. If tests are delegated to another host, require the exact ref, commands, exit codes, and real output. A timeout or agent self-report is not a passing test result.

This prevents a stale checkout from being mistaken for the user's updated implementation.