"""Knowledge Base browser — entity statistics and OOKB entity pages."""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_kb_data: dict | None = None


def _extract_qid(wd):
    if not wd:
        return ""
    if isinstance(wd, list):
        wd = wd[0] if wd else ""
    if not wd:
        return ""
    qid = str(wd).rstrip("/").split("/")[-1]
    return qid if qid.startswith("Q") else ""


def _load_kb():
    global _kb_data
    if _kb_data is not None:
        return _kb_data

    gt_dir = Path(os.getenv("ANNOTATIONS_DIR", "./obliquer/data/viewsari/ground_truth"))

    entities = {}       # entity_id -> info dict
    mention_counts = Counter()  # type -> count
    total_mentions = 0
    bio_stats = {}      # slug -> {mentions, entities, ookb, wd}

    for vol_dir in sorted(gt_dir.iterdir()):
        if not vol_dir.is_dir() or not vol_dir.name.isdigit():
            continue
        vol = vol_dir.name
        for fpath in sorted(vol_dir.glob("*_enriched.json")):
            slug = fpath.stem.removesuffix("_enriched")
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)

            bio_mentions = 0
            bio_entities = set()
            bio_ookb = set()
            bio_wd = set()

            for p in data:
                for m in p.get("mentions", []):
                    total_mentions += 1
                    bio_mentions += 1
                    mtype = m.get("type", "")
                    mention_counts[mtype] += 1

                    # Skip coreferents — they share entity_ids with
                    # antecedents and would pollute entity-level stats
                    if mtype == "coreferent":
                        continue

                    eid = m.get("entity_id", "")
                    if not eid:
                        continue
                    bio_entities.add(eid)

                    is_ookb = m.get("ookb", False)
                    wd = _extract_qid(m.get("wikidata_id"))
                    label = m.get("label") or ""
                    surface = m.get("surface_form", "")
                    ookb_uri = m.get("ookb_uri") or ""
                    pid = p.get("paragraph_id", "")

                    if eid not in entities:
                        entities[eid] = {
                            "entity_id": eid,
                            "label": label,
                            "ookb": is_ookb,
                            "wikidata": wd,
                            "ookb_uri": ookb_uri,
                            "surfaces": [],
                            "mention_count": 0,
                            "bios": set(),
                            "types": set(),
                            "occurrences": [],  # (slug, pid, surface, type)
                        }
                    ent = entities[eid]
                    ent["mention_count"] += 1
                    ent["bios"].add(slug)
                    ent["types"].add(mtype)
                    if surface and surface not in ent["surfaces"]:
                        ent["surfaces"].append(surface)
                    if label:
                        ent["label"] = label
                    if ookb_uri:
                        ent["ookb_uri"] = ookb_uri
                    if is_ookb:
                        ent["ookb"] = True
                    if wd:
                        ent["wikidata"] = wd
                    ent["occurrences"].append((slug, str(pid), surface, mtype))

                    if is_ookb:
                        bio_ookb.add(eid)
                    if wd:
                        bio_wd.add(eid)

            bio_stats[slug] = {
                "slug": slug,
                "mentions": bio_mentions,
                "entities": len(bio_entities),
                "ookb": len(bio_ookb),
                "wd": len(bio_wd),
            }

    # Convert sets to lists for JSON
    for ent in entities.values():
        ent["bios"] = sorted(ent["bios"])
        ent["types"] = sorted(ent["types"])

    ookb_entities = {k: v for k, v in entities.items() if v["ookb"]}
    wd_entities = {k: v for k, v in entities.items() if v["wikidata"]}

    _kb_data = {
        "total_mentions": total_mentions,
        "total_entities": len(entities),
        "mention_types": dict(mention_counts),
        "ookb_count": len(ookb_entities),
        "wd_count": len(wd_entities),
        "entities": entities,
        "ookb_entities": ookb_entities,
        "wd_entities": wd_entities,
        "bio_stats": bio_stats,
    }
    return _kb_data


@router.get("/kb", response_class=HTMLResponse)
async def kb_index(request: Request):
    kb = _load_kb()
    return templates.TemplateResponse(request, "kb.html", {"kb": kb})


@router.get("/kb/entity/{entity_id}", response_class=HTMLResponse)
async def kb_entity(entity_id: str, request: Request):
    kb = _load_kb()
    ent = kb["entities"].get(entity_id)
    if not ent:
        return templates.TemplateResponse(
            request, "404.html",
            {"message": f"Entity '{entity_id}' not found in the knowledge base."},
            status_code=404,
        )
    return templates.TemplateResponse(request, "kb_entity.html", {"ent": ent})


@router.get("/kb/1.0")
async def kb_ookb_redirect(request: Request):
    """Handle /kb/1.0#fragment URIs — redirect to the entity page."""
    return templates.TemplateResponse(request, "kb.html", {"kb": _load_kb()})
