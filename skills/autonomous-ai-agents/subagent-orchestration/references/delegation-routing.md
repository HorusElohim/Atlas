# Delegation Routing — stall signature & decision table

## The exact stall signature (from a real session)

A parallel `delegate_task` batch dispatched to a busy local node returned:

```
[ASYNC DELEGATION BATCH COMPLETE — deleg_xxxx]
Role: leaf   Model: Qwen3.8-27B   Total duration: 692.1s
--- ✗ TASK 1/3: ... (status=interrupted, api_calls=1, 688.01s) ---
Partial output:
Operation interrupted: waiting for model response (411.1s elapsed).
```

Tells:
- `Model: <local-model-name>` in the batch header — NOT the chat's active model.
- `api_calls=1` — the child never got past its first model call.
- `status=interrupted` with `waiting for model response (~400s elapsed)`.
- Live transcript `.hermes/cache/delegation/live/<id>/task-N.log` shows only the
  `kickoff` and `start` lines, no `tool ->` / `result` lines.

Contrast a healthy child (same session, after repointing to cloud): transcript
fills with `tool -> search_files`, `result ok 0.1s`, `read_file`, etc. within
seconds, and the batch completes with `status=completed, api_calls=11-19`.

## Why routing is independent

`hermes config get model` shows the CHAT model. Delegated subagents route via
the SEPARATE `delegation:` block in `~/.hermes/config.yaml`:

```
delegation:
  max_iterations: 250
  provider: atlas          # <- a self-hosted/local node in this fleet
  model: Qwen3.8-27B
```

A `[System: active model changed]` notice about the CHAT does not change
delegation routing. Always check the `delegation:` block, not the chat model,
before latency-sensitive fan-out.

## Decision table

| Situation | Action |
|-----------|--------|
| Local delegation node busy/offline, work is urgent | Repoint delegation to a reachable cloud provider, re-dispatch, revert after |
| Local node will free up soon, work not urgent, cost matters | Wait, then re-dispatch on local as originally configured |
| Only 1-2 sub-tasks, results must be reasoned over in full | Skip delegation — run inline on the chat model |
| Repoint chosen | Back up config, set provider+model, verify, stop stuck children, re-dispatch SAME tasks, REVERT + confirm when done |

## Revert discipline

The local node is usually the default for cost reasons (routing cheap/simple
work to a self-hosted model). ALWAYS revert after a temporary cloud repoint, and
confirm with `grep -A4 '^delegation:' ~/.hermes/config.yaml`. Treat the revert
as part of the task's completion, not optional cleanup.
