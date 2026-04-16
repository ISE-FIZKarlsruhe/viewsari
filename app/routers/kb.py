"""Knowledge Base browser — consolidated entities from data/kg/viewsari_kg.ttl.

Data is prebuilt offline by scripts/build_kb.py into data/kb/kb.json.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

KB_PATH = Path("data/kb/kb.json")
_kb_data: dict | None = None


def _load_kb() -> dict:
    global _kb_data
    if _kb_data is not None:
        return _kb_data
    if not KB_PATH.exists():
        raise FileNotFoundError(
            f"{KB_PATH} is missing. Run `python scripts/build_kb.py` to generate it."
        )
    _kb_data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    return _kb_data


def _lookup(kb: dict, entity_id: str) -> dict | None:
    for bucket in ("persons", "artworks", "cooccurrences"):
        ent = kb[bucket].get(entity_id)
        if ent:
            return ent
    return None


@router.get("/kb", response_class=HTMLResponse)
async def kb_index(request: Request):
    return templates.TemplateResponse(request, "kb.html", {"kb": _load_kb()})


@router.get("/kb/entity/{entity_id}", response_class=HTMLResponse)
async def kb_entity(entity_id: str, request: Request):
    kb = _load_kb()
    ent = _lookup(kb, entity_id)
    if not ent:
        return templates.TemplateResponse(
            request, "404.html",
            {"message": f"Entity '{entity_id}' not found in the knowledge base."},
            status_code=404,
        )
    return templates.TemplateResponse(request, "kb_entity.html", {"ent": ent})


@router.get("/kb/artworks.json", response_class=JSONResponse)
async def kb_artworks(q: str = "", offset: int = 0, limit: int = 60, source: str = "all"):
    kb = _load_kb()
    items = list(kb["artworks"].values())
    if source in ("gt", "obliquer", "other"):
        items = [e for e in items if e.get("source") == source]
    if q:
        ql = q.lower()
        items = [e for e in items if ql in e["label"].lower() or ql in e["entity_id"].lower()]
    items.sort(key=lambda e: (e.get("vol") or "", e.get("para") or "", e["label"].lower()))
    total = len(items)
    page = items[offset: offset + limit]
    return JSONResponse({"total": total, "offset": offset, "limit": limit, "items": page})


@router.get("/kb/obq_explicit.json", response_class=JSONResponse)
async def kb_obq_explicit(q: str = "", offset: int = 0, limit: int = 60, strategy: str = "all"):
    kb = _load_kb()
    items = kb.get("obq_explicit", [])
    if strategy != "all":
        items = [e for e in items if e.get("strategy") == strategy]
    if q:
        ql = q.lower()
        items = [e for e in items if ql in e["surface"].lower() or ql in e.get("mention_id", "").lower()]
    total = len(items)
    return JSONResponse({"total": total, "offset": offset, "limit": limit, "items": items[offset:offset+limit]})


@router.get("/kb/obq_implicit.json", response_class=JSONResponse)
async def kb_obq_implicit(q: str = "", offset: int = 0, limit: int = 60, strategy: str = "all"):
    kb = _load_kb()
    items = kb.get("obq_implicit", [])
    if strategy != "all":
        items = [e for e in items if e.get("strategy") == strategy]
    if q:
        ql = q.lower()
        items = [e for e in items if ql in e["surface"].lower() or ql in e.get("mention_id", "").lower()]
    total = len(items)
    return JSONResponse({"total": total, "offset": offset, "limit": limit, "items": items[offset:offset+limit]})


@router.get("/kb/entity-data/{entity_id}", response_class=JSONResponse)
async def kb_entity_data(entity_id: str):
    kb = _load_kb()
    ent = _lookup(kb, entity_id)
    if not ent:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(ent)


@router.get("/kb/1.0")
async def kb_entity_fragment(request: Request):
    return templates.TemplateResponse(request, "kb_entity_fragment.html", {"kb": _load_kb()})
