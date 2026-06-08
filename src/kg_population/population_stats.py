"""Population statistics for the Viewsari KG.

Reports how the KG is populated — mentions, resolved artworks, coreference
links, paragraphs covered — broken down by the provenance run that produced
them (ground truth vs. each ObliquER strategy).

Usage:
    python src/kg_population/population_stats.py [--kg data/kg/viewsari_kg.ttl]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, OWL

OA = Namespace("http://www.w3.org/ns/oa#")
PROV = Namespace("http://www.w3.org/ns/prov#")
VIEWSARI = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/")
VKB = "https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#"

# Mention subtype classes → human label
TYPE_LABELS = {
    "0001017": "explicit artwork",
    "0001020": "explicit artwork",
    "0001016": "implicit artwork",
    "0001021": "implicit artwork",
    "0001018": "coreferent",
    "0001019": "generic",
}
IN_PARAGRAPH = VIEWSARI["0001032"]
REFERS_TO = VIEWSARI["0001035"]


def run_family(local: str) -> str:
    """Bucket a provenance-activity local name into a run family."""
    if local.startswith("ground_truth"):
        return "ground truth"
    if local.startswith("named_entity_recognition_run"):
        return "NER (legacy run_1)"
    if local.startswith(("ner_run_ontology_guided_all", "el_run_final_ontology_linked_all")):
        return "ontology_guided_all (new)"
    if local.startswith(("ner_run_ontology_guided_v2", "el_run_ontology_guided_v2")):
        return "ontology_guided_v2"
    if local.startswith(("ner_run_few_shot_v2", "el_run_few_shot_v2")):
        return "few_shot_v2"
    if local.startswith(("ner_run_cot_v2", "el_run_cot_v2")):
        return "cot_v2"
    return f"other ({local[:32]})"


def loc(uri) -> str:
    s = str(uri)
    return s[len(VKB):] if s.startswith(VKB) else s


def class_local(uri) -> str:
    """Local name of an ontology class IRI (segment after the last # or /)."""
    s = str(uri)
    return re.split(r"[#/]", s)[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kg", type=Path,
                    default=Path("data/kg/viewsari_kg.noprompts.ttl"))
    args = ap.parse_args()

    t0 = time.time()
    print(f"loading {args.kg} …", file=sys.stderr, flush=True)
    g = Graph()
    g.parse(args.kg.as_posix(), format="turtle")
    print(f"  {len(g):,} triples ({time.time()-t0:.1f}s)\n", file=sys.stderr)

    # ── Mentions: by run family and by type ──────────────────────────────────
    mention_by_run: Counter = Counter()
    mention_by_type: Counter = Counter()
    mtype_of: dict = {}
    mentions = set(g.subjects(RDF.type, OA.Annotation))
    for m in mentions:
        for run in g.objects(m, PROV.wasGeneratedBy):
            mention_by_run[run_family(loc(run))] += 1
        types = {class_local(t) for t in g.objects(m, RDF.type)}
        label = next((TYPE_LABELS[t] for t in types if t in TYPE_LABELS), "unclassified")
        mention_by_type[label] += 1
        mtype_of[m] = label

    # ── Artwork entities (viewsari:0001012): linked vs OOKB, by run family ────
    linked_by_run: Counter = Counter()
    ookb_by_run: Counter = Counter()
    # mention-centric outcome: (run, status, mention_type) -> count of mentions
    # resolved via prov:wasDerivedFrom from an artwork entity.
    outcome: Counter = Counter()
    qids: set[str] = set()
    artworks = set(g.subjects(RDF.type, VIEWSARI["0001012"]))
    for a in artworks:
        fam = next((run_family(loc(r)) for r in g.objects(a, PROV.wasGeneratedBy)),
                   "(no run)")
        sames = list(g.objects(a, OWL.sameAs))
        status = "Wikidata" if sames else "OOKB"
        if sames:
            linked_by_run[fam] += 1
            for w in sames:
                mq = re.search(r"(Q\d+)$", str(w).rstrip("/"))
                if mq:
                    qids.add(mq.group(1))
        else:
            ookb_by_run[fam] += 1
        for m in g.objects(a, PROV.wasDerivedFrom):
            outcome[(fam, status, mtype_of.get(m, "unclassified"))] += 1

    # ── Other population counts ──────────────────────────────────────────────
    n_refers = sum(1 for _ in g.triples((None, REFERS_TO, None)))
    paragraphs = set(g.objects(None, IN_PARAGRAPH))
    activities = set(g.subjects(RDF.type, PROV.Activity))
    agents = set(g.subjects(RDF.type, PROV.SoftwareAgent))

    # ── Report ───────────────────────────────────────────────────────────────
    def table(title, counter):
        print(f"\n{title}")
        print("-" * len(title))
        width = max((len(k) for k in counter), default=10)
        for k, v in sorted(counter.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<{width}}  {v:>8,}")
        print(f"  {'TOTAL':<{width}}  {sum(counter.values()):>8,}")

    print("=" * 60)
    print("VIEWSARI KG — POPULATION STATISTICS")
    print(f"source: {args.kg.name}")
    print("=" * 60)
    n_linked = sum(linked_by_run.values())
    n_ookb = sum(ookb_by_run.values())
    print(f"\nTotal triples: {len(g):,}")
    print(f"Mentions (oa:Annotation): {len(mentions):,}")
    print(f"Artwork entities (viewsari:0001012): {len(artworks):,}")
    print(f"  linked (owl:sameAs): {n_linked:,}  ({len(qids):,} distinct Wikidata QIDs)")
    print(f"  OOKB (no owl:sameAs): {n_ookb:,}")
    print(f"Coreference / refers_to links: {n_refers:,}")
    print(f"Paragraphs with mentions: {len(paragraphs):,}")
    print(f"Provenance activities: {len(activities):,}   software agents: {len(agents):,}")

    table("Mentions by run family", mention_by_run)
    table("Mentions by type", mention_by_type)
    table("Linked artworks by run family", linked_by_run)
    table("OOKB artworks by run family", ookb_by_run)

    # ── Cross-tab: mention outcome (Wikidata vs OOKB) by mention type ─────────
    runs = sorted({k[0] for k in outcome}, key=lambda r: -sum(
        v for k, v in outcome.items() if k[0] == r))
    row_types = ["explicit artwork", "implicit artwork", "coreferent", "generic", "unclassified"]
    for fam in runs:
        rows = [t for t in row_types
                if any((fam, s, t) in outcome for s in ("Wikidata", "OOKB"))]
        if not rows:
            continue
        title = f"Resolved mentions by type — {fam}"
        print(f"\n{title}")
        print("-" * len(title))
        print(f"  {'mention type':<20}{'Wikidata':>10}{'OOKB':>10}{'total':>10}"
              f"{'% linked':>10}")
        tw = to = 0
        for t in rows:
            w = outcome.get((fam, "Wikidata", t), 0)
            o = outcome.get((fam, "OOKB", t), 0)
            tot = w + o
            pct = f"{100*w/tot:.1f}%" if tot else "—"
            print(f"  {t:<20}{w:>10,}{o:>10,}{tot:>10,}{pct:>10}")
            tw += w; to += o
        tot = tw + to
        pct = f"{100*tw/tot:.1f}%" if tot else "—"
        print(f"  {'TOTAL':<20}{tw:>10,}{to:>10,}{tot:>10,}{pct:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
