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
VIEWSARI_KB = Namespace("https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#")
DOCO        = Namespace("http://purl.org/spar/doco/")
PROV        = Namespace("http://www.w3.org/ns/prov#")
OA          = Namespace("http://www.w3.org/ns/oa#")

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE        = Path(__file__).resolve().parent.parent.parent
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
CLS_EL_ACTIVITY          = VIEWSARI["0001023"]
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


def load_provenance(strategy_dir: Path) -> dict[tuple[str, str], dict]:
    """Return {(vol, prompt_file): provenance_entry} from provenance.jsonl."""
    prov_file = strategy_dir / "provenance.jsonl"
    out: dict[tuple[str, str], dict] = {}
    if not prov_file.exists():
        return out
    with open(prov_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            vol = e.get("volume", "").replace("volume_", "")
            pf = e.get("prompt_file", "")
            if vol and pf:
                out[(vol, pf)] = e
    return out


# ── Provenance triples ────────────────────────────────────────────────────────

MODEL_PAGES = {
    "openai/gpt-oss-120b": "https://huggingface.co/openai/gpt-oss-120b",
}


def _agent_uri_for(g: Graph, model_name: str) -> URIRef:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", model_name)
    uri = VIEWSARI_KB[f"llm_agent_{slug}"]
    g.add((uri, RDF.type, PROV.SoftwareAgent))
    g.add((uri, RDFS.label, Literal(model_name)))
    page = MODEL_PAGES.get(model_name)
    if page:
        g.add((uri, RDFS.seeAlso, URIRef(page)))
    return uri


def create_parent_activity(g: Graph, strategy: str, prov_index: dict) -> URIRef:
    """Create the umbrella prov:Activity for the strategy run."""
    slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)
    parent = VIEWSARI_KB[f"ner_run_{slug}"]
    g.add((parent, RDF.type, PROV.Activity))
    g.add((parent, RDF.type, CLS_NER_ACTIVITY))
    g.add((parent, RDFS.label, Literal(f"ObliquER NER Run — {strategy}")))

    if prov_index:
        any_entry = next(iter(prov_index.values()))
        model_name = any_entry.get("model", "")
        if model_name:
            g.add((parent, PROV.wasAssociatedWith, _agent_uri_for(g, model_name)))
        starts = [e["started_at"] for e in prov_index.values() if e.get("started_at")]
        ends   = [e["ended_at"]   for e in prov_index.values() if e.get("ended_at")]
        if starts:
            g.add((parent, PROV.startedAtTime, Literal(min(starts), datatype=XSD.dateTime)))
        if ends:
            g.add((parent, PROV.endedAtTime,   Literal(max(ends),   datatype=XSD.dateTime)))
    return parent


def create_prompt_entity(g: Graph, strategy: str, vol: str, nnn: str, mmm: str,
                          prompt_path: Path) -> URIRef:
    """Create a prov:Entity for the prompt text and return its URI."""
    strat_slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)
    uri = VIEWSARI_KB[f"prompt_{strat_slug}_vol{vol}_p{nnn}_p{mmm}"]
    g.add((uri, RDF.type, PROV.Entity))
    g.add((uri, RDFS.label,
           Literal(f"Prompt — {strategy}, vol {vol}, paragraphs {nnn}-{mmm}")))
    if prompt_path.exists():
        text = prompt_path.read_text(encoding="utf-8")
        g.add((uri, RDFS.comment, Literal(text)))
    return uri


def create_extraction_activity(
    g: Graph, strategy: str, vol: str, nnn: str, mmm: str,
    parent: URIRef, pmeta: dict,
    used_paragraphs: list[URIRef],
    prompt_uri: URIRef | None = None,
) -> URIRef:
    """Create a per-extraction NER sub-activity. Returns its URI."""
    strat_slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)
    suffix = f"vol{vol}_p{nnn}_p{mmm}"
    ner_sub = VIEWSARI_KB[f"ner_run_{strat_slug}_{suffix}"]

    g.add((ner_sub, RDF.type, PROV.Activity))
    g.add((ner_sub, RDF.type, CLS_NER_ACTIVITY))
    g.add((ner_sub, RDFS.label, Literal(f"NER extraction — {strategy}, vol {vol}, paragraphs {nnn}-{mmm}")))
    g.add((ner_sub, PROV.wasInformedBy, parent))
    for p_uri in used_paragraphs:
        g.add((ner_sub, PROV.used, p_uri))
    if prompt_uri is not None:
        g.add((ner_sub, PROV.used, prompt_uri))
    if pmeta:
        if pmeta.get("started_at"):
            g.add((ner_sub, PROV.startedAtTime, Literal(pmeta["started_at"], datatype=XSD.dateTime)))
        if pmeta.get("ended_at"):
            g.add((ner_sub, PROV.endedAtTime,   Literal(pmeta["ended_at"],   datatype=XSD.dateTime)))
        if pmeta.get("model"):
            g.add((ner_sub, PROV.wasAssociatedWith, _agent_uri_for(g, pmeta["model"])))
    return ner_sub


