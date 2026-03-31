from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ROOT = Path(__file__).resolve().parent.parent.parent
FAC_DIR = ROOT / "data" / "facsimile_pages"


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
        {"biographies": biographies},
    )
