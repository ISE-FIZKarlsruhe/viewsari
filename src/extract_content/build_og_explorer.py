"""
build_og_explorer.py
=====================
Pre-computes subgraph JSON files for the *third* KG Explorer layer:
the **ontology-guided-all** extraction run and its **entity-linking (EL)**
results, as merged into ``data/kg/viewsari_kg.ttl``.

Unlike the ground-truth explorer (``build_explorer_graphs.py``), this layer's
data lives in the big merged KG. We stream-parse it block-by-block (no rdflib —
same approach as ``src/kg_population/mint_ookb_entities.py``) and pull out only
what the explorer needs.

We read ``viewsari_kg.noprompts.ttl`` by default: it is the *same* merge as
``viewsari_kg.ttl`` (mentions, EL entities and OOKB entities are identical) but
with the bulky prompt-text blocks stripped. That matters for correctness, not
just speed — the full KG's prompt literals contain blank lines, which fracture
blank-line block splitting; the no-prompt file has no multi-line literals, so
every block parses cleanly. Pass ``--kg data/kg/viewsari_kg.ttl`` to use the
full file anyway. The fields we read are:

  * artwork **mentions**            vkb:ontology_guided_all_vol{V}_p{P}_m_{N}
        viewsari:0001032 -> paragraph token
  * **linked** EL entities          vkb:final_ontology_linked_all_artwork_Q{...}
        owl:sameAs <wikidata/Q...> ; prov:wasDerivedFrom <representative mention>
  * **OOKB / NIL** EL entities       vkb:final_ontology_linked_all_ookb_{...}
        rdfs:label "..." ; viewsari:0001032 -> paragraph ; wasDerivedFrom <mention>

Each artwork mention's EL outcome is therefore either a Wikidata-linked entity
(an ``entity`` node, carrying its QID) or an out-of-KB ``ookb`` node (NIL).
Subgraphs are built for the *same* person / artwork / biography seeds as the GT
explorer so the three layers are directly comparable.

Output: data/kg/explorer/og/ — one JSON per subgraph + index.json.

Usage:
    python src/extract_content/build_og_explorer.py [--kg data/kg/viewsari_kg.ttl]
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

BASE = Path(__file__).resolve().parent.parent.parent
KG_DIR = BASE / "data" / "kg_foundation"
DEFAULT_KG = BASE / "data" / "kg" / "viewsari_kg.noprompts.ttl"
OUT_DIR = BASE / "data" / "kg" / "explorer" / "og"
KB = "https://viewsari.ise.fiz-karlsruhe.de/kb/"

# Artwork mention classes (explicit / implicit artwork mention).
ARTWORK_CLASSES = {"0001020", "0001021"}

MENTION_PREFIX = "ontology_guided_all_"
LINKED_PREFIX = "final_ontology_linked_all_artwork_"
OOKB_PREFIX = "final_ontology_linked_all_ookb_"

PARA_TOKEN_RE = re.compile(r"volume-(\d+)_paragraph-(\d+)")
HASPARA_RE = re.compile(r"viewsari:0001032\s+vkb:(\S+?)\s*[;.]")
SAMEAS_RE = re.compile(r"owl:sameAs\s+<[^>]*?(Q\d+)>")
LABEL_RE = re.compile(r'rdfs:label\s+"((?:[^"\\]|\\.)*)"')
CLASS_RE = re.compile(r"viewsari:(\d{7})")
# A linked entity may aggregate several mentions in a comma-separated
# wasDerivedFrom list, so collect every mention local after the predicate.
MENTION_LOCAL_RE = re.compile(r"ontology_guided_all_vol\d+_p\d+_m_\d+")
SLUG_RE = re.compile(r"[^a-z0-9]+")


def _derived_mentions(text):
    i = text.find("prov:wasDerivedFrom")
    return MENTION_LOCAL_RE.findall(text[i:]) if i >= 0 else []


# ──────────────────────────────────────────────────────────────────────────
# Foundation CSVs (same loaders as build_explorer_graphs.py)
# ──────────────────────────────────────────────────────────────────────────
def load_para_bio_map():
    """Map (vol, paragraph_id) -> bio uri, and bio uri -> label."""
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


def _bio_slug_from_uri(bio_uri):
    """'viewsari:..._cimabue-bio' -> 'cimabue'."""
    part = bio_uri.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
    return part


# ──────────────────────────────────────────────────────────────────────────
# Stream-parse the merged KG
# ──────────────────────────────────────────────────────────────────────────
def parse_kg(kg_path):
    """Single pass over the KG. Returns:
        mention_para  {mention_local: (vol, pid)}
        linked        [{qid, label, mention}]
        ookb          [{label, mention, vol, pid}]
    """
    mention_para = {}
    linked = []
    ookb = []
    block = []

    def handle(b):
        if not b:
            return
        head = b[0]
        if not head.startswith("vkb:"):
            return
        local = head.split(None, 1)[0][4:]
        text = "".join(b)

        if local.startswith(MENTION_PREFIX) and "_m_" in local and " a oa:Annotation" in head:
            if ARTWORK_CLASSES & set(CLASS_RE.findall(head)):
                m = HASPARA_RE.search(text)
                if m:
                    tok = PARA_TOKEN_RE.search(m.group(1))
                    if tok:
                        mention_para[local] = (tok.group(1), tok.group(2))
        elif local.startswith(LINKED_PREFIX):
            qm = SAMEAS_RE.search(text)
            lm = LABEL_RE.search(text)
            mentions = _derived_mentions(text)
            if qm and mentions:
                linked.append({"qid": qm.group(1),
                               "label": lm.group(1) if lm else qm.group(1),
                               "mentions": mentions})
        elif local.startswith(OOKB_PREFIX):
            lm = LABEL_RE.search(text)
            mentions = _derived_mentions(text)
            pm = HASPARA_RE.search(text)
            vol = pid = None
            if pm:
                tok = PARA_TOKEN_RE.search(pm.group(1))
                if tok:
                    vol, pid = tok.group(1), tok.group(2)
            ookb.append({"label": lm.group(1) if lm else "(untitled)",
                         "mention": mentions[0] if mentions else None,
                         "vol": vol, "pid": pid})

    with open(kg_path, encoding="utf-8") as f:
        for line in f:
            if line.strip() == "":
                handle(block)
                block = []
            else:
                block.append(line)
        handle(block)

    return mention_para, linked, ookb


# ──────────────────────────────────────────────────────────────────────────
# EL entity records with resolved (vol, pid)
# ──────────────────────────────────────────────────────────────────────────
def resolve_entities(mention_para, linked, ookb):
    """Attach (vol, pid) to every EL entity and tag its kind."""
    ents = []
    seen = set()
    for e in linked:
        for mention in e["mentions"]:
            loc = mention_para.get(mention)
            if not loc:
                continue
            key = ("entity", e["qid"], loc[0], loc[1])
            if key in seen:
                continue
            seen.add(key)
            ents.append({"kind": "entity", "qid": e["qid"], "label": e["label"],
                         "vol": loc[0], "pid": loc[1]})
    for e in ookb:
        vol, pid = e["vol"], e["pid"]
        if (vol is None or pid is None) and e["mention"]:
            loc = mention_para.get(e["mention"])
            if loc:
                vol, pid = loc
        if vol is not None and pid is not None:
            ents.append({"kind": "ookb", "qid": "", "label": e["label"],
                         "vol": vol, "pid": pid})
    return ents


# ──────────────────────────────────────────────────────────────────────────
# Subgraph builders
# ──────────────────────────────────────────────────────────────────────────
MAX_ENTS = 60          # cap entities per bio-centric graph for legibility
MAX_ARTWORK = 30       # cap matches per artwork-seed graph


def _new_graph():
    nodes = {}
    edges = []

    def add(uri, label, ntype, **kw):
        if uri not in nodes:
            nodes[uri] = {"id": uri, "label": label, "type": ntype, **kw}
    return nodes, edges, add


def _ent_uri(ent):
    if ent["kind"] == "entity":
        return KB + f"ol_artwork_{ent['qid']}"
    slug = SLUG_RE.sub("-", ent["label"].lower()).strip("-")[:40] or "untitled"
    return KB + f"ol_ookb_{ent['vol']}_{ent['pid']}_{slug}"


def _add_chain(add, edges, ent, bio_uri, bio_slug):
    """Add ent -> paragraph -> biography chain. Caller adds the bio node."""
    vol, pid = ent["vol"], ent["pid"]
    pu = KB + f"the_lives_1568_volume-{vol}_paragraph-{pid}"
    plink = f"/biography/{bio_slug}/{pid}" if bio_slug else None
    add(pu, f"Vol. {vol}, §{pid}", "paragraph", link=plink)
    eu = _ent_uri(ent)
    elink = f"/biography/{bio_slug}/{pid}" if bio_slug else None
    if ent["kind"] == "entity":
        add(eu, ent["label"][:40], "entity", wikidata=ent["qid"], link=elink)
        edges.append({"source": eu, "target": pu, "label": "refers to"})
    else:
        add(eu, ent["label"][:40], "ookb", link=elink)
        edges.append({"source": eu, "target": pu, "label": "refers to (NIL)", "dashed": True})
    if bio_uri:
        edges.append({"source": pu, "target": bio_uri, "label": "frbr:isPartOf", "dashed": True})


def build_bio_graph(name, ents, para_bio, bio_labels):
    """Bio-centric graph: biography -> paragraphs -> EL entities (linked / OOKB)."""
    target_bio = None
    for bio_id, label in bio_labels.items():
        if name.lower() in label.lower():
            target_bio = bio_id
            break
    if not target_bio:
        return None

    bio_paras = {(v, p) for (v, p), b in para_bio.items() if b == target_bio}
    if not bio_paras:
        return None

    nodes, edges, add = _new_graph()
    bio_slug = _bio_slug_from_uri(target_bio)
    bu = KB + target_bio.replace("viewsari:", "")
    add(bu, bio_labels[target_bio], "biography", link=f"/biography/{bio_slug}")

    count = 0
    for ent in ents:
        if count >= MAX_ENTS:
            break
        if (ent["vol"], ent["pid"]) in bio_paras:
            _add_chain(add, edges, ent, bu, bio_slug)
            count += 1

    return {"nodes": list(nodes.values()), "edges": edges}


def build_artwork_graph(seed, ents, para_bio, bio_labels):
    """Artwork-centric graph: EL entities whose label matches the seed, with context."""
    matches = [e for e in ents if seed.lower() in e["label"].lower()][:MAX_ARTWORK]
    if not matches:
        return None

    nodes, edges, add = _new_graph()
    for ent in matches:
        bio_uri = para_bio.get((ent["vol"], ent["pid"]), "")
        bu = ""
        bio_slug = ""
        if bio_uri:
            bio_slug = _bio_slug_from_uri(bio_uri)
            bu = KB + bio_uri.replace("viewsari:", "")
            add(bu, bio_labels.get(bio_uri, bio_slug), "biography", link=f"/biography/{bio_slug}")
        _add_chain(add, edges, ent, bu, bio_slug)

    return {"nodes": list(nodes.values()), "edges": edges}


# ──────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kg", type=Path, default=DEFAULT_KG,
                    help="merged KG turtle (default: data/kg/viewsari_kg.noprompts.ttl)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Parsing {args.kg} (streaming) ...")
    mention_para, linked, ookb = parse_kg(args.kg)
    print(f"  {len(mention_para):,} artwork mentions, {len(linked):,} linked entities, "
          f"{len(ookb):,} OOKB entities")

    para_bio, bio_labels = load_para_bio_map()
    ents = resolve_entities(mention_para, linked, ookb)
    n_link = sum(1 for e in ents if e["kind"] == "entity")
    n_ookb = sum(1 for e in ents if e["kind"] == "ookb")
    print(f"  resolved {len(ents):,} EL entities to paragraphs "
          f"({n_link:,} linked, {n_ookb:,} OOKB)")

    index = []

    # Person + biography graphs are both bio-centric in this layer.
    person_seeds = [
        "Giotto", "Cimabue", "Michelagnolo", "Raphael", "Brunelleschi",
        "Donatello", "Ghirlandajo", "Perugino", "Mantegna", "Pontormo",
        "Bandinelli", "Giulio Romano", "Sansovino", "Signorelli",
    ]
    for name in person_seeds:
        g = build_bio_graph(name, ents, para_bio, bio_labels)
        if g and len(g["nodes"]) > 2:
            fname = f"person_{name.lower().replace(' ', '_')}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(g, f)
            index.append({"file": fname, "label": name, "mode": "person",
                          "nodes": len(g["nodes"]), "edges": len(g["edges"])})
            print(f"  person/{name}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    artwork_seeds = [
        "S. Croce", "Sistine", "S. Maria Novella", "Madonna",
        "Crucifix", "Chapel", "Last Supper", "Annunciation",
        "tomb", "fresco", "Baptistery", "S. Pietro",
    ]
    for name in artwork_seeds:
        g = build_artwork_graph(name, ents, para_bio, bio_labels)
        if g and len(g["nodes"]) > 2:
            fname = f"artwork_{name.lower().replace(' ', '_').replace('.', '')}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(g, f)
            index.append({"file": fname, "label": name, "mode": "artwork",
                          "nodes": len(g["nodes"]), "edges": len(g["edges"])})
            print(f"  artwork/{name}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    bio_seeds = ["Giotto", "Botticelli", "Ghirlandajo", "Brunelleschi", "Michelagnolo"]
    for name in bio_seeds:
        g = build_bio_graph(name, ents, para_bio, bio_labels)
        if g and len(g["nodes"]) > 2:
            fname = f"bio_{name.lower().replace(' ', '_')}.json"
            with open(OUT_DIR / fname, "w") as f:
                json.dump(g, f)
            index.append({"file": fname, "label": f"Bio: {name}", "mode": "biography",
                          "nodes": len(g["nodes"]), "edges": len(g["edges"])})
            print(f"  bio/{name}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")

    with open(OUT_DIR / "index.json", "w") as f:
        json.dump(index, f, indent=2)
    print(f"\nDone — {len(index)} subgraphs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
