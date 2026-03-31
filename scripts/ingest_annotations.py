"""
ingest_annotations.py
=====================
Ingests artwork entities and mentions from the ObliquER ground truth
annotations into the Viewsari KG Turtle file.

Maps annotation JSON fields to the Viewsari ontology:
  - Artworks:  viewsari:artwork (0001012)
  - Mentions:  viewsari:mention (0001026) and subtypes
  - TextChunks, TextPositionSelectors, oa:Annotation patterns
  - owl:sameAs for Wikidata-linked entities
  - OOKB URIs for out-of-knowledge-base entities
  - Paragraph anchoring via volume + paragraph_id matching

Usage:
    python scripts/ingest_annotations.py
"""

import csv
import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD

csv.field_size_limit(sys.maxsize)

VIEWSARI = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/#")
VIEWSARI_KB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/")
DOCO = Namespace("http://purl.org/spar/doco/")
PROV = Namespace("http://www.w3.org/ns/prov#")
OA = Namespace("http://www.w3.org/ns/oa#")

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
CLS_EXTRACTED_CONTENT = VIEWSARI["0001033"]

# Map annotation type strings to ontology classes
TYPE_TO_CLASS = {
    "explicit artwork mention": [CLS_MENTION, CLS_EXPLICIT_MENTION, CLS_EXPLICIT_ART_MENTION, OA.Annotation, PROV.Entity],
    "implicit artwork mention": [CLS_MENTION, CLS_IMPLICIT_MENTION, CLS_IMPLICIT_ART_MENTION, OA.Annotation, PROV.Entity],
    "coreferent":               [CLS_MENTION, CLS_COREFERENT, OA.Annotation, PROV.Entity],
    "generic mention":          [CLS_MENTION, CLS_GENERIC, OA.Annotation, PROV.Entity],
}


def load_para_map() -> dict[tuple[str, str], str]:
    """Build (vol, paragraph_id) -> KG paragraph URI mapping."""
    para_map = {}
    with open(PARA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vol = row.get("vol", "")
            pid = row.get("paragraph_id", "")
            para_map[(vol, pid)] = row.get("instance_id", "")
    return para_map


def main():
    print("Loading existing KG …")
    g = Graph()
    g.parse(str(KG_FILE), format="turtle")
    initial = len(g)
    print(f"  {initial} triples loaded")

    # Bind prefixes
    g.bind("viewsari", VIEWSARI)
    g.bind("vkb", VIEWSARI_KB)
    g.bind("doco", DOCO)
    g.bind("prov", PROV)
    g.bind("oa", OA)

    para_map = load_para_map()
    print(f"  {len(para_map)} KG paragraphs indexed")

    # Provenance activity for ObliquER extraction
    obliquer_activity = VIEWSARI_KB["obliquer_extraction_run_1"]
    g.add((obliquer_activity, RDF.type, PROV.Activity))
    g.add((obliquer_activity, RDFS.label, Literal("ObliquER Extraction Run 1")))

    el_activity = VIEWSARI_KB["entity_linking_run_1"]
    g.add((el_activity, RDF.type, PROV.Activity))
    g.add((el_activity, RDFS.label, Literal("Entity Linking Run 1")))

    entity_count = 0
    mention_count = 0
    linked_count = 0
    ookb_count = 0

    # Track entities already created (per biography scope)
    created_entities = set()

    for vol_dir in sorted(ANN_DIR.iterdir()):
        if not vol_dir.is_dir() or not vol_dir.name.isdigit():
            continue
        vol = vol_dir.name

        for ann_file in sorted(vol_dir.glob("*_enriched.json")):
            slug = ann_file.stem.removesuffix("_enriched")
            print(f"  Processing {slug} (vol {vol}) …")

            with open(ann_file, encoding="utf-8") as f:
                data = json.load(f)

            for para in data:
                pid = str(para.get("paragraph_id", ""))
                para_uri_str = para_map.get((vol, pid))
                if not para_uri_str:
                    continue
                para_uri = VIEWSARI_KB[para_uri_str.replace("viewsari:", "")]

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

                    # Mention URI (scoped to biography)
                    mention_uri = VIEWSARI_KB[f"{slug}_{mid}"]

                    # TextChunk and selector
                    chunk_uri = VIEWSARI_KB[f"{slug}_{mid}_chunk"]
                    sel_uri = VIEWSARI_KB[f"{slug}_{mid}_selector"]

                    # -- TextPositionSelector --
                    g.add((sel_uri, RDF.type, OA.TextPositionSelector))
                    g.add((sel_uri, OA.start, Literal(start, datatype=XSD.nonNegativeInteger)))
                    g.add((sel_uri, OA.end, Literal(end, datatype=XSD.nonNegativeInteger)))

                    # -- TextChunk --
                    g.add((chunk_uri, RDF.type, DOCO.TextChunk))
                    g.add((chunk_uri, OA.hasSource, para_uri))
                    g.add((chunk_uri, OA.hasSelector, sel_uri))
                    g.add((chunk_uri, RDFS.label, Literal(surface[:100])))

                    # -- Mention annotation --
                    classes = TYPE_TO_CLASS.get(mtype, [CLS_MENTION, OA.Annotation, PROV.Entity])
                    for cls in classes:
                        g.add((mention_uri, RDF.type, cls))
                    g.add((mention_uri, OA.hasTarget, chunk_uri))
                    g.add((mention_uri, RDFS.label, Literal(surface[:100])))
                    g.add((mention_uri, PROV.wasGeneratedBy, obliquer_activity))

                    # Coreferent link
                    if refers_to:
                        ref_uri = VIEWSARI_KB[f"{slug}_{refers_to}"]
                        g.add((mention_uri, VIEWSARI["0001035"], ref_uri))  # viewsari:refersTo

                    mention_count += 1

                    # -- Artwork entity --
                    if eid:
                        entity_key = f"{slug}_{eid}"
                        entity_uri = VIEWSARI_KB[entity_key]

                        g.add((mention_uri, OA.hasBody, entity_uri))

                        if entity_key not in created_entities:
                            created_entities.add(entity_key)
                            g.add((entity_uri, RDF.type, CLS_ARTWORK))
                            g.add((entity_uri, RDF.type, CLS_EXTRACTED_CONTENT))
                            g.add((entity_uri, RDFS.label, Literal(label[:200])))
                            g.add((entity_uri, PROV.wasGeneratedBy, el_activity))

                            # Wikidata link
                            if wikidata_id and wikidata_id.startswith("http"):
                                g.add((entity_uri, OWL.sameAs, URIRef(wikidata_id)))
                                linked_count += 1

                            # OOKB URI
                            if is_ookb and ookb_uri:
                                g.add((entity_uri, VIEWSARI_KB["hasOokbUri"], URIRef(ookb_uri)))
                                ookb_count += 1

                            # WGA link
                            if wga_id:
                                g.add((entity_uri, RDFS.seeAlso, URIRef(wga_id)))

                            # Paragraph anchoring
                            g.add((entity_uri, VIEWSARI["0001032"], para_uri))  # viewsari:inParagraph

                            entity_count += 1

    new_triples = len(g) - initial
    print(f"\nIngested:")
    print(f"  {entity_count} artwork entities ({linked_count} Wikidata, {ookb_count} OOKB)")
    print(f"  {mention_count} mentions")
    print(f"  {new_triples} new triples added")
    print(f"  {len(g)} total triples")

    print(f"\nSerializing to {KG_FILE} …")
    g.serialize(destination=str(KG_FILE), format="turtle")
    size_mb = KG_FILE.stat().st_size / (1024 * 1024)
    print(f"Done — {len(g)} triples, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
