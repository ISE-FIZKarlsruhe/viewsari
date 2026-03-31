from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/publications", response_class=HTMLResponse)
async def publications(request: Request):
    return templates.TemplateResponse(
        request,
        "publications.html",
        {},
    )
