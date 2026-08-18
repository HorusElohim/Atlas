# Coverage Gate Mechanics

Detail for writing a coverage threshold gate that can explain its own failures.
Examples use `cargo-llvm-cov` (Rust), but the traps generalize to any
LLVM-source-coverage tool and most `--json`-exporting coverage tools.

## Why the built-in `--fail-under-*` flags fail blind

`cargo llvm-cov --fail-under-functions 100 --fail-under-regions 99` aborts the
run when a threshold is missed. In terminal-summary mode you'd at least see the
table. But with a **file output format** (`--lcov`, `--json`,
`--cobertura`, `--codecov`) there is no summary table produced at all, so the
run ends with a bare exit 1 and the last line in the log is whatever the tool
printed before that — typically:

```
    Finished report saved to /tmp/nexus-coverage.d37Bsv
##[error]Process completed with exit code 1.
```

No percentage. No file. No function name. Every failure then costs a full local
reproduction. Move enforcement into a script that reads the export instead.

## One invocation, not two

Do NOT run the tool once to test and again to "just read the report".
`cargo llvm-cov report` **has no workspace selection** — it answers for the
current package alone, whatever you pass it. Doing this produced a report
covering 13 files out of 71, so a per-line gate silently examined only the root
package and passed everything else.

> A gate that inspects a fifth of the code and says nothing about the rest is
> worse than no gate, because it is believed.

Run once with `--json --output-path "$report"`, then read `$report`.

## `--json` export structure

Top level: `{"data": [ { "totals": {...}, "files": [...], "functions": [...] } ]}`

- `data[0].totals` — authoritative aggregate. Keys include `functions`,
  `regions`, `lines`, `branches`, `instantiations`, each
  `{count, covered, percent}` (and sometimes `notcovered`).
- `data[0].files[]` — per file: `filename`, `summary` (same shape as totals),
  and `segments`.
- `data[0].functions[]` — per function: `name` (mangled), `filenames` (list),
  `count` (executions), `regions`.

**`totals` reflects the set AFTER `--ignore-filename-regex`; `functions[]` does
NOT.** Reading `functions[]` raw therefore contradicts the totals.

## Trap: uncovered-function list contradicts 100% totals

**Observed:** a script reported *523 uncovered functions* from a report whose
own totals said `functions 232/232 (100.00%)`.

Two independent causes, both must be handled:

1. **Unfiltered list.** `functions[]` includes files excluded by
   `--ignore-filename-regex`, and dependencies from the registry
   (`~/.cargo/registry/.../tokio-*/src/macros/select.rs` etc.). Intersect with
   the measured file set first.
2. **Each crate is compiled twice — with and without `cfg(test)`.** The same
   function then appears under **two different mangled names**, because the
   crate disambiguator differs:
   ```
   portalis_nexus_protocol[83dd8a83153bf09]::signing::SessionBinding::encode
   portalis_nexus_protocol[769af64eb2792e5]::signing::SessionBinding::encode
   ```
   The copy belonging to the build that did not run it carries `count: 0` while
   the function itself is fully covered. Measured on a real report:
   765 function entries → 351 touching measured files → 109 with `count == 0`,
   against a summary of 232/232 covered.

   Generic functions compound this: one instantiation per concrete type, and a
   generic reached through two different stores cannot execute every line from
   every instantiation.

**Robust approach — trust the per-file summary, use `functions[]` only for names:**

```python
# 1. Which files are genuinely short, per the same summaries the totals use.
short_files = {
    f["filename"]
    for f in data.get("files", [])
    if f["summary"]["functions"]["covered"] < f["summary"]["functions"]["count"]
}

# 2. Only then name functions, summing across builds/instantiations.
executions = defaultdict(int)
for fn in data.get("functions", []):
    names = [f for f in (fn.get("filenames") or []) if f in short_files]
    if not names:
        continue
    executions[(names[0], strip_disambiguator(fn["name"]))] += fn.get("count", 0)

uncovered = [key for key, count in executions.items() if count == 0]
```

with

```python
def strip_disambiguator(name: str) -> str:
    """v0 mangling embeds `Cs<hash>_`; legacy embeds `17h<hash>`."""
    without_v0 = re.sub(r"Cs[0-9A-Za-z]+_", "", name)
    return re.sub(r"17h[0-9a-f]{16}E?$", "", without_v0)
```

**Self-consistency check to build in:** if your script lists uncovered functions
while `totals.functions.percent == 100`, your script is wrong. Fail loudly on
that contradiction rather than printing a misleading list.

## Locating uncovered lines from `segments`

Each entry in `files[].segments` is
`[line, col, count, has_count, is_region_entry, ...]`. A line is uncovered when
a region-entry segment has `count == 0` **and** no other region-entry segment
on that same line has `count > 0` (subtract the covered set — otherwise
multi-region lines report false positives).

```python
covered, zero = set(), set()
for line, _col, count, has_count, is_region_entry in (s[:5] for s in segments):
    if not has_count or not is_region_entry:
        continue
    (covered if count > 0 else zero).add(line)
uncovered_lines = zero - covered
```

Prefer this merged-profile view over the summary's line percentage: the summary
counts a line once per instantiation, so a line covered by *some* instantiation
can still drag the percentage down. LCOV/merged data reports the truth — a line
is tested if anything reached it.

## Demangling names for humans

`rustfilt` (or `c++filt -p` as a fallback) turns mangled names readable. Neither
may be installed. Degrade gracefully — never crash the gate over cosmetics:

```python
for tool in (["rustfilt"], ["c++filt", "-p"]):
    try:
        out = subprocess.run(tool, input="\n".join(names), capture_output=True,
                             text=True, timeout=30, check=True).stdout.splitlines()
        if len(out) == len(names):
            return dict(zip(names, out))
    except (OSError, subprocess.SubprocessError):
        continue
return {n: n for n in names}   # identity fallback
```

## Legitimate exclusions vs. lowering the bar

Extending an ignore regex is acceptable ONLY for genuine platform adapters
whose error arms cannot be triggered deterministically — driver-internal error
propagation, socket plumbing driven by already-covered decisions, process
bootstrap. It is NOT acceptable for a real decision.

Worked example of the distinction: a capsule size cap
(`CapsuleError::TooLarge`) is *why a hostile input cannot become an
allocation* — a decision, so it gets a real test (seal one byte over the cap;
decode a length field claiming one byte over, asserting the cap is checked
*before* the slice), not an exclusion.

When a threshold looks odd (regions 99 rather than 100), read the surrounding
comments before changing it — it usually documents a specific tool artifact,
e.g. one region that the summary reports uncovered no matter what exercises it,
stable at exactly one region regardless of how many concrete types exercise the
code.

## Running coverage on a constrained host

Full-workspace coverage instruments and compiles every crate twice — it is far
heavier than a normal build and will OOM a small box. On a constrained host,
verify per-crate (`cargo llvm-cov -p <crate> --lib --json --output-path ...`
with `CARGO_BUILD_JOBS=2`) and let CI run the full gate. Say explicitly which
you ran. See `shared-dev-host-safety`.
