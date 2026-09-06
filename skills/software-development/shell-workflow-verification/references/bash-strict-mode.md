# Bash Strict-Mode Wrapper Checklist

Use this checklist for scripts with `set -euo pipefail` that parse and forward
optional arguments.

## Empty arrays

Bash wrapper arrays can fail under `nounset` when expanded with no elements.
Guard every optional expansion, including arrays created by a second parser:

```bash
if [[ ${#POSITIONAL[@]} -gt 0 ]]; then
  FORWARDED=("${POSITIONAL[@]}")
else
  FORWARDED=()
fi

if [[ ${#FORWARDED[@]} -gt 0 ]]; then
  COMMAND+=("${FORWARDED[@]}")
fi
```

Audit both a build helper and its run wrapper; fixing one does not fix the other.

## AI output capture

For a subprocess `run` helper:

1. Create a temporary log file.
2. Redirect both stdout and stderr into it.
3. On success, remove the log and print only the wrapper's one-line status.
4. On failure, capture `$?` immediately, replay the complete log to stderr,
   remove the log, and return the saved status.

Never use `||` in a way that overwrites the subprocess status, and never print
only the final line of a failed Cargo/Flutter command.

## Verification matrix

At minimum, run:

```bash
bash -n tool/build.sh tool/run.sh
tool/build.sh --dry-run
tool/run.sh --dry-run
tool/run.sh ios --dry-run --clean --device test-device
tool/run.sh macos --dry-run --dart-define=MODE=test
git diff --check
```

Use a temporary fake `flutter` executable to verify that AI success is concise,
AI failure contains complete output, and the failure exit code is preserved.
Do not launch the actual app for argument-parser tests.
