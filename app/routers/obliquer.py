from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/obliquer", response_class=HTMLResponse)
async def obliquer_about(request: Request):
    return templates.TemplateResponse(request, "obliquer_about.html", {})


@router.get("/obliquer/demo", response_class=HTMLResponse)
async def obliquer_demo(request: Request):
    return templates.TemplateResponse(request, "obliquer.html", {})
