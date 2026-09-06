---
name: adr-documentation-refactoring
description: "Use when ADRs retire living specs. Preserve frozen history."
version: 1.0.0
---

# ADR Documentation Refactoring

Use when an Architecture Decision Record replaces a mutable specification,
implementation plan, or architecture narrative with frozen ADRs and code as the
current-state map.

## Core rule

**ADRs are historical records, not living documentation.** Do not edit a frozen
ADR to repair a stale path or modernize its wording. A successor ADR supersedes
a decision; the old record remains intact.

## Workflow

1. Read the ADR and extract its explicit retirement scope.
2. Inventory every reference to the candidate documents. Separate:
   - active links and live references in READMEs, comments, scripts, and docs;
   - historical references inside frozen ADRs.
3. Update active references first. Replace central-spec links with the ADR index
   and keep behavioral explanation next to the owning code.
4. Delete only documents that are central mutable architecture sources or named
   stale narratives. Retain focused feature acceptance notes unless they compete
   with the ADR index as an architecture source of truth.
5. Verify the deleted paths are now mentioned only in frozen ADR history.
6. Run link checks, `git diff --check`, and the repository validation gate.
7. Keep documentation-governance changes and product README reframing in
   separate commits so review scope stays clear.

## PortalisApp specifics

- ADR index: `doc/adr/README.md`.
- Backend gate: `./tests/nexus.sh` from the repository root.
- Code is the current-state map; update active README links to the ADR index.
- Use `📚 docs:` conventional commits for documentation-retirement changes.

## Pitfalls

- Do not delete focused feature acceptance criteria merely because the filename
  contains `SPEC`; assess whether it is a competing central architecture source.
- Do not alter historical ADR references after a path moves or disappears.
- Do not leave code comments, scripts, or READMEs pointing at deleted docs.
