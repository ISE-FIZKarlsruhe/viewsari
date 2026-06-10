"""Knowledge Base browser — consolidated entities from data/kg/viewsari_kg.ttl.

Data is prebuilt offline by src/kg_population/build_kb.py into data/kb/kb.json.
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
            f"{KB_PATH} is missing. Run `python src/kg_population/build_kb.py` to generate it."
        )
    _kb_data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    return _kb_data


def _lookup(kb: dict, entity_id: str) -> dict | None:
    for bucket in ("persons", "artworks", "cooccurrences"):
        ent = kb[bucket].get(entity_id)
        if ent:
            return ent
    return None


# ── Unified facet-search index ──────────────────────────────────────────────
# A single flat list across all entity buckets, so /kb/search.json can filter
# people, artworks, mentions and co-occurrences together with shared facets.
_flat_index: list[dict] | None = None

TYPE_ORDER = {"person": 0, "artwork": 1, "explicit": 2, "implicit": 3, "cooccurrence": 4}


def _build_flat_index(kb: dict) -> list[dict]:
    global _flat_index
    if _flat_index is not None:
        return _flat_index

    items: list[dict] = []

    for eid, e in kb["persons"].items():
        alt = e.get("alt_labels", []) or []
        items.append({
            "type": "person", "id": eid, "label": e["label"],
            "source": "", "vol": None, "para": None,
            "wikidata": e.get("wikidata") or "", "ookb": bool(e.get("ookb")),
            "strategy": "", "alt": alt, "involves": None,
            "_search": (e["label"] + " " + " ".join(alt) + " " + eid).lower(),
        })

    for eid, e in kb["artworks"].items():
        items.append({
            "type": "artwork", "id": eid, "label": e["label"],
            "source": e.get("source") or "", "vol": e.get("vol"), "para": e.get("para"),
            "wikidata": e.get("wikidata") or "", "ookb": bool(e.get("ookb")),
            "strategy": "", "alt": None, "involves": None,
            "_search": (e["label"] + " " + eid).lower(),
        })

    for eid, e in kb["cooccurrences"].items():
        items.append({
            "type": "cooccurrence", "id": eid, "label": e["label"],
            "source": "other", "vol": None, "para": None,
            "wikidata": "", "ookb": False,
            "strategy": "", "alt": None, "involves": e.get("involves", []) or [],
            "_search": e["label"].lower(),
        })

    for kind, key in (("explicit", "obq_explicit"), ("implicit", "obq_implicit")):
        for e in kb.get(key, []):
            mid = e.get("mention_id", "")
            items.append({
                "type": kind, "id": mid, "label": e["surface"],
                "source": "obliquer", "vol": e.get("vol"), "para": e.get("para"),
                "wikidata": "", "ookb": False,
                "strategy": e.get("strategy") or "", "alt": None, "involves": None,
                "_search": (e["surface"] + " " + mid).lower(),
            })

    _flat_index = items
    return items


def _passes(e: dict, q: str, types: set[str], source: str, wikidata: str,
            strategy: str, skip: str | None = None) -> bool:
    """True if entity e survives every active filter except the one named in `skip`."""
    if skip != "q" and q and q not in e["_search"]:
        return False
    if skip != "type" and types and e["type"] not in types:
        return False
    if skip != "source" and source != "all" and e["source"] != source:
        return False
    if skip != "wikidata" and wikidata != "all":
        has = bool(e["wikidata"])
        if (wikidata == "yes") != has:
            return False
    if skip != "strategy" and strategy != "all" and e["strategy"] != strategy:
        return False
    return True


def _facet_counts(items, q, types, source, wikidata, strategy, dim, key):
    """Count values of `key` over items passing all filters except dimension `dim`."""
    counts: dict[str, int] = {}
    for e in items:
        if _passes(e, q, types, source, wikidata, strategy, skip=dim):
            v = key(e)
            if v:
                counts[v] = counts.get(v, 0) + 1
    return counts


@router.get("/kb", response_class=HTMLResponse)
async def kb_index(request: Request):
    return templates.TemplateResponse(request, "kb.html", {"kb": _load_kb()})


@router.get("/kb/search.json", response_class=JSONResponse)
async def kb_search(q: str = "", types: str = "", source: str = "all",
                    wikidata: str = "all", strategy: str = "all",
                    offset: int = 0, limit: int = 60):
    items = _build_flat_index(_load_kb())
    ql = q.strip().lower()
    typeset = {t for t in types.split(",") if t}

    matched = [e for e in items
               if _passes(e, ql, typeset, source, wikidata, strategy)]
    matched.sort(key=lambda e: (TYPE_ORDER.get(e["type"], 9), e["label"].lower()))
    total = len(matched)
    page = matched[offset: offset + limit]

    # Faceted counts: each dimension counted over items passing the *other* filters.
    facets = {
        "type": _facet_counts(items, ql, typeset, source, wikidata, strategy,
                              "type", lambda e: e["type"]),
        "source": _facet_counts(items, ql, typeset, source, wikidata, strategy,
                                "source", lambda e: e["source"]),
        "wikidata": _facet_counts(items, ql, typeset, source, wikidata, strategy,
                                  "wikidata", lambda e: "yes" if e["wikidata"] else "no"),
        "strategy": _facet_counts(items, ql, typeset, source, wikidata, strategy,
                                  "strategy", lambda e: e["strategy"]),
    }

    # Strip the internal search blob before sending.
    clean = [{k: v for k, v in e.items() if k != "_search"} for e in page]
    return JSONResponse({
        "total": total, "offset": offset, "limit": limit,
        "items": clean, "facets": facets,
    })


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
