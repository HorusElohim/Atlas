# In-flight run blocks manual triggers

Observed 2026-08-18: after re-pinning a cron job from Qwen to claude-opus-5 (`hermes cron edit <job_id> --model claude-opus-5 --provider anthropic`), an immediate `cronjob action=run` was rejected:

```
execution_skipped: "Job is already running (a scheduler tick or another manual run is executing it); not started again."
```

A scheduled run that had started under the OLD pin was still in flight (stuck on a 180s local-API timeout loop). A new run cannot start until it reaches a terminal state, and the in-flight run keeps the OLD model — so triggering immediately after a pin change is silently a no-op.

## Working procedure

1. Poll the top run entry until it leaves `running`:

   ```bash
   hermes cron runs <job_id> | head -1
   # running → wait; completed/failed → proceed
   ```

2. Do NOT restart the gateway to force the lock — a stuck run self-terminates when its API calls time out (e.g. `Non-streaming API call timed out after 180s`), which releases the lock.

3. Trigger again — this run starts under the NEW pin.

4. Verify the live run's actual model from the gateway log, not from stored config:

   ```bash
   grep -E "<job_id>" ~/.hermes/logs/agent.log | tail -5
   # expect API-call lines like: model=claude-opus-5 provider=anthropic in=... out=...
   ```

Other live-run evidence: `hermes cron runs <job_id>` (start time + source=builtin/direct), and `~/.hermes/sessions/request_dump_cron_<job_id>_<ts>_*.json` marking the run window.
