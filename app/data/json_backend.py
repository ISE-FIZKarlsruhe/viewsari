import csv
import json
import os
import random
from pathlib import Path

from app.data.base import DataBackend

# CSS class mapping for mention types
TYPE_CLASS = {
    "explicit artwork mention": "explicit",
    "implicit artwork mention": "implicit",
    "coreferent": "coref",
    "generic mention": "generic",
}

# Priority order for overlap resolution (lower number = higher priority)
TYPE_PRIORITY = {
    "explicit artwork mention": 0,
    "implicit artwork mention": 1,
    "coreferent": 2,
    "generic mention": 3,
}


def _extract_qid(wikidata_id) -> str | None:
    """Extract the QID from a full Wikidata URL, e.g. 'https://www.wikidata.org/wiki/Q573881' -> 'Q573881'."""
    if not wikidata_id:
        return None
    if isinstance(wikidata_id, list):
        wikidata_id = wikidata_id[0] if wikidata_id else None
    if not wikidata_id:
        return None
    qid = str(wikidata_id).rstrip("/").split("/")[-1]
    if qid.startswith("Q"):
        return qid
    return None


def build_biblio(para_dict: dict, meta: dict) -> dict:
    """Build bibliographic chain dict for the JS BIBLIO variable."""
    para_csv = meta.get("para_csv") or {}
    bio_csv  = meta.get("bio_csv")  or {}
    vol_csv  = meta.get("vol_csv")  or {}

    para_uri  = para_csv.get("para_uri") or f"viewsari:paragraph-{para_dict.get('paragraph_id', '')}"
    para_label = f"§{para_dict.get('paragraph_id', '')} · p. {para_dict.get('page', '')}"
    page_uri  = para_csv.get("page_uri") or ""
    page_label = f"p. {(para_dict.get('page') or '').split('-')[0]}"

    # Prefer direct bio record from slug-based lookup over para_csv chain
    direct_bio = meta.get("direct_bio")
    if direct_bio:
        bio_record = direct_bio
        bio_uri = direct_bio.get("bio_uri", "")
    else:
        bio_uri = para_csv.get("bio_uri") or ""
        bio_record = bio_csv.get(bio_uri, {}) if bio_uri else {}

    bio_label  = bio_record.get("bio_label", "")
    vol_uri    = bio_record.get("vol_uri", "")

    vol_record = vol_csv.get(vol_uri, {}) if vol_uri else {}
    vol_label  = vol_record.get("vol_label", "") or f"Volume {meta.get('vol', '')}"

    edition_uri   = vol_record.get("edition_uri", "") or "viewsari:#0001029"
    edition_label = "Le Vite (1568 ed.)"

    return {
        "para_uri":     para_uri,
        "para_label":   para_label,
        "page_uri":     page_uri,
        "page_label":   page_label,
        "bio_uri":      bio_uri,
        "bio_label":    bio_label,
        "vol_uri":      vol_uri,
        "vol_label":    vol_label,
        "edition_uri":  edition_uri,
        "edition_label": edition_label,
    }


_SPEECHES_EXPLICIT = [
    "Ah, {surface}! I recall this work most vividly. I wrote of it with such care that my quill nearly caught fire from the passion of description.",
    "Now here is {surface} \u2014 a work I deemed worthy of mention by name, for only a fool buries greatness in vague allusion.",
    "I speak plainly of {surface}, as any honest biographer must. Let no one say Vasari was afraid to call a masterpiece by its name!",
    "Behold, {surface}! I saw it with mine own eyes and thought: this must be recorded, lest future generations forget what genius looks like.",
    "{surface} \u2014 a work so fine that I interrupted my supper to write of it. My soup grew cold, but Art is a jealous mistress.",
    "When I set down {surface} in my pages, I confess I lingered over the description longer than was strictly necessary. Can you blame me?",
    "I named {surface} directly, for I am no poet who hides meaning behind metaphor. I am a painter who writes \u2014 and painters deal in what is seen.",
    "They asked me, 'Giorgio, must you mention every last painting?' And I said, 'Yes, especially {surface}, for posterity demands it.'",
    "Of {surface}, I wrote with the confidence of one who has seen ten thousand works and knows which deserve to be remembered.",
    "{surface}! This one I measured with my eye and judged with my heart. Both agreed: it belonged in The Lives.",
]

