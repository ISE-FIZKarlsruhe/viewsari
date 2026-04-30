"""
build_explorer_graphs.py
========================
Pre-computes subgraph JSON files for the KG Explorer from the
annotation data and KG foundation CSVs. No rdflib/SPARQL needed.

Output: data/kg/explorer/ — one JSON per subgraph.

Usage:
    python src/extract_content/build_explorer_graphs.py
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

BASE = Path(__file__).resolve().parent.parent.parent
ANN_DIR = BASE / "obliquer" / "data" / "viewsari" / "ground_truth"
KG_DIR = BASE / "data" / "kg_foundation"
OUT_DIR = BASE / "data" / "kg" / "explorer"
KB = "https://viewsari.ise.fiz-karlsruhe.de/kb/"


def load_cooccurrences():
    """Load person co-occurrences."""
    coocs = []
    persons = {}
    with open(KG_DIR / "cooccurrences" / "viewsari_cooccurrences.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            coocs.append(row)
    person_wd = {}
    with open(KG_DIR / "persons" / "viewsari_persons.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            persons[row["instance_id"]] = row["rdfs:label"]
            qid = row.get("Wikidata QID", "")
            if qid:
                person_wd[row["instance_id"]] = qid
    return coocs, persons, person_wd


def load_para_bio_map():
    """Map (vol, para_id) -> bio info."""
    para_bio = {}
    with open(KG_DIR / "viewsari_paragraphs.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            para_bio[(row["vol"], row["paragraph_id"])] = row.get("frbr:is part of", "")
    bio_labels = {}
    with open(KG_DIR / "viewsari_biographies.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("rdf:type") == "viewsari:biography":
                bio_labels[row["instance_id"]] = row["rdfs:label"]
    return para_bio, bio_labels


def load_artworks():
    """Load all artwork entities from annotations."""
    artworks = {}  # key -> {label, wd, ookb, paras: [(vol, pid, slug)]}
    for vol_dir in sorted(ANN_DIR.iterdir()):
        if not vol_dir.is_dir() or not vol_dir.name.isdigit():
            continue
        vol = vol_dir.name
        for f in sorted(vol_dir.glob("*_enriched.json")):
            slug = f.stem.removesuffix("_enriched")
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            for p in data:
                pid = str(p.get("paragraph_id", ""))
                for m in p.get("mentions", []):
                    eid = m.get("entity_id")
                    if not eid:
                        continue
                    key = f"{slug}_{eid}"
                    if key not in artworks:
                        wid = m.get("wikidata_id") or ""
                        if isinstance(wid, list):
                            wid = wid[0] if wid else ""
                        artworks[key] = {
                            "label": m.get("label") or m.get("surface_form", ""),
                            "wd": wid.split("/")[-1] if wid and "wikidata" in wid else "",
                            "ookb": m.get("ookb", False),
                            "paras": [],
                            "slug": slug,
                        }
                    artworks[key]["paras"].append((vol, pid, slug))
    return artworks


def _bio_slug_from_uri(bio_uri):
    """Extract annotation slug from a biography URI like 'viewsari:..._cimabue-bio'."""
    part = bio_uri.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
    return part


def _cooc_label_to_link(label, bio_labels, para_bio):
    """Try to extract a /biography/slug/para link from a co-occurrence label like 'Co-occurrence of X and Y, Vol. 1, Para. 13'."""
    import re
    m = re.search(r"Vol\.\s*(\d+),\s*Para\.\s*(\d+)", label)
    if not m:
        return None
    vol, pid = m.group(1), m.group(2)
    bio_uri = para_bio.get((vol, pid), "")
    if bio_uri:
        slug = _bio_slug_from_uri(bio_uri)
        return f"/biography/{slug}/{pid}"
    return None


def build_person_graph(person_name, coocs, persons, person_wd, para_bio, bio_labels):
    """Build subgraph centered on a person."""
    nodes = {}
    edges = []

    def add(uri, label, ntype, **kw):
        if uri not in nodes:
            nodes[uri] = {"id": uri, "label": label, "type": ntype, **kw}

    def add_person(pid, plabel):
        add(KB + pid.replace("viewsari:", ""), plabel, "person",
            wikidata=person_wd.get(pid, ""))

    # Find person URI
    person_uri = None
    for pid, plabel in persons.items():
        if person_name.lower() in plabel.lower():
            person_uri = pid
            add_person(pid, plabel)
            break
    if not person_uri:
        return None

    pu = KB + person_uri.replace("viewsari:", "")

    # Find co-occurrences involving this person
    for c in coocs:
        p1, p2 = c["viewsari:involves"], c["viewsari:involves_2"]
        if person_uri not in (p1, p2):
            continue
        other = p2 if p1 == person_uri else p1
        other_label = persons.get(other, other)
        cu = KB + c["instance_id"].replace("viewsari:", "")
        add_person(other, other_label)
        link = _cooc_label_to_link(c["rdfs:label"], bio_labels, para_bio)
        add(cu, c["rdfs:label"][:50], "cooccurrence", link=link)
        edges.append({"source": cu, "target": pu, "label": "involves"})
        edges.append({"source": cu, "target": KB + other.replace("viewsari:", ""), "label": "involves"})

    return {"nodes": list(nodes.values()), "edges": edges}


def build_artwork_graph(seed, artworks, para_bio, bio_labels):
    """Build subgraph for artworks matching seed."""
    nodes = {}
    edges = []

    def add(uri, label, ntype, **kw):
        if uri not in nodes:
            nodes[uri] = {"id": uri, "label": label, "type": ntype, **kw}

    matches = [(k, v) for k, v in artworks.items() if seed.lower() in v["label"].lower()]
    if not matches:
        return None

    seen_paras = set()
    for key, art in matches[:15]:
        au = KB + key
        slug = art["slug"]
        art_link = None
        if art["paras"]:
            vol, pid, slug = art["paras"][0]
            art_link = f"/biography/{slug}/{pid}"
        add(au, art["label"][:40], "artwork", wikidata=art["wd"], link=art_link)
        # Link to first paragraph
        if art["paras"]:
            vol, pid, slug = art["paras"][0]
            para_key = f"the_lives_1568_volume-{vol}_paragraph-{pid}"
            pu = KB + para_key
            para_link = f"/biography/{slug}/{pid}"
            add(pu, f"Vol. {vol}, §{pid}", "paragraph", link=para_link)
            edges.append({"source": au, "target": pu, "label": "inParagraph"})
            seen_paras.add((vol, pid))
            # Link to biography
            bio_uri = para_bio.get((vol, pid), "")
            if bio_uri:
                bu = KB + bio_uri.replace("viewsari:", "")
                bl = bio_labels.get(bio_uri, "")
                bio_slug = _bio_slug_from_uri(bio_uri)
                add(bu, bl, "biography", link=f"/biography/{bio_slug}")
                edges.append({"source": pu, "target": bu, "label": "frbr:isPartOf", "dashed": True})

    # Add sibling artworks in same paragraphs
    for key, art in artworks.items():
        if key in {k for k, _ in matches}:
            continue
        for vol, pid, slug in art["paras"]:
            if (vol, pid) in seen_paras:
                au = KB + key
                pu = KB + f"the_lives_1568_volume-{vol}_paragraph-{pid}"
                sib_link = f"/biography/{slug}/{pid}"
                add(au, art["label"][:40], "artwork", wikidata=art["wd"], link=sib_link)
                edges.append({"source": au, "target": pu, "label": "inParagraph", "dashed": True})
                break

    return {"nodes": list(nodes.values()), "edges": edges}


def build_biography_graph(bio_name, coocs, persons, artworks, para_bio, bio_labels):
    """Build subgraph showing all entities in a biography."""
    nodes = {}
    edges = []

    def add(uri, label, ntype, **kw):
        if uri not in nodes:
            nodes[uri] = {"id": uri, "label": label, "type": ntype, **kw}

    # Find biography
    target_bio = None
    for bio_id, label in bio_labels.items():
        if bio_name.lower() in label.lower():
            target_bio = bio_id
            bu = KB + bio_id.replace("viewsari:", "")
            bio_slug = _bio_slug_from_uri(bio_id)
            add(bu, label, "biography", link=f"/biography/{bio_slug}")
            break
    if not target_bio:
        return None

    # Find paragraphs in this biography
    bio_paras = set()
    for (vol, pid), bio_id in para_bio.items():
        if bio_id == target_bio:
            bio_paras.add((vol, pid))

    # Artworks in these paragraphs
    for key, art in artworks.items():
        for vol, pid, slug in art["paras"]:
            if (vol, pid) in bio_paras:
                au = KB + key
                art_link = f"/biography/{slug}/{pid}"
                add(au, art["label"][:40], "artwork", wikidata=art["wd"], link=art_link)
                bu = KB + target_bio.replace("viewsari:", "")
                edges.append({"source": au, "target": bu, "label": "mentioned in", "dashed": True})
                break

    return {"nodes": list(nodes.values()), "edges": edges}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    coocs, persons, person_wd = load_cooccurrences()
    para_bio, bio_labels = load_para_bio_map()
    artworks = load_artworks()
    print(f"  {len(coocs)} co-occurrences, {len(persons)} persons ({len(person_wd)} with WD QID), {len(artworks)} artworks")

    # Index of all generated graphs
    index = []

    # Person graphs
    person_seeds = [
        "Giotto", "Cimabue", "Michelagnolo", "Raphael", "Brunelleschi",
        "Donatello", "Ghirlandajo", "Perugino", "Mantegna", "Pontormo",
        "Bandinelli", "Giulio Romano", "Sansovino", "Signorelli",
    ]
    for name in person_seeds:
        g = build_person_graph(name, coocs, persons, person_wd, para_bio, bio_labels)
        if g and len(g["nodes"]) > 2:
            fname = f"person_{name.lower().replace(' ', '_')}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(g, f)
            index.append({"file": fname, "label": name, "mode": "person",
                          "nodes": len(g["nodes"]), "edges": len(g["edges"])})
            print(f"  person/{name}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    # Artwork graphs
    artwork_seeds = [
        "S. Croce", "Sistine", "S. Maria Novella", "Madonna",
        "Crucifix", "Chapel", "Last Supper", "Annunciation",
        "tomb", "fresco", "Baptistery", "S. Pietro",
    ]
    for name in artwork_seeds:
        g = build_artwork_graph(name, artworks, para_bio, bio_labels)
        if g and len(g["nodes"]) > 2:
            fname = f"artwork_{name.lower().replace(' ', '_').replace('.', '')}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(g, f)
            index.append({"file": fname, "label": name, "mode": "artwork",
                          "nodes": len(g["nodes"]), "edges": len(g["edges"])})
            print(f"  artwork/{name}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    # Biography graphs
    bio_seeds = ["Giotto", "Botticelli", "Ghirlandajo", "Brunelleschi", "Michelagnolo"]
    for name in bio_seeds:
        g = build_biography_graph(name, coocs, persons, artworks, para_bio, bio_labels)
        if g and len(g["nodes"]) > 2:
            fname = f"bio_{name.lower().replace(' ', '_')}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(g, f)
            index.append({"file": fname, "label": f"Bio: {name}", "mode": "biography",
                          "nodes": len(g["nodes"]), "edges": len(g["edges"])})
            print(f"  bio/{name}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    # Write index
    with open(OUT_DIR / "index.json", "w") as f:
        json.dump(index, f, indent=2)
    print(f"\nDone — {len(index)} subgraphs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
