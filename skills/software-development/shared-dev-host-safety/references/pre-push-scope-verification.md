# Pre-push scope verification

A clean working tree and successful `git push` do not prove the requested
implementation was included. Before reporting completion, compare the branch
to its base:

```bash
git diff --stat origin/<base>...HEAD
git diff --name-status origin/<base>...HEAD
```

Confirm the intended implementation paths—not only documentation—appear in the
branch. This catches the failure mode where a docs-only commit is pushed while
the user expected code. If the scope is wrong, stop and correct it before
opening or reporting the PR.