_SPEECHES_IMPLICIT = [
    "I spoke of {surface} without naming the work directly \u2014 sometimes the context speaks louder than a title, and a good reader catches what a lazy one misses.",
    "Here I alluded to {surface} rather than stating it outright. A writer must trust his audience occasionally, even if it pains him.",
    "Notice how I wove {surface} into the narrative without brandishing it like a signpost. Subtlety, dear reader, is also an art.",
    "{surface} \u2014 I did not name it explicitly, for the educated reader of my time would have known at once. I flatter you by assuming the same.",
    "Some works need no introduction. {surface} was so well known in my day that naming it would have been like pointing at the sun.",
    "I mentioned {surface} in passing, as one does with things so obvious they need no elaboration. My editor disagreed, but I am Vasari.",
    "Ah, {surface}! I wrapped this reference in context rather than laying it bare. Think of it as a small puzzle I left for you.",
    "The implicit mention of {surface} was deliberate. Not everything must be spelled out \u2014 where would the pleasure of reading be?",
    "I trust you caught my reference to {surface}. If not, do not despair \u2014 you have found it now, five centuries later. Better late than never!",
    "Here the work reveals itself through description rather than title. {surface} \u2014 those who know, know. And now, so do you.",
]


def _build_speeches(mentions_list: list[dict]) -> dict[str, str]:
    """Generate a Vasari-style speech for each explicit or implicit mention."""
    speeches = {}
    rng = random.Random(42)  # deterministic per server start
    for m in mentions_list:
        mid = m.get("mention_id", "")
        mtype = m.get("type", "")
        surface = m.get("surface_form", "")
        if not surface or mtype in ("coreferent", "generic mention"):
            continue
        if "explicit" in mtype:
            pool = _SPEECHES_EXPLICIT
        elif "implicit" in mtype:
            pool = _SPEECHES_IMPLICIT
        else:
            continue
        # Pick deterministically based on mention_id
        idx = rng.randint(0, len(pool) - 1)
        speeches[mid] = pool[idx].format(surface=surface)
    return speeches


def _repair_offsets(text: str, mentions: list[dict]) -> list[dict]:
    """Re-align mention offsets when surface_form doesn't match text at the recorded position."""
    repaired = []
    for m in mentions:
        s = m.get("start_offset", 0)
        e = m.get("end_offset", 0)
        surface = m.get("surface_form", "")
        if not surface:
            repaired.append(m)
            continue
        # Check if offset is already correct
        if text[s:e] == surface:
            repaired.append(m)
            continue
        # Try to find the surface form near the recorded offset first, then anywhere
        search_start = max(0, s - 200)
        pos = text.find(surface, search_start)
        if pos == -1:
            pos = text.find(surface)
        if pos >= 0:
            fixed = dict(m)
            fixed["start_offset"] = pos
            fixed["end_offset"] = pos + len(surface)
            repaired.append(fixed)
        else:
            # Surface form not found at all — keep original (will be skipped by overlap logic)
            repaired.append(m)
    return repaired


def _match_surface_in_ocr(surface: str, words: list[dict]) -> dict | None:
    """Find a surface form in OCR words and return bounding box, or None."""
    surface_tokens = surface.split()
    n = len(surface_tokens)
    if n == 0:
        return None

    for i in range(len(words) - n + 1):
        # Try exact match (case-insensitive, stripping punctuation from OCR)
        match = True
        for j, st in enumerate(surface_tokens):
            ocr_clean = words[i + j]["t"].strip(".,;:!?\"'()[]—-–")
            st_clean = st.strip(".,;:!?\"'()[]—-–")
            if ocr_clean.lower() != st_clean.lower():
                match = False
                break
        if match:
            x0 = min(words[i + j]["x"] for j in range(n))
            y0 = min(words[i + j]["y"] for j in range(n))
            x1 = max(words[i + j]["x"] + words[i + j]["w"] for j in range(n))
            y1 = max(words[i + j]["y"] + words[i + j]["h"] for j in range(n))
            return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}

    # Fallback: try substring containment for multi-word surface forms
    if n >= 2:
        for i in range(len(words) - n + 1):
            match = True
            for j, st in enumerate(surface_tokens):
                ocr_low = words[i + j]["t"].lower()
                st_low = st.strip(".,;:!?\"'()[]—-–").lower()
                if st_low not in ocr_low and ocr_low not in st_low:
                    match = False
                    break
            if match:
                x0 = min(words[i + j]["x"] for j in range(n))
                y0 = min(words[i + j]["y"] for j in range(n))
                x1 = max(words[i + j]["x"] + words[i + j]["w"] for j in range(n))
                y1 = max(words[i + j]["y"] + words[i + j]["h"] for j in range(n))
                return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}

    return None


