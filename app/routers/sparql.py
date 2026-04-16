import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://localhost:7200")
GRAPHDB_REPO = os.getenv("GRAPHDB_REPO", "viewsari")
SPARQL_ENDPOINT = f"{GRAPHDB_URL}/repositories/{GRAPHDB_REPO}"


@router.get("/sparql", response_class=HTMLResponse)
async def sparql_page(request: Request):
    return templates.TemplateResponse(request, "sparql.html", {})


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
