#!/usr/bin/env python3
"""Competency-question evaluation routine for the Viewsari ontology.

Implements the methodology of dissertation §10.2.3:

    A CQ is *fully answerable* if its SPARQL query returns a non-empty result
    set consistent with the expected answer type; *partially answerable* if
    the result set is structurally correct but incomplete due to missing
    data; *unanswerable* if the query fails or returns structurally
    incorrect results.

The script reads `cq_catalog.json`, executes each per-CQ `.rq` file against
either a local TTL dump (default: data/kg/viewsari_kg.ttl) or a SPARQL
endpoint, classifies each CQ, and writes a Markdown coverage report plus a
machine-readable JSON next to it.

Usage
-----

    # Local KG (default)
    python src/evaluation/run_cq_evaluation.py

    # Specific KG and ontology header
    python src/evaluation/run_cq_evaluation.py \
        --kg data/kg/viewsari_kg.ttl \
        --ontology data/ontology/viewsari_ontology.rdf

    # Remote endpoint (e.g. GraphDB)
    python src/evaluation/run_cq_evaluation.py \
        --endpoint http://localhost:7200/repositories/viewsari

    # Dry run: just check that every .rq file parses
    python src/evaluation/run_cq_evaluation.py --parse-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

# Make sibling modules (materialise_inferences) importable when --materialise
# is used.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Prefer the inferred (post-closure) dump if it exists; fall back to the raw
# extraction. The closure adds the materialised viewsari:0001032 edges that
# CQI.3, CQI.12, CQI.19, CQI.21 and CQI.22 depend on.
_KG_INFERRED = ROOT / "data" / "kg" / "viewsari_kg.inferred.ttl"
_KG_RAW = ROOT / "data" / "kg" / "viewsari_kg.ttl"
DEFAULT_KG = _KG_INFERRED if _KG_INFERRED.exists() else _KG_RAW
DEFAULT_ONTOLOGY = ROOT / "data" / "ontology" / "viewsari_ontology.rdf"
CATALOG = HERE / "cq_catalog.json"
REPORTS_DIR = HERE / "reports"

# Status labels (per dissertation §10.2.3)
STATUS_FULL = "fully-answerable"
STATUS_PARTIAL = "partially-answerable"
STATUS_UNANSWERABLE = "unanswerable"
STATUS_DESCRIPTIVE = "non-sparql"

ROOT_CAUSE_DATA = "data-gap"            # query OK, no triples present yet
ROOT_CAUSE_MODEL = "modelling-gap"      # query references vocabulary not in ontology
ROOT_CAUSE_RUNTIME = "runtime-error"    # exception while executing
ROOT_CAUSE_PARSE = "parse-error"        # SPARQL syntax error
ROOT_CAUSE_NONE = ""


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

class Backend:
    """Common interface for the local rdflib backend and the HTTP backend."""

    def query(self, sparql: str) -> dict[str, Any]:
        raise NotImplementedError


class RDFLibBackend(Backend):
    def __init__(
        self,
        kg_path: Path,
        ontology_path: Path | None,
        materialise_rules: Path | None = None,
    ) -> None:
        from rdflib import Graph

        self.graph = Graph()
        for label, path in [("ontology", ontology_path), ("KG", kg_path)]:
            if path is None:
                continue
            print(f"  loading {label}: {path} ...", file=sys.stderr, flush=True)
            t0 = time.time()
            fmt = "xml" if path.suffix in (".rdf", ".owl", ".xml") else "turtle"
            self.graph.parse(path.as_posix(), format=fmt)
            print(
                f"  {label} loaded ({len(self.graph):,} triples, "
                f"{time.time() - t0:.1f}s)",
                file=sys.stderr,
                flush=True,
            )

        if materialise_rules is not None:
            from materialise_inferences import split_updates, rule_label  # type: ignore

            print(f"  materialising rules from {materialise_rules.name} ...",
                  file=sys.stderr, flush=True)
            blocks, prologue = split_updates(materialise_rules.read_text())
            for block in blocks:
                before = len(self.graph)
                t0 = time.time()
                self.graph.update(prologue + "\n\n" + block if prologue else block)
                added = len(self.graph) - before
                print(f"    [{rule_label(block)}] +{added:,} triples "
                      f"({time.time()-t0:.1f}s)", file=sys.stderr)

    def query(self, sparql: str) -> dict[str, Any]:
        result = self.graph.query(sparql)
        if result.type == "ASK":
            return {"type": "ask", "boolean": bool(result.askAnswer), "rows": []}
        rows = []
        # cap retained rows so the report stays compact
        for i, row in enumerate(result):
            if i < 10:
                rows.append([_serialise(v) for v in row])
        return {"type": "select", "rows": rows, "count": len(result)}


class EndpointBackend(Backend):
    def __init__(self, url: str) -> None:
        import httpx
        self.url = url
        self.client = httpx.Client(timeout=120.0)

    def query(self, sparql: str) -> dict[str, Any]:
        # Use SPARQL JSON results for SELECT/ASK uniformly.
        r = self.client.post(
            self.url,
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        r.raise_for_status()
        payload = r.json()
        if "boolean" in payload:
            return {"type": "ask", "boolean": payload["boolean"], "rows": []}
        bindings = payload.get("results", {}).get("bindings", [])
        rows = []
        for binding in bindings[:10]:
            rows.append([_serialise_json(b) for b in binding.values()])
        return {"type": "select", "rows": rows, "count": len(bindings)}


def _serialise(node: Any) -> str:
    s = str(node)
    return s if len(s) <= 120 else s[:117] + "..."


def _serialise_json(b: dict[str, Any]) -> str:
    s = b.get("value", "")
    return s if len(s) <= 120 else s[:117] + "..."


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text())


def read_query(query_path: Path) -> str:
    return query_path.read_text()


def classify(
    cq: dict[str, Any],
    result: dict[str, Any] | None,
    error: tuple[str, str] | None,
) -> tuple[str, str, str]:
    """Return (status, root_cause, summary)."""
    if cq["type"] == "descriptive":
        return STATUS_DESCRIPTIVE, ROOT_CAUSE_NONE, "answered by documentation, not SPARQL"

    if error is not None:
        kind, message = error
        cause = ROOT_CAUSE_PARSE if kind == "parse" else ROOT_CAUSE_RUNTIME
        return STATUS_UNANSWERABLE, cause, message

    assert result is not None
    if result["type"] == "ask":
        if result["boolean"]:
            return STATUS_FULL, ROOT_CAUSE_NONE, "ASK -> true"
        if cq.get("expected_gap"):
            return STATUS_PARTIAL, ROOT_CAUSE_DATA, "ASK -> false (expected data/modelling gap)"
        return STATUS_UNANSWERABLE, ROOT_CAUSE_DATA, "ASK -> false"

    n = result["count"]
    if n > 0:
        return STATUS_FULL, ROOT_CAUSE_NONE, f"{n} row(s)"
    if cq.get("expected_gap"):
        return STATUS_PARTIAL, ROOT_CAUSE_DATA, "0 rows (expected data/modelling gap)"
    return STATUS_UNANSWERABLE, ROOT_CAUSE_DATA, "0 rows"


def run(
    backend: Backend | None,
    catalog: dict[str, Any],
    parse_only: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for cq in catalog["questions"]:
        record = {
            "id": cq["id"],
            "phase": cq["phase"],
            "cluster": cq["cluster"],
            "persona": cq["persona"],
            "question": cq["question"],
            "type": cq["type"],
            "complexity": cq.get("complexity"),
            "status": "",
            "root_cause": "",
            "summary": "",
            "row_count": None,
            "elapsed_ms": None,
            "sample": [],
        }

        if cq["type"] == "descriptive":
            record["status"] = STATUS_DESCRIPTIVE
            record["summary"] = cq.get("rationale", "")
            rows.append(record)
            continue

        query_file = HERE / cq["query"]
        if not query_file.exists():
            record["status"] = STATUS_UNANSWERABLE
            record["root_cause"] = ROOT_CAUSE_PARSE
            record["summary"] = f"missing query file: {cq['query']}"
            rows.append(record)
            continue

        sparql = read_query(query_file)

        if parse_only:
            try:
                from rdflib.plugins.sparql import prepareQuery
                prepareQuery(sparql)
                record["status"] = STATUS_FULL
                record["summary"] = "parses OK"
            except Exception as exc:  # noqa: BLE001
                record["status"] = STATUS_UNANSWERABLE
                record["root_cause"] = ROOT_CAUSE_PARSE
                record["summary"] = f"parse error: {exc}"
            rows.append(record)
            continue

        assert backend is not None
        t0 = time.time()
        try:
            result = backend.query(sparql)
            error = None
        except Exception as exc:  # noqa: BLE001
            kind = "parse" if "ParseException" in type(exc).__name__ else "runtime"
            result = None
            error = (kind, f"{type(exc).__name__}: {exc}")
        record["elapsed_ms"] = int((time.time() - t0) * 1000)

        status, cause, summary = classify(cq, result, error)
        record["status"] = status
        record["root_cause"] = cause
        record["summary"] = summary
        if result is not None:
            record["row_count"] = result.get("count")
            if result["type"] == "ask":
                record["row_count"] = 1 if result["boolean"] else 0
            record["sample"] = result.get("rows", [])
        rows.append(record)
        print(f"  [{record['id']:>8s}] {status:<22s} {summary}", file=sys.stderr)

    return rows


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _pct(n: int, total: int) -> str:
    return "—" if total == 0 else f"{100 * n / total:.1f}%"


def write_report(rows: list[dict[str, Any]], out_md: Path, out_json: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)

    statuses = Counter(r["status"] for r in rows)
    causes = Counter(r["root_cause"] for r in rows if r["root_cause"])
    by_cluster = defaultdict(Counter)
    for r in rows:
        by_cluster[r["cluster"]][r["status"]] += 1
    complexity = Counter(r["complexity"] or "n/a" for r in rows)

    sparql_total = sum(1 for r in rows if r["type"] != "descriptive")

    # ---- Markdown ----
    lines: list[str] = []
    lines.append(f"# Viewsari CQ coverage report")
    lines.append("")
    lines.append(
        f"_Generated_: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  "
    )
    lines.append(f"_Methodology_: dissertation §10.2.3")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count | % of all 70 | % of SPARQL-only |")
    lines.append("|---|---|---|---|")
    for label, key in [
        ("Fully answerable",     STATUS_FULL),
        ("Partially answerable", STATUS_PARTIAL),
        ("Unanswerable",         STATUS_UNANSWERABLE),
        ("Non-SPARQL (descriptive)", STATUS_DESCRIPTIVE),
    ]:
        n = statuses.get(key, 0)
        sparql_n = n if key == STATUS_DESCRIPTIVE else n
        pct_sparql = "n/a" if key == STATUS_DESCRIPTIVE else _pct(n, sparql_total)
        lines.append(f"| {label} | {n} | {_pct(n, len(rows))} | {pct_sparql} |")
    lines.append("")

    lines.append("## Root-cause distribution (unanswerable + partial)")
    lines.append("")
    if causes:
        lines.append("| Root cause | Count |")
        lines.append("|---|---|")
        for cause, n in causes.most_common():
            lines.append(f"| {cause} | {n} |")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## Query complexity distribution")
    lines.append("")
    lines.append("| Complexity | Count |")
    lines.append("|---|---|")
    for c, n in sorted(complexity.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {c} | {n} |")
    lines.append("")

    lines.append("## Per-cluster coverage")
    lines.append("")
    lines.append(
        "| Cluster | Fully | Partial | Unanswerable | Descriptive | Total |"
    )
    lines.append("|---|---|---|---|---|---|")
    for cluster in sorted(by_cluster):
        c = by_cluster[cluster]
        total = sum(c.values())
        lines.append(
            f"| {cluster} | {c.get(STATUS_FULL,0)} | {c.get(STATUS_PARTIAL,0)} | "
            f"{c.get(STATUS_UNANSWERABLE,0)} | {c.get(STATUS_DESCRIPTIVE,0)} | {total} |"
        )
    lines.append("")

    lines.append("## Per-CQ results")
    lines.append("")
    lines.append("| ID | Status | Cluster | Complexity | Rows | Time (ms) | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        rc = r["row_count"] if r["row_count"] is not None else "—"
        ms = r["elapsed_ms"] if r["elapsed_ms"] is not None else "—"
        notes = (r["summary"] or "").replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {r['status']} | {r['cluster']} | "
            f"{r.get('complexity') or '—'} | {rc} | {ms} | {notes} |"
        )
    lines.append("")

    lines.append("## Question text and result samples")
    lines.append("")
    for r in rows:
        lines.append(f"### {r['id']} — {r['status']}")
        lines.append(f"_{r['question']}_  ")
        lines.append(f"Cluster: **{r['cluster']}** · Persona: {r['persona']} · "
                     f"Complexity: {r.get('complexity') or '—'}")
        lines.append("")
        lines.append(f"- summary: {r['summary']}")
        if r.get("root_cause"):
            lines.append(f"- root cause: `{r['root_cause']}`")
        if r.get("sample"):
            lines.append("- first rows:")
            for row in r["sample"]:
                lines.append("  - " + " · ".join(row))
        lines.append("")

    out_md.write_text("\n".join(lines))
    out_json.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                                     "summary": dict(statuses),
                                     "rows": rows}, indent=2))
    print(f"\nWrote {out_md.relative_to(ROOT)}", file=sys.stderr)
    print(f"Wrote {out_json.relative_to(ROOT)}", file=sys.stderr)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kg", type=Path, default=DEFAULT_KG,
                    help="Path to TTL/RDF KG dump (ignored if --endpoint is given).")
    ap.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY,
                    help="Path to ontology header to merge with the KG.")
    ap.add_argument("--no-ontology", action="store_true",
                    help="Skip loading the ontology header.")
    ap.add_argument("--endpoint", type=str, default=None,
                    help="SPARQL endpoint URL (e.g. GraphDB /repositories/viewsari).")
    ap.add_argument("--materialise", action="store_true",
                    help="Apply src/evaluation/inferences.ru in memory after "
                         "loading. Equivalent to running materialise_inferences.py "
                         "first but skips the disk write.")
    ap.add_argument("--rules", type=Path, default=HERE / "inferences.ru",
                    help="Rules file used by --materialise.")
    ap.add_argument("--output-dir", type=Path, default=REPORTS_DIR,
                    help="Where to write the Markdown + JSON report.")
    ap.add_argument("--parse-only", action="store_true",
                    help="Only parse each query file; do not execute.")
    args = ap.parse_args()

    catalog = load_catalog()
    backend: Backend | None = None
    if not args.parse_only:
        if args.endpoint:
            backend = EndpointBackend(args.endpoint)
            print(f"Using SPARQL endpoint: {args.endpoint}", file=sys.stderr)
        else:
            ontology_path = None if args.no_ontology else args.ontology
            rules = args.rules if args.materialise else None
            backend = RDFLibBackend(args.kg, ontology_path,
                                    materialise_rules=rules)

    rows = run(backend, catalog, parse_only=args.parse_only)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_md = args.output_dir / f"cq_evaluation_{stamp}.md"
    out_json = args.output_dir / f"cq_evaluation_{stamp}.json"
    write_report(rows, out_md, out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
