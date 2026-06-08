"""Materialise OOKB artwork entities for `ontology_guided_all` NIL mentions.

The entity-linking run emits `el_output … rdf:value "NIL"` when it declines to
link a mention. Unlike the ground truth — which records out-of-knowledge-base
artworks as `viewsari:0001012` entities without `owl:sameAs` — the run left
these only as raw NIL outputs. This mints the parallel OOKB artwork entities so
both runs model OOKB the same way.

Only **artwork** mentions (explicit / implicit) are materialised; NIL mentions
typed as generic or coreferent are skipped (they are not artworks).

Each minted entity mirrors GT OOKB / the run's linked artworks, minus owl:sameAs:

    vkb:final_ontology_linked_all_ookb_<rest> a prov:Entity, viewsari:0001012, viewsari:0001033 ;
        rdfs:label "<surface form>" ;
        prov:wasGeneratedBy vkb:el_run_final_ontology_linked_all ;
        prov:wasDerivedFrom vkb:ontology_guided_all_<rest> ;
        viewsari:0001032 <paragraph> .

The blocks are appended (text) to both the full and no-prompt KG files, after a
unique separator line so the addition can be truncated if needed.

Usage:
    python src/kg_population/mint_ookb_entities.py \
        --full data/kg/viewsari_kg.ttl \
        --noprompt data/kg/viewsari_kg.noprompts.ttl
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EL_OUT_PREFIX = "el_output_final_ontology_linked_all_"
MENTION_PREFIX = "ontology_guided_all_"
SEP = "\n# ===== ontology_guided_all OOKB (NIL) artworks =====\n\n"

ARTWORK_MENTION_CLASSES = {"0001017", "0001020", "0001016", "0001021"}  # explicit/implicit
LITERAL_RE = re.compile(r'rdf:value\s+("(?:[^"\\]|\\.)*")')
PARA_RE = re.compile(r"viewsari:0001032\s+(vkb:\S+?)\s*[;.]")
HASBODY_RE = re.compile(r"oa:hasBody\s+vkb:(\S+?)\s*[;.]")


def collect_nil_mentions(full_kg: Path) -> set[str]:
    """Return the set of mention local names whose EL output was NIL."""
    nil: set[str] = set()
    subj = None
    with open(full_kg, encoding="utf-8") as f:
        for line in f:
            if line.startswith(f"vkb:{EL_OUT_PREFIX}"):
                subj = line.split()[0][4:]
            elif subj and 'rdf:value "NIL"' in line:
                nil.add(subj.replace(EL_OUT_PREFIX, MENTION_PREFIX, 1))
                subj = None
    return nil


def collect_mention_data(noprompt_kg: Path, wanted: set[str]):
    """For wanted mentions return {local: (is_artwork, paragraph_token, body_local)}
    and for all bodies {body_local: raw_literal}. The body IRI is read from the
    mention's oa:hasBody rather than computed, since mention/body local names do
    not map mechanically."""
    info: dict[str, tuple[bool, str | None, str | None]] = {}
    bodies: dict[str, str] = {}
    block: list[str] = []

    def handle(b: list[str]) -> None:
        if not b:
            return
        head = b[0]
        local = head.split()[0][4:]
        if " a oa:Annotation" in head and local in wanted:
            cls = set(re.findall(r"viewsari:(\d{7})", head))
            is_art = bool(cls & ARTWORK_MENTION_CLASSES)
            text = "".join(b)
            pm = PARA_RE.search(text)
            bm = HASBODY_RE.search(text)
            info[local] = (is_art, pm.group(1) if pm else None,
                           bm.group(1) if bm else None)
        elif " a oa:TextualBody" in head:
            lm = LITERAL_RE.search("".join(b))
            if lm:
                bodies[local] = lm.group(1)

    with open(noprompt_kg, encoding="utf-8") as f:
        for line in f:
            if line.strip() == "":
                handle(block)
                block = []
            else:
                block.append(line)
        handle(block)
    return info, bodies


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", type=Path, default=Path("data/kg/viewsari_kg.ttl"))
    ap.add_argument("--noprompt", type=Path, default=Path("data/kg/viewsari_kg.noprompts.ttl"))
    args = ap.parse_args()

    print("collecting NIL mentions from full KG …", file=sys.stderr)
    nil = collect_nil_mentions(args.full)
    print(f"  {len(nil):,} NIL mentions", file=sys.stderr)

    info, bodies = collect_mention_data(args.noprompt, nil)

    minted, skip_nonart, skip_missing = [], 0, 0
    for ml in sorted(nil):
        meta = info.get(ml)
        if meta is None:
            skip_missing += 1
            continue
        is_art, para, body_local = meta
        if not is_art:
            skip_nonart += 1
            continue
        rest = ml[len(MENTION_PREFIX):]
        label = bodies.get(body_local) if body_local else None
        if label is None or para is None:
            skip_missing += 1
            continue
        block = (
            f"vkb:final_ontology_linked_all_ookb_{rest} a prov:Entity, viewsari:0001012, viewsari:0001033 ;\n"
            f"    rdfs:label {label} ;\n"
            f"    prov:wasGeneratedBy vkb:el_run_final_ontology_linked_all ;\n"
            f"    prov:wasDerivedFrom vkb:{ml} ;\n"
            f"    viewsari:0001032 {para} .\n"
        )
        minted.append(block)

    print(f"  minting {len(minted):,} OOKB artworks; "
          f"skipped {skip_nonart:,} non-artwork (generic/coreferent), "
          f"{skip_missing:,} missing data", file=sys.stderr)

    payload = SEP + "\n".join(minted) + "\n"
    for path in (args.full, args.noprompt):
        before = path.stat().st_size
        with open(path, "a", encoding="utf-8") as f:
            f.write(payload)
        print(f"  {path.name}: appended at byte {before:,} → {path.stat().st_size:,}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
