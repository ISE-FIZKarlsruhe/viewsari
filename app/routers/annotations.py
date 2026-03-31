import json
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _compute_bio_stats(annotations_dir: str) -> list[dict]:
    """Compute per-biography annotation statistics."""
    ann_dir = Path(annotations_dir)
    stats = []

    for vol_dir in sorted(ann_dir.iterdir()):
        if not vol_dir.is_dir():
            continue
        for f in sorted(vol_dir.glob("*_enriched.json")):
            slug = f.stem.replace("_enriched", "")
            with open(f) as fh:
                data = json.load(fh)

            paras = len(data)
            mentions = []
            entities = set()
            for p in data:
                for m in p.get("mentions", []):
                    mentions.append(m)
                    entities.add(m.get("entity_id", ""))

            total = len(mentions)
            tc = Counter(m.get("type", "") for m in mentions)
            wd_count = sum(
                1 for m in mentions
                if (m.get("wikidata_id") or "") and not m.get("ookb")
            )
            ookb_count = sum(1 for m in mentions if m.get("ookb"))

            name = slug.replace("_", " ").replace("-", " ").title()
            stats.append({
                "slug": slug,
                "name": name,
                "volume": vol_dir.name,
                "paras": paras,
                "mentions": total,
                "entities": len(entities),
                "explicit": tc.get("explicit artwork mention", 0),
                "implicit": tc.get("implicit artwork mention", 0),
                "coref": tc.get("coreferent", 0),
                "generic": tc.get("generic mention", 0),
                "wd": wd_count,
                "wd_pct": round(100 * wd_count / total) if total else 0,
                "ookb": ookb_count,
                "ookb_pct": round(100 * ookb_count / total) if total else 0,
            })

    return stats


@router.get("/annotations", response_class=HTMLResponse)
async def annotations(request: Request):
    backend = request.app.state.backend
    ann_dir = backend._annotations_dir
    bio_stats = _compute_bio_stats(str(ann_dir))

    total_bios = len(bio_stats)
    total_paras = sum(b["paras"] for b in bio_stats)
    total_mentions = sum(b["mentions"] for b in bio_stats)
    total_entities = sum(b["entities"] for b in bio_stats)

    return templates.TemplateResponse(
        request,
        "annotations.html",
        {
            "bio_stats": bio_stats,
            "total_bios": total_bios,
            "total_paras": total_paras,
            "total_mentions": total_mentions,
            "total_entities": total_entities,
        },
    )
