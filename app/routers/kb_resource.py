"""KG resource pages — persons, text chunks, and other RDF entities.

Queries GraphDB instead of loading the TTL into memory.
"""

import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.routers.volume import try_volume, _load_volumes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPO = os.getenv("GRAPHDB_REPO", "viewsari")
SPARQL_ENDPOINT = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPO}"

VKB = "https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#"


async def _sparql(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            SPARQL_ENDPOINT,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
    data = resp.json()
    cols = data.get("head", {}).get("vars", [])
    rows = []
    for b in data.get("results", {}).get("bindings", []):
        rows.append({c: b.get(c, {}).get("value", "") for c in cols})
    return rows


async def _load_person(resource_id: str) -> dict | None:
    uri = VKB + resource_id
    rows = await _sparql(f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX viewsari: <https://viewsari.ise.fiz-karlsruhe.de/ontology/>
        SELECT ?label ?wikidata WHERE {{
            <{uri}> a viewsari:0001013 ;
                     rdfs:label ?label .
            OPTIONAL {{ <{uri}> owl:sameAs ?wikidata . }}
        }} LIMIT 1
    """)
    if not rows:
        return None
    label = rows[0]["label"]
    wikidata_url = rows[0].get("wikidata", "")
    wikidata_id = wikidata_url.rstrip("/").split("/")[-1] if wikidata_url else ""

    alt_rows = await _sparql(f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?alt WHERE {{
            <{uri}> skos:altLabel ?alt .
        }} ORDER BY ?alt
    """)
    alt_labels = sorted(set(r["alt"] for r in alt_rows))

    cooc_rows = await _sparql(f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX viewsari: <https://viewsari.ise.fiz-karlsruhe.de/ontology/>
        SELECT ?cooc ?cooc_label ?other ?other_label WHERE {{
            ?cooc viewsari:involves <{uri}> ;
                  rdfs:label ?cooc_label ;
                  viewsari:involves ?other .
            ?other rdfs:label ?other_label .
            FILTER(?other != <{uri}>)
        }} ORDER BY ?cooc_label
    """)
    coocs_map: dict[str, dict] = {}
    for r in cooc_rows:
        cid = r["cooc"]
        if cid not in coocs_map:
            coocs_map[cid] = {"label": r["cooc_label"], "others": []}
        other_id = r["other"].split("#")[-1] if "#" in r["other"] else r["other"].split("/")[-1]
        coocs_map[cid]["others"].append({"id": other_id, "label": r["other_label"]})
    coocs = sorted(coocs_map.values(), key=lambda c: c["label"])

    return {
        "id": resource_id,
        "label": label,
        "wikidata_id": wikidata_id,
        "wikidata_url": wikidata_url,
        "alt_labels": alt_labels,
        "cooccurrences": coocs,
    }


async def _load_textchunk(resource_id: str) -> dict | None:
    uri = VKB + resource_id
    rows = await _sparql(f"""
        PREFIX oa: <http://www.w3.org/ns/oa#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX doco: <http://purl.org/spar/doco/>
        SELECT ?source ?start ?end ?body ?provenance WHERE {{
            <{uri}> a doco:TextChunk ;
                     oa:hasSource ?source .
            OPTIONAL {{
                <{uri}> oa:hasSelector ?sel .
                ?sel oa:start ?start ; oa:end ?end .
            }}
            OPTIONAL {{
                ?annot oa:hasTarget <{uri}> ;
                       oa:hasBodyValue ?body .
                OPTIONAL {{ ?annot prov:wasGeneratedBy ?provenance . }}
            }}
        }} LIMIT 1
    """)
    if not rows:
        return None
    r = rows[0]
    source_id = r["source"].split("#")[-1] if "#" in r["source"] else r["source"].split("/")[-1]

    para_id = ""
    vol_num = ""
    if source_id:
        parts = source_id.rsplit("_paragraph-", 1)
        if len(parts) == 2:
            para_id = parts[1]
            vol_parts = parts[0].rsplit("_volume-", 1)
            if len(vol_parts) == 2:
                vol_num = vol_parts[1]

    prov = r.get("provenance", "")
    if prov:
        prov = prov.split("#")[-1] if "#" in prov else prov.split("/")[-1]

    return {
        "id": resource_id,
        "source": source_id,
        "source_uri": r["source"],
        "paragraph_id": para_id,
        "volume": vol_num,
        "start": r.get("start", ""),
        "end": r.get("end", ""),
        "text": r.get("body", ""),
        "provenance": prov,
    }


@router.get("/kb/{resource_id}", response_class=HTMLResponse)
async def kb_resource(resource_id: str, request: Request):
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

    person = await _load_person(resource_id)
    if person:
        return templates.TemplateResponse(
            request, "kb_person.html", {"person": person},
        )

    chunk = await _load_textchunk(resource_id)
    if chunk:
        return templates.TemplateResponse(
            request, "kb_textchunk.html", {"chunk": chunk},
        )

    return templates.TemplateResponse(
        request, "404.html",
        {"message": f"Resource '{resource_id}' not found in the knowledge graph."},
        status_code=404,
    )
