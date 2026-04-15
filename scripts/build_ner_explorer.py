"""
build_ner_explorer.py
=====================
Pre-computes D3-ready subgraph JSON files for the ObliquER Extraction Explorer
from the raw NER .response.json results.

For each biography and each strategy, one JSON file is written:
    data/kg/explorer/ner/<strategy>/bio_<slug>.json

Plus one index file per strategy:
    data/kg/explorer/ner/<strategy>/index.json

Graph structure per biography
──────────────────────────────
  biography ──hasPartParagraph──► paragraph (for each para with ≥1 mention)
  paragraph ──contains──► mention  (colored by type)
  mention   ──oa:hasBody──► entity  (artwork cluster, if non-generic)
  entity    ──coref──► entity       (same-paragraph entity chains)
  mention   ──prov:wasGeneratedBy──► activity
  activity  ──prov:wasAssociatedWith──► agent

Usage:
    python scripts/build_ner_explorer.py
    python scripts/build_ner_explorer.py --run oss_v3
    python scripts/build_ner_explorer.py --run oss_v3 --strategies few_shot_v2
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

BASE          = Path(__file__).resolve().parent.parent
RESULTS_BASE  = BASE / "obliquer" / "data" / "viewsari" / "prompting_results"
PARA_CSV      = BASE / "data" / "kg_foundation" / "viewsari_paragraphs.csv"
BIO_CSV       = BASE / "data" / "kg_foundation" / "viewsari_biographies.csv"
OUT_BASE      = BASE / "data" / "kg" / "explorer" / "ner"


# ── Node colour palette (mirrors the template legend) ────────────────────────
NODE_COLORS = {
    "biography":         {"s": "#7C3AED", "f": "#F5F3FF", "t": "#6D28D9"},
    "paragraph":         {"s": "#6B7280", "f": "#F3F4F6", "t": "#374151"},
    "explicit":          {"s": "#B45309", "f": "#FFFBEB", "t": "#92400E"},
    "implicit":          {"s": "#0369A1", "f": "#EFF6FF", "t": "#1E40AF"},
    "coreferent":        {"s": "#9333EA", "f": "#FAF5FF", "t": "#7E22CE"},
    "generic":           {"s": "#9CA3AF", "f": "#F9FAFB", "t": "#6B7280"},
    "entity":            {"s": "#D97706", "f": "#FFF7ED", "t": "#B45309"},
    "activity":          {"s": "#0F766E", "f": "#F0FDF9", "t": "#115E59"},
    "agent":             {"s": "#374151", "f": "#F3F4F6", "t": "#111827"},
}


def _mention_subtype(mtype: str) -> str:
    if "explicit" in mtype:
        return "explicit"
    if "implicit" in mtype:
        return "implicit"
    if "coref" in mtype:
        return "coreferent"
    return "generic"


# ── CSV loading ───────────────────────────────────────────────────────────────

def load_para_index() -> tuple[dict, dict]:
    """
    Returns:
      para_to_bio:  {(vol, pid_str): slug}
      bio_labels:   {slug: display_label}
    """
    para_to_bio: dict[tuple, str] = {}
    bio_labels: dict[str, str] = {}

    # biography labels from viewsari_biographies.csv
    with open(BIO_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("rdf:type") != "viewsari:biography":
                continue
            iid = row.get("instance_id", "")
            label = row.get("rdfs:label", "")
            slug = iid.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
            bio_labels[slug] = label

    # paragraph → biography mapping
    with open(PARA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vol = row.get("vol", "")
            pid = str(int(row.get("paragraph_id", 0)))
            bio_uri = row.get("frbr:is part of", "")
            slug = bio_uri.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
            para_to_bio[(vol, pid)] = slug

    return para_to_bio, bio_labels


def load_provenance(strategy_dir: Path) -> dict:
    """Return {model: str, started_at: str, ended_at: str} summary."""
    prov_file = strategy_dir / "provenance.jsonl"
    if not prov_file.exists():
        return {}
    entries = []
    with open(prov_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not entries:
        return {}
    model = entries[0].get("model", "unknown model")
    starts = [e["started_at"] for e in entries if e.get("started_at")]
    ends   = [e["ended_at"]   for e in entries if e.get("ended_at")]
    return {
        "model":      model,
        "started_at": min(starts) if starts else "",
        "ended_at":   max(ends)   if ends   else "",
        "paragraphs": len(entries),
    }


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_bio_graph(
    slug: str,
    bio_label: str,
    paragraphs: list[dict],      # [{vol, pid, mentions: [...raw response items...]}]
    strategy: str,
    prov: dict,
) -> dict:
    """
    Build a D3-ready {nodes, edges} graph for one biography and strategy.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(nid: str, ntype: str, label: str, **extra):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, **extra}

    # ── Shared provenance nodes ───────────────────────────────────────
    strat_slug  = re.sub(r"[^a-zA-Z0-9]", "_", strategy)
    activity_id = f"activity_{strat_slug}"
    agent_id    = f"agent_{re.sub(r'[^a-zA-Z0-9]', '_', prov.get('model',''))}"

    add_node(activity_id, "activity",
             f"ObliquER NER — {strategy}",
             model=prov.get("model", ""),
             started_at=prov.get("started_at", ""),
             ended_at=prov.get("ended_at", ""),
             paragraphs_processed=prov.get("paragraphs", 0))

    add_node(agent_id, "agent",
             prov.get("model", "LLM agent"))

    edges.append({"source": activity_id, "target": agent_id,
                  "label": "wasAssociatedWith"})

    # ── Biography node ────────────────────────────────────────────────
    bio_id = f"bio_{slug}"
    add_node(bio_id, "biography", bio_label or slug.title())

    # ── Paragraphs + mentions ─────────────────────────────────────────
    for para in paragraphs:
        vol      = para["vol"]
        pid      = para["pid"]
        mentions = para["mentions"]
        if not mentions:
            continue  # skip paragraphs with no extracted mentions

        para_id = f"para_{vol}_{pid}"
        add_node(para_id, "paragraph", f"§{pid}")
        edges.append({"source": bio_id, "target": para_id,
                      "label": "hasPartParagraph"})

        # Track entity nodes created in this paragraph (entity_id is paragraph-local)
        para_entities: dict[str, str] = {}  # entity_id → node_id

        for m in mentions:
            mid     = m.get("mention_id", "")
            mtype   = m.get("type", "")
            surface = m.get("surface_form", "")[:80]
            eid     = m.get("entity_id")
            refers_to = m.get("refers_to")
            subtype = _mention_subtype(mtype)

            mention_id = f"mention_{strat_slug}_{vol}_{pid}_{mid}"
            add_node(mention_id, subtype,
                     surface,
                     mention_id=mid,
                     full_type=mtype,
                     paragraph=pid,
                     vol=vol)

            edges.append({"source": para_id, "target": mention_id,
                          "label": "contains"})
            edges.append({"source": mention_id, "target": activity_id,
                          "label": "wasGeneratedBy", "dashed": True})

            # Entity cluster (non-generic only)
            if eid and subtype != "generic":
                entity_node_id = f"entity_{strat_slug}_{vol}_{pid}_{re.sub(r'[^a-zA-Z0-9]','_',eid)}"
                if entity_node_id not in para_entities.values():
                    add_node(entity_node_id, "entity", surface[:60],
                             entity_id=eid, para=pid)
                para_entities[eid] = entity_node_id
                edges.append({"source": mention_id, "target": entity_node_id,
                              "label": "refersTo"})

            # Coreferent link
            if refers_to:
                ref_mid = f"mention_{strat_slug}_{vol}_{pid}_{refers_to}"
                # Only add if the antecedent will also be in the graph
                edges.append({"source": mention_id, "target": ref_mid,
                              "label": "refersTo", "dashed": True})

    return {"nodes": list(nodes.values()), "edges": edges}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pre-compute ObliquER NER explorer graphs.")
    parser.add_argument("--run", default="oss_v3")
    parser.add_argument("--strategies", nargs="+",
                        default=["few_shot_v2", "ontology_guided_v2"])
    args = parser.parse_args()

    run_dir = RESULTS_BASE / args.run
    if not run_dir.exists():
        print(f"Error: run directory not found: {run_dir}")
        sys.exit(1)

    print("Loading paragraph index …")
    para_to_bio, bio_labels = load_para_index()
    print(f"  {len(para_to_bio)} paragraphs, "
          f"{len(bio_labels)} biography labels")

    for strategy in args.strategies:
        strategy_dir = run_dir / strategy
        if not strategy_dir.exists():
            print(f"  [skip] {strategy_dir} not found")
            continue

        out_dir = OUT_BASE / strategy
        out_dir.mkdir(parents=True, exist_ok=True)

        prov = load_provenance(strategy_dir)
        print(f"\nBuilding graphs for {strategy} (model: {prov.get('model','?')}) …")

        # Collect all mentions grouped by biography
        bio_paragraphs: dict[str, list[dict]] = {}

        for vol_dir in sorted(strategy_dir.iterdir()):
            if not vol_dir.is_dir():
                continue
            vol = vol_dir.name.split("_")[-1]

            for response_file in sorted(vol_dir.glob("*.response.json")):
                pid = str(int(
                    response_file.name.replace(".response.json", "").split("_")[-1]
                ))
                bio_slug = para_to_bio.get((vol, pid), "")
                if not bio_slug:
                    continue

                try:
                    raw = response_file.read_text(encoding="utf-8")
                    s, e = raw.find("["), raw.rfind("]") + 1
                    if s == -1 or e == 0:
                        continue
                    mentions = json.loads(raw[s:e])
                except (json.JSONDecodeError, ValueError):
                    continue

                bio_paragraphs.setdefault(bio_slug, []).append({
                    "vol": vol, "pid": pid, "mentions": mentions
                })

        # Write one JSON per biography
        index_entries = []
        for slug, paragraphs in sorted(bio_paragraphs.items()):
            label = bio_labels.get(slug, slug.title())
            graph = build_bio_graph(slug, label, paragraphs, strategy, prov)
            fname = f"bio_{slug}.json"
            with open(out_dir / fname, "w", encoding="utf-8") as f:
                json.dump(graph, f, ensure_ascii=False)

            n_mentions = sum(
                1 for n in graph["nodes"]
                if n["type"] in ("explicit", "implicit", "coreferent", "generic")
            )
            index_entries.append({
                "slug":     slug,
                "label":    label,
                "file":     fname,
                "mentions": n_mentions,
                "paragraphs": len([p for p in paragraphs if p["mentions"]]),
            })

        index_entries.sort(key=lambda x: x["label"])
        with open(out_dir / "index.json", "w", encoding="utf-8") as f:
            json.dump({
                "strategy": strategy,
                "model":    prov.get("model", ""),
                "run":      args.run,
                "biographies": index_entries,
            }, f, ensure_ascii=False, indent=2)

        print(f"  Wrote {len(index_entries)} biography graphs → {out_dir}")

    print("\nDone.")


if __name__ == "__main__":
    main()
