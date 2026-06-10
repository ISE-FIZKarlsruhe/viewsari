import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPO = os.getenv("GRAPHDB_REPO", "viewsari")
SPARQL_ENDPOINT = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPO}"

# Ontology term catalogue powering the query "building blocks" palette and the
# in-editor autocomplete. Parsed once from the (small) ontology doc and cached.
ONTOLOGY_TTL = Path("data/ontology/viewsari_ontology_docs/doc/ontology.ttl")
ONTO_NS = "https://viewsari.ise.fiz-karlsruhe.de/ontology/"
_terms_cache: dict | None = None


def _clean(text) -> str:
    return " ".join(str(text).split()) if text else ""


def _load_terms() -> dict:
    """Classes and properties from the Viewsari ontology, each with the opaque
    numeric CURIE used in the graph plus its human-readable label and comment."""
    global _terms_cache
    if _terms_cache is not None:
        return _terms_cache

    terms: dict = {"classes": [], "properties": []}
    try:
        from rdflib import OWL, RDF, RDFS, Graph

        g = Graph()
        g.parse(ONTOLOGY_TTL, format="turtle")
    except Exception:
        _terms_cache = terms
        return terms

    def local(uri) -> str:
        return str(uri).rsplit("/", 1)[-1].split("#")[-1]

    seen: set[str] = set()
    for cls in g.subjects(RDF.type, OWL.Class):
        if not str(cls).startswith(ONTO_NS):
            continue
        lid = local(cls)
        label = g.value(cls, RDFS.label)
        if lid in seen or not label:
            continue
        seen.add(lid)
        terms["classes"].append({
            "id": lid, "curie": f"viewsari:{lid}",
            "label": str(label), "comment": _clean(g.value(cls, RDFS.comment)),
        })

    seen_p: set[str] = set()
    for prop_type, kind in ((OWL.ObjectProperty, "object"), (OWL.DatatypeProperty, "data")):
        for prop in g.subjects(RDF.type, prop_type):
            if not str(prop).startswith(ONTO_NS):
                continue
            lid = local(prop)
            label = g.value(prop, RDFS.label)
            if lid in seen_p or not label:
                continue
            seen_p.add(lid)
            terms["properties"].append({
                "id": lid, "curie": f"viewsari:{lid}", "kind": kind,
                "label": str(label), "comment": _clean(g.value(prop, RDFS.comment)),
            })

    terms["classes"].sort(key=lambda t: t["id"])
    terms["properties"].sort(key=lambda t: t["id"])
    _terms_cache = terms
    return terms


@router.get("/sparql", response_class=HTMLResponse)
async def sparql_page(request: Request):
    return templates.TemplateResponse(request, "sparql.html", {"terms": _load_terms()})


@router.post("/sparql/query")
async def sparql_query(request: Request):
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse({"error": "Empty query"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                SPARQL_ENDPOINT,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json, text/turtle"},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            {"error": e.response.text[:500]}, status_code=e.response.status_code
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

    content_type = resp.headers.get("content-type", "")

    if "sparql-results+json" in content_type:
        data = resp.json()
        cols = data.get("head", {}).get("vars", [])
        rows = []
        for binding in data.get("results", {}).get("bindings", []):
            rows.append([binding.get(c, {}).get("value", "") for c in cols])
        return JSONResponse({"columns": cols, "rows": rows, "count": len(rows)})
    elif "turtle" in content_type or "rdf" in content_type:
        return JSONResponse({"turtle": resp.text})
    elif "boolean" in content_type:
        data = resp.json()
        return JSONResponse({"result": data.get("boolean", False)})
    else:
        return JSONResponse({"turtle": resp.text})
