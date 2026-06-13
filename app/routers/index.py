import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ROOT = Path(__file__).resolve().parent.parent.parent
FAC_DIR = ROOT / "data" / "facsimile_pages"
KB_PATH = ROOT / "data" / "kb" / "kb.json"

# Authoritative knowledge-graph totals — mirror the latest KG evaluation report
# under src/evaluation/kg_reports/ and docs/population_stats.md. `triples` is the
# base graph (data/kg/viewsari_kg.ttl); the corpus totals (biographies,
# paragraphs, volumes) are the full populated KG, not just the annotated GT
# subset. Update these when the KG is re-populated; regenerate the source with:
# python3 src/kg_population/population_stats.py
KG_STATS = {
    "triples": 2_559_459,
    "mentions": 112_113,
    "artworks": 15_804,
    "linked_qids": 3_070,
    "ookb": 12_529,
    "biographies": 165,
    "paragraphs": 3_479,
    "volumes": 10,
}


def _kb_counts() -> dict:
    if not KB_PATH.exists():
        return {}
    return json.loads(KB_PATH.read_text(encoding="utf-8")).get("counts", {})


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    backend = request.app.state.backend
    biographies = backend.list_biographies()

    # Attach a preview facsimile page URL to each biography
    for bio in biographies:
        bio["preview"] = None
        slug = bio["slug"]
        vol = bio["volume"]
        if not vol:
            continue
        paragraphs = backend.get_paragraphs(slug)
        if not paragraphs:
            continue
        # Use the first page of the first paragraph as preview
        page_str = paragraphs[0].get("page", "") or ""
        first_page = page_str.split("-")[0].strip()
        if first_page.isdigit() and (FAC_DIR / vol / f"{first_page}.png").exists():
            bio["preview"] = f"/facsimile/{vol}/{first_page}.png"

    return templates.TemplateResponse(
        request,
        "index.html",
        {"biographies": biographies, "kb_counts": _kb_counts(), "kg_stats": KG_STATS},
    )