def _build_ocr_highlights(mentions_list: list[dict], pages: list[int],
                          ocr_dir: Path, vol: str) -> dict:
    """Match annotation mentions against OCR data and return highlight rects per page.

    Returns: { "<page_num>": { "img_w": int, "img_h": int, "rects": [ {mid, x, y, w, h, type}, ... ] } }
    """
    result = {}
    # Load OCR data for each page
    page_ocr = {}
    for p in pages:
        ocr_path = ocr_dir / vol / f"{p}.json"
        if ocr_path.exists():
            with open(ocr_path, "r", encoding="utf-8") as f:
                page_ocr[p] = json.load(f)

    if not page_ocr:
        return result

    for p, ocr in page_ocr.items():
        words = ocr.get("words", [])
        if not words:
            continue
        rects = []
        for m in mentions_list:
            surface = m.get("surface_form", "")
            if not surface:
                continue
            bbox = _match_surface_in_ocr(surface, words)
            if bbox:
                css = TYPE_CLASS.get(m.get("type", ""), "generic")
                rects.append({
                    "mid": m.get("mention_id", ""),
                    "x": bbox["x"],
                    "y": bbox["y"],
                    "w": bbox["w"],
                    "h": bbox["h"],
                    "type": css,
                })
        if rects:
            result[str(p)] = {
                "img_w": ocr.get("width", 0),
                "img_h": ocr.get("height", 0),
                "rects": rects,
            }

    return result


