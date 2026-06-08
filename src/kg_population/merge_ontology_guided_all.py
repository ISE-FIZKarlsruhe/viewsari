"""Merge the `ontology_guided_all` run export into the Viewsari KG.

The export (`viewsari_ontology_guided_all.ttl`) is a self-contained Turtle file
holding the new mentions, 2,964 Wikidata-linked artworks, refers_to links, and
full NER/EL provenance. ~94% of its bytes are verbatim prompt-text literals.

This produces two merged files, both = base KG + additions:

  --full-out      base + the entire export (prompt text kept)
  --noprompt-out  base + export minus the bulky prompt entities
                  (subjects starting el_prompt_, prompt_, el_output_)

Merge is done by streaming text concatenation: the base KG and the export are
both valid Turtle with compatible prefixes (base declares a superset), and the
base contains zero `ontology_guided_all` triples, so no rdflib round-trip is
needed. The export's @prefix header is dropped (base already declares them).

Block model: the export serialises one subject per top-level block, blocks
separated by blank lines, predicate-object lines indented. A block is dropped
from the no-prompt output when its subject's local name starts with one of the
strip prefixes.

Usage:
    python src/kg_population/merge_ontology_guided_all.py \
        --base data/kg/viewsari_kg.ttl \
        --additions viewsari_ontology_guided_all.ttl \
        --full-out data/kg/viewsari_kg.full.tmp.ttl \
        --noprompt-out data/kg/viewsari_kg.noprompts.ttl
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SUBJECT_RE = re.compile(r"^(vkb:[^\s]+)")
STRIP_PREFIXES = ("el_prompt", "prompt_", "el_output")
SEP = "\n# ===== ontology_guided_all run (merged) =====\n\n"


def local_name(subject: str) -> str:
    return subject[len("vkb:"):] if subject.startswith("vkb:") else subject


def is_prompt_block(first_line: str) -> bool:
    m = SUBJECT_RE.match(first_line)
    if not m:
        return False
    name = local_name(m.group(1))
    return name.startswith(STRIP_PREFIXES)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--additions", type=Path, required=True)
    ap.add_argument("--full-out", type=Path, required=True)
    ap.add_argument("--noprompt-out", type=Path, required=True)
    args = ap.parse_args()

    # Seed both outputs with the base KG verbatim.
    print(f"copying base → {args.full_out.name}, {args.noprompt_out.name}", file=sys.stderr)
    shutil.copyfile(args.base, args.full_out)
    shutil.copyfile(args.base, args.noprompt_out)

    blocks_total = blocks_kept = blocks_stripped = 0
    in_header = True

    with open(args.additions, encoding="utf-8") as fin, \
         open(args.full_out, "a", encoding="utf-8") as ffull, \
         open(args.noprompt_out, "a", encoding="utf-8") as fnop:

        ffull.write(SEP)
        fnop.write(SEP)

        block: list[str] = []

        def flush(block_lines: list[str]) -> None:
            nonlocal blocks_total, blocks_kept, blocks_stripped
            if not block_lines:
                return
            blocks_total += 1
            text = "".join(block_lines)
            if not text.endswith("\n"):
                text += "\n"
            ffull.write(text + "\n")
            if is_prompt_block(block_lines[0]):
                blocks_stripped += 1
            else:
                fnop.write(text + "\n")
                blocks_kept += 1

        for line in fin:
            # Skip the export's prefix header; it ends at the first vkb: subject.
            if in_header:
                if line.startswith("vkb:"):
                    in_header = False
                else:
                    continue
            if line.strip() == "":
                flush(block)
                block = []
            else:
                block.append(line)
        flush(block)

    print(f"blocks: {blocks_total:,} total, {blocks_kept:,} kept, "
          f"{blocks_stripped:,} stripped from no-prompt output", file=sys.stderr)
    for path in (args.full_out, args.noprompt_out):
        mb = path.stat().st_size / (1024 * 1024)
        print(f"  {path}  {mb:.1f} MB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
