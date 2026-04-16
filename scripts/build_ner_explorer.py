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
  biography ──hasPart──► paragraph
  paragraph ──contains──► mention
  mention   ──wasGeneratedBy──► NER sub-activity
  NER sub-activity ──wasInformedBy──► parent NER run
  NER sub-activity ──wasAssociatedWith──► agent
  NER sub-activity ──used──► prompt (prov:Entity)
  entity    ──wasDerivedFrom──► mention
  entity    ──wasGeneratedBy──► EL sub-activity
  mention   ──refersTo──► mention  (coreferent chains)

Usage:
    python scripts/build_ner_explorer.py
    python scripts/build_ner_explorer.py --run oss_v3
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


def _mention_subtype(mtype: str) -> str:
    if "explicit" in mtype:
        return "explicit"
    if "implicit" in mtype:
        return "implicit"
    if "coref" in mtype:
        return "coreferent"
    return "generic"


def load_para_index() -> tuple[dict, dict]:
    para_to_bio: dict[tuple, str] = {}
    bio_labels: dict[str, str] = {}
    with open(BIO_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("rdf:type") != "viewsari:biography":
                continue
            iid = row.get("instance_id", "")
            label = row.get("rdfs:label", "")
            slug = iid.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
            bio_labels[slug] = label
    with open(PARA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vol = row.get("vol", "")
            pid = str(int(row.get("paragraph_id", 0)))
            bio_uri = row.get("frbr:is part of", "")
            slug = bio_uri.rsplit("_", 1)[-1].replace("-bio", "").replace("-second", "")
            para_to_bio[(vol, pid)] = slug
    return para_to_bio, bio_labels


def load_provenance_index(strategy_dir: Path) -> tuple[dict[tuple[str, str], dict], dict]:
    """Return per-extraction provenance keyed by (vol, prompt_file), plus a summary."""
    prov_file = strategy_dir / "provenance.jsonl"
    per_extraction: dict[tuple[str, str], dict] = {}
    all_entries = []
    if prov_file.exists():
        for line in prov_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            all_entries.append(e)
            vol = e.get("volume", "").replace("volume_", "")
            pf = e.get("prompt_file", "")
            if vol and pf:
                per_extraction[(vol, pf)] = e

    summary = {}
    if all_entries:
        summary["model"] = all_entries[0].get("model", "unknown")
        starts = [e["started_at"] for e in all_entries if e.get("started_at")]
        ends = [e["ended_at"] for e in all_entries if e.get("ended_at")]
        summary["started_at"] = min(starts) if starts else ""
        summary["ended_at"] = max(ends) if ends else ""
        summary["paragraphs"] = len(all_entries)
    return per_extraction, summary


def build_bio_graph(
    slug: str,
    bio_label: str,
    paragraphs: list[dict],
    strategy: str,
    prov_index: dict[tuple[str, str], dict],
    prov_summary: dict,
) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(nid: str, ntype: str, label: str, **extra):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, **extra}

    strat_slug = re.sub(r"[^a-zA-Z0-9]", "_", strategy)
    model_name = prov_summary.get("model", "LLM agent")
    agent_id = f"agent_{re.sub(r'[^a-zA-Z0-9]', '_', model_name)}"
    add_node(agent_id, "agent", model_name)

    parent_id = f"activity_{strat_slug}"
    add_node(parent_id, "activity",
             f"ObliquER NER — {strategy}",
             model=model_name,
             started_at=prov_summary.get("started_at", ""),
             ended_at=prov_summary.get("ended_at", ""),
             paragraphs_processed=prov_summary.get("paragraphs", 0))
    edges.append({"source": parent_id, "target": agent_id,
                  "label": "wasAssociatedWith"})

    bio_id = f"bio_{slug}"
    add_node(bio_id, "biography", bio_label or slug.title())

    for para in paragraphs:
        vol = para["vol"]
        pid = para["pid"]
        stem = para.get("stem", "")
        mentions = para["mentions"]
        if not mentions:
            continue

        para_id = f"para_{vol}_{pid}"
        add_node(para_id, "paragraph", f"§{pid}")
        edges.append({"source": para_id, "target": bio_id,
                      "label": "part of", "reverse_label": "hasPart"})

        # Per-extraction NER sub-activity
        ner_sub_id = f"ner_{strat_slug}_{vol}_{stem}" if stem else f"ner_{strat_slug}_{vol}_p{pid}"
        pmeta = prov_index.get((vol, f"{stem}.j2"), {}) if stem else {}
        ner_label = f"NER {strategy} vol {vol}"
        if pmeta:
            ner_label += f" ({pmeta.get('started_at', '')[:10]})"
        add_node(ner_sub_id, "activity", ner_label,
                 model=pmeta.get("model", model_name),
                 started_at=pmeta.get("started_at", ""),
                 ended_at=pmeta.get("ended_at", ""))
        edges.append({"source": ner_sub_id, "target": parent_id,
                      "label": "wasInformedBy", "dashed": True})
        edges.append({"source": ner_sub_id, "target": agent_id,
                      "label": "wasAssociatedWith", "dashed": True})

        # Prompt node
        if stem:
            prompt_id = f"prompt_{strat_slug}_vol{vol}_{stem}"
            add_node(prompt_id, "entity", f"Prompt {stem}",
                     entity_id=prompt_id, is_prompt=True)
            edges.append({"source": ner_sub_id, "target": prompt_id,
                          "label": "used"})

        for m in mentions:
            mid = m.get("mention_id", "")
            mtype = m.get("type", "")
            surface = m.get("surface_form", "")[:80]
            refers_to = m.get("refers_to")
            subtype = _mention_subtype(mtype)

            mention_id = f"mention_{strat_slug}_{vol}_{pid}_{mid}"
            add_node(mention_id, subtype,
                     surface,
                     mention_id=mid,
                     full_type=mtype,
                     paragraph=pid,
                     vol=vol)

            edges.append({"source": mention_id, "target": para_id,
                          "label": "in paragraph", "reverse_label": "contains"})
            edges.append({"source": ner_sub_id, "target": mention_id,
                          "label": "generated", "reverse_label": "wasGeneratedBy", "dashed": True})

            if refers_to and subtype == "coreferent":
                ref_mid = f"mention_{strat_slug}_{vol}_{pid}_{refers_to}"
                edges.append({"source": mention_id, "target": ref_mid,
                              "label": "coreferent", "dashed": True})

    return {"nodes": list(nodes.values()), "edges": edges}


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
    print(f"  {len(para_to_bio)} paragraphs, {len(bio_labels)} biography labels")

    for strategy in args.strategies:
        strategy_dir = run_dir / strategy
        if not strategy_dir.exists():
            print(f"  [skip] {strategy_dir} not found")
            continue

        out_dir = OUT_BASE / strategy
        out_dir.mkdir(parents=True, exist_ok=True)

        prov_index, prov_summary = load_provenance_index(strategy_dir)
        print(f"\nBuilding graphs for {strategy} (model: {prov_summary.get('model', '?')}) …")

        bio_paragraphs: dict[str, list[dict]] = {}

        for vol_dir in sorted(strategy_dir.iterdir()):
            if not vol_dir.is_dir():
                continue
            vol = vol_dir.name.split("_")[-1]

            for response_file in sorted(vol_dir.glob("*.response.json")):
                stem = response_file.name.replace(".response.json", "")
                pid = str(int(stem.split("_")[-1]))
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
                    "vol": vol, "pid": pid, "stem": stem, "mentions": mentions,
                })

        index_entries = []
        for slug, paragraphs in sorted(bio_paragraphs.items()):
            label = bio_labels.get(slug, slug.title())
            graph = build_bio_graph(slug, label, paragraphs, strategy,
                                    prov_index, prov_summary)
            fname = f"bio_{slug}.json"
            with open(out_dir / fname, "w", encoding="utf-8") as f:
                json.dump(graph, f, ensure_ascii=False)

            n_mentions = sum(
                1 for n in graph["nodes"]
                if n["type"] in ("explicit", "implicit", "coreferent", "generic")
            )
            index_entries.append({
                "slug": slug,
                "label": label,
                "file": fname,
                "mentions": n_mentions,
                "paragraphs": len([p for p in paragraphs if p["mentions"]]),
            })

        index_entries.sort(key=lambda x: x["label"])
        with open(out_dir / "index.json", "w", encoding="utf-8") as f:
            json.dump({
                "strategy": strategy,
                "model": prov_summary.get("model", ""),
                "run": args.run,
                "biographies": index_entries,
            }, f, ensure_ascii=False, indent=2)

        print(f"  Wrote {len(index_entries)} biography graphs → {out_dir}")

    print("\nDone.")


if __name__ == "__main__":
    main()
