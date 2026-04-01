"""KG resource pages — persons, text chunks, and other RDF entities."""

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from rdflib import Graph, Namespace, URIRef

from app.routers.volume import try_volume, _load_volumes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_KG_PATH = Path("data/kg/viewsari_kg.ttl")
_graph: Graph | None = None

VKB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/")
VIEWSARI = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/#")
OA = Namespace("http://www.w3.org/ns/oa#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DOCO = Namespace("http://purl.org/spar/doco/")

# Ontology class IDs
PERSON_CLASS = VIEWSARI["0001013"]
COOC_CLASS = VIEWSARI["0001025"]
TEXTCHUNK_CLASS = DOCO["TextChunk"]


def _get_graph() -> Graph:
    global _graph
    if _graph is None:
        _graph = Graph()
        _graph.parse(str(_KG_PATH), format="turtle")
    return _graph


def _load_person(g: Graph, uri: URIRef) -> dict | None:
    """Load person data from the KG."""
    label = g.value(uri, RDFS.label)
    if label is None:
        return None

    # Check it's actually a person
    types = [str(o) for o in g.objects(uri, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"))]
    if str(PERSON_CLASS) not in types:
        return None

    wikidata = g.value(uri, OWL.sameAs)
    wikidata_id = ""
    if wikidata:
        wikidata_id = str(wikidata).rstrip("/").split("/")[-1]

    alt_labels = sorted(set(str(o) for o in g.objects(uri, SKOS.altLabel)))

    # Co-occurrences
    coocs = []
    for cooc in g.subjects(VIEWSARI.involves, uri):
        cooc_label = g.value(cooc, RDFS.label)
        others = []
        for other in g.objects(cooc, VIEWSARI.involves):
            if other != uri:
                other_label = g.value(other, RDFS.label)
                if other_label:
                    other_id = str(other).split("/")[-1]
                    others.append({"id": other_id, "label": str(other_label)})
        coocs.append({
            "label": str(cooc_label) if cooc_label else "",
            "others": others,
        })
    coocs.sort(key=lambda c: c["label"])

    return {
        "id": str(uri).split("/")[-1],
        "label": str(label),
        "wikidata_id": wikidata_id,
        "wikidata_url": str(wikidata) if wikidata else "",
        "alt_labels": alt_labels,
        "cooccurrences": coocs,
    }


def _load_textchunk(g: Graph, uri: URIRef) -> dict | None:
    """Load text chunk data from the KG."""
    types = [str(o) for o in g.objects(uri, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"))]
    if str(TEXTCHUNK_CLASS) not in types:
        return None

    # Source paragraph
    source = g.value(uri, OA.hasSource)
    source_id = str(source).split("/")[-1] if source else ""

    # Position selector
    selector = g.value(uri, OA.hasSelector)
    start = end = ""
    if selector:
        s = g.value(selector, OA.start)
        e = g.value(selector, OA.end)
        start = str(s) if s else ""
        end = str(e) if e else ""

    # Annotation body (the surface text)
    body = ""
    annotation = None
    for annot in g.subjects(OA.hasTarget, uri):
        body_val = g.value(annot, OA.hasBodyValue)
        if body_val:
            body = str(body_val)
            annotation = annot
            break

    # Provenance
    provenance = ""
    if annotation:
        gen = g.value(annotation, PROV.wasGeneratedBy)
        if gen:
            provenance = str(gen).split("/")[-1]

    # Parse paragraph info from source
    para_id = ""
    bio_slug = ""
    vol_num = ""
    if source_id:
        # e.g. "the_lives_1568_volume-1_paragraph-95"
        parts = source_id.rsplit("_paragraph-", 1)
        if len(parts) == 2:
            para_id = parts[1]
            bio_part = parts[0]
            # e.g. "the_lives_1568_volume-1"
            vol_parts = bio_part.rsplit("_volume-", 1)
            if len(vol_parts) == 2:
                vol_num = vol_parts[1]

    return {
        "id": str(uri).split("/")[-1],
        "source": source_id,
        "source_uri": str(source) if source else "",
        "paragraph_id": para_id,
        "volume": vol_num,
        "start": start,
        "end": end,
        "text": body,
        "provenance": provenance,
    }


@router.get("/kb/{resource_id}", response_class=HTMLResponse)
async def kb_resource(resource_id: str, request: Request):
    # Try volume first
    data_dir = os.getenv("DATA_DIR", "./data/kg_foundation")
    vol = try_volume(resource_id, data_dir)
    if vol:
        backend = request.app.state.backend
        volumes = _load_volumes(data_dir)
        all_bios = backend.list_biographies()
        available_slugs = {b["slug"] for b in all_bios}
        for bio in vol["biographies"]:
            bio["available"] = bio["slug"] in available_slugs
            bio["paragraph_count"] = 0
            if bio["available"]:
                match = next((b for b in all_bios if b["slug"] == bio["slug"]), None)
                if match:
                    bio["paragraph_count"] = match["paragraph_count"]
        return templates.TemplateResponse(
            request, "volume.html", {"vol": vol, "volumes": volumes},
        )

    g = _get_graph()
    uri = VKB[resource_id]

    # Try person
    person = _load_person(g, uri)
    if person:
        return templates.TemplateResponse(
            request, "kb_person.html", {"person": person},
        )

    # Try text chunk
    chunk = _load_textchunk(g, uri)
    if chunk:
        return templates.TemplateResponse(
            request, "kb_textchunk.html", {"chunk": chunk},
        )

    return templates.TemplateResponse(
        request, "404.html",
        {"message": f"Resource '{resource_id}' not found in the knowledge graph."},
        status_code=404,
    )
