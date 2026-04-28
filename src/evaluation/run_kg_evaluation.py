#!/usr/bin/env python3
"""KG evaluation runner — operationalises dissertation §9.3.

Computes the metrics catalogued in `kg_metrics.json` against the populated
Viewsari knowledge graph and emits a Markdown + JSON report under
`src/evaluation/kg_reports/`. The metrics correspond to:

  §9.3.1  Instance counts by ontology class (Table 9.11)
  §9.3.2  Provenance coverage (Listing 9.6) + strict variant
  §9.3.3  External linking coverage (Table 9.12) + OOKB long-tail

Both backends supported by `run_cq_evaluation.py` are reused: a local rdflib
graph (default) or an HTTP SPARQL endpoint.

Usage
-----

    python src/evaluation/run_kg_evaluation.py
    python src/evaluation/run_kg_evaluation.py --materialise
    python src/evaluation/run_kg_evaluation.py \
        --endpoint http://localhost:7200/repositories/viewsari
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Reuse the backends (RDFLibBackend / EndpointBackend) from the CQ runner.
from run_cq_evaluation import RDFLibBackend, EndpointBackend, _serialise  # noqa: E402

_KG_INFERRED = ROOT / "data" / "kg" / "viewsari_kg.inferred.ttl"
_KG_RAW = ROOT / "data" / "kg" / "viewsari_kg.ttl"
DEFAULT_KG = _KG_INFERRED if _KG_INFERRED.exists() else _KG_RAW
DEFAULT_ONTOLOGY = ROOT / "data" / "ontology" / "viewsari_ontology.rdf"
CATALOG = HERE / "kg_metrics.json"
REPORTS_DIR = HERE / "kg_reports"


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text())


def _row_to_dict(headers: list[str], row: list[Any]) -> dict[str, str]:
    return {h: _serialise(v) for h, v in zip(headers, row)}


def execute(backend: Any, sparql: str) -> dict[str, Any]:
    """Run a query and normalise the result to {headers, rows, type}."""
    # rdflib backend exposes .graph; for it we use the Result object
    # directly to keep column names. The HTTP backend already returns
    # row dicts.
    if isinstance(backend, RDFLibBackend):
        result = backend.graph.query(sparql)
        if result.type == "ASK":
            return {"type": "ask", "boolean": bool(result.askAnswer),
                    "headers": [], "rows": []}
        headers = [str(v) for v in result.vars]
        rows = []
        count = 0
        for r in result:
            count += 1
            if len(rows) < 50:
                rows.append([_serialise(v) for v in r])
        return {"type": "select", "headers": headers, "rows": rows, "count": count}

    # endpoint
    import httpx  # noqa: F401  (imported indirectly)
    r = backend.client.post(
        backend.url,
        data={"query": sparql},
        headers={"Accept": "application/sparql-results+json"},
    )
    r.raise_for_status()
    payload = r.json()
    if "boolean" in payload:
        return {"type": "ask", "boolean": payload["boolean"],
                "headers": [], "rows": []}
    headers = payload.get("head", {}).get("vars", [])
    bindings = payload.get("results", {}).get("bindings", [])
    rows = []
    for b in bindings[:50]:
        rows.append([_serialise(b.get(h, {}).get("value", "")) for h in headers])
    return {"type": "select", "headers": headers, "rows": rows,
            "count": len(bindings)}


def run(backend: Any, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for metric in catalog["metrics"]:
        record = dict(metric)
        record.update({"status": "ok", "elapsed_ms": None,
                       "headers": [], "rows": [], "summary": "",
                       "error": None})
        sparql = (HERE / metric["query"]).read_text()
        t0 = time.time()
        try:
            result = execute(backend, sparql)
        except Exception as exc:  # noqa: BLE001
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            print(f"  [{metric['id']}] ERROR: {record['error']}", file=sys.stderr)
            out.append(record)
            continue
        record["elapsed_ms"] = int((time.time() - t0) * 1000)
        record["headers"] = result.get("headers", [])
        record["rows"] = result.get("rows", [])
        record["row_count"] = result.get("count")

        if result["type"] == "ask":
            record["summary"] = "true" if result["boolean"] else "false"
        elif metric["kind"] == "scalar" and result["rows"]:
            record["summary"] = " · ".join(result["rows"][0])
        elif metric["kind"] == "scalar-table" and result["rows"]:
            record["summary"] = " · ".join(
                f"{h}={v}" for h, v in zip(result["headers"], result["rows"][0]))
        else:
            record["summary"] = f"{record['row_count']} row(s)"

        print(f"  [{metric['id']}] {metric['title']}: {record['summary']} "
              f"({record['elapsed_ms']} ms)", file=sys.stderr)
        out.append(record)
    return out


def write_report(records: list[dict[str, Any]], catalog: dict[str, Any],
                 out_md: Path, out_json: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Viewsari KG evaluation report",
        "",
        f"_Generated_: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"_Methodology_: dissertation §9.3 (Knowledge Graph Population Results)",
        "",
        "## Headline metrics",
        "",
        "| ID | §  | Metric | Value |",
        "|---|---|---|---|",
    ]
    for r in records:
        if r["kind"] in ("scalar", "scalar-table") and r["status"] == "ok":
            lines.append(f"| {r['id']} | {r['section']} | "
                         f"{r['title']} | `{r['summary']}` |")
    lines.append("")

    # Per-metric detail
    lines.append("## Per-metric detail")
    lines.append("")
    for r in records:
        lines.append(f"### {r['id']} (§{r['section']}) — {r['title']}")
        lines.append("")
        if r.get("description"):
            lines.append(f"_{r['description']}_")
            lines.append("")
        if r["status"] != "ok":
            lines.append(f"**ERROR**: {r['error']}")
            lines.append("")
            continue
        if r["headers"] and r["rows"]:
            lines.append("| " + " | ".join(r["headers"]) + " |")
            lines.append("|" + "|".join(["---"] * len(r["headers"])) + "|")
            for row in r["rows"]:
                lines.append("| " + " | ".join(row) + " |")
        else:
            lines.append(f"_no rows returned_")
        lines.append("")
        lines.append(f"_query: {r['query']} · {r['elapsed_ms']} ms_")
        lines.append("")

    out_md.write_text("\n".join(lines))
    out_json.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "metrics": records,
    }, indent=2))
    print(f"\nWrote {out_md.relative_to(ROOT)}", file=sys.stderr)
    print(f"Wrote {out_json.relative_to(ROOT)}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kg", type=Path, default=DEFAULT_KG)
    ap.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY)
    ap.add_argument("--no-ontology", action="store_true")
    ap.add_argument("--endpoint", type=str, default=None)
    ap.add_argument("--materialise", action="store_true",
                    help="Apply inferences.ru in memory after loading.")
    ap.add_argument("--rules", type=Path, default=HERE / "inferences.ru")
    ap.add_argument("--output-dir", type=Path, default=REPORTS_DIR)
    args = ap.parse_args()

    catalog = load_catalog()
    if args.endpoint:
        backend = EndpointBackend(args.endpoint)
        print(f"Using SPARQL endpoint: {args.endpoint}", file=sys.stderr)
    else:
        ontology = None if args.no_ontology else args.ontology
        rules = args.rules if args.materialise else None
        backend = RDFLibBackend(args.kg, ontology, materialise_rules=rules)

    records = run(backend, catalog)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    write_report(records, catalog,
                 args.output_dir / f"kg_evaluation_{stamp}.md",
                 args.output_dir / f"kg_evaluation_{stamp}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
