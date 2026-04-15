import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

NER_EXPLORER_BASE = Path("data/kg/explorer/ner")


@router.get("/obliquer", response_class=HTMLResponse)
async def obliquer_about(request: Request):
    return templates.TemplateResponse(request, "obliquer_about.html", {})


@router.get("/obliquer/demo", response_class=HTMLResponse)
async def obliquer_demo(request: Request):
    return templates.TemplateResponse(request, "obliquer.html", {})


@router.get("/obliquer/explore", response_class=HTMLResponse)
async def obliquer_explore(request: Request):
    # Load strategy index files for the biography selector
    strategies = {}
    for strategy_dir in sorted(NER_EXPLORER_BASE.iterdir()):
        index_file = strategy_dir / "index.json"
        if index_file.exists():
            strategies[strategy_dir.name] = json.loads(index_file.read_text(encoding="utf-8"))
    return templates.TemplateResponse(request, "obliquer_explore.html", {"strategies": strategies})


@router.get("/obliquer/explore/subgraph", response_class=JSONResponse)
async def obliquer_explore_subgraph(
    strategy: str = Query(...),
    bio: str = Query(...),
):
    graph_file = NER_EXPLORER_BASE / strategy / f"bio_{bio}.json"
    if not graph_file.exists():
        raise HTTPException(status_code=404, detail="Graph not found")
    return JSONResponse(json.loads(graph_file.read_text(encoding="utf-8")))
