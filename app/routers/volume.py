"""Volume sub-pages — one page per volume with biography listing."""

import csv
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_vol_cache: dict | None = None


def _load_volumes(data_dir: str) -> dict:
    """Load volume and biography metadata from CSVs."""
    global _vol_cache
    if _vol_cache is not None:
        return _vol_cache

    data = Path(data_dir)
    volumes = {}

    # Parse volume metadata
    vol_csv = data / "viewsari_volumes.csv"
    if vol_csv.exists():
        with open(vol_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("level") != "expression":
                    continue
                iid = row["instance_id"]
                # Extract volume number from e.g. "viewsari:the_lives_1568_volume-9"
                num = iid.rsplit("-", 1)[-1]
                label = row.get("rdfs:label", "")
                # Slug matches the instance_id without the prefix
                slug = iid.replace("viewsari:", "")
                volumes[num] = {
                    "number": num,
                    "slug": slug,
                    "label": label,
                    "gutenberg_url": "",
                    "biographies": [],
                }

    # Parse Gutenberg URLs from manifestation rows
    with open(vol_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("level") != "manifestation":
                continue
            see_also = row.get("rdfs:seeAlso", "")
            # Match to volume via the label, e.g. "... Volume 3"
            label = row.get("rdfs:label", "")
            for vol in volumes.values():
                if f"Volume {vol['number']}" in label:
                    vol["gutenberg_url"] = see_also
                    break

    # Parse biographies per volume
    bio_csv = data / "viewsari_biographies.csv"
    if bio_csv.exists():
        with open(bio_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("level") != "expression":
                    continue
                vol_num = row.get("vol", "")
                if vol_num not in volumes:
                    continue
                # Extract slug from instance_id
                iid = row["instance_id"].replace("viewsari:", "")
                # e.g. "the_lives_1568_volume-1_cimabue-bio" -> "cimabue"
                bio_part = iid.split(f"volume-{vol_num}_", 1)[-1]
                bio_slug = bio_part.removesuffix("-bio")
                bio_label = row.get("rdfs:label", "")
                start_page = row.get("start_page", "")
                volumes[vol_num]["biographies"].append({
                    "slug": bio_slug,
                    "label": bio_label,
                    "start_page": start_page,
                })

    # Sort biographies by start page
    for vol in volumes.values():
        vol["biographies"].sort(
            key=lambda b: int(b["start_page"]) if b["start_page"].isdigit() else 0
        )

    _vol_cache = volumes
    return _vol_cache


def try_volume(volume_slug: str, data_dir: str) -> dict | None:
    """Return volume dict if slug matches, else None."""
    volumes = _load_volumes(data_dir)
    vol_num = volume_slug.rsplit("-", 1)[-1]
    vol = volumes.get(vol_num)
    if vol and vol["slug"] == volume_slug:
        return vol
    return None


