"""
build_kg_ttl.py
===============
Builds the Viewsari Knowledge Graph as a Turtle (.ttl) file from the
CSV seed files in data/kg_foundation/, using the Viewsari ontology as schema.

Usage:
    python src/kg_population/build_kg_ttl.py

Output:
    data/kg/viewsari_kg.ttl
"""

import csv
import os
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD, DCTERMS, SKOS

# ── Namespaces ──────────────────────────────────────────────────────────────

VIEWSARI = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/#")
VIEWSARI_KB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/")
FABIO = Namespace("http://purl.org/spar/fabio/")
DOCO = Namespace("http://purl.org/spar/doco/")
FRBR = Namespace("http://purl.org/vocab/frbr/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
OA = Namespace("http://www.w3.org/ns/oa#")

BASE = Path(__file__).resolve().parent.parent
KG_DIR = BASE / "data" / "kg_foundation"
OUT_DIR = BASE / "data" / "kg"
ONTOLOGY_FILE = BASE / "data" / "ontology" / "viewsari_ontology.rdf"



# Map CSV rdf:type values to proper ontology/vocabulary URIs
TYPE_MAP = {
    "viewsari:volume":                      VIEWSARI["0001006"],
    "viewsari:volume web representation":   VIEWSARI["0001007"],
    "viewsari:biography":                   VIEWSARI["0001008"],
    "viewsari:biography web representation":VIEWSARI["0001010"],
    "viewsari:page":                        VIEWSARI["0001009"],
    "viewsari:page web representation":     VIEWSARI["0001011"],
    "viewsari:person":                      VIEWSARI["0001013"],
    "viewsari:cooccurrence":                VIEWSARI["0001025"],
    "fabio:Expression":                     FABIO.Expression,
    "fabio:BookSeries":                     FABIO.BookSeries,
    "fabio:WebSite":                        FABIO.WebSite,
    "fabio:WebPage":                        FABIO.WebPage,
    "fabio:Book":                           FABIO.Book,
    "fabio:ManifestationCollection":        FABIO.ManifestationCollection,
    "doco:Paragraph":                       DOCO.Paragraph,
    "doco:TextChunk":                       DOCO.TextChunk,
    "doco:TextPositionSelector":            DOCO.TextPositionSelector,
    "oa:TextPositionSelector":              OA.TextPositionSelector,
    "oa:Annotation":                        OA.Annotation,
    "prov:Entity":                          PROV.Entity,
    "prov:Activity":                        PROV.Activity,
}


def uri(prefix_id: str) -> URIRef:
    """Convert 'viewsari:foo' or a full URI to a URIRef."""
    s = prefix_id.strip().strip('"')
    # Check type map first (handles spaces in type names)
    if s in TYPE_MAP:
        return TYPE_MAP[s]
    if s.startswith("viewsari:"):
        local = s[len("viewsari:"):]
        # If it looks like an ontology class ID (numeric), use ontology namespace
        if local.startswith("0001"):
            return VIEWSARI[local]
        return VIEWSARI_KB[local.replace(" ", "_")]
    if s.startswith("http://") or s.startswith("https://"):
        return URIRef(s)
    if s.startswith("oa:"):
        return OA[s[3:]]
    if s.startswith("prov:"):
        return PROV[s[5:]]
    if s.startswith("doco:"):
        return DOCO[s[5:]]
    if s.startswith("fabio:"):
        return FABIO[s[6:]]
    return VIEWSARI_KB[s.replace(" ", "_")]


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add_volumes(g: Graph):
    """Stage 1: Volumes (expression + manifestation)."""
    for row in read_csv(KG_DIR / "viewsari_volumes.csv"):
        subj = uri(row["instance_id"])
        rdf_type1 = row.get("rdf_type_1", "")
        rdf_type2 = row.get("rdf_type_2", "")
        label = row.get("rdfs:label", "")
        part_of = row.get("frbr:is part of", "")
        embodiment = row.get("frbr:has embodiment", "")
        see_also = row.get("rdfs:seeAlso", "")
        level = row.get("level", "")

        if rdf_type1:
            g.add((subj, RDF.type, uri(rdf_type1)))
        if rdf_type2:
            g.add((subj, RDF.type, uri(rdf_type2)))
        if label:
            g.add((subj, RDFS.label, Literal(label)))
        if part_of:
            g.add((subj, FRBR["isPartOf"], uri(part_of)))
        if embodiment:
            g.add((subj, FRBR["hasEmbodiment"], uri(embodiment)))
        if see_also:
            g.add((subj, RDFS.seeAlso, URIRef(see_also)))


def add_biographies(g: Graph):
    """Stage 2: Biographies."""
    for row in read_csv(KG_DIR / "viewsari_biographies.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, uri(row["rdf:type"])))
        if row.get("rdf_type_2"):
            g.add((subj, RDF.type, uri(row["rdf_type_2"])))
        g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("frbr:is part of"):
            g.add((subj, FRBR["isPartOf"], uri(row["frbr:is part of"])))
        if row.get("frbr:has embodiment"):
            g.add((subj, FRBR["hasEmbodiment"], uri(row["frbr:has embodiment"])))
        if row.get("rdfs:seeAlso"):
            g.add((subj, RDFS.seeAlso, URIRef(row["rdfs:seeAlso"])))
        if row.get("start_page"):
            g.add((subj, VIEWSARI["hasStartPage"], Literal(int(row["start_page"]), datatype=XSD.integer)))


def add_pages(g: Graph):
    """Stage 3: Pages."""
    for row in read_csv(KG_DIR / "viewsari_pages.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, uri(row["rdf:type"])))
        if row.get("rdf_type_2"):
            g.add((subj, RDF.type, uri(row["rdf_type_2"])))
        g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("frbr:is part of"):
            g.add((subj, FRBR["isPartOf"], uri(row["frbr:is part of"])))
        if row.get("frbr:has embodiment"):
            g.add((subj, FRBR["hasEmbodiment"], uri(row["frbr:has embodiment"])))
        if row.get("rdfs:seeAlso"):
            g.add((subj, RDFS.seeAlso, URIRef(row["rdfs:seeAlso"])))
        if row.get("page_number"):
            g.add((subj, VIEWSARI["hasPageNumber"], Literal(int(row["page_number"]), datatype=XSD.integer)))


def add_paragraphs(g: Graph):
    """Stage 4: Paragraphs."""
    for row in read_csv(KG_DIR / "viewsari_paragraphs.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, DOCO.Paragraph))
        g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("dct:isPartOf"):
            g.add((subj, DCTERMS.isPartOf, uri(row["dct:isPartOf"])))
        if row.get("viewsari:has start page"):
            g.add((subj, VIEWSARI["hasStartPage"], uri(row["viewsari:has start page"])))
        if row.get("viewsari:has end page"):
            g.add((subj, VIEWSARI["hasEndPage"], uri(row["viewsari:has end page"])))
        if row.get("viewsari:has length in characters"):
            g.add((subj, VIEWSARI["hasLengthInCharacters"],
                   Literal(int(row["viewsari:has length in characters"]), datatype=XSD.nonNegativeInteger)))
        if row.get("viewsari:has text"):
            g.add((subj, VIEWSARI["hasText"], Literal(row["viewsari:has text"])))
        if row.get("frbr:is part of"):
            g.add((subj, FRBR["isPartOf"], uri(row["frbr:is part of"])))


def add_persons(g: Graph):
    """Stage 5a: Persons."""
    persons_dir = KG_DIR / "persons"

    for row in read_csv(persons_dir / "viewsari_persons.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, VIEWSARI["0001013"]))
        g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("prov:wasGeneratedBy"):
            g.add((subj, PROV.wasGeneratedBy, uri(row["prov:wasGeneratedBy"])))
        if row.get("Wikidata QID"):
            wd_uri = URIRef(f"http://www.wikidata.org/entity/{row['Wikidata QID']}")
            g.add((subj, OWL.sameAs, wd_uri))
        if row.get("Wikidata alt-labels"):
            for alt in row["Wikidata alt-labels"].split(";"):
                alt = alt.strip()
                if alt:
                    g.add((subj, SKOS.altLabel, Literal(alt, lang="en")))

    # TextChunks
    for row in read_csv(persons_dir / "viewsari_textchunks.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, DOCO.TextChunk))
        if row.get("rdfs:label"):
            g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("oa:hasSource"):
            g.add((subj, OA.hasSource, uri(row["oa:hasSource"])))
        if row.get("oa:hasSelector"):
            g.add((subj, OA.hasSelector, uri(row["oa:hasSelector"])))

    # Selectors
    for row in read_csv(persons_dir / "viewsari_selectors.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, OA.TextPositionSelector))
        if row.get("oa:start"):
            g.add((subj, OA.start, Literal(int(row["oa:start"]), datatype=XSD.nonNegativeInteger)))
        if row.get("oa:end"):
            g.add((subj, OA.end, Literal(int(row["oa:end"]), datatype=XSD.nonNegativeInteger)))

    # Annotations
    for row in read_csv(persons_dir / "viewsari_annotations.csv"):
        subj = uri(row["instance_id"])
        for t in row.get("rdf:type", "").split(","):
            t = t.strip()
            if t:
                g.add((subj, RDF.type, uri(t)))
        if row.get("oa:hasTarget"):
            g.add((subj, OA.hasTarget, uri(row["oa:hasTarget"])))
        if row.get("oa:hasBodyValue"):
            g.add((subj, OA.hasBodyValue, Literal(row["oa:hasBodyValue"])))
        if row.get("prov:wasGeneratedBy"):
            g.add((subj, PROV.wasGeneratedBy, uri(row["prov:wasGeneratedBy"])))
        if row.get("oa:hasSource"):
            g.add((subj, OA.hasSource, uri(row["oa:hasSource"])))


def add_activities(g: Graph):
    """Stage 5b: Provenance activities."""
    for row in read_csv(KG_DIR / "viewsari_activities.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, PROV.Activity))
        g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("prov:wasAssociatedWith"):
            g.add((subj, PROV.wasAssociatedWith, uri(row["prov:wasAssociatedWith"])))
        # prov:used is space-separated list of URIs
        used = row.get("prov:used", "").strip()
        if used:
            for u in used.split():
                u = u.strip()
                if u:
                    g.add((subj, PROV.used, uri(u)))


def add_cooccurrences(g: Graph):
    """Stage 6: Co-occurrences."""
    cooc_dir = KG_DIR / "cooccurrences"

    for row in read_csv(cooc_dir / "viewsari_cooccurrences.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, VIEWSARI["0001025"]))
        g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("viewsari:involves"):
            g.add((subj, VIEWSARI.involves, uri(row["viewsari:involves"])))
        if row.get("viewsari:involves_2"):
            g.add((subj, VIEWSARI.involves, uri(row["viewsari:involves_2"])))
        if row.get("prov:wasGeneratedBy"):
            g.add((subj, PROV.wasGeneratedBy, uri(row["prov:wasGeneratedBy"])))

    # Cooc TextChunks
    for row in read_csv(cooc_dir / "viewsari_cooc_textchunks.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, DOCO.TextChunk))
        if row.get("rdfs:label"):
            g.add((subj, RDFS.label, Literal(row["rdfs:label"])))
        if row.get("oa:hasSource"):
            g.add((subj, OA.hasSource, uri(row["oa:hasSource"])))
        if row.get("oa:hasSelector"):
            g.add((subj, OA.hasSelector, uri(row["oa:hasSelector"])))

    # Cooc Selectors
    for row in read_csv(cooc_dir / "viewsari_cooc_selectors.csv"):
        subj = uri(row["instance_id"])
        g.add((subj, RDF.type, OA.TextPositionSelector))
        if row.get("oa:start"):
            g.add((subj, OA.start, Literal(int(row["oa:start"]), datatype=XSD.nonNegativeInteger)))
        if row.get("oa:end"):
            g.add((subj, OA.end, Literal(int(row["oa:end"]), datatype=XSD.nonNegativeInteger)))

    # Cooc Annotations
    for row in read_csv(cooc_dir / "viewsari_cooc_annotations.csv"):
        subj = uri(row["instance_id"])
        for t in row.get("rdf:type", "").split(","):
            t = t.strip()
            if t:
                g.add((subj, RDF.type, uri(t)))
        if row.get("oa:hasTarget"):
            g.add((subj, OA.hasTarget, uri(row["oa:hasTarget"])))
        if row.get("oa:hasBodyValue"):
            g.add((subj, OA.hasBodyValue, Literal(row["oa:hasBodyValue"])))
        if row.get("prov:wasGeneratedBy"):
            g.add((subj, PROV.wasGeneratedBy, uri(row["prov:wasGeneratedBy"])))


def main():
    g = Graph()

    # Bind prefixes
    g.bind("viewsari", VIEWSARI)
    g.bind("vkb", VIEWSARI_KB)
    g.bind("fabio", FABIO)
    g.bind("doco", DOCO)
    g.bind("frbr", FRBR)
    g.bind("prov", PROV)
    g.bind("oa", OA)
    g.bind("dct", DCTERMS)
    g.bind("skos", SKOS)

    # Import ontology TBox
    print("Loading ontology TBox …")
    g.parse(str(ONTOLOGY_FILE), format="xml")
    print(f"  {len(g)} triples after ontology import")

    print("Stage 1 — Volumes")
    add_volumes(g)
    print(f"  {len(g)} triples")

    print("Stage 2 — Biographies")
    add_biographies(g)
    print(f"  {len(g)} triples")

    print("Stage 3 — Pages")
    add_pages(g)
    print(f"  {len(g)} triples")

    print("Stage 4 — Paragraphs")
    add_paragraphs(g)
    print(f"  {len(g)} triples")

    print("Stage 5 — Persons + Annotations")
    add_persons(g)
    print(f"  {len(g)} triples")

    print("Stage 6 — Activities")
    add_activities(g)
    print(f"  {len(g)} triples")

    print("Stage 7 — Co-occurrences")
    add_cooccurrences(g)
    print(f"  {len(g)} triples")

    # Serialize
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "viewsari_kg.ttl"
    print(f"\nSerializing to {out_path} …")
    g.serialize(destination=str(out_path), format="turtle")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Done — {len(g)} triples, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
