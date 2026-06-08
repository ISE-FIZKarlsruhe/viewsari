import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

CQ_CATALOG = Path("src/evaluation/cq_catalog.json")

# Personas the competency questions were elicited from (see CQ_CATALOG.md).
PERSONAS = {
    "Elena Rossi": "Art historian / researcher",
    "Nazeera Marfi": "Professor of digital art history",
    "Aaron Warner": "Computer scientist / knowledge engineer",
    "John Saffron": "Art history student",
}

PHASE_TITLES = {
    "I": "Phase I — Ontology design",
    "II": "Phase II — Extended coverage",
}

_cq_cache: dict | None = None


def _load_cqs() -> dict:
    """Load and group the competency-question catalog by phase → cluster."""
    global _cq_cache
    if _cq_cache is None:
        qs = json.loads(CQ_CATALOG.read_text(encoding="utf-8"))["questions"]
        phases = []
        for pid in ("I", "II"):
            order: list[str] = []
            bucket: dict[str, list] = {}
            for q in qs:
                if q["phase"] != pid:
                    continue
                c = q["cluster"]
                if c not in bucket:
                    bucket[c] = []
                    order.append(c)
                bucket[c].append(q)
            phases.append({
                "id": pid,
                "title": PHASE_TITLES[pid],
                "count": sum(len(bucket[c]) for c in order),
                "clusters": [{"name": c, "questions": bucket[c]} for c in order],
            })
        _cq_cache = {
            "total": len(qs),
            "n_sparql": sum(1 for q in qs if q.get("query")),
            "phases": phases,
            "personas": PERSONAS,
        }
    return _cq_cache


@router.get("/ontology", response_class=HTMLResponse)
async def ontology(request: Request):
    return templates.TemplateResponse(
        request,
        "ontology.html",
        {},
    )


@router.get("/ontology/cqs", response_class=HTMLResponse)
async def ontology_cqs(request: Request):
    return templates.TemplateResponse(request, "cqs.html", dict(_load_cqs()))
