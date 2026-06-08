import json
import random
from pathlib import Path

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

EXPLORER_DIR = Path("data/kg/explorer")

# Config consumed by the shared explore.html template. Reproduces the
# ground-truth explorer's original hard-coded presets/legend/labels. The
# ontology-guided layer (app/routers/explore_og.py) passes its own CFG.
CFG = {
    "api_base": "/explore",
    "title": "Viewsari · Artwork explorer",
    "chip": "Artwork explorer",
    "placeholder": "Search a person or artwork (e.g. Giotto, S. Croce)",
    "intro": ("Each dot is a person, artwork, or biography from Vasari's "
              "<em>Lives</em>. Lines link people and works that appear together "
              "in the same passage. Search a name above, or try an example:"),
    "examples": [
        {"mode": "person", "seed": "Giotto", "label": "Who appears with Giotto?"},
        {"mode": "artwork", "seed": "S. Croce", "label": "Artworks in S. Croce"},
        {"mode": "biography", "seed": "Botticelli", "label": "Botticelli's biography"},
    ],
    "initial": {"mode": "person", "seed": "Giotto"},
    "presets": [
        {"mode": "person", "seed": "Giotto", "label": "Giotto"},
        {"mode": "person", "seed": "Michelagnolo", "label": "Michelangelo"},
        {"mode": "person", "seed": "Brunelleschi", "label": "Brunelleschi"},
        {"mode": "person", "seed": "Donatello", "label": "Donatello"},
        {"sep": True},
        {"mode": "artwork", "seed": "S. Croce", "label": "S. Croce"},
        {"mode": "artwork", "seed": "Sistine", "label": "Sistine"},
        {"mode": "artwork", "seed": "Madonna", "label": "Madonna"},
        {"sep": True},
        {"mode": "biography", "seed": "Botticelli", "label": "Bio: Botticelli"},
        {"mode": "biography", "seed": "Giotto", "label": "Bio: Giotto"},
    ],
    "legend": [
        {"color": "#BE185D", "label": "Person",
         "tip": "A person named in the text — usually an artist."},
        {"color": "#B45309", "label": "Artwork",
         "tip": "A work of art (painting, sculpture, building) mentioned in the text."},
        {"color": "#0F766E", "label": "Appears together",
         "tip": "Two people named together in the same passage."},
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
    return templates.TemplateResponse(request, "explore.html", {"cfg": CFG})


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
