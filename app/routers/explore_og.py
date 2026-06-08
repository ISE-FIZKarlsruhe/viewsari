import json
import random
from pathlib import Path

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

EXPLORER_DIR = Path("data/kg/explorer/og")

# Node types that feed the search autocomplete for this layer.
SUGGEST_TYPES = ("entity", "ookb")

# Config consumed by the shared explore.html template (see explore.py for the
# ground-truth counterpart). Drives the API base, presets, legend and labels.
CFG = {
    "api_base": "/explore/og",
    "title": "Viewsari · Artwork explorer — AI-extracted + linked",
    "chip": "Artwork explorer — AI-extracted + linked",
    "placeholder": "Search a person, biography or artwork (e.g. Giotto, Madonna)",
    "intro": ("Here the AI read the text, found each artwork, and tried to match "
              "it to Wikidata. <strong>Blue</strong> = matched to a Wikidata entry; "
              "<strong>grey</strong> = a new artwork not yet in Wikidata. "
              "Search a name above, or try an example:"),
    "examples": [
        {"mode": "person", "seed": "Giotto", "label": "Giotto's artworks"},
        {"mode": "artwork", "seed": "Madonna", "label": "All the Madonnas"},
        {"mode": "biography", "seed": "Botticelli", "label": "Botticelli's biography"},
    ],
    "initial": {"mode": "person", "seed": "Giotto"},
    "presets": [
        {"mode": "person", "seed": "Giotto", "label": "Giotto"},
        {"mode": "person", "seed": "Michelagnolo", "label": "Michelangelo"},
        {"mode": "person", "seed": "Brunelleschi", "label": "Brunelleschi"},
        {"mode": "person", "seed": "Donatello", "label": "Donatello"},
        {"sep": True},
        {"mode": "artwork", "seed": "Madonna", "label": "Madonna"},
        {"mode": "artwork", "seed": "Sistine", "label": "Sistine"},
        {"mode": "artwork", "seed": "S. Croce", "label": "S. Croce"},
        {"sep": True},
        {"mode": "biography", "seed": "Botticelli", "label": "Bio: Botticelli"},
        {"mode": "biography", "seed": "Giotto", "label": "Bio: Giotto"},
    ],
    "legend": [
        {"color": "#1B6EF3", "label": "Linked to Wikidata",
         "tip": "The AI matched this artwork to an existing Wikidata entry."},
        {"color": "#9CA3AF", "label": "New (not in Wikidata)",
         "tip": "The AI found this artwork, but it has no Wikidata entry yet."},
        {"color": "#7C3AED", "label": "Biography",
         "tip": "One of Vasari's artist biographies."},
        {"color": "#6B7280", "label": "Passage",
         "tip": "A single paragraph of the text."},
    ],
}

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
        for entry in _load_index():
            g = _load_graph(entry["file"])
            for n in g["nodes"]:
                if n["type"] in SUGGEST_TYPES:
                    _suggest_labels.append({"label": n["label"], "type": n["type"]})
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


@router.get("/explore/og", response_class=HTMLResponse)
async def explore_og_page(request: Request):
    return templates.TemplateResponse(request, "explore.html", {"cfg": CFG})


@router.get("/explore/og/suggest")
async def explore_og_suggest(q: str = Query(default="")):
    q = q.strip().lower()
    if len(q) < 2:
        return JSONResponse([])
    labels = _build_suggest_labels()
    results = []
    for item in labels:
        if q in item["label"].lower():
            results.append(item)
        if len(results) >= 12:
            break
    results.sort(key=lambda x: (0 if x["label"].lower().startswith(q) else 1, x["label"]))
    return JSONResponse(results[:12])


@router.get("/explore/og/index")
async def explore_og_index():
    return JSONResponse(_load_index())


@router.get("/explore/og/subgraph")
async def explore_og_subgraph(
    seed: str = Query(default=""),
    mode: str = Query(default="random"),
):
    index = _load_index()
    seed_lower = seed.lower().strip()

    if mode == "random":
        candidates = [e for e in index if e["mode"] == "person"]
        if candidates:
            chosen = random.choice(candidates)
            return JSONResponse(_load_graph(chosen["file"]))
        return JSONResponse({"nodes": [], "edges": []})

    if seed_lower:
        for entry in index:
            if entry["mode"] == mode and seed_lower == entry["label"].lower():
                return JSONResponse(_load_graph(entry["file"]))
        for entry in index:
            if entry["mode"] == mode and seed_lower in entry["label"].lower():
                return JSONResponse(_load_graph(entry["file"]))

        best = None
        best_count = 0
        for entry in index:
            g = _load_graph(entry["file"])
            count = sum(1 for n in g["nodes"]
                        if seed_lower in n["label"].lower()
                        and n["type"] in SUGGEST_TYPES)
            if count > best_count:
                best = g
                best_count = count
        if best:
            return JSONResponse(best)

    return JSONResponse({"nodes": [], "edges": []})
