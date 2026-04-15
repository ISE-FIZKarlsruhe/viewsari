from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

csv.field_size_limit(sys.maxsize)

# ── Namespaces ────────────────────────────────────────────────────────────────

VIEWSARI    = Namespace("https://viewsari.ise.fiz-karlsruhe.de/ontology/#")
VIEWSARI_KB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/")
DOCO        = Namespace("http://purl.org/spar/doco/")
PROV        = Namespace("http://www.w3.org/ns/prov#")
OA          = Namespace("http://www.w3.org/ns/oa#")

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE        = Path(__file__).resolve().parent.parent
KG_FILE     = BASE / "data" / "kg" / "viewsari_kg.ttl"
RESULTS_BASE = BASE / "obliquer" / "data" / "viewsari" / "prompting_results"
VOLUMES_DIR = BASE / "obliquer" / "data" / "viewsari" / "volumes"
PARA_CSV    = BASE / "data" / "kg_foundation" / "viewsari_paragraphs.csv"

# ── Ontology class IRIs ───────────────────────────────────────────────────────

CLS_MENTION              = VIEWSARI["0001026"]
CLS_EXPLICIT_MENTION     = VIEWSARI["0001017"]
CLS_IMPLICIT_MENTION     = VIEWSARI["0001016"]
CLS_EXPLICIT_ART_MENTION = VIEWSARI["0001020"]
CLS_IMPLICIT_ART_MENTION = VIEWSARI["0001021"]
CLS_COREFERENT           = VIEWSARI["0001018"]
CLS_GENERIC              = VIEWSARI["0001019"]
CLS_ARTWORK              = VIEWSARI["0001012"]
CLS_NER_ACTIVITY         = VIEWSARI["0001022"]
CLS_EXTRACTED_CONTENT    = VIEWSARI["0001033"]

PROP_REFERS_TO           = VIEWSARI["0001035"]
PROP_IN_PARAGRAPH        = VIEWSARI["0001032"]

TYPE_TO_CLASSES = {
    "explicit artwork mention":  [CLS_MENTION, CLS_EXPLICIT_MENTION, CLS_EXPLICIT_ART_MENTION,
                                   OA.Annotation, PROV.Entity],
    "implicit artwork mention":  [CLS_MENTION, CLS_IMPLICIT_MENTION, CLS_IMPLICIT_ART_MENTION,
                                   OA.Annotation, PROV.Entity],
    "coreferent":                [CLS_MENTION, CLS_COREFERENT, OA.Annotation, PROV.Entity],
    "generic mention":           [CLS_MENTION, CLS_GENERIC, OA.Annotation, PROV.Entity],
    "generic collection mention":[CLS_MENTION, CLS_GENERIC, OA.Annotation, PROV.Entity],
}


# ── Span resolution ───────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Replace every non-alphanumeric character with '_' (length-preserving)."""
    return re.sub(r"[^a-zA-Z0-9]", "_", text)


def resolve_span(in_text_annotation: str, paragraph_text: str, surface_form: str):
    """
    Resolve (start, end) character offsets from a <<surface_form>> in-text
    annotation against the full paragraph text.

    The LLM annotates the surface form with <<...>> markers inside a short
    context excerpt from the paragraph. Resolution steps:
      1. Record the position of << within the annotation.
      2. Strip << and >> to get the clean context string.
      3. Find the clean context in the paragraph (normalised comparison).
      4. Offset by the <<-position to land on the surface form.
      5. Fall back to a direct substring search if the context isn't found.

    Returns (start, end) or None on failure.
    """
    if not paragraph_text or not surface_form:
        return None

    # Remove Unicode/ASCII ellipses used to truncate the context
    annotation = re.sub(r"…|\.\.\.", "", in_text_annotation).strip()

    marker_pos = annotation.find("<<")
    if marker_pos != -1:
        clean_annotation = annotation.replace("<<", "").replace(">>", "").strip()
    else:
        marker_pos = 0
        clean_annotation = annotation

    norm_para = _normalize(paragraph_text)
    norm_ann  = _normalize(clean_annotation)
    norm_surf = _normalize(surface_form)

    context_pos = norm_para.find(norm_ann)
    if context_pos != -1:
        start = context_pos + marker_pos
        end   = start + len(surface_form)
        # Verify and try small offsets for Unicode/whitespace normalisation drift
        for delta in range(0, 4):
            for sign in (0, 1, -1):
                s = start + sign * delta
                e = s + len(surface_form)
                if s >= 0 and paragraph_text[s:e] == surface_form:
                    return s, e

    # Fallback: direct substring search
    idx = paragraph_text.find(surface_form)
    if idx != -1:
        return idx, idx + len(surface_form)

    # Last resort: normalised direct search
    norm_idx = norm_para.find(norm_surf)
    if norm_idx != -1:
        return norm_idx, norm_idx + len(surface_form)

    return None


# ── Data loading ──────────────────────────────────────────────────────────────

