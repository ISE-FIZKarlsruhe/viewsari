from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/ontology", response_class=HTMLResponse)
async def ontology(request: Request):
    return templates.TemplateResponse(
        request,
        "ontology.html",
        {},
    )