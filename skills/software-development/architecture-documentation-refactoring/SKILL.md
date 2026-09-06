---
name: architecture-documentation-refactoring
description: "Use when replacing living architecture docs with ADRs."
version: 1.0.0
---

# Architecture Documentation Refactoring

Use when a repository replaces a mutable design/specification/plan with frozen
architecture decision records (ADRs), or otherwise retires stale architecture
narratives without losing active developer guidance.

## Goal

Remove documents that compete with the code and ADR history as sources of truth,
while preserving intentional historical evidence and keeping every active link
accurate.

## Workflow

1. **Read the governing decision first.** Extract its explicit deletion scope,
   its replacement source of truth, and its historical-record policy.
2. **Inventory candidates and references.** Search for the filenames, link
   targets, and in-text citations across README files, code docs, scripts,
   builds, and CI configuration.
3. **Classify every reference.**
   - *Active:* update or remove it before deleting the target.
   - *Frozen record:* retain it if ADR policy is append-only; it is history, not
     a live dependency.
   - *Focused acceptance note:* keep it unless it duplicates the system-wide
     architecture source of truth.
4. **Delete the stale central documents.** Do not replace them with a new
   mutable mega-document. Point entry-point READMEs to the ADR index and state
   that code is the current-state map.
5. **Make code docs self-contained.** Replace section-number references with a
   short explanation of the behavior or invariant at the module boundary.
6. **Rewrite inherited/template READMEs as product documentation.** State what
   the product is, its primary use case, ownership boundaries, layout, setup,
   validation, and contribution rules. Remove template/migration marketing.
7. **Verify.** Re-run the reference search. The only remaining deleted-path
   mentions should be intentionally frozen historical records. Check Markdown
   links and run the repository validation gate.
8. **Commit atomically.** Use a `📚 docs:` commit and include the deletions,
   active-reference updates, and README changes together.

## Pitfalls

- Do not edit frozen ADRs merely to repair a historical path; append-only
  records must remain auditable.
- Do not delete feature-local acceptance criteria just because their filename
  includes `SPEC`; decide whether they are a competing central architecture
  document first.
- Do not preserve stale document links inside code comments. Explain the local
  invariant directly instead.
- Do not claim a link sweep succeeded without running it after deletion.

## PortalisApp Notes

- ADR index: `doc/adr/README.md`.
- Backend validation: `./tests/nexus.sh` from repository root.
- Keep platform/build guides that describe current use, but delete central
  narrative backend specifications and historical migration plans when an ADR
  requires it.
