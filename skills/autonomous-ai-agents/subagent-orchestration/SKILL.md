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

## The moving-tree trap: children read a snapshot, you keep editing

A child that inspects shared mutable state (a working tree, a database, a
scratch dir) reads it **at its own pace, over tens of seconds**. Anything you
change while it runs is invisible to it. Its verdict describes the world as it
was at dispatch — but arrives phrased in the present tense, and reads as
authoritative.

**Observed:** dispatched a read-only reviewer against an uncommitted working
tree, then kept fixing things while it worked. 79s later it returned
`passed: false` naming two defects — both already fixed. Acting on that verdict
literally would have meant dispatching a fix agent to repair correct code.

**Rules:**

1. **Quiesce before dispatch.** Stop editing the shared state. For a git tree,
   `git add` first — a staged diff is a frozen diff, and it guarantees you and
   the child are reading the same bytes.
2. **Treat every finding as a hypothesis about a past state.** Before acting on
   one *or dismissing it*, re-check the live state at the named symbol. Never
   let a child's claim be the last word on the current tree.
3. **Harvest suggestions even when the defect is stale.** A finding that was
   correct at dispatch and is now fixed still tells you something — most often
   that the fix has no regression test pinning it. "Already fixed" frequently
   means "fixed but unpinned".
4. **Report honestly.** Don't call a review clean because it came back stale.
   Say which findings you verified, against what, and what you did with each.

The fix is freezing the input, never skipping the child.

## Live control while children run

- `delegate_task(action='list')` — live children + ids.
- `delegate_task(action='steer', subagent_id=, message=)` — redirect a drifting
  child without stopping it (watch its transcript to catch drift).
- `delegate_task(action='stop', subagent_id=)` — end one early; its partial
  result still returns.

## Iterative review rounds on security-sensitive surfaces

Don't treat one clean-passing independent review as the finish line for code
that validates untrusted input against a deny/allow list (SSRF address
policies, URL parsers, path-traversal guards, auth checks). Dispatching a
second and third independent reviewer AFTER fixing round one's findings tends
to surface *genuinely different* gaps each time, not restate the same one —
observed on one exact-source-fetch address policy: round 1 caught missing
private/loopback ranges, round 2 caught IPv4-mapped/NAT64/6to4 embedding,
round 3 caught the deprecated IPv4-compatible IPv6 form none of the first two
named. Keep dispatching fix-then-reverify rounds until a fresh reviewer
returns no new finding — not merely until one round returns `passed: true`.

When a later round's finding no longer matches the current code (because an
earlier round's fix already covers it, or the reviewer was dispatched against
a commit since superseded by further work), don't silently redo a no-op fix
and don't silently ignore the claim either — grep/read the live code for the
named symbol, and say explicitly in the follow-up ('this claim was already
fixed in commit X') rather than treating the mismatch as either a pass or a
new defect.

## Pitfalls

- Don't assume children run on the chat's current model. Verify
  `delegation.model` before dispatching anything latency-sensitive.
- Don't poll `wait` in a loop — you'll burn the whole turn. Dispatch, keep
  working, act on the completion message when it arrives.
- Child summaries are SELF-REPORTS. For anything with external side effects,
  verify the artifact yourself. For read-only audits, cross-corroborate the
  reports against each other (they often confirm the same finding from
  different angles — that's your confidence signal).
- Child summaries are also STALE the moment shared state moves. See the
  moving-tree trap above: freeze the input before dispatch, and re-verify every
  finding against the live state before acting on it.
- **`action='steer'` can silently miss its target.** If the child finishes
  before the steer message is delivered, the result explicitly says
  `steer did not land — the subagent finished before it could be delivered`.
  This is not an error to retry — the child already returned its result by
  then; read that result and move on rather than re-issuing the steer.
- After any config repoint, the leak-sweep habit applies: confirm you reverted.
