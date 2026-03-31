import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from rdflib import Graph

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Load KG once at module level
_KG_PATH = Path("data/kg/viewsari_kg.ttl")
_graph: Graph | None = None


def _get_graph() -> Graph:
    global _graph
    if _graph is None:
        _graph = Graph()
        _graph.parse(str(_KG_PATH), format="turtle")
    return _graph


@router.get("/sparql", response_class=HTMLResponse)
async def sparql_page(request: Request):
    return templates.TemplateResponse(request, "sparql.html", {})


@router.post("/sparql/query")
async def sparql_query(request: Request):
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse({"error": "Empty query"}, status_code=400)

    g = _get_graph()
    try:
        results = g.query(query)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if results.type == "SELECT":
        cols = [str(v) for v in results.vars]
        rows = []
        for row in results:
            rows.append([str(cell) if cell is not None else "" for cell in row])
        return JSONResponse({"columns": cols, "rows": rows, "count": len(rows)})
    elif results.type == "ASK":
        return JSONResponse({"result": bool(results.askAnswer)})
    elif results.type == "CONSTRUCT" or results.type == "DESCRIBE":
        ttl = results.serialize(format="turtle")
        return JSONResponse({"turtle": ttl})
    else:
        return JSONResponse({"error": f"Unsupported query type: {results.type}"}, status_code=400)
