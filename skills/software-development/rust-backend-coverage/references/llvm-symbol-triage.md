# LLVM symbol triage

A raw `cargo llvm-cov` function list may contain mangled symbols such as async
closures and duplicate instantiations. Map the source path and symbol suffix
to declarations before adding tests.

## Categories

- `follow_*`, `publish_*`, `resolve`, `acquire`: real worker workflows. Drive
  them through deterministic substrate doubles and shutdown notifications.
- `...NCNv...`/similar closure or future symbols: compiler-generated bodies;
  cover by exercising the parent async workflow, never by invoking the symbol.
- `Debug::fmt`: cover only when the representation is a meaningful public
  contract; otherwise do not add a test solely for formatter percentage.
- `app_store` under `cfg(not(test))`: the normal test binary cannot execute the
  production cache twin. Treat it as an explicit build-configuration artifact.
- redb conversion arms requiring internal transaction/table/commit failures:
  do not manufacture impossible healthy-store failures just for coverage.

## Portalis gate

From the repository root:

```bash
bash tests/nexus.sh > /tmp/nexus-coverage.log 2>&1
rc=$?
printf 'gate exit=%s\n' "$rc"
grep -E 'Uncovered functions|Coverage summary|functions    |regions     |lines       |Coverage gate' /tmp/nexus-coverage.log | tail -12
rm -f /tmp/nexus-coverage.log
exit "$rc"
```

The 95% function floor is mandatory. Keep uncovered lines visible and explain
why any intentionally unreachable spans are excluded.
