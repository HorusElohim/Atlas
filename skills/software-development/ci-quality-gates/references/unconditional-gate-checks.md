# Unconditional Gate Checks (thresholds can't fix these)

A gate usually enforces **several** conditions, and only some are wired to
tunable flags. Before proposing "lower the threshold", read the enforcement
code and find out whether the failing condition is parameterized at all.

## The pattern

```python
if functions_pct < args.min_functions:      # threshold-governed
    failures.append(f"functions {functions_pct:.2f}% < {args.min_functions:.2f}%")
if regions_pct < args.min_regions:          # threshold-governed
    failures.append(f"regions {regions_pct:.2f}% < {args.min_regions:.2f}%")
if uncovered_lines:                         # UNCONDITIONAL — no flag guards it
    failures.append(f"{sum(len(v) for v in uncovered_lines.values())} uncovered lines")
```

The third check fails on a **single** uncovered line regardless of
`--min-functions` / `--min-regions`. Setting both floors to `0` still fails.

## Signature

Reported percentages sit **above** the configured minimums, yet the job exits
non-zero.

Real instance (Portalis, Aug 2026): the repo owner lowered the floors from
`100`/`99` to `80`/`80` and pushed. CI still failed:

```
  functions    2190 / 2251   (97.29%)
  regions     30085 / 30967  (97.15%)
  lines       22073 / 22418  (98.46%)
Coverage gate FAILED: 259 uncovered lines
```

Every percentage clears 80 comfortably. The thresholds were never the binding
constraint — the unconditional per-line check was.

## What to do

Report the mismatch and stop. The genuine options are:

1. **Cover the lines** with real tests.
2. **Put the check behind its own flag** (`--allow-uncovered-lines`) if the
   project wants it optional.
3. **Delete the check** and rely on percentages.

"Lower the numbers" is not among them. Offering it burns a full CI cycle
(often 20+ minutes) to re-learn something readable from the source in seconds.

## Related tell: commit message diverging from code

The same commit's message claimed *"the region percentage is reported for
visibility but no longer fails the CI job"* — while the code still compared
`regions_pct` against a floor and appended a failure. It also said "the
function gate remains active" while setting that gate to `80`.

**Trust the code over the message**, and flag the divergence to the owner;
it usually means the change didn't do what its author believed.

## Locating which lines are actually uncovered

When the gate does name them, aggregate before reading — hundreds of
individual `file.rs:NNN` lines are unreadable raw:

```bash
gh run view --job <id> --log-failed \
  | grep -oE 'src/[a-z/_]+\.rs' | sort | uniq -c | sort -rn
```

This turns 259 scattered lines into a ranked file list, which immediately
shows whether the gap is one neglected module or a broad regression.
