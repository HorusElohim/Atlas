# Driving a Peer Build Host as a Fast Verify Loop

Companion to `peer-build-host-provisioning.md`. That file covers *getting* a
peer set up; this covers *working* on one day to day, once it exists.

## The payoff is the loop, not the hardware

| | Constrained edge node | Peer build host |
|---|---|---|
| Full coverage gate | **OOM — impossible** | **~2 min** (`cargo llvm-cov` alone: 1:27) |

Measured on a 24-core / 31 GB peer vs. a 6-core / 7.3 GB no-swap Jetson, at
~700% CPU. The same gate takes ~24 min in CI.

The change this enables matters more than the speed: when verification is
impossible locally, you push and let CI be the first real test. When it takes
90 seconds, you **measure hypotheses instead of reasoning about them**. Prefer
running the experiment over arguing from plausibility — see
`ci-quality-gates/references/uncovered-line-triage.md` for a worked case where
a confident causal story turned out to be worth 4 lines out of 424.

## Quoting: write the script, `scp` it, then run it

Nesting a heredoc inside `ssh '...'` stacks three quoting layers (local shell,
ssh's remote shell, the heredoc). Backslashes get mangled and the failure is
misleading — a Python `assert` on a string anchor fails even though the anchor
is visibly present in the file.

```bash
# FRAGILE — escaping breaks in non-obvious ways
ssh peer 'cd ~/repo && python3 - <<EOF
s = s.replace("""  --workspace \\\\""", ...)
EOF'

# ROBUST — one quoting layer, and the script stays re-runnable
write_file /tmp/patch.py  ...
scp -q /tmp/patch.py peer:/tmp/
ssh peer 'cd ~/repo && python3 /tmp/patch.py'
```

Same principle for moving local edits to the peer: generate a patch with
`git diff > /tmp/x.patch`, `scp` it, then `git apply --check` **before**
`git apply` so a bad patch fails loudly rather than half-applying.

## Capture artifacts the gate script deletes

Gate scripts commonly `mktemp` a report and `trap 'rm -f "$report"' EXIT`, so
after a run there is nothing left to analyze. To iterate on the *reporting*
half without re-running the expensive build, reproduce the tool invocation
directly with a durable output path:

```bash
ssh peer 'cd ~/proj && ignore=$(grep -oP "^ignore='\''\K[^'\'']+" scripts/coverage.sh) \
  && cargo llvm-cov --workspace --all-features \
       --ignore-filename-regex "$ignore" \
       --json --output-path /tmp/cov-keep.json -- --skip <slow-test>'
```

Then run the report script against `/tmp/cov-keep.json` as many times as needed
— seconds per iteration instead of minutes. Extract the real arguments from the
script rather than retyping them, so you are testing what CI actually runs.

## Clean up the peer, not just the local box

The post-task sweep in the parent skill applies to **every** host you touched:

```bash
ssh peer 'cd ~/repo && git checkout -- . && git status --short'   # expect empty
ssh peer 'ps aux | grep -E "rustc|cargo|llvm-cov" | grep -v grep | wc -l'  # expect 0
```

Experimental edits left on a peer are invisible from the local checkout and
will silently contaminate the next run's results — the worst kind of stale
state, because it looks like a real measurement.

## Report which host ran what

Never let a peer run stand in for a claim about CI, or vice versa. State
plainly: "ran the full gate on the peer, 365 uncovered; CI last reported 259 on
a different commit." Divergent numbers between hosts are usually different
commits or different flags, not flakiness — check before explaining it away.
