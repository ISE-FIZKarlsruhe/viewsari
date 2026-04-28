"""One-shot rebuild of the Viewsari KG from the .bak base.

Steps:
  1. Load the backup KG.
  2. Strip ObliquER artifacts (URIs prefixed with few_shot_v2_, ontology_guided_v2_,
     cot_v2_, ner_run_few_shot_v2, ner_run_ontology_guided_v2, ner_run_cot_v2,
     el_run_*, llm_agent_openai_gpt_oss_120b).
  3. Strip TextChunk rdfs:label triples.
  4. Swap rdfs:label → oa:hasBodyValue on oa:Annotation instances.
  5. Re-ingest ObliquER NER runs (per-extraction NER + EL activities).
  6. Re-ingest GT (per-cluster EL via prov:wasDerivedFrom).
  7. Serialize once at the end.

Run:  python src/kg_population/rebuild_kg.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
KG_PATH = ROOT / "data" / "kg" / "viewsari_kg.ttl"
BAK_PATH = ROOT / "data" / "kg" / "viewsari_kg.ttl.bak"

OA = Namespace("http://www.w3.org/ns/oa#")
DOCO = Namespace("http://purl.org/spar/doco/")
OLD_VKB = "https://viewsari.ise.fiz-karlsruhe.de/kb/"
NEW_VKB = "https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#"
VKB = OLD_VKB  # for stripping ObliquER artifacts from the backup

OBLIQUER_PREFIXES = (
    VKB + "few_shot_v2_",
    VKB + "ontology_guided_v2_",
    VKB + "cot_v2_",
    VKB + "ner_run_few_shot_v2",
    VKB + "ner_run_ontology_guided_v2",
    VKB + "ner_run_cot_v2",
    VKB + "el_run_few_shot_v2",
    VKB + "el_run_ontology_guided_v2",
    VKB + "el_run_cot_v2",
    VKB + "llm_agent_openai_gpt_oss_120b",
)

def is_obliquer(uri: str) -> bool:
    return any(uri.startswith(p) for p in OBLIQUER_PREFIXES)


def main():
    print("Loading backup …")
    g = Graph()
    g.parse(str(BAK_PATH), format="turtle")
    print(f"  {len(g):,} triples")

    print("Stripping legacy ObliquER artifacts …")
    n = 0
    for s, p, o in list(g):
        if (isinstance(s, URIRef) and is_obliquer(str(s))) or (isinstance(o, URIRef) and is_obliquer(str(o))):
            g.remove((s, p, o)); n += 1
    print(f"  removed {n:,} triples → {len(g):,}")

    print("Stripping TextChunk labels …")
    n = 0
    for c in list(g.subjects(RDF.type, DOCO.TextChunk)):
        for lab in list(g.objects(c, RDFS.label)):
            g.remove((c, RDFS.label, lab)); n += 1
    print(f"  removed {n} chunk labels → {len(g):,}")

    print("Migrating vkb: namespace from /kb/ to /kb/1.0# …")
    def _migrate_uri(uri):
        s = str(uri)
        if s.startswith(OLD_VKB):
            return URIRef(NEW_VKB + s[len(OLD_VKB):])
        return uri
    new_g = Graph()
    for s, p, o in g:
        s2 = _migrate_uri(s) if isinstance(s, URIRef) else s
        o2 = _migrate_uri(o) if isinstance(o, URIRef) else o
        new_g.add((s2, p, o2))
    g = new_g
    from rdflib.namespace import Namespace as NS
    g.bind("vkb", NS(NEW_VKB))
    g.bind("viewsari", NS("https://viewsari.ise.fiz-karlsruhe.de/ontology/#"))
    g.bind("doco", NS("http://purl.org/spar/doco/"))
    g.bind("oa", NS("http://www.w3.org/ns/oa#"))
    g.bind("prov", NS("http://www.w3.org/ns/prov#"))
    g.bind("frbr", NS("http://purl.org/vocab/frbr/core#"))
    g.bind("fabio", NS("http://purl.org/spar/fabio/"))
    g.bind("dct", NS("http://purl.org/dc/terms/"))
    g.bind("dc", NS("http://purl.org/dc/elements/1.1/"))
    g.bind("foaf", NS("http://xmlns.com/foaf/0.1/"))
    print(f"  migrated → {len(g):,} triples")

    print("Swapping annotation rdfs:label → oa:hasBodyValue …")
    n = 0
    for ann in list(g.subjects(RDF.type, OA.Annotation)):
        existing = list(g.objects(ann, OA.hasBodyValue))
        for lab in list(g.objects(ann, RDFS.label)):
            g.remove((ann, RDFS.label, lab))
            if not existing:
                g.add((ann, OA.hasBodyValue, lab))
            n += 1
    print(f"  swapped {n} annotation labels → {len(g):,}")

    # Re-ingest ObliquER
    print("\nRe-ingesting ObliquER …")
    from src.kg_population.ingest_ner_results import (
        load_paragraph_texts, load_para_map, ingest_strategy, RESULTS_BASE,
    )
    para_texts = load_paragraph_texts()
    para_map = load_para_map()
    run_dir = RESULTS_BASE / "oss_v3"
    total_m = total_e = total_se = 0
    for strategy in ("few_shot_v2", "ontology_guided_v2"):
        print(f"  {strategy} …")
        m, e, se = ingest_strategy(g, run_dir, strategy, para_texts, para_map)
        total_m += m; total_e += e; total_se += se
    print(f"  ObliquER: {total_m} mentions, {total_e} entity stubs, {total_se} span errors → {len(g):,}")

    # Re-ingest GT
    print("\nRe-ingesting GT …")
    from src.kg_population.ingest_annotations import (
        load_para_map as gt_para_map_fn, setup_provenance,
        TYPE_TO_CLASSES, CLS_ARTWORK, CLS_EXTRACTED_CONTENT,
        PROP_REFERS_TO, PROP_IN_PARAGRAPH, ANN_DIR, VIEWSARI_KB,
    )
    from rdflib import Literal, URIRef as URef
    from rdflib.namespace import OWL, XSD
    PROV = Namespace("http://www.w3.org/ns/prov#")
    g.bind("vkb", VIEWSARI_KB)
    import csv, json, re
    csv.field_size_limit(sys.maxsize)
    para_map = gt_para_map_fn()
    ann_activity, el_activity = setup_provenance(g)
    ent_count = ment_count = 0
    created_entities = set()
    for vol_dir in sorted(ANN_DIR.iterdir()):
        if not vol_dir.is_dir() or not vol_dir.name.isdigit():
            continue
        vol = vol_dir.name
        for ann_file in sorted(vol_dir.glob("*_enriched.json")):
            slug = ann_file.stem.removesuffix("_enriched")
            with open(ann_file, encoding="utf-8") as f:
                data = json.load(f)
            for para in data:
                pid = str(para.get("paragraph_id", ""))
                pu = para_map.get((vol, pid))
                if not pu: continue
                para_uri = VIEWSARI_KB[pu.replace("viewsari:", "")]
                g.add((ann_activity, PROV.used, para_uri))
                mention_uris = {}
                for m in para.get("mentions", []):
                    mid = m.get("mention_id", "")
                    mtype = m.get("type", "")
                    surface = m.get("surface_form", "")
                    eid = m.get("entity_id")
                    is_ookb = m.get("ookb", False)
                    label = m.get("label") or surface
                    start = m.get("start_offset", 0); end = m.get("end_offset", 0)
                    prefix = f"gt_{slug}_{re.sub(r'[^a-zA-Z0-9]', '_', mid)}"
                    mention_uri = VIEWSARI_KB[prefix]
                    chunk_uri = VIEWSARI_KB[f"{prefix}_chunk"]
                    sel_uri = VIEWSARI_KB[f"{prefix}_selector"]
                    mention_uris[mid] = mention_uri
                    g.add((sel_uri, RDF.type, OA.TextPositionSelector))
                    g.add((sel_uri, OA.start, Literal(start, datatype=XSD.nonNegativeInteger)))
                    g.add((sel_uri, OA.end, Literal(end, datatype=XSD.nonNegativeInteger)))
                    g.add((chunk_uri, RDF.type, DOCO.TextChunk))
                    g.add((chunk_uri, OA.hasSource, para_uri))
                    g.add((chunk_uri, OA.hasSelector, sel_uri))
                    for cls in TYPE_TO_CLASSES.get(mtype, []):
                        g.add((mention_uri, RDF.type, cls))
                    g.add((mention_uri, OA.hasTarget, chunk_uri))
                    g.add((mention_uri, OA.hasBodyValue, Literal(surface)))
                    g.add((mention_uri, PROV.wasGeneratedBy, ann_activity))
                    g.add((mention_uri, PROP_IN_PARAGRAPH, para_uri))
                    ment_count += 1
                    wikidata_id = m.get("wikidata_id") or ""
                    if isinstance(wikidata_id, list): wikidata_id = wikidata_id[0] if wikidata_id else ""
                    ookb_uri = m.get("ookb_uri") or ""
                    wga_id = m.get("wga_id") or ""
                    qid = ""
                    if isinstance(wikidata_id, str) and wikidata_id.startswith("http"):
                        mq = re.search(r"(Q\d+)$", wikidata_id.rstrip("/"))
                        if mq: qid = mq.group(1)
                    entity_key = ""
                    entity_uri = None
                    if qid:
                        entity_key = qid
                        entity_uri = VIEWSARI_KB[qid]
                    elif is_ookb and ookb_uri:
                        fragment = ookb_uri.rsplit("#", 1)[-1] if "#" in ookb_uri else ""
                        if fragment:
                            entity_key = fragment
                            entity_uri = VIEWSARI_KB[fragment]
                    if entity_key and entity_uri:
                        g.add((el_activity, PROV.used, mention_uri))
                        g.add((entity_uri, PROV.wasDerivedFrom, mention_uri))
                        g.add((entity_uri, PROP_IN_PARAGRAPH, para_uri))
                        if entity_key not in created_entities:
                            created_entities.add(entity_key)
                            g.add((entity_uri, RDF.type, CLS_ARTWORK))
                            g.add((entity_uri, RDF.type, CLS_EXTRACTED_CONTENT))
                            g.add((entity_uri, RDF.type, PROV.Entity))
                            g.add((entity_uri, RDFS.label, Literal(label[:200])))
                            g.add((entity_uri, PROV.wasGeneratedBy, el_activity))
                            if qid: g.add((entity_uri, OWL.sameAs, URef(wikidata_id)))
                            pass  # OOKB status is implicit (no owl:sameAs)
                            if wga_id: g.add((entity_uri, RDFS.seeAlso, URef(wga_id)))
                            ent_count += 1
                for m in para.get("mentions", []):
                    mid = m.get("mention_id", "")
                    rt = m.get("refers_to")
                    if rt and mid in mention_uris and rt in mention_uris:
                        g.add((mention_uris[mid], PROP_REFERS_TO, mention_uris[rt]))
    print(f"  GT: {ment_count} mentions, {ent_count} entities → {len(g):,}")

    print(f"\nSerializing → {KG_PATH}")
    g.serialize(destination=str(KG_PATH), format="turtle")
    print(f"Done. Final size: {KG_PATH.stat().st_size/1024/1024:.1f} MB ({len(g):,} triples)")


if __name__ == "__main__":
    main()
