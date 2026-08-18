#!/usr/bin/env python3
"""Explain WHY coverage lines are uncovered, by mapping them to enclosing items.

A coverage gate lists `file.rs:NNN` hundreds of times. That says *where* but
never *why*. This maps each uncovered line to its enclosing function plus any
`#[cfg(...)]` / `#[ignore]` attributes, then ranks by size so the biggest
single cause is the first thing you read.

Usage:
    why_uncovered.py --log <gate-output.log> --root <src/dir> [--prefix <path-fragment>]

    # from a saved CI/local gate log, Rust workspace
    why_uncovered.py --log /tmp/coverage.log --root ~/proj/backend/src/

`--prefix` is the path fragment the log uses before the file path
(default: `src/`), e.g. `backend/src/` when logs are absolute-ish.

Language note: the regexes target Rust. For another language, change FN_RE and
the attribute markers; the bucketing logic is language-independent.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict

FN_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+([A-Za-z0-9_]+)"
)
ATTR_RE = re.compile(r"^\s*#\[")
CFG_RE = re.compile(r"^\s*#\[(cfg|ignore|allow|expect)\b")


def enclosing(lines: list[str], n: int) -> tuple[str | None, list[str], int]:
    """Nearest `fn` at or above line n, plus cfg-ish attributes attached to it."""
    for i in range(min(n, len(lines)) - 1, -1, -1):
        m = FN_RE.match(lines[i])
        if not m:
            continue
        attrs: list[str] = []
        j = i - 1
        while j >= 0 and (
            ATTR_RE.match(lines[j])
            or lines[j].strip().startswith("//")
            or not lines[j].strip()
        ):
            if CFG_RE.match(lines[j]):
                attrs.append(lines[j].strip())
            j -= 1
        return m.group(1), attrs, i + 1
    return None, [], 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="file containing gate output")
    ap.add_argument("--root", required=True, help="source root the paths are relative to")
    ap.add_argument("--prefix", default="src/", help="path fragment preceding the file path")
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    root = args.root.rstrip("/") + "/"
    pattern = re.compile(re.escape(args.prefix) + r"([A-Za-z0-9_/]+\.rs):(\d+)")

    uncovered: dict[str, set[int]] = defaultdict(set)
    with open(args.log, encoding="utf-8", errors="replace") as fh:
        for m in pattern.finditer(fh.read()):
            uncovered[m.group(1)].add(int(m.group(2)))

    if not uncovered:
        print("No uncovered lines matched. Check --prefix against the log format.")
        return 1

    rows = []
    for rel, lns in sorted(uncovered.items()):
        try:
            with open(root + rel, encoding="utf-8") as fh:
                src = fh.read().splitlines()
        except OSError:
            continue
        groups: dict[tuple, list[int]] = defaultdict(list)
        for n in sorted(lns):
            name, attrs, at = enclosing(src, n)
            groups[(name, tuple(attrs), at)].append(n)
        for (name, attrs, at), ns in groups.items():
            rows.append((len(ns), rel, name, at, " ".join(attrs)))

    rows.sort(reverse=True)
    print(f"{'N':>4}  {'FILE':<26} {'FN':<38} {'DEF':>6}  ATTRS")
    print("-" * 110)
    for n, rel, fn, at, attrs in rows[: args.top]:
        print(f"{n:>4}  {rel:<26} {str(fn):<38} {at:>6}  {attrs[:44]}")

    total = sum(len(v) for v in uncovered.values())
    print(f"\nTOTAL uncovered: {total}")

    # The bucket that is impossible to cover, called out explicitly.
    for marker, label in (
        ("cfg(not(test))", "#[cfg(not(test))] — UNCOVERABLE by unit tests"),
        ("ignore", "#[ignore]d test helpers — skipped unless named"),
    ):
        hits = [r for r in rows if marker in r[4]]
        if hits:
            print(f"\n{label}: {sum(r[0] for r in hits)} lines")
            for r in hits:
                print(f"    {r[1]}::{r[2]}  ({r[0]} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