def build_viewer_data(para_dict: dict, meta: dict | None = None) -> dict:
    """Build the viewer_data dict that the JS expects."""
    text = para_dict.get("text", "")
    mentions_list = _repair_offsets(text, para_dict.get("mentions", []))

    # Sort mentions by start_offset, then by length descending (longer first for tie-breaking)
    sorted_mentions = sorted(
        mentions_list,
        key=lambda m: (m.get("start_offset", 0), -(m.get("end_offset", 0) - m.get("start_offset", 0))),
    )

    # Select non-overlapping mentions with priority
    selected: list[dict] = []
    for m in sorted_mentions:
        s = m.get("start_offset", 0)
        e = m.get("end_offset", 0)
        m_priority = TYPE_PRIORITY.get(m.get("type", ""), 99)

        # Check for overlap with already-selected mentions
        overlaps = False
        for sel in selected:
            ss = sel.get("start_offset", 0)
            se = sel.get("end_offset", 0)
            # Check if there's any overlap
            if s < se and e > ss:
                sel_priority = TYPE_PRIORITY.get(sel.get("type", ""), 99)
                # If this mention is completely inside a higher-or-equal-priority selected one, skip it
                if s >= ss and e <= se and m_priority >= sel_priority:
                    overlaps = True
                    break
                # If a selected mention is completely inside this one and this has higher priority,
                # we'll replace it (handled below)
        if not overlaps:
            selected.append(m)

    # Build segment list
    segs = []
    cursor = 0
    # Sort final selected by start offset for traversal
    selected_sorted = sorted(selected, key=lambda m: m.get("start_offset", 0))

    for m in selected_sorted:
        s = m.get("start_offset", 0)
        e = m.get("end_offset", 0)
        mid = m.get("mention_id", "")
        mtype = m.get("type", "")
        css = TYPE_CLASS.get(mtype, "generic")
        ookb = bool(m.get("ookb", False))

        # Plain text before this mention
        if cursor < s:
            segs.append({"t": text[cursor:s], "y": None, "id": None, "o": False})

        # Annotated span
        segs.append({"t": text[s:e], "y": css, "id": mid, "o": ookb})
        cursor = e

    # Trailing plain text
    if cursor < len(text):
        segs.append({"t": text[cursor:], "y": None, "id": None, "o": False})

    # Build mentions dict
    mentions_dict = {}
    for m in mentions_list:
        mid = m.get("mention_id", "")
        mentions_dict[mid] = {
            "surface": m.get("surface_form", ""),
            "type": m.get("type", ""),
            "start": m.get("start_offset", 0),
            "end": m.get("end_offset", 0),
            "entity_id": m.get("entity_id", ""),
            "ookb": bool(m.get("ookb", False)),
            "ookb_uri": m.get("ookb_uri", ""),
            "refers_to": m.get("refers_to", ""),
            "label": m.get("label", ""),
            "wga_id": m.get("wga_id", ""),
            "wikidata_id": (m.get("wikidata_id") or [""])[0] if isinstance(m.get("wikidata_id"), list) else (m.get("wikidata_id") or ""),
        }

    # Build qids dict
    qids_dict = {}
    for m in mentions_list:
        mid = m.get("mention_id", "")
        qid = _extract_qid(m.get("wikidata_id"))
        if qid:
            qids_dict[mid] = qid

    # Derive pages / all_pages / biblio from meta if available
    if meta is not None:
        facsimile_dir = meta.get("facsimile_dir")
        vol           = meta.get("vol", "")

        # Pages for current paragraph
        raw_page = para_dict.get("page", "") or ""
        try:
            current_pages = [int(p) for p in raw_page.split("-") if p.strip().isdigit()]
        except Exception:
            current_pages = []

        if facsimile_dir and vol:
            pages     = [p for p in current_pages if (facsimile_dir / vol / f"{p}.png").exists()]
            all_pages = [p for p in meta.get("all_pages", []) if (facsimile_dir / vol / f"{p}.png").exists()]
        else:
            pages     = []
            all_pages = []

        biblio = build_biblio(para_dict, meta)
        page_map = meta.get("page_map", {})

        # OCR-based annotation highlights on facsimile
        ocr_dir = meta.get("ocr_dir")
        if ocr_dir and vol and pages:
            ocr_highlights = _build_ocr_highlights(mentions_list, pages, ocr_dir, vol)
        else:
            ocr_highlights = {}
    else:
        pages     = []
        all_pages = []
        vol       = ""
        biblio    = {}
        page_map  = {}
        ocr_highlights = {}

    return {
        "segs": segs,
        "mentions": mentions_dict,
        "qids": qids_dict,
        "wd": {},
        "speeches": _build_speeches(mentions_list),
        "para": {
            "paragraph_id": para_dict.get("paragraph_id"),
            "page": para_dict.get("page", ""),
            "biography": para_dict.get("biography", ""),
        },
        "vasari": "/static/vasari.png",
        "fac": "",
        "pages":     pages,
        "all_pages": all_pages,
        "vol":       vol,
        "biblio":    biblio,
        "page_map":  {str(k): v for k, v in page_map.items()},
        "ocr_hl":    ocr_highlights,
    }