def load_paragraph_texts() -> dict:
    """Return {(vol, paragraph_id_str): text} from viewsari_paragraphs.csv.

    Uses the KG-foundation CSV rather than the obliquer volumes CSVs so that
    oa:TextPositionSelector offsets are anchored to the exact text stored in
    the KG under viewsari:hasText.
    """
    texts = {}
    with open(PARA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vol = row.get("vol", "")
            pid = str(int(row.get("paragraph_id", 0)))
            texts[(vol, pid)] = row.get("viewsari:has text", "")
    return texts


def load_para_map() -> dict:
    """Return {(vol, paragraph_id_str): instance_id_str} from kg_foundation CSV."""
    para_map = {}
    with open(PARA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vol = row.get("vol", "")
            pid = str(int(row.get("paragraph_id", 0)))
            para_map[(vol, pid)] = row.get("instance_id", "")
    return para_map


def para_uri_from_instance_id(instance_id: str) -> URIRef:
    """Convert 'viewsari:the_lives_1568_…' to its kb/ URIRef."""
    local = instance_id.replace("viewsari:", "").replace("vkb:", "")
    return VIEWSARI_KB[local]


def load_provenance(strategy_dir: Path) -> list:
    prov_file = strategy_dir / "provenance.jsonl"
    if not prov_file.exists():
        return []
    entries = []
    with open(prov_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


# ── Provenance triples ────────────────────────────────────────────────────────

def create_activity(g: Graph, strategy: str, prov_entries: list) -> URIRef:
    """
    Create a prov:Activity + prov:SoftwareAgent for the strategy run.
    Returns the activity URIRef.
    """
    slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)
    activity_uri = VIEWSARI_KB[f"ner_run_{slug}"]

    g.add((activity_uri, RDF.type, PROV.Activity))
    g.add((activity_uri, RDF.type, CLS_NER_ACTIVITY))
    g.add((activity_uri, RDFS.label, Literal(f"ObliquER NER Run — {strategy}")))

    if prov_entries:
        model_name = prov_entries[0].get("model", "")
        if model_name:
            agent_slug = re.sub(r"[^a-zA-Z0-9]", "_", model_name)
            agent_uri  = VIEWSARI_KB[f"llm_agent_{agent_slug}"]
            g.add((agent_uri, RDF.type, PROV.SoftwareAgent))
            g.add((agent_uri, RDFS.label, Literal(model_name)))
            g.add((activity_uri, PROV.wasAssociatedWith, agent_uri))

        starts = [e["started_at"] for e in prov_entries if e.get("started_at")]
        ends   = [e["ended_at"]   for e in prov_entries if e.get("ended_at")]
        if starts:
            g.add((activity_uri, PROV.startedAtTime,
                   Literal(min(starts), datatype=XSD.dateTime)))
        if ends:
            g.add((activity_uri, PROV.endedAtTime,
                   Literal(max(ends), datatype=XSD.dateTime)))

    return activity_uri


# ── Main ingestion ────────────────────────────────────────────────────────────

def ingest_strategy(g: Graph, run_dir: Path, strategy: str,
                    para_texts: dict, para_map: dict) -> tuple[int, int, int]:
    strategy_dir = run_dir / strategy
    if not strategy_dir.exists():
        print(f"  [skip] {strategy_dir} not found")
        return 0, 0, 0

    prov_entries = load_provenance(strategy_dir)
    activity_uri = create_activity(g, strategy, prov_entries)

    mention_count = entity_count = span_errors = 0
    strat_slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)

    for vol_dir in sorted(strategy_dir.iterdir()):
        if not vol_dir.is_dir():
            continue
        vol = vol_dir.name.split("_")[-1]  # "volume_1" → "1"

        for response_file in sorted(vol_dir.glob("*.response.json")):
            # "paragraph_003_004.response.json" → paragraph_id = 4
            pid = str(int(response_file.name.replace(".response.json", "").split("_")[-1]))

            para_text     = para_texts.get((vol, pid), "")
            instance_id   = para_map.get((vol, pid), "")
            if not instance_id:
                continue
            para_uri = para_uri_from_instance_id(instance_id)

            try:
                raw = response_file.read_text(encoding="utf-8")
                s, e = raw.find("["), raw.rfind("]") + 1
                if s == -1 or e == 0:
                    continue
                mentions_data = json.loads(raw[s:e])
            except (json.JSONDecodeError, ValueError):
                continue

            # Track within-paragraph URIs for coreferent wiring
            mention_uris: dict[str, URIRef] = {}
            entity_seen:  set[str] = set()

            for m in mentions_data:
                mid     = m.get("mention_id", "")
                mtype   = m.get("type", "")
                surface = m.get("surface_form", "")
                eid     = m.get("entity_id")
                in_text = m.get("in-text span annotation", "")

                prefix       = f"{strat_slug}_vol{vol}_p{pid}_{mid}"
                mention_uri  = VIEWSARI_KB[prefix]
                chunk_uri    = VIEWSARI_KB[f"{prefix}_chunk"]
                sel_uri      = VIEWSARI_KB[f"{prefix}_selector"]
                mention_uris[mid] = mention_uri

                # Span resolution
                span = resolve_span(in_text, para_text, surface) if (para_text and in_text) else None
                if span is None:
                    span_errors += 1
                start_off, end_off = span if span else (0, 0)

                # oa:TextPositionSelector
                g.add((sel_uri, RDF.type, OA.TextPositionSelector))
                g.add((sel_uri, OA.start, Literal(start_off, datatype=XSD.nonNegativeInteger)))
                g.add((sel_uri, OA.end,   Literal(end_off,   datatype=XSD.nonNegativeInteger)))

                # doco:TextChunk
                g.add((chunk_uri, RDF.type, DOCO.TextChunk))
                g.add((chunk_uri, OA.hasSource,   para_uri))
                g.add((chunk_uri, OA.hasSelector, sel_uri))
                g.add((chunk_uri, RDFS.label, Literal(surface[:100])))

                # Mention annotation
                for cls in TYPE_TO_CLASSES.get(mtype, [CLS_MENTION, OA.Annotation, PROV.Entity]):
                    g.add((mention_uri, RDF.type, cls))
                g.add((mention_uri, OA.hasTarget,         chunk_uri))
                g.add((mention_uri, RDFS.label,           Literal(surface[:100])))
                g.add((mention_uri, PROV.wasGeneratedBy,  activity_uri))
                g.add((mention_uri, PROP_IN_PARAGRAPH,    para_uri))
                mention_count += 1

                # Artwork entity stub (non-generic mentions with a cluster id)
                if eid and mtype not in ("generic mention", "generic collection mention"):
                    eid_key    = f"{strat_slug}_vol{vol}_p{pid}_{re.sub(r'[^a-zA-Z0-9]', '_', eid)}"
                    entity_uri = VIEWSARI_KB[eid_key]
                    g.add((mention_uri, OA.hasBody, entity_uri))

                    if eid_key not in entity_seen:
                        entity_seen.add(eid_key)
                        g.add((entity_uri, RDF.type, CLS_ARTWORK))
                        g.add((entity_uri, RDF.type, CLS_EXTRACTED_CONTENT))
                        g.add((entity_uri, RDFS.label,          Literal(surface[:200])))
                        g.add((entity_uri, PROV.wasGeneratedBy, activity_uri))
                        g.add((entity_uri, PROP_IN_PARAGRAPH,   para_uri))
                        entity_count += 1

            # Wire coreferent → antecedent links
            for m in mentions_data:
                mid       = m.get("mention_id", "")
                refers_to = m.get("refers_to")
                if refers_to and mid in mention_uris and refers_to in mention_uris:
                    g.add((mention_uris[mid], PROP_REFERS_TO, mention_uris[refers_to]))

    return mention_count, entity_count, span_errors


def main():
    parser = argparse.ArgumentParser(description="Ingest ObliquER NER results into the Viewsari KG.")
    parser.add_argument("--run", default="oss_v3",
                        help="Name of the results run directory under prompting_results/ (default: oss_v3)")
    parser.add_argument("--strategies", nargs="+",
                        default=["few_shot_v2", "ontology_guided_v2"],
                        help="Strategy subdirectories to ingest (default: few_shot_v2 ontology_guided_v2)")
    args = parser.parse_args()

    run_dir = RESULTS_BASE / args.run
    if not run_dir.exists():
        print(f"Error: run directory not found: {run_dir}")
        sys.exit(1)

    print("Loading existing KG …")
    g = Graph()
    g.parse(str(KG_FILE), format="turtle")
    g.bind("viewsari", VIEWSARI)
    g.bind("vkb",      VIEWSARI_KB)
    g.bind("doco",     DOCO)
    g.bind("prov",     PROV)
    g.bind("oa",       OA)
    initial = len(g)
    print(f"  {initial} triples loaded")

    print("Loading paragraph index …")
    para_texts = load_paragraph_texts()
    para_map   = load_para_map()
    print(f"  {len(para_texts)} paragraph texts, {len(para_map)} KG paragraph URIs")

    total_mentions = total_entities = total_span_errors = 0

    for strategy in args.strategies:
        print(f"\nIngesting {args.run}/{strategy} …")
        m, e, se = ingest_strategy(g, run_dir, strategy, para_texts, para_map)
        total_mentions     += m
        total_entities     += e
        total_span_errors  += se

    new_triples = len(g) - initial
    print(f"\nIngested:")
    print(f"  {total_mentions} mentions across {len(args.strategies)} strategies")
    print(f"  {total_entities} artwork entity stubs")
    print(f"  {total_span_errors} span resolution failures")
    print(f"  {new_triples} new triples added")
    print(f"  {len(g)} total triples")

    print(f"\nSerializing to {KG_FILE} …")
    g.serialize(destination=str(KG_FILE), format="turtle")
    size_mb = KG_FILE.stat().st_size / (1024 * 1024)
    print(f"Done — {len(g)} triples, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
