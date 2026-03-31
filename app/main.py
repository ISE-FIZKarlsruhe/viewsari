import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.data.json_backend import JSONBackend
from app.routers import index as index_router
from app.routers import biography as biography_router
from app.routers import ontology as ontology_router
from app.routers import publications as publications_router
from app.routers import annotations as annotations_router
from app.routers import sparql as sparql_router
from app.routers import explore as explore_router
from app.routers import obliquer as obliquer_router
from app.routers import kb as kb_router
from app.routers import about as about_router

load_dotenv()

ANNOTATIONS_DIR = os.getenv("ANNOTATIONS_DIR", "./annotations")
DATA_DIR = os.getenv("DATA_DIR", "./data/kg_foundation")


@asynccontextmanager
async def lifespan(app: FastAPI):
    backend = JSONBackend(
        annotations_dir=ANNOTATIONS_DIR,
        data_dir=DATA_DIR,
    )
    app.state.backend = backend
    yield


app = FastAPI(title="Viewsari", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/facsimile", StaticFiles(directory="data/facsimile_pages"), name="facsimile")
app.mount(
    "/ontology/docs",
    StaticFiles(directory="data/ontology/viewsari", html=True),
    name="ontology-docs",
)

app.include_router(index_router.router)
app.include_router(biography_router.router)
app.include_router(ontology_router.router)
app.include_router(publications_router.router)
app.include_router(annotations_router.router)
app.include_router(sparql_router.router)
app.include_router(explore_router.router)
app.include_router(obliquer_router.router)
app.include_router(kb_router.router)
app.include_router(about_router.router)