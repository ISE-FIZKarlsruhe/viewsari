"""Build data/kb/kb.json from the consolidated Viewsari KG (data/kg/viewsari_kg.ttl).

Entity classes surfaced:
  - viewsari:0001013  Person (consolidated across biographies)
  - viewsari:0001012  Artwork (per-paragraph ObliquER-extracted entities)
  - viewsari:0001025  Co-occurrence

Run:
    python src/kg_population/build_kb.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from collections import Counter

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
from rdflib.namespace import SKOS, PROV
OA = Namespace("http://www.w3.org/ns/oa#")
ANNOTATION_CLASS = URIRef(OA + "Annotation")

KG_PATH = Path("data/kg/viewsari_kg.ttl")
OUT_PATH = Path("data/kb/kb.json")

VIEWSARI = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/")
VKB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#")
PERSON_CLASS = URIRef(VIEWSARI + "0001013")
ARTWORK_CLASS = URIRef(VIEWSARI + "0001012")
COOC_CLASS = URIRef(VIEWSARI + "0001025")
LOCATED_IN_PARA = URIRef(VIEWSARI + "0001032")
INVOLVES = URIRef(VIEWSARI + "involves")
CLS_EXPLICIT_ART = URIRef(VIEWSARI + "0001020")
CLS_IMPLICIT_ART = URIRef(VIEWSARI + "0001021")

WD_RE = re.compile(r"(Q\d+)$")
PARA_RE = re.compile(r"the_lives_1568_volume-(\d+)_paragraph-(\d+)")


def extract_qid(uri: str) -> str:
    m = WD_RE.search(uri.rstrip("/"))
    return m.group(1) if m else ""


def slug_of(uri: URIRef) -> str:
    s = str(uri)
    return s[len(str(VKB)):] if s.startswith(str(VKB)) else s


def paragraph_location(uri: str) -> tuple[str, str]:
    m = PARA_RE.search(uri)
    return (m.group(1), m.group(2)) if m else ("", "")


def main() -> None:
    print(f"Parsing {KG_PATH} …")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    print(f"  {len(g):,} triples loaded")

    persons: dict[str, dict] = {}
    for s in g.subjects(RDF.type, PERSON_CLASS):
        if not str(s).startswith(str(VKB)):
            continue
        slug = slug_of(s)
        label = next((str(o) for o in g.objects(s, RDFS.label)), slug)
        alt_labels = sorted({str(o) for o in g.objects(s, SKOS.altLabel)})
        wikidata = ""
        for o in g.objects(s, OWL.sameAs):
            qid = extract_qid(str(o))
            if qid:
                wikidata = qid
                break
        gen = next((slug_of(o) for o in g.objects(s, PROV.wasGeneratedBy)), "")
        persons[slug] = {
            "kind": "person",
            "entity_id": slug,
            "label": label,
            "alt_labels": alt_labels,
            "wikidata": wikidata,
            "ookb": not wikidata,
            "generated_by": gen,
        }
    print(f"  persons: {len(persons)}")

    OA_HAS_BODY = URIRef(OA + "hasBody")
    OA_HAS_TARGET = URIRef(OA + "hasTarget")
    OA_HAS_SOURCE = URIRef(OA + "hasSource")
    PROV_DERIVED = URIRef(PROV + "wasDerivedFrom")

    # Map each mention (oa:Annotation with hasBody) to (bio_slug, vol, para, surface, type)
    # so we can list all occurrences for a consolidated entity.
    GT_MENTION_RE = re.compile(r"^gt_([a-z0-9\-]+)_m_(\d+)$")
    OBQ_MENTION_RE = re.compile(r"^(few_shot_v2|ontology_guided_v2)_vol(\d+)_p(\d+)_m_(\d+)$")

    artworks: dict[str, dict] = {}
    for s in g.subjects(RDF.type, ARTWORK_CLASS):
        if not str(s).startswith(str(VKB)):
            continue
        slug = slug_of(s)
        label = next((str(o) for o in g.objects(s, RDFS.label)), slug)
        wikidata = ""
        for o in g.objects(s, OWL.sameAs):
            qid = extract_qid(str(o))
            if qid:
                wikidata = qid
                break
        gen = next((slug_of(o) for o in g.objects(s, PROV.wasGeneratedBy)), "")

        # Collect all paragraph anchors from viewsari:0001032
        paragraphs: list[tuple[str, str]] = []
        seen_paras: set[tuple[str, str]] = set()
        for o in g.objects(s, LOCATED_IN_PARA):
            vp = paragraph_location(str(o))
            if vp[0] and vp not in seen_paras:
                seen_paras.add(vp)
                paragraphs.append(vp)

        artworks[slug] = {
            "kind": "artwork",
            "entity_id": slug,
            "label": label,
            "wikidata": wikidata,
            "ookb": not wikidata,
            "generated_by": gen,
            "vol": paragraphs[0][0] if paragraphs else "",
            "para": paragraphs[0][1] if paragraphs else "",
            "paragraphs": [{"vol": v, "para": p} for v, p in paragraphs],
            "occurrences": [],
        }

    def _record_occurrence(entity_slug: str, ann: URIRef) -> None:
        ann_slug = slug_of(ann)
        surface = next((str(o) for o in g.objects(ann, URIRef(OA + "hasBodyValue"))), "")
        bio_slug = ""
        vol = ""
        para = ""
        m_gt = GT_MENTION_RE.match(ann_slug)
        m_oq = OBQ_MENTION_RE.match(ann_slug)
        if m_gt:
            bio_slug = m_gt.group(1)
        elif m_oq:
            vol, para = m_oq.group(2), m_oq.group(3)
        if not vol:
            for p_uri in g.objects(ann, LOCATED_IN_PARA):
                v, pr = paragraph_location(str(p_uri))
                if v:
                    vol, para = v, pr
                    break
        artworks[entity_slug]["occurrences"].append({
            "bio": bio_slug,
            "vol": vol,
            "para": para,
            "surface": surface[:120],
            "mention": ann_slug,
        })

    # GT: entity prov:wasDerivedFrom mention
    for ent_uri in [URIRef(str(VKB) + k) for k in artworks.keys()]:
        for mention in g.objects(ent_uri, PROV_DERIVED):
            _record_occurrence(slug_of(ent_uri), mention)

    # ObliquER (legacy): mention oa:hasBody entity
    for ann in g.subjects(OA_HAS_BODY, None):
        for body in g.objects(ann, OA_HAS_BODY):
            body_slug = slug_of(body)
            if body_slug in artworks:
                _record_occurrence(body_slug, ann)

    for aw in artworks.values():
        aw["occurrences"].sort(key=lambda o: (o.get("vol") or "", o.get("para") or "", o.get("bio") or ""))

    print(f"  artworks: {len(artworks)}")

    cooccurrences: dict[str, dict] = {}
    for s in g.subjects(RDF.type, COOC_CLASS):
        if not str(s).startswith(str(VKB)):
            continue
        slug = slug_of(s)
        label = next((str(o) for o in g.objects(s, RDFS.label)), slug)
        involves = sorted({slug_of(o) for o in g.objects(s, INVOLVES)})
        gen = next((slug_of(o) for o in g.objects(s, PROV.wasGeneratedBy)), "")
        cooccurrences[slug] = {
            "kind": "cooccurrence",
            "entity_id": slug,
            "label": label,
            "involves": involves,
            "generated_by": gen,
        }
    print(f"  cooccurrences: {len(cooccurrences)}")

    # ObliquER explicit & implicit mentions (viewsari:0001020 / 0001021)
    OBQ_MENTION_RE2 = re.compile(r"^(few_shot_v2|ontology_guided_v2)_vol(\d+)_p(\d+)_")
    OA_BODY_VALUE = URIRef(OA + "hasBodyValue")

    def _build_obq_mentions(cls_uri: URIRef, kind_label: str) -> list[dict]:
        items = []
        for s in g.subjects(RDF.type, cls_uri):
            sl = slug_of(s)
            m = OBQ_MENTION_RE2.match(sl)
            if not m:
                continue
            strategy = m.group(1)
            vol, para = m.group(2), m.group(3)
            surface = next((str(o) for o in g.objects(s, OA_BODY_VALUE)), "")
            gen = next((slug_of(o) for o in g.objects(s, PROV.wasGeneratedBy)), "")
            items.append({
                "kind": kind_label,
                "mention_id": sl,
                "surface": surface[:200],
                "strategy": strategy.replace("_v2", "").replace("_", " "),
                "vol": vol,
                "para": para,
                "generated_by": gen,
            })
        items.sort(key=lambda x: (x["vol"], x["para"], x["surface"].lower()))
        return items

    obq_explicit = _build_obq_mentions(CLS_EXPLICIT_ART, "explicit mention")
    print(f"  obliquer explicit mentions: {len(obq_explicit)}")
    obq_implicit = _build_obq_mentions(CLS_IMPLICIT_ART, "implicit mention")
    print(f"  obliquer implicit mentions: {len(obq_implicit)}")

    # Count oa:Annotation instances per provenance activity
    mention_counts: Counter = Counter()
    for ann in g.subjects(RDF.type, ANNOTATION_CLASS):
        for act in g.objects(ann, PROV.wasGeneratedBy):
            mention_counts[slug_of(act)] += 1

    # Group runs into sources (GT / ObliquER / other) for UI filtering
    def categorize(run_slug: str) -> str:
        if run_slug.startswith("ground_truth_"):
            return "gt"
        if (run_slug.startswith("ner_run_") or run_slug.startswith("el_run_")
                or run_slug.startswith("obliquer_")):
            return "obliquer"
        return "other"

    prov_runs = sorted({
        e["generated_by"]
        for bucket in (persons, artworks, cooccurrences)
        for e in bucket.values()
        if e.get("generated_by")
    } | set(mention_counts.keys()))

    sources: dict[str, dict] = {}
    for run in prov_runs:
        cat = categorize(run)
        sources.setdefault(cat, {"runs": [], "mentions": 0, "artworks": 0})
        sources[cat]["runs"].append(run)
        sources[cat]["mentions"] += mention_counts.get(run, 0)
    for aw in artworks.values():
        cat = categorize(aw.get("generated_by", ""))
        sources.setdefault(cat, {"runs": [], "mentions": 0, "artworks": 0})
        sources[cat]["artworks"] += 1
    for aw in artworks.values():
        aw["source"] = categorize(aw.get("generated_by", ""))

    data = {
        "counts": {
            "persons": len(persons),
            "artworks": len(artworks),
            "cooccurrences": len(cooccurrences),
            "total": len(persons) + len(artworks) + len(cooccurrences),
        },
        "persons_stats": {
            "total": len(persons),
            "wd": sum(1 for e in persons.values() if e["wikidata"]),
            "ookb": sum(1 for e in persons.values() if e["ookb"]),
            "alt_labels": sum(len(e["alt_labels"]) for e in persons.values()),
        },
        "artworks_stats": {
            "total": len(artworks),
            "wd": sum(1 for e in artworks.values() if e["wikidata"]),
            "ookb": sum(1 for e in artworks.values() if e["ookb"]),
        },
        "provenance_runs": prov_runs,
        "mention_counts": dict(mention_counts),
        "sources": sources,
        "total_mentions": sum(mention_counts.values()),
        "persons": persons,
        "artworks": artworks,
        "cooccurrences": cooccurrences,
        "obq_explicit": obq_explicit,
        "obq_implicit": obq_implicit,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