class JSONBackend(DataBackend):

    def __init__(self, annotations_dir: str, data_dir: str):
        self._annotations_dir = Path(annotations_dir)
        self._data_dir = Path(data_dir)

        # Root of the project (two levels up from this file: app/data/ -> app/ -> project root)
        ROOT = Path(__file__).resolve().parent.parent.parent
        self._facsimile_dir: Path = ROOT / "data" / "facsimile_pages"
        self._ocr_dir: Path = ROOT / "data" / "ocr"

        # Index: slug -> list of paragraph dicts
        self._index: dict[str, list[dict]] = {}
        # Meta: slug -> {name, volume} — populated during annotation loading
        self._meta: dict[str, dict] = {}
        # All printed pages per slug: slug -> sorted list of unique ints
        self._all_pages: dict[str, list[int]] = {}

        # CSV lookup tables
        self._para_csv: dict[tuple, dict] = {}   # (vol, paragraph_id) -> row
        self._bio_csv:  dict[str, dict] = {}   # instance_id  -> row
        self._bio_by_slug: dict[tuple, dict] = {}  # (vol, slug_fragment) -> bio record
        self._vol_csv:  dict[str, dict] = {}   # instance_id  -> row

        # Annotation slug → CSV biography URI for cases where auto-matching fails
        self._slug_bio_override: dict[str, str] = {}

        self._load_csv_data()
        self._load_annotations()

    def _load_csv_data(self):
        """Load bibliographic CSV tables."""
        # paragraphs
        para_path = self._data_dir / "viewsari_paragraphs.csv"
        try:
            with open(para_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        pid = int(row.get("paragraph_id", ""))
                    except (ValueError, TypeError):
                        continue
                    vol = row.get("vol", "")
                    self._para_csv[(vol, pid)] = {
                        "para_uri": row.get("instance_id", ""),
                        "page_uri": row.get("dct:isPartOf", ""),
                        "bio_uri":  row.get("frbr:is part of", ""),
                        "vol":      vol,
                    }
        except Exception as e:
            print(f"Warning: could not load {para_path}: {e}")

        # biographies
        bio_path = self._data_dir / "viewsari_biographies.csv"
        try:
            with open(bio_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    iid = row.get("instance_id", "")
                    if not iid:
                        continue
                    bio_record = {
                        "bio_label": row.get("rdfs:label", ""),
                        "vol_uri":   row.get("frbr:is part of", ""),
                        "bio_uri":   iid,
                    }
                    self._bio_csv[iid] = bio_record
                    # Build label-based index for expression-level bios
                    if row.get("rdf:type", "") == "viewsari:biography":
                        vol = row.get("vol", "")
                        # Index by slug extracted from URI
                        slug_part = iid.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
                        self._bio_by_slug[(vol, slug_part)] = bio_record
        except Exception as e:
            print(f"Warning: could not load {bio_path}: {e}")

        # volumes
        vol_path = self._data_dir / "viewsari_volumes.csv"
        try:
            with open(vol_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    iid = row.get("instance_id", "")
                    if not iid:
                        continue
                    self._vol_csv[iid] = {
                        "vol_label":   row.get("rdfs:label", ""),
                        "edition_uri": row.get("frbr:is part of", ""),
                    }
        except Exception as e:
            print(f"Warning: could not load {vol_path}: {e}")

    def _load_annotations(self):
        if not self._annotations_dir.exists():
            return
        for json_file in sorted(self._annotations_dir.rglob("*.json")):
            slug = json_file.stem.removesuffix("_enriched")
            # Volume from parent directory name if it's a digit, else empty
            parent = json_file.parent.name
            volume = parent if parent.isdigit() else ""
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._index[slug] = data
                    # Use biography field from first paragraph as canonical name
                    bio_name = ""
                    if data and isinstance(data[0], dict):
                        raw = data[0].get("biography", "")
                        # Strip bracketed alternative name e.g. "Filippo Brunelleschi [...]"
                        bio_name = raw.split("[")[0].strip()
                    self._meta[slug] = {"name": bio_name or slug.title(), "volume": volume}

                    # Collect all printed page numbers for this biography
                    page_set: set[int] = set()
                    for para in data:
                        if not isinstance(para, dict):
                            continue
                        raw_page = para.get("page", "") or ""
                        try:
                            for part in raw_page.split("-"):
                                part = part.strip()
                                if part.isdigit():
                                    page_set.add(int(part))
                        except Exception:
                            pass
                    self._all_pages[slug] = sorted(page_set)
                else:
                    self._index[slug] = []
                    self._meta[slug] = {"name": slug.title(), "volume": volume}
                    self._all_pages[slug] = []
            except Exception as e:
                print(f"Warning: could not load {json_file}: {e}")

    def list_biographies(self) -> list[dict]:
        result = [
            {
                "slug": slug,
                "name": self._meta[slug]["name"],
                "paragraph_count": len(paragraphs),
                "volume": self._meta[slug]["volume"],
            }
            for slug, paragraphs in self._index.items()
        ]

        def sort_key(b):
            try:
                vol = int(b["volume"])
            except (ValueError, TypeError):
                vol = 99
            return (vol, b["name"])

        result.sort(key=sort_key)
        return result

    # Manual aliases for biography slugs that differ between the KG
    # (derived from bio URIs) and the annotation filenames.
    _SLUG_ALIASES: dict[str, str] = {
        "filippo-brunelleschi": "brunelleschi",
        "ghirlandajo": "ghirlandaio",
        "michelagnolo": "michelangelo",
        "tiziano": "titian",
        "sandro-botticelli": "botticelli",
        "andrea-verrocchio": "verrocchio",
        "andrea-del-verrocchio": "verrocchio",
        "cosimo-rosselli": "rosselli",
        "alesso-baldovinetti": "baldovinetti",
        "leon-batista-alberti": "alberti",
        "pietro-cavallini": "cavallini",
        "jacopo-da-pontormo": "pontormo",
        "filippino-lippi": "lippi",
        "filippo-lippi": "lippi",
        "antonio-pollaiuolo": "pollaiuolo",
        "piero-pollaiuolo": "pollaiuolo",
        "giovanni-cimabue": "cimabue",
    }

    def resolve_slug(self, slug: str) -> str | None:
        """Return the canonical annotation slug, or None if no match.

        Tries: exact match, alias table, substring containment, then
        difflib close-match as a last resort.
        """
        if slug in self._index:
            return slug
        # Alias table
        alias = self._SLUG_ALIASES.get(slug.lower())
        if alias and alias in self._index:
            return alias
        # Substring containment
        sl = slug.lower()
        for key in self._index:
            kl = key.lower()
            if sl in kl or kl in sl:
                return key
        # Fuzzy match (handles j/i swaps, minor spelling differences)
        import difflib
        matches = difflib.get_close_matches(sl, list(self._index.keys()), n=1, cutoff=0.75)
        if matches:
            return matches[0]
        return None

    def get_paragraphs(self, slug: str) -> list[dict]:
        return self._index.get(slug, [])

    def _build_page_map(self, slug: str) -> dict[int, int]:
        """Build page_number → first paragraph_id mapping for navigation."""
        page_map: dict[int, int] = {}
        for para in self._index.get(slug, []):
            pid = para.get("paragraph_id")
            raw_page = para.get("page", "") or ""
            for part in raw_page.split("-"):
                part = part.strip()
                if part.isdigit():
                    page_num = int(part)
                    if page_num not in page_map:
                        page_map[page_num] = pid
        return page_map

    def get_paragraph(self, slug: str, paragraph_id: int) -> dict | None:
        paragraphs = self._index.get(slug)
        if paragraphs is None:
            return None
        for para in paragraphs:
            if para.get("paragraph_id") == paragraph_id:
                vol = self._meta[slug]["volume"]
                # Try to find the bio record by matching the annotation slug
                direct_bio = self._bio_by_slug.get((vol, slug))
                # If not found by slug, construct a fallback from the annotation data
                if not direct_bio:
                    bio_name = (para.get("biography") or "").split("[")[0].strip()
                    direct_bio = {
                        "bio_label": f"Life of {bio_name}" if bio_name else "",
                        "vol_uri": f"viewsari:the_lives_1568_volume-{vol}" if vol else "",
                        "bio_uri": "",
                    }
                meta = {
                    "vol":           vol,
                    "all_pages":     self._all_pages.get(slug, []),
                    "facsimile_dir": self._facsimile_dir,
                    "ocr_dir":       self._ocr_dir,
                    "para_csv":      self._para_csv.get((vol, para.get("paragraph_id"))),
                    "bio_csv":       self._bio_csv,
                    "vol_csv":       self._vol_csv,
                    "page_map":      self._build_page_map(slug),
                    "direct_bio":    direct_bio,
                }
                viewer_data = build_viewer_data(para, meta)
                return {**para, "viewer_data": viewer_data}
        return None