"""
build_reasoner_test.py
======================
Builds a single Turtle file that combines:

  1. The Viewsari ontology TBox (data/ontology/test/viewsari_ontology.rdf)
  2. A minimal subgraph from data/kg/viewsari_kg.ttl that exercises every
     class and predicate used in the full KG, with one-hop closure so any
     IRI referenced from a kept block is itself described.

The resulting file is suitable for loading into an OWL reasoner (HermiT,
Pellet, ELK, the Protégé built-ins) to check the ontology against
realistic instance data.

Output: data/ontology/test/viewsari_reasoner_test.ttl

Usage:
    python src/kg_population/build_reasoner_test.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from rdflib import Graph

BASE = Path(__file__).resolve().parent.parent.parent
KG_PATH       = BASE / "data" / "kg" / "viewsari_kg.ttl"
ONTOLOGY_PATH = BASE / "data" / "ontology" / "viewsari_ontology.rdf"
OUT_PATH      = BASE / "data" / "ontology" / "viewsari_reasoner_test.ttl"


# ── triple-quote-aware block iterator ────────────────────────────────────────

def _count_triple_quotes(line: str) -> int:
    cnt, i = 0, 0
    while True:
        j = line.find('"""', i)
        if j < 0:
            return cnt
        cnt += 1
        i = j + 3


def iter_blocks(path: Path):
    """Yield one subject-block at a time. A block ends on a line ending with
    `.` while we are NOT inside a triple-quoted literal."""
    in_triple = False
    in_header = True
    buf: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if in_header:
                if stripped.startswith("@prefix") or stripped.startswith("@base") or stripped == "":
                    continue
                in_header = False
            tq = _count_triple_quotes(line)
            started_in_triple = in_triple
            if tq % 2 == 1:
                in_triple = not in_triple
            if not started_in_triple and not in_triple and stripped == "":
                continue
            buf.append(line)
            if not in_triple and line.rstrip().endswith("."):
                yield "".join(buf)
                buf = []
        if buf:
            yield "".join(buf)


def read_header(path: Path) -> str:
    """Capture the @prefix block at the top of the file so each isolated
    subject-block remains parseable as Turtle."""
    out: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("@prefix") or s.startswith("@base"):
                out.append(line)
            elif s == "":
                if out:
                    out.append(line)
            else:
                break
    return "".join(out)


# ── per-block parsing ────────────────────────────────────────────────────────

QNAME_RE = re.compile(r"<[^>\s]+>|[A-Za-z_][\w.-]*:[A-Za-z0-9_][\w./%-]*")
TYPE_RE  = re.compile(r"(?:^|[\s;])(?:a|rdf:type)\s+([^;.]+)")


def _mask_literals(text: str) -> str:
    """Blank out string-literal contents so semicolons / dots inside them
    don't confuse the predicate scanner."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            if text[i:i + 3] == '"""':
                end = text.find('"""', i + 3)
                if end < 0:
                    out.append(' ' * (n - i))
                    return ''.join(out)
                out.append('"""' + ' ' * (end - i - 3) + '"""')
                i = end + 3
            else:
                j = i + 1
                while j < n and text[j] != '"':
                    if text[j] == '\\' and j + 1 < n:
                        j += 2
                    else:
                        j += 1
                if j >= n:
                    out.append('"' + ' ' * (n - i - 1))
                    return ''.join(out)
                out.append('"' + ' ' * (j - i - 1) + '"')
                i = j + 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def parse_block(block: str) -> tuple[str, set[str], set[str], set[str]]:
    """Return (subject, types, predicates, iri-objects) for a subject-block."""
    masked = _mask_literals(block)

    m = re.match(r"\s*(<[^>\s]+>|\[\]|[A-Za-z_][\w.-]*:[A-Za-z0-9_][\w./%-]*)", masked)
    subject = m.group(1) if m else ""

    types: set[str] = set()
    for tm in TYPE_RE.finditer(masked):
        for t in tm.group(1).split(","):
            tok = t.strip()
            if tok:
                qm = QNAME_RE.match(tok)
                if qm:
                    types.add(qm.group(0))

    predicates: set[str] = set()
    iri_objects: set[str] = set()
    body = masked[m.end():] if m else masked
    for chunk in re.split(r"\s*;\s*", body.strip().rstrip(".")):
        chunk = chunk.strip()
        if not chunk:
            continue
        pm = QNAME_RE.match(chunk)
        if not pm:
            continue
        pred = pm.group(0)
        if pred == "a":
            pred = "rdf:type"
        predicates.add(pred)
        rest = chunk[pm.end():].strip()
        for om in QNAME_RE.finditer(rest):
            iri_objects.add(om.group(0))

    return subject, types, predicates, iri_objects


# ── main ─────────────────────────────────────────────────────────────────────

# IRIs that look like qnames but never refer to KG instances we'd need to
# pull in for one-hop closure.
SKIP_PREFIXES = (
    "xsd:", "rdf:", "rdfs:", "owl:", "dc:", "dct:", "foaf:",
    "oa:", "prov:", "frbr:", "fabio:", "doco:", "skos:",
)


def main() -> int:
    if not KG_PATH.exists():
        print(f"missing: {KG_PATH}", file=sys.stderr); return 2
    if not ONTOLOGY_PATH.exists():
        print(f"missing: {ONTOLOGY_PATH}", file=sys.stderr); return 2

    header = read_header(KG_PATH)

    # Single streaming pass: build an index of every block keyed by subject,
    # plus its types, predicates, and referenced IRIs. Greedy cover happens
    # on the fly so we hold only metadata (not full text) for blocks we
    # don't keep — but block text is small and this lets pass-2 closure run
    # as O(1) dictionary lookups instead of a second 183 MB scan.
    seen_classes:  set[str] = set()
    seen_preds:    set[str] = set()
    selected:      dict[str, str]      = {}
    selected_refs: dict[str, set[str]] = {}
    block_index:   dict[str, str]      = {}   # subject -> block text

    print("pass 1: streaming KG, indexing blocks + greedy cover ...",
          file=sys.stderr)
    n_blocks = 0
    for block in iter_blocks(KG_PATH):
        n_blocks += 1
        subj, types, preds, refs = parse_block(block)
        if not subj:
            continue
        # Remember the block text for closure-time lookup; it gets
        # overwritten if we see the subject twice (shouldn't happen).
        block_index[subj] = block
        if (types - seen_classes) or (preds - seen_preds):
            seen_classes |= types
            seen_preds   |= preds
            if subj not in selected:
                selected[subj]      = block
                selected_refs[subj] = refs
        if n_blocks % 50000 == 0:
            print(f"  scanned {n_blocks:>7} blocks, "
                  f"selected {len(selected)}, "
                  f"classes {len(seen_classes)}, preds {len(seen_preds)}",
                  file=sys.stderr)
    print(
        f"  done: {n_blocks} blocks, "
        f"{len(selected)} selected, "
        f"{len(seen_classes)} classes, {len(seen_preds)} predicates",
        file=sys.stderr,
    )

    # Pass 2: one-hop closure via dictionary lookups against the index.
    needed: set[str] = set()
    for refs in selected_refs.values():
        needed |= refs
    needed -= set(selected.keys())
    needed = {r for r in needed if r and not r.startswith(SKIP_PREFIXES) and ":" in r}
    print(f"pass 2: closing over {len(needed)} referenced subjects ...",
          file=sys.stderr)
    found = 0
    for ref in needed:
        block = block_index.get(ref)
        if block is not None:
            selected[ref] = block
            found += 1
    print(f"  pulled in {found} describing blocks", file=sys.stderr)

    # Free the full index now that closure is done.
    block_index.clear()

    # Emit the test KG directly (no rdflib roundtrip on the ABox; cheap).
    # Parse only the ontology with rdflib and serialize it as Turtle to
    # prepend.
    print("serialising ontology TBox ...", file=sys.stderr)
    ont = Graph()
    ont.parse(ONTOLOGY_PATH)
    ont_ttl = ont.serialize(format="turtle")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"writing {OUT_PATH} ...", file=sys.stderr)
    with OUT_PATH.open("w", encoding="utf-8") as out:
        out.write("# Reasoner test graph for Viewsari\n")
        out.write("# - Ontology TBox parsed from data/ontology/viewsari_ontology.rdf\n")
        out.write("# - Minimal ABox subset of data/kg/viewsari_kg.ttl that\n")
        out.write("#   exercises every class and predicate, plus one-hop closure\n")
        out.write("#   over referenced subjects.\n\n")
        out.write("# ── Ontology TBox ──────────────────────────────────────────\n\n")
        out.write(ont_ttl)
        if not ont_ttl.endswith("\n"):
            out.write("\n")
        out.write("\n# ── ABox sample ────────────────────────────────────────────\n\n")
        # KG header has @prefix lines we need so the ABox blocks parse;
        # strip prefixes that already appear in the ontology serialization
        # to keep the output clean.
        out.write(header)
        if not header.endswith("\n"):
            out.write("\n")
        out.write("\n")
        for subj, block in selected.items():
            out.write(block)
            if not block.endswith("\n"):
                out.write("\n")
            out.write("\n")

    size = OUT_PATH.stat().st_size
    print(
        f"wrote {OUT_PATH}\n"
        f"  {size:,} bytes, {len(selected)} ABox subjects + ontology TBox\n"
        f"  classes covered: {len(seen_classes)}\n"
        f"  predicates covered: {len(seen_preds)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
