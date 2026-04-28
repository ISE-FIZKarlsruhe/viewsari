#!/usr/bin/env python3
"""Materialise inference rules against the Viewsari KG.

Applies the SPARQL UPDATE statements in `inferences.ru` and writes a closed
copy of the KG (default: data/kg/viewsari_kg.inferred.ttl). The runner can
then evaluate the CQs against the closed file with no query changes.

Each `;`-separated UPDATE block is executed independently so the script can
report how many triples each rule contributed.

Usage
-----

    # Apply rules and write the closed KG
    python src/evaluation/materialise_inferences.py

    # Custom input/output
    python src/evaluation/materialise_inferences.py \
        --kg data/kg/viewsari_kg.ttl \
        --rules src/evaluation/inferences.ru \
        --output data/kg/viewsari_kg.inferred.ttl

    # Skip writing the file (just report counts)
    python src/evaluation/materialise_inferences.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

DEFAULT_KG = ROOT / "data" / "kg" / "viewsari_kg.ttl"
DEFAULT_RULES = HERE / "inferences.ru"
DEFAULT_OUT = ROOT / "data" / "kg" / "viewsari_kg.inferred.ttl"


# Split the rules file into independent UPDATE statements.
#
# SPARQL UPDATE separates statements with `;` at the top level, but `;` is
# also a predicate-object list separator INSIDE `{ ... }` blocks. So we only
# split on `;` when brace depth is zero AND we are outside a string literal
# or a # line comment. Prefixes from the prologue are prepended to each
# resulting block so each block is a self-contained UPDATE.
def split_updates(text: str) -> tuple[list[str], str]:
    blocks: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    string_quote = ""
    in_comment = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_comment:
            current.append(ch)
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if in_string:
            if ch == "\\" and i + 1 < len(text):
                current.append(text[i:i + 2])
                i += 2
                continue
            if ch == string_quote:
                in_string = False
            current.append(ch)
            i += 1
            continue
        if ch == "#":
            in_comment = True
            current.append(ch)
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = True
            string_quote = ch
            current.append(ch)
            i += 1
            continue
        if ch == "{":
            depth += 1
            current.append(ch)
            i += 1
            continue
        if ch == "}":
            depth -= 1
            current.append(ch)
            i += 1
            continue
        if ch == ";" and depth == 0:
            block = "".join(current).strip()
            if block:
                blocks.append(block)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        blocks.append(tail)

    # Pull the leading PREFIX declarations off the first block and use them
    # as a shared prologue for the remaining blocks (each block is then a
    # self-contained UPDATE that rdflib can parse on its own).
    prologue_lines: list[str] = []
    body_blocks: list[str] = []
    for block in blocks:
        non_prologue: list[str] = []
        for raw_line in block.splitlines():
            stripped = raw_line.strip()
            if stripped.upper().startswith("PREFIX") or stripped.upper().startswith("BASE"):
                if not non_prologue:
                    prologue_lines.append(raw_line)
                    continue
            non_prologue.append(raw_line)
        rest = "\n".join(non_prologue).strip()
        if rest:
            body_blocks.append(rest)
    prologue = "\n".join(prologue_lines).strip()
    return body_blocks, prologue


def rule_label(block: str) -> str:
    """Find the closest `# Rx: ...` comment above the block, for logging."""
    match = re.search(r"#\s*(R\d+:[^\n]+)", block)
    return match.group(1).strip() if match else "rule"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kg", type=Path, default=DEFAULT_KG)
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true",
                    help="Apply rules in memory but skip writing the closed KG.")
    args = ap.parse_args()

    from rdflib import Graph

    print(f"loading KG: {args.kg}", file=sys.stderr, flush=True)
    t0 = time.time()
    g = Graph()
    g.parse(args.kg.as_posix(), format="turtle")
    initial = len(g)
    print(f"  {initial:,} triples ({time.time()-t0:.1f}s)", file=sys.stderr)

    rules_text = args.rules.read_text()
    blocks, prologue = split_updates(rules_text)
    print(f"applying {len(blocks)} rule block(s) from {args.rules.name}",
          file=sys.stderr)

    grand_added = 0
    for block in blocks:
        before = len(g)
        t0 = time.time()
        g.update(prologue + "\n\n" + block if prologue else block)
        added = len(g) - before
        grand_added += added
        print(f"  [{rule_label(block):<60s}] +{added:,} triples "
              f"({time.time()-t0:.1f}s)", file=sys.stderr)

    print(f"closure complete: {initial:,} → {len(g):,} triples "
          f"(+{grand_added:,})", file=sys.stderr)

    if args.dry_run:
        print("--dry-run: not writing output", file=sys.stderr)
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(f"writing {args.output}", file=sys.stderr, flush=True)
    t0 = time.time()
    g.serialize(destination=args.output.as_posix(), format="turtle")
    print(f"  done ({time.time()-t0:.1f}s, "
          f"{args.output.stat().st_size / (1024*1024):.1f} MB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