# ── Main ingestion ────────────────────────────────────────────────────────────

def ingest_strategy(g: Graph, run_dir: Path, strategy: str,
                    para_texts: dict, para_map: dict) -> tuple[int, int, int]:
    strategy_dir = run_dir / strategy
    if not strategy_dir.exists():
        print(f"  [skip] {strategy_dir} not found")
        return 0, 0, 0

    prov_index = load_provenance(strategy_dir)
    parent_activity = create_parent_activity(g, strategy, prov_index)

    mention_count = entity_count = span_errors = 0
    strat_slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)

    for vol_dir in sorted(strategy_dir.iterdir()):
        if not vol_dir.is_dir():
            continue
        vol = vol_dir.name.split("_")[-1]

        for response_file in sorted(vol_dir.glob("*.response.json")):
            # "paragraph_003_004.response.json" → context pid 3, target pid 4
            stem = response_file.name.replace(".response.json", "")
            parts = stem.split("_")
            if len(parts) < 3:
                continue
            nnn, mmm = parts[-2], parts[-1]
            target_pid = str(int(mmm))
            context_pid = str(int(nnn)) if int(nnn) > 0 else None

            para_text   = para_texts.get((vol, target_pid), "")
            instance_id = para_map.get((vol, target_pid), "")
            if not instance_id:
                continue
            target_para_uri = para_uri_from_instance_id(instance_id)

            used_paragraphs = [target_para_uri]
            if context_pid:
                ctx_iid = para_map.get((vol, context_pid), "")
                if ctx_iid:
                    used_paragraphs.append(para_uri_from_instance_id(ctx_iid))

            pmeta = prov_index.get((vol, f"{stem}.j2"), {})
            prompt_path = vol_dir / f"{stem}.j2"
            prompt_uri = create_prompt_entity(g, strategy, vol, nnn, mmm, prompt_path)
            ner_sub = create_extraction_activity(
                g, strategy, vol, nnn, mmm, parent_activity, pmeta,
                used_paragraphs, prompt_uri=prompt_uri,
            )

            try:
                raw = response_file.read_text(encoding="utf-8")
                s, e = raw.find("["), raw.rfind("]") + 1
                if s == -1 or e == 0:
                    continue
                mentions_data = json.loads(raw[s:e])
            except (json.JSONDecodeError, ValueError):
                continue

            mention_uris: dict[str, URIRef] = {}

            for m in mentions_data:
                mid     = m.get("mention_id", "")
                mtype   = m.get("type", "")
                surface = m.get("surface_form", "")
                in_text = m.get("in-text span annotation", "")

                prefix       = f"{strat_slug}_vol{vol}_p{target_pid}_{mid}"
                mention_uri  = VIEWSARI_KB[prefix]
                chunk_uri    = VIEWSARI_KB[f"{prefix}_chunk"]
                sel_uri      = VIEWSARI_KB[f"{prefix}_selector"]
                mention_uris[mid] = mention_uri

                span = resolve_span(in_text, para_text, surface) if (para_text and in_text) else None
                if span is None:
                    span_errors += 1
                start_off, end_off = span if span else (0, 0)

                g.add((sel_uri, RDF.type, OA.TextPositionSelector))
                g.add((sel_uri, OA.start, Literal(start_off, datatype=XSD.nonNegativeInteger)))
                g.add((sel_uri, OA.end,   Literal(end_off,   datatype=XSD.nonNegativeInteger)))

                g.add((chunk_uri, RDF.type, DOCO.TextChunk))
                g.add((chunk_uri, OA.hasSource,   target_para_uri))
                g.add((chunk_uri, OA.hasSelector, sel_uri))

                for cls in TYPE_TO_CLASSES.get(mtype, [CLS_MENTION, OA.Annotation, PROV.Entity]):
                    g.add((mention_uri, RDF.type, cls))
                g.add((mention_uri, OA.hasTarget,         chunk_uri))
                g.add((mention_uri, OA.hasBodyValue,      Literal(surface)))
                g.add((mention_uri, PROV.wasGeneratedBy,  ner_sub))
                g.add((mention_uri, PROP_IN_PARAGRAPH,    target_para_uri))
                mention_count += 1

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
