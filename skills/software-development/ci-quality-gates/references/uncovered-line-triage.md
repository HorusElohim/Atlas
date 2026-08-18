# Triaging Uncovered Lines: *Why*, Not Just *Where*

A coverage gate tells you **which** lines are uncovered. It never tells you
**why**, and the why determines whether the right fix is a test, a gate
correction, or nothing at all.

Aggregating by file (see `unconditional-gate-checks.md`) is step one. This is
step two: map every uncovered line to its **enclosing function and its cfg
attributes**, then bucket by root cause.

Run `scripts/why_uncovered.py` (in this skill) to do the mapping.

## The four buckets

Real distribution from a Rust backend with 293 uncovered lines:

| Bucket | Example | Right response |
|---|---|---|
| **Structurally uncoverable** | `#[cfg(not(test))]` production twin | Exclude from gate |
| **Skipped-test helpers** | code nested inside an `#[ignore]`d test | Exclude from gate |
| **Daemon / infinite loops** | `loop { tick.await; … }` supervisor task | Write a driven test |
| **Defensive error arms** | `Err(e) => { log!(e); continue }` on a healthy store | Usually justified ignore |

Only the third bucket is "we owe this code a test." Treating all four as the
same debt produces either an impossible task or a weakened gate.

## Bucket 1: `#[cfg(not(test))]` — the trap worth knowing

A deliberate production/test split compiles **both** halves into the
instrumented binary. Under `cargo test` the `cfg(test)` twin runs; the
production definition is compiled, measured, and **by construction never
entered**.

```rust
#[cfg(not(test))]
pub(crate) fn app_store() -> Result<Arc<Store>, StoreError> { /* process-wide cache */ }

#[cfg(test)]
pub(crate) fn app_store() -> Result<Arc<Store>, StoreError> { /* isolated per test */ }
```

No test can ever cover the first one. Demanding 100% here asks for a test that
cannot be written. The same applies to `#[ignore]`d tests: skipped unless named
explicitly, so every helper nested inside them is compiled but never driven.

> The distinction that matters: **code no test reached** vs. **code no test
> _can_ reach.** Excluding the second is not lowering the bar.

## Implementing the exclusion

Detect spans by scanning source for the attribute, stepping past the remaining
attribute/doc block, then consuming the whole item by brace depth (or to `;` for
a `static`/`const`). Brace counting is sufficient — the span only needs to cover
whole items, not parse the language.

Two non-negotiables:

- **Print what you excluded, with counts per file.** A silent exclusion is
  indistinguishable from a bug.
- **Keep the strict check for everything else.** Exclude the impossible; do not
  relax the possible.

```
Excluded as unreachable by the test build (57 lines):
  src/core/service.rs  43     ← #[ignore]d live-server test
  src/store/mod.rs     14     ← #[cfg(not(test))] production twin
```

## Verify the exclusion with a NEGATIVE test

The dangerous failure is over-matching — silently swallowing real gaps. So
assert what must **not** be excluded, not just what must be:

```python
spans = unreachable_spans("src/store/mod.rs")
twin = [n for n in range(128, 133) if n in spans]   # the cfg(test) twin
print("cfg(test) twin wrongly excluded:", twin or "NO (correct)")
```

Also print the flagged spans grouped contiguously with the source line at each
start, and eyeball that each begins at a real item:

```
L109-123  [cfg(not(test))]  pub(crate) fn app_store() -> Result<Arc<Store>, …
L670-758  [ignored test]    async fn reaches_a_running_service() {
```

## Measure the hypothesis before shipping it

A plausible causal story about coverage is still a guess. With a fast verify
loop, **run the experiment**.

Worked example: the theory was that demo binaries executing outside
instrumentation (via a separate `cargo run` loop) explained the uncovered bulk,
so folding them in with `--all-targets` + `harness = false` would close it.

Measured, baseline vs. patched, same host:

| | Baseline | With `--all-targets` |
|---|---|---|
| Uncovered lines | 424 | **420** |
| functions | 97.25% | 97.29% |

**Net: 4 lines.** The demos genuinely ran as test targets — confirmed by
`Running unittests src/bin/01-formats.rs` in the log — they just barely move
coverage. The hypothesis was wrong.

The change was still worth landing, on its *real* merit: one compilation
instead of three, ~24 min → ~2 min. **Judge a change by what it measurably
delivers, not by the theory that motivated it** — and go correct the earlier
claim out loud rather than letting it stand.

Diff two runs mechanically instead of eyeballing totals; a net figure can hide
offsetting moves:

```python
newly_covered = baseline_uncovered - patched_uncovered
regressed     = patched_uncovered - baseline_uncovered   # must be empty
```

## Reading the test log while you're there

- `test result: ok. 183 passed; 0 failed; 1 ignored` — uncovered lines here are
  **unexercised code**, not failing tests. Say which it is; they imply totally
  different work.
- A panic in output is not automatically a failure. One demo printed
  `panicked at …: the torrent engine could not open its port` and the run still
  passed — the binary *demonstrates* graceful degradation and prints
  `panicked — reported, and survived`. Read the surrounding output before
  reporting a crash.
