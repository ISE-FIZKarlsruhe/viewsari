import json
import random
from pathlib import Path

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

EXPLORER_DIR = Path("data/kg/explorer")

# Caches
_index: list[dict] | None = None
_graph_cache: dict[str, dict] = {}
_suggest_labels: list[dict] | None = None


def _load_index() -> list[dict]:
    global _index
    if _index is None:
        with open(EXPLORER_DIR / "index.json") as f:
            _index = json.load(f)
    return _index


def _load_graph(filename: str) -> dict:
    if filename not in _graph_cache:
        path = EXPLORER_DIR / filename
        if path.exists():
            with open(path) as f:
                _graph_cache[filename] = json.load(f)
        else:
            _graph_cache[filename] = {"nodes": [], "edges": []}
    return _graph_cache[filename]


def _build_suggest_labels() -> list[dict]:
    global _suggest_labels
    if _suggest_labels is None:
        _suggest_labels = []
        index = _load_index()
        for entry in index:
            g = _load_graph(entry["file"])
            for n in g["nodes"]:
                if n["type"] in ("person", "artwork"):
                    _suggest_labels.append({"label": n["label"], "type": n["type"]})
        # Deduplicate
        seen = set()
        unique = []
        for item in _suggest_labels:
            key = (item["label"], item["type"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        unique.sort(key=lambda x: x["label"])
        _suggest_labels = unique
    return _suggest_labels


@router.get("/explore", response_class=HTMLResponse)
async def explore_page(request: Request):
    return templates.TemplateResponse(request, "explore.html", {})


@router.get("/explore/suggest")
async def explore_suggest(q: str = Query(default="")):
    q = q.strip().lower()
    if len(q) < 2:
        return JSONResponse([])
    labels = _build_suggest_labels()
    # Prefix matches first, then contains
    results = []
    for item in labels:
        if q in item["label"].lower():
            results.append(item)
        if len(results) >= 12:
            break
    results.sort(key=lambda x: (0 if x["label"].lower().startswith(q) else 1, x["label"]))
    return JSONResponse(results[:12])


@router.get("/explore/index")
async def explore_index():
    return JSONResponse(_load_index())


@router.get("/explore/subgraph")
async def explore_subgraph(
    seed: str = Query(default=""),
    mode: str = Query(default="random"),
):
    index = _load_index()
    seed_lower = seed.lower().strip()

    if mode == "random":
        # Pick a random pre-computed graph
        candidates = [e for e in index if e["mode"] == "person"]
        if candidates:
            chosen = random.choice(candidates)
            return JSONResponse(_load_graph(chosen["file"]))
        return JSONResponse({"nodes": [], "edges": []})

    # Search: find the best matching pre-computed graph
    if seed_lower:
        # Exact file match first
        for entry in index:
            if entry["mode"] == mode and seed_lower == entry["label"].lower():
                return JSONResponse(_load_graph(entry["file"]))

        # Partial match
        for entry in index:
            if entry["mode"] == mode and seed_lower in entry["label"].lower():
                return JSONResponse(_load_graph(entry["file"]))

        # Cross-mode: search in any graph's nodes for matching entities
        best = None
        best_count = 0
        for entry in index:
            g = _load_graph(entry["file"])
            count = sum(1 for n in g["nodes"]
                        if seed_lower in n["label"].lower()
                        and n["type"] in ("person", "artwork"))
            if count > best_count:
                best = g
                best_count = count
        if best:
            return JSONResponse(best)

    return JSONResponse({"nodes": [], "edges": []})
