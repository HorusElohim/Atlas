---
name: hermes-cron-troubleshooting
description: "Diagnose failed/skipped Hermes cron jobs and fix them."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, cron, troubleshooting, drift-guard, scheduled-jobs]
    related: [hermes-agent]
---

# Hermes Cron Job Troubleshooting

Diagnose and fix Hermes scheduled (cron) jobs that appear to fail, skip, or stop delivering. Most "job failed" reports are NOT job logic failures — they are blocked by guard rails or delivery misconfig. Identify the class first, then apply the matching fix.

## Diagnosis flow (always start here)

```bash
hermes cron list          # find the job: last_status, last_error, last_run_at
```

Read `last_error` carefully — it usually names the failure class:

| Marker in `last_error` | Class | Fix |
|---|---|---|
| `[drift_skip]` / `[drift_skip:silent]` | Provider/model drift guard (#44585) | Pin the job (see below) |
| `[blocked_config]` | Config validation blocked the run | Fix the config, not the job |
| `Connection error` / provider timeout | Provider unreachable | Check provider host is up |
| `last_status=error` but `last_run_at` stale | Run never dispatched | Check gateway + manual re-trigger |
| `Interrupted by shutdown` | Gateway restarted mid-run | Re-run the job |

Supporting evidence:
```bash
tail -20 ~/.hermes/cron/usage_audit.jsonl   # per-fire audit: model, tokens, duration, error
```

## Class 1: Drift guard (`drift_skip`) — most common

**What it is:** An UNPINNED job (no explicit `provider`/`model`) follows the global default model. If the global config changed after the job was created (e.g. `anthropic/claude-opus-5` → `atlas/Qwen3.8-27B`), the guard fails closed — skips the run, makes NO LLM call, alerts once (silent after). Purpose: prevent silent spend on a different, possibly pricier, config.

**Fix — pin the job explicitly:**

```bash
hermes cron edit <job_id> --model <model> --provider <provider>
```

⚠️ The `cronjob` tool's `action=update` does NOT expose model/provider params — use the CLI. After editing, verify the pin landed:

```bash
python3 -c "
import json
from pathlib import Path
j=[x for x in json.loads((Path.home()/'.hermes/cron/jobs.json').read_text())['jobs'] if x['id']=='<job_id>'][0]
print(j.get('provider'), j.get('model'))
"
```

**Verify the guard is satisfied** (optional but definitive — calls the guard's own logic):

```bash
cd ~/.hermes/hermes-agent && venv/bin/python -c "
import json
from hermes_cli.config import cron_model_drift_axes, read_user_config_raw, get_hermes_home
from hermes_cli.runtime_provider import resolve_runtime_provider
job=json.load(open(str(get_hermes_home()/'cron/jobs.json')))['jobs'][<idx>]
snap=resolve_runtime_provider(requested=None)
cp=str(snap.get('provider') or '').strip().lower()
cfg=read_user_config_raw(get_hermes_home()/'config.yaml')
print('drifted axes:', cron_model_drift_axes(job, current_provider=cp, current_model='<current-model>', config=cfg))
"
# [] = guard satisfied, job will run
```

The guard skips an axis if the job has an explicit value for it (`hermes_cli/config.py: cron_model_drift_axes`) — a pinned axis never drifts.

## Re-running a job to confirm the fix

⚠️ `hermes cron run <job_id>` BLOCKS until the agent run completes — LLM jobs can take 3–10 min. A foreground call with default timeout will be killed at ~180s and the run may not even dispatch. Run in background:

```bash
# terminal tool: background=true, notify_on_complete=true
hermes cron run <job_id>
```

Then check results:
```bash
tail -1 ~/.hermes/cron/usage_audit.jsonl   # new entry with error=null = success
ls -t ~/.hermes/cron/output/ | head -3     # latest output file
```

## Pitfalls

- **Don't trust memory for the active model/provider.** Config changes between sessions. Always verify with `hermes config get model` / `resolve_runtime_provider` before reasoning about which model a job will use.
- **`cronjob action=update` ≠ `hermes cron edit`.** The tool lacks model/provider params; the CLI has them. The error message even suggests the tool form, but the tool silently ignores it.
- **Pin to the RIGHT config, not just any config.** Pinning a job meant for Opus onto a free local model to "unblock" it changes the work quality — ask the user which they want when in doubt.
- **Alert-once semantics:** after the first drift alert, subsequent skipped ticks are silent. A job can sit broken for days without further messages. Check `last_run_at` staleness proactively.
- **Provider name forms:** config may show `custom:atlas` while jobs store `atlas`. The guard lowercases and compares; the CLI accepts the bare provider name (`atlas`), which is what `resolve_runtime_provider` also returns.
