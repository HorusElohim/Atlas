---
name: generated-artifact-maintenance
description: "Use when codegen changes tracked files."
version: 1.0.0
---

# Generated Artifact Maintenance

## When to use

Use this skill whenever a repository tracks output produced by a generator:
bridge bindings, API clients, protocol stubs, ORM models, asset registrants,
parser output, schemas, or platform integration files. It applies when a user
asks to run regeneration, when a dependency update changes generated output, or
when a format/lint/build gate fails after codegen.

Generated output is a product of a pipeline—not an editable source of truth.
The **Generator** pattern owns the public artifact boundary: modify its inputs
or helper, regenerate, and validate the emitted files through the same gates CI
uses.

## Procedure

### 1. Discover the pipeline before running it

Read the generation helper, its manifest/configuration, and the repository's
relevant acceptance gate. Identify:

- the source modules or schemas the generator consumes;
- expected output paths and whether they are tracked;
- platform-specific side effects such as plugin registrants;
- the formatter, analyzer, compiler, and targeted tests that consume output.

Do not assume a script's working directory. Locate the actual language workspace
or manifest and run build commands from that root.

### 2. Establish a tight verification loop

Use the narrowest deterministic command that detects invalid generated output:
for example `cargo fmt --check`, a generated-code compile, or a codegen-diff
check. Run it before changing a helper when fixing a pipeline defect, so the
failure is known to be real and reproducible.

### 3. Regenerate without hand edits

Run the repository-owned generation helper. Treat generator diagnostics as data:

- Failure, missing output, or changed public boundary requires investigation.
- Notices about internal types may be acceptable only if the generated public
  surface compiles and its tests pass; do not blanket-suppress them.
- Never hand-format or patch generated output to make a current diff green.
  Fix the helper or generator configuration, then regenerate.

### 4. Preserve formatter and lint gates in the helper

A successful generator invocation alone is insufficient. Immediately run the
relevant formatter and static gate on the generated language(s). If a
repository-owned helper deterministically emits files that its formatter rejects,
add the formatter directly after generation in that helper. Then rerun the whole
helper and the exact failing gate; this proves future regeneration remains clean.

### 5. Review the generated diff separately

Inspect changed paths and a bounded diff. Expected changes normally belong only
to generated entry points, dependency locks, and platform registrants. Confirm
that generated public APIs still agree with handwritten callers; run the analyzer
or compiler rather than relying on visual inspection.

When dependency updates change registrant package names, treat the registrant as
generated output and commit it with the dependency lock—not as a handwritten
platform fix.

### 6. Verify and commit atomically

Run, in order appropriate to the repository:

1. format/diff check;
2. static analysis of the consuming client;
3. focused generated-boundary or backend suite;
4. broader acceptance suite when the bridge or public interface changed;
5. target-platform build on the actual target OS when native build integration
   changed.

Commit source dependency/configuration changes, generated artifacts, and helper
repair together when they are inseparable parts of one reproducible pipeline.
Rebase immediately before push and rerun verification if the rebase combines
new upstream changes with the altered boundary.

## Pitfalls

- **Running a build from the app directory instead of the language workspace:**
  find the manifest first; a missing manifest is a path error, not a code error.
- **Calling code generation “verified” because it exited 0:** format, compile,
  and test its actual outputs.
- **Editing generated files by hand:** the next generation will erase the fix;
  repair inputs, generator configuration, or the helper.
- **Ignoring generator warnings wholesale:** validate the exported surface and
  keep warnings visible until their reachability is understood.
- **Committing a new dependency without refreshed platform registrants or lock
  files:** the build may resolve a different native implementation on CI or a
  target machine.
- **Claiming a native platform build passed from another OS:** report only the
  local checks actually run and identify the remaining target-OS verification.

## Verification checklist

- [ ] Generator/helper completed successfully.
- [ ] Generated outputs are formatted and pass static analysis.
- [ ] The language workspace builds from its actual manifest root.
- [ ] Generated public interfaces compile with handwritten callers.
- [ ] Relevant focused and acceptance tests pass.
- [ ] Diff scope contains only expected source, generated, lock, and registrant files.
- [ ] Any native target build is verified on its actual platform before claiming success.

## Reference

- `references/flutter-rust-bridge.md` — validated Flutter-Rust Bridge 2.x
  regeneration and formatting pattern.
