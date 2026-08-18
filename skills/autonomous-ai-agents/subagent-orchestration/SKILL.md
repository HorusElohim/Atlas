---
name: subagent-orchestration
description: Orchestrate delegate_task subagents; recover stalls.
version: 1.0.0
metadata:
  hermes:
    tags: [delegation, subagents, parallel, orchestration, delegate_task, fan-out]
    related_skills: [plan, claude-code, codex]
---

# Subagent Orchestration

Use when a task is large enough to blow the parent's context or splits into
independent workstreams, and you reach for `delegate_task`. Covers the parallel
fan-out pattern, structured outputs, and — most importantly — recovering when
delegated subagents STALL because of the delegation model/provider routing.

## When to fan out vs do it inline

Fan out when ALL hold:
- The work splits into 2+ genuinely independent sub-investigations (e.g. audit
  backend / frontend / git-history separately).
- Each sub-investigation would flood the parent context with intermediate reads
  (large codebases, many files) that the parent doesn't need verbatim.
- You only need each child's *conclusions*, not its raw exploration.

Do it inline (no delegation) when the sub-results must be reasoned over in full,
or when the pieces depend on each other sequentially.

## Parallel fan-out recipe (proven)

1. Pass ALL context each child needs — children know NOTHING of this
   conversation. Include repo paths, branch, the user's suspicion/goal, and
   concrete leads you already spotted (e.g. "src/nexus.rs vs src/core/nexus.rs
   look like parallel impls — confirm"). Specific leads dramatically raise
   audit quality.
2. Give each task an `output_schema` with the exact fields you'll synthesize
   (module_map, duplication_findings, dead_code, risks, ...). Structured output
   is far easier to merge than prose.
3. State READ-ONLY explicitly when it's an audit ("do NOT modify files; use
   git log/show/diff only; restore HEAD if you touch it").
4. Dispatch the whole batch in ONE `delegate_task` call with a `tasks` array —
   they run in parallel and the consolidated result re-enters as one message.
   Do NOT poll; keep working.
5. Child summaries get TRUNCATED into the parent (head+tail). The FULL output is
   saved to `~/.hermes/cache/delegation/subagent-summary-*.txt` — `read_file`
   those paths to get every field before synthesizing.
6. Live transcripts stream to
   `.hermes/cache/delegation/live/<deleg_id>/task-N.log` — `tail` them to watch
   a child work or confirm it's making real tool calls (not stalled).

## Stall recovery: the delegation-routing trap

**Symptom:** subagents dispatch but never produce tool calls; the live
transcript shows only `kickoff` + `start`, and the batch eventually returns
`status=interrupted` with `Operation interrupted: waiting for model response
(~400s elapsed)` and `api_calls=1`.

**Root cause:** delegation routing is separate from the chat's active model.
Check `~/.hermes/config.yaml` → `delegation.provider` / `delegation.model`. If
those point at a LOCAL/self-hosted node (e.g. a GPU box running a local model)
and that node is busy or offline, the children hang waiting for a model
response that never comes. Restarting them unchanged just re-stalls on the same
dead node.

**Fix (temporary repoint, then revert):**
```
# 1. back up config
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-<task>
# 2. repoint delegation to a cloud provider that IS reachable
hermes config set delegation.provider anthropic
hermes config set delegation.model claude-sonnet-5
# 3. verify
grep -A4 '^delegation:' ~/.hermes/config.yaml
# 4. stop the stuck children, re-dispatch the SAME tasks
# 5. when done, REVERT to the original local routing
hermes config set delegation.provider <original>
hermes config set delegation.model <original>
rm ~/.hermes/config.yaml.bak-<task>
```
Always revert — the local node is usually the default for cost reasons. Confirm
the revert with `grep -A4 '^delegation:'` before considering the job done.

See `references/delegation-routing.md` for the full transcript signature and a
decision table (wait for local vs repoint to cloud vs run inline).

## Live control while children run

- `delegate_task(action='list')` — live children + ids.
- `delegate_task(action='steer', subagent_id=, message=)` — redirect a drifting
  child without stopping it (watch its transcript to catch drift).
- `delegate_task(action='stop', subagent_id=)` — end one early; its partial
  result still returns.

## Pitfalls

- Don't assume children run on the chat's current model. Verify
  `delegation.model` before dispatching anything latency-sensitive.
- Don't poll `wait` in a loop — you'll burn the whole turn. Dispatch, keep
  working, act on the completion message when it arrives.
- Child summaries are SELF-REPORTS. For anything with external side effects,
  verify the artifact yourself. For read-only audits, cross-corroborate the
  reports against each other (they often confirm the same finding from
  different angles — that's your confidence signal).
- After any config repoint, the leak-sweep habit applies: confirm you reverted.
