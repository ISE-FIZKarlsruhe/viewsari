import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/biography/{slug}", response_class=HTMLResponse)
async def biography_redirect(slug: str, request: Request):
    backend = request.app.state.backend
    resolved = backend.resolve_slug(slug)
    if resolved and resolved != slug:
        return RedirectResponse(url=f"/biography/{resolved}")
    paragraphs = backend.get_paragraphs(slug)
    if not paragraphs:
        available = [b["name"] for b in backend.list_biographies()]
        return templates.TemplateResponse(
            request,
            "404.html",
            {"message": f"Biography '{slug}' not found. The annotated corpus currently covers {len(available)} biographies: {', '.join(available)}."},
            status_code=404,
        )
    first_id = paragraphs[0].get("paragraph_id")
    return RedirectResponse(url=f"/biography/{slug}/{first_id}")


@router.get("/biography/{slug}/{paragraph_id}", response_class=HTMLResponse)
async def biography_paragraph(slug: str, paragraph_id: int, request: Request):
    backend = request.app.state.backend

    resolved = backend.resolve_slug(slug)
    if resolved and resolved != slug:
        return RedirectResponse(url=f"/biography/{resolved}/{paragraph_id}")

    paragraphs = backend.get_paragraphs(slug)
    if not paragraphs:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "message": f"Biography '{slug}' not found."},
            status_code=404,
        )

    paragraph_data = backend.get_paragraph(slug, paragraph_id)
    if paragraph_data is None:
        return templates.TemplateResponse(
            request,
            "404.html",
            {"message": f"Paragraph {paragraph_id} not found in '{slug}'."},
            status_code=404,
        )

    viewer_data = paragraph_data["viewer_data"]
    raw_json = json.dumps(viewer_data, ensure_ascii=False)

    # Build nav list (id + page for each paragraph)
    all_paragraphs = [
        {"paragraph_id": p.get("paragraph_id"), "page": p.get("page", "")}
        for p in paragraphs
    ]

    # Find prev/next
    ids = [p.get("paragraph_id") for p in paragraphs]
    try:
        current_index = ids.index(paragraph_id)
    except ValueError:
        current_index = 0

    prev_id = ids[current_index - 1] if current_index > 0 else None
    next_id = ids[current_index + 1] if current_index < len(ids) - 1 else None

    bio_name = paragraph_data.get("biography", slug)

    return templates.TemplateResponse(
        request,
        "biography.html",
        {
            "raw_json": raw_json,
            "paragraph": paragraph_data,
            "all_paragraphs": all_paragraphs,
            "slug": slug,
            "prev_id": prev_id,
            "next_id": next_id,
            "bio_name": bio_name,
        },
    )