"""
rebuild_pages_paragraphs.py
============================
Rebuilds viewsari_pages.csv and updates viewsari_paragraphs.csv
to reflect the corrected biography start pages and slugs.

For each page number in each volume, determines which biography it
belongs to based on the biography start pages in viewsari_biographies.csv.

Usage:
    python src/kg_population/rebuild_pages_paragraphs.py
"""

import csv
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

BASE = Path(__file__).resolve().parent.parent
KG_DIR = BASE / "data" / "kg_foundation"

# ── Load biographies ─────────────────────────────────────────────────

def load_biographies():
    """Load biography data, return dict: (vol, slug) -> {start_page, label, ...}
    and a lookup: vol -> sorted list of (start_page, slug, label, expr_uri, manif_uri, gutenberg_url)
    """
    bios_by_vol = {}  # vol -> list of (start, slug, label, expr_uri, manif_uri, gutenberg_url)

    expr_rows = {}   # slug -> row
    manif_rows = {}  # slug -> row

    with open(KG_DIR / "viewsari_biographies.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            vol = r.get("vol", "")
            if r["rdf:type"] == "viewsari:biography":
                slug = r["instance_id"].split(f"volume-{vol}_")[1].replace("-bio", "")
                start = int(r.get("start_page", 0))
                label = r["rdfs:label"]
                expr_uri = r["instance_id"]
                manif_uri = r.get("frbr:has embodiment", "")

                if vol not in bios_by_vol:
                    bios_by_vol[vol] = []
                bios_by_vol[vol].append((start, slug, label, expr_uri, manif_uri))
            elif r["rdf:type"] == "viewsari:biography web representation":
                gutenberg = r.get("rdfs:seeAlso", "")
                # Store for later lookup
                manif_rows[r["instance_id"]] = gutenberg

    # Sort each volume's bios by start page
    for vol in bios_by_vol:
        bios_by_vol[vol].sort(key=lambda x: x[0])

    return bios_by_vol, manif_rows


def find_bio_for_page(bios_list, page_num):
    """Given a sorted list of (start, slug, label, expr_uri, manif_uri) and a page number,
    find which biography the page belongs to."""
    result = bios_list[0]  # default to first
    for bio in bios_list:
        if bio[0] <= page_num:
            result = bio
        else:
            break
    return result


# ── Load volume Gutenberg URLs ───────────────────────────────────────

def load_volume_urls():
    """Return dict: vol -> gutenberg_base_url"""
    urls = {}
    with open(KG_DIR / "viewsari_volumes.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sa = r.get("rdfs:seeAlso", "")
            if sa and "gutenberg" in sa:
                # Extract vol number from instance_id
                iid = r["instance_id"]
                for i in range(1, 11):
                    if f"volume-{i}" in iid:
                        urls[str(i)] = sa
                        break
    return urls


# ── Rebuild pages ────────────────────────────────────────────────────

def rebuild_pages(bios_by_vol, vol_urls):
    """Read existing pages, reassign biography ownership based on page numbers."""

    with open(KG_DIR / "viewsari_pages.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        old_rows = list(reader)

    # Collect unique (vol, page_number) pairs from existing data
    page_set = {}
    for r in old_rows:
        vol = r.get("vol", "")
        pn = r.get("page_number", "")
        if vol and pn and r.get("level") == "expression":
            page_set.setdefault(vol, set()).add(int(pn))

    new_rows = []

    for vol in sorted(page_set.keys(), key=int):
        if vol not in bios_by_vol:
            print(f"  Warning: no biographies for volume {vol}")
            continue

        bios = bios_by_vol[vol]
        gutenberg_base = vol_urls.get(vol, "")

        for pn in sorted(page_set[vol]):
            start, slug, label, expr_uri, manif_uri = find_bio_for_page(bios, pn)

            bio_expr = expr_uri
            bio_manif = manif_uri

            page_expr_id = f"viewsari:the_lives_1568_volume-{vol}_{slug}-bio_page_{pn}"
            page_manif_id = f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{vol}_{slug}-bio_page_{pn}"

            # Expression row
            new_rows.append({
                "instance_id": page_expr_id,
                "rdf:type": "viewsari:page",
                "rdf_type_2": "fabio:Expression",
                "rdfs:label": f"The Lives, 1568, Vol. {vol}, {label}, Page {pn}",
                "frbr:is part of": bio_expr,
                "frbr:has embodiment": page_manif_id,
                "rdfs:seeAlso": "",
                "page_number": str(pn),
                "biography_slug": slug,
                "vol": vol,
                "level": "expression",
            })

            # Manifestation row
            new_rows.append({
                "instance_id": page_manif_id,
                "rdf:type": "viewsari:page web representation",
                "rdf_type_2": "fabio:WebPage",
                "rdfs:label": f"Gutenberg Web Version of {label}, Page {pn}",
                "frbr:is part of": f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{vol}_{slug}-bio",
                "frbr:has embodiment": "",
                "rdfs:seeAlso": f"{gutenberg_base}#Page_{pn}" if gutenberg_base else "",
                "page_number": str(pn),
                "biography_slug": slug,
                "vol": vol,
                "level": "manifestation",
            })

    with open(KG_DIR / "viewsari_pages.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(new_rows)

    print(f"  Pages: wrote {len(new_rows)} rows ({len(new_rows)//2} pages)")
    return new_rows


# ── Rebuild paragraphs ───────────────────────────────────────────────

def rebuild_paragraphs(bios_by_vol):
    """Update paragraph biography references based on their start page."""

    with open(KG_DIR / "viewsari_paragraphs.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        old_rows = list(reader)

    updated = 0
    new_rows = []

    for r in old_rows:
        vol = r.get("vol", "")
        if vol not in bios_by_vol:
            new_rows.append(r)
            continue

        bios = bios_by_vol[vol]

        # Extract start page number from the start page URI
        start_page_uri = r.get("viewsari:has start page", "")
        end_page_uri = r.get("viewsari:has end page", "")

        # Parse page number from URI like "viewsari:..._page_N"
        start_pn = None
        if "_page_" in start_page_uri:
            try:
                start_pn = int(start_page_uri.rsplit("_page_", 1)[1])
            except (ValueError, IndexError):
                pass

        end_pn = None
        if "_page_" in end_page_uri:
            try:
                end_pn = int(end_page_uri.rsplit("_page_", 1)[1])
            except (ValueError, IndexError):
                pass

        if start_pn is None:
            new_rows.append(r)
            continue

        # Find correct biography for this paragraph's start page
        start, slug, label, expr_uri, manif_uri = find_bio_for_page(bios, start_pn)

        # Update dct:isPartOf (page expression URI)
        new_page_expr = f"viewsari:the_lives_1568_volume-{vol}_{slug}-bio_page_{start_pn}"

        # Update start page URI (manifestation)
        new_start_page = f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{vol}_{slug}-bio_page_{start_pn}"

        # Update end page URI (may be different bio if paragraph spans bio boundary, but use same bio)
        if end_pn is not None:
            end_start, end_slug, _, _, _ = find_bio_for_page(bios, end_pn)
            new_end_page = f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{vol}_{end_slug}-bio_page_{end_pn}"
        else:
            new_end_page = end_page_uri

        # Update frbr:is part of (biography expression URI)
        new_bio_ref = expr_uri

        old_bio = r.get("frbr:is part of", "")
        if (r["dct:isPartOf"] != new_page_expr or
            r["viewsari:has start page"] != new_start_page or
            r["viewsari:has end page"] != new_end_page or
            r["frbr:is part of"] != new_bio_ref):
            updated += 1

        r_new = dict(r)
        r_new["dct:isPartOf"] = new_page_expr
        r_new["viewsari:has start page"] = new_start_page
        r_new["viewsari:has end page"] = new_end_page
        r_new["frbr:is part of"] = new_bio_ref
        new_rows.append(r_new)

    with open(KG_DIR / "viewsari_paragraphs.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(new_rows)

    print(f"  Paragraphs: updated {updated}/{len(new_rows)} rows")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("Loading biographies...")
    bios_by_vol, manif_rows = load_biographies()
    for vol in sorted(bios_by_vol.keys(), key=int):
        print(f"  Vol {vol}: {len(bios_by_vol[vol])} biographies")

    print("\nLoading volume URLs...")
    vol_urls = load_volume_urls()

    print("\nRebuilding pages...")
    rebuild_pages(bios_by_vol, vol_urls)

    print("\nRebuilding paragraphs...")
    rebuild_paragraphs(bios_by_vol)

    print("\nDone.")


if __name__ == "__main__":
    main()
