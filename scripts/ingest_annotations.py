"""Ingest ground-truth artwork entities and mentions into the Viewsari KG.

Mirrors the ObliquER NER ingestion pattern (see ingest_ner_results.py) so the GT
layer sits alongside the LLM-generated annotations with full PROV-O provenance.

Provenance model
----------------
  - Activity:  vkb:ground_truth_annotation_run_2  (prov:Activity + viewsari:NER activity class)
  - Agent:     vkb:sarah_ondraszek                (prov:Person)
  - Time:      March 2026  (xsd:gYearMonth, attached via dct:date)

URI namespacing for mentions/entities is prefixed with `gt_` to avoid collision
with ObliquER runs.

Usage:
    python scripts/ingest_annotations.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS

csv.field_size_limit(sys.maxsize)

VIEWSARI = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/#")
VIEWSARI_KB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#")
DOCO = Namespace("http://purl.org/spar/doco/")
PROV = Namespace("http://www.w3.org/ns/prov#")
OA = Namespace("http://www.w3.org/ns/oa#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

BASE = Path(__file__).resolve().parent.parent
KG_FILE = BASE / "data" / "kg" / "viewsari_kg.ttl"
ANN_DIR = BASE / "obliquer" / "data" / "viewsari" / "ground_truth"
PARA_CSV = BASE / "data" / "kg_foundation" / "viewsari_paragraphs.csv"

# Ontology class IRIs
CLS_ARTWORK = VIEWSARI["0001012"]
CLS_MENTION = VIEWSARI["0001026"]
CLS_EXPLICIT_MENTION = VIEWSARI["0001017"]
CLS_IMPLICIT_MENTION = VIEWSARI["0001016"]
CLS_EXPLICIT_ART_MENTION = VIEWSARI["0001020"]
CLS_IMPLICIT_ART_MENTION = VIEWSARI["0001021"]
CLS_COREFERENT = VIEWSARI["0001018"]
CLS_GENERIC = VIEWSARI["0001019"]
CLS_NER_ACTIVITY = VIEWSARI["0001022"]
CLS_EL_ACTIVITY = VIEWSARI["0001023"]
CLS_EXTRACTED_CONTENT = VIEWSARI["0001033"]

PROP_REFERS_TO = VIEWSARI["0001035"]
PROP_IN_PARAGRAPH = VIEWSARI["0001032"]

TYPE_TO_CLASSES = {
    "explicit artwork mention": [CLS_MENTION, CLS_EXPLICIT_MENTION, CLS_EXPLICIT_ART_MENTION, OA.Annotation, PROV.Entity],
    "implicit artwork mention": [CLS_MENTION, CLS_IMPLICIT_MENTION, CLS_IMPLICIT_ART_MENTION, OA.Annotation, PROV.Entity],
    "coreferent":               [CLS_MENTION, CLS_COREFERENT, OA.Annotation, PROV.Entity],
    "generic mention":          [CLS_MENTION, CLS_GENERIC, OA.Annotation, PROV.Entity],
}


def load_para_map() -> dict[tuple[str, str], str]:
    para_map = {}
    with open(PARA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vol = row.get("vol", "")
            pid = row.get("paragraph_id", "")
            para_map[(vol, pid)] = row.get("instance_id", "")
    return para_map


def setup_provenance(g: Graph) -> tuple[URIRef, URIRef]:
    """Create the annotation + entity-linking activities and the shared agent.
    Returns (annotation_activity, entity_linking_activity)."""
    ann_activity = VIEWSARI_KB["ground_truth_annotation_run_2"]
    el_activity = VIEWSARI_KB["ground_truth_entity_linking_run_1"]
    agent = VIEWSARI_KB["sarah_ondraszek"]

    g.add((ann_activity, RDF.type, PROV.Activity))
    g.add((ann_activity, RDF.type, CLS_NER_ACTIVITY))
    g.add((ann_activity, RDFS.label, Literal("Ground Truth Annotation Run 2")))
    g.add((ann_activity, DCTERMS.date, Literal("2026-03", datatype=XSD.gYearMonth)))
    g.add((ann_activity, PROV.wasAssociatedWith, agent))

    g.add((el_activity, RDF.type, PROV.Activity))
    g.add((el_activity, RDF.type, CLS_EL_ACTIVITY))
    g.add((el_activity, RDFS.label, Literal("Ground Truth Entity Linking Run 1")))
    g.add((el_activity, DCTERMS.date, Literal("2026-03", datatype=XSD.gYearMonth)))
    g.add((el_activity, PROV.wasAssociatedWith, agent))

    g.add((agent, RDF.type, PROV.Person))
    g.add((agent, RDF.type, PROV.Agent))
    g.add((agent, RDF.type, FOAF.Person))
    g.add((agent, RDFS.label, Literal("Sarah Rebecca Ondraszek")))
    g.add((agent, FOAF.name, Literal("Sarah Rebecca Ondraszek")))

    return ann_activity, el_activity


def main() -> None:
    print("Loading existing KG …")
    g = Graph()
    g.parse(str(KG_FILE), format="turtle")
    initial = len(g)
    print(f"  {initial:,} triples loaded")

    g.bind("viewsari", VIEWSARI)
    g.bind("vkb", VIEWSARI_KB)
    g.bind("doco", DOCO)
    g.bind("prov", PROV)
    g.bind("oa", OA)
    g.bind("foaf", FOAF)
    g.bind("dct", DCTERMS)

    para_map = load_para_map()
    print(f"  {len(para_map)} KG paragraphs indexed")

    ann_activity, el_activity = setup_provenance(g)

    entity_count = mention_count = linked_count = ookb_count = 0
    created_entities: set[str] = set()

    for vol_dir in sorted(ANN_DIR.iterdir()):
        if not vol_dir.is_dir() or not vol_dir.name.isdigit():
            continue
        vol = vol_dir.name

        for ann_file in sorted(vol_dir.glob("*_enriched.json")):
            slug = ann_file.stem.removesuffix("_enriched")
            print(f"  Processing vol {vol} / {slug} …")

            with open(ann_file, encoding="utf-8") as f:
                data = json.load(f)

            for para in data:
                pid = str(para.get("paragraph_id", ""))
                para_uri_str = para_map.get((vol, pid))
                if not para_uri_str:
                    continue
                para_uri = VIEWSARI_KB[para_uri_str.replace("viewsari:", "")]
                g.add((ann_activity, PROV.used, para_uri))

                mention_uris: dict[str, URIRef] = {}

                for m in para.get("mentions", []):
                    mid = m.get("mention_id", "")
                    mtype = m.get("type", "")
                    surface = m.get("surface_form", "")
                    eid = m.get("entity_id")
                    wikidata_id = m.get("wikidata_id") or ""
                    if isinstance(wikidata_id, list):
                        wikidata_id = wikidata_id[0] if wikidata_id else ""
                    is_ookb = m.get("ookb", False)
                    ookb_uri = m.get("ookb_uri") or ""
                    refers_to = m.get("refers_to") or ""
                    label = m.get("label") or surface
                    wga_id = m.get("wga_id") or ""
                    start = m.get("start_offset", 0)
                    end = m.get("end_offset", 0)

                    prefix = f"gt_{slug}_{re.sub(r'[^a-zA-Z0-9]', '_', mid)}"
                    mention_uri = VIEWSARI_KB[prefix]
                    chunk_uri = VIEWSARI_KB[f"{prefix}_chunk"]
                    sel_uri = VIEWSARI_KB[f"{prefix}_selector"]
                    mention_uris[mid] = mention_uri

                    g.add((sel_uri, RDF.type, OA.TextPositionSelector))
                    g.add((sel_uri, OA.start, Literal(start, datatype=XSD.nonNegativeInteger)))
                    g.add((sel_uri, OA.end, Literal(end, datatype=XSD.nonNegativeInteger)))

                    g.add((chunk_uri, RDF.type, DOCO.TextChunk))
                    g.add((chunk_uri, OA.hasSource, para_uri))
                    g.add((chunk_uri, OA.hasSelector, sel_uri))

                    for cls in TYPE_TO_CLASSES.get(mtype, [CLS_MENTION, OA.Annotation, PROV.Entity]):
                        g.add((mention_uri, RDF.type, cls))
                    g.add((mention_uri, OA.hasTarget, chunk_uri))
                    g.add((mention_uri, OA.hasBodyValue, Literal(surface)))
                    g.add((mention_uri, PROV.wasGeneratedBy, ann_activity))
                    g.add((mention_uri, PROP_IN_PARAGRAPH, para_uri))
                    mention_count += 1

                    # Entity linking: only mentions with a wikidata_id or ookb_uri
                    # produce a viewsari:artwork entity. entity_id is ignored.
                    qid = ""
                    if isinstance(wikidata_id, str) and wikidata_id.startswith("http"):
                        m_qid = re.search(r"(Q\d+)$", wikidata_id.rstrip("/"))
                        if m_qid:
                            qid = m_qid.group(1)

                    entity_key = ""
                    entity_uri = None
                    if qid:
                        entity_key = qid
                        entity_uri = VIEWSARI_KB[qid]
                    elif is_ookb and ookb_uri:
                        fragment = ookb_uri.rsplit("#", 1)[-1] if "#" in ookb_uri else ""
                        if fragment:
                            entity_key = fragment
                            entity_uri = VIEWSARI_KB[fragment]

                    if entity_key and entity_uri:
                        g.add((el_activity, PROV.used, mention_uri))
                        g.add((entity_uri, PROV.wasDerivedFrom, mention_uri))
                        g.add((entity_uri, PROP_IN_PARAGRAPH, para_uri))

                        if entity_key not in created_entities:
                            created_entities.add(entity_key)
                            g.add((entity_uri, RDF.type, CLS_ARTWORK))
                            g.add((entity_uri, RDF.type, CLS_EXTRACTED_CONTENT))
                            g.add((entity_uri, RDF.type, PROV.Entity))
                            g.add((entity_uri, RDFS.label, Literal(label[:200])))
                            g.add((entity_uri, PROV.wasGeneratedBy, el_activity))

                            if qid:
                                g.add((entity_uri, OWL.sameAs, URIRef(wikidata_id)))
                                linked_count += 1

                            if is_ookb:
                                ookb_count += 1

                            if wga_id:
                                g.add((entity_uri, RDFS.seeAlso, URIRef(wga_id)))

                            entity_count += 1

                for m in para.get("mentions", []):
                    mid = m.get("mention_id", "")
                    refers_to = m.get("refers_to")
                    if refers_to and mid in mention_uris and refers_to in mention_uris:
                        g.add((mention_uris[mid], PROP_REFERS_TO, mention_uris[refers_to]))

    new_triples = len(g) - initial
    print(f"\nIngested ground truth:")
    print(f"  activity:  vkb:ground_truth_annotation_run_2 (agent: vkb:sarah_ondraszek, date: 2026-03)")
    print(f"  {entity_count} artwork entities ({linked_count} Wikidata, {ookb_count} OOKB)")
    print(f"  {mention_count} mentions")
    print(f"  {new_triples:,} new triples added")
    print(f"  {len(g):,} total triples")

    print(f"\nSerializing to {KG_FILE} …")
    g.serialize(destination=str(KG_FILE), format="turtle")
    size_mb = KG_FILE.stat().st_size / (1024 * 1024)
    print(f"Done — {len(g):,} triples, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
