# Viewsari CQ evaluation

Operationalises §10.2.3 of the dissertation: every competency question from
[`data/ontology/CQ_CATALOG.md`](../../data/ontology/CQ_CATALOG.md)
(70 entries, mirrored as Appendix B) is translated into a SPARQL query and
executed against the populated knowledge graph. Each CQ is then classified as
**fully answerable**, **partially answerable**, **unanswerable**, or
**non-SPARQL** (a process / FAIR / UX question that is answered by
documentation, not by a graph pattern). The output is a per-CQ coverage
report ready to drop into the dissertation evaluation chapter.

## Layout

```
scripts/evaluation/
├── README.md                       ← this file
├── cq_catalog.json                 ← machine-readable index of all 70 CQs
├── run_cq_evaluation.py            ← runner (rdflib local + HTTP endpoint)
├── inferences.ru                   ← SPARQL UPDATE closure rules (R1/R2/R3)
├── materialise_inferences.py       ← apply rules, write closed KG to disk
├── queries/                        ← one .rq per SPARQL-answerable CQ
│   ├── _prefixes.rq                    (shared prefix block, copy/paste only)
│   ├── cqi_01.rq … cqi_28.rq           (Phase I)
│   ├── cqii_01.rq … cqii_40.rq         (Phase II)
│   └── federated_example.rq            (illustrative SERVICE query for CQII.27)
└── reports/                        ← timestamped Markdown + JSON outputs
```

## Closure (run once before evaluating)

Five Phase-I queries (CQI.3, CQI.12, CQI.19, CQI.21, CQI.22) need a direct
`viewsari:0001032` edge on cooccurrence and person nodes. The pipeline does
not write that edge, but it can be derived; `inferences.ru` materialises it
in three rules:

| Rule | What it adds | Triples on the current KG |
|---|---|---|
| R1 — artwork closure (entity ← `prov:wasDerivedFrom` ← annotation → 0001032) | defensive — most artworks already carry the edge | 0 |
| R2 — cooccurrence closure (parse "Vol. N, Para. M" out of `rdfs:label`)       | cooccurrence → paragraph                   | 617 |
| R3 — person closure (chains off R2 through `viewsari:involves`)               | person → paragraph                         | 1,282 |

```bash
# One-shot: write data/kg/viewsari_kg.inferred.ttl
python scripts/evaluation/materialise_inferences.py

# Or apply rules in memory at evaluation time
python scripts/evaluation/run_cq_evaluation.py --materialise
```

The runner auto-detects `viewsari_kg.inferred.ttl` and loads it instead of
the raw dump when present.

`cq_catalog.json` carries cluster, persona, complexity (`simple` /
`multi-hop` / `aggregation`), and a `query` pointer per SPARQL CQ. CQs that
cannot be answered by SPARQL alone (FAIR principles, teaching reuse, map UX,
…) are flagged `type: descriptive` with a `rationale` instead of a query.

## Running

```bash
# Default: load the local dump (data/kg/viewsari_kg.ttl) plus the ontology
python scripts/evaluation/run_cq_evaluation.py

# Run against a GraphDB endpoint instead of loading the dump
python scripts/evaluation/run_cq_evaluation.py \
    --endpoint http://localhost:7200/repositories/viewsari

# Sanity-check: parse every .rq file without executing
python scripts/evaluation/run_cq_evaluation.py --parse-only

# Custom output directory
python scripts/evaluation/run_cq_evaluation.py \
    --output-dir data/evaluation
```

The runner needs only `rdflib` (local mode) or `httpx` (endpoint mode). Both
are already declared in `requirements.txt`.

## Classification rules

| Backend result | Status | Root cause |
|---|---|---|
| `ASK -> true`                                          | fully-answerable     | — |
| `ASK -> false`, no `expected_gap`                      | unanswerable         | data-gap |
| `ASK -> false`, `expected_gap` set                     | partially-answerable | data-gap |
| `SELECT` returns ≥ 1 row                               | fully-answerable     | — |
| `SELECT` returns 0 rows, no `expected_gap`             | unanswerable         | data-gap |
| `SELECT` returns 0 rows, `expected_gap` set            | partially-answerable | data-gap |
| SPARQL parse error                                     | unanswerable         | parse-error |
| Backend exception                                      | unanswerable         | runtime-error |
| `type: descriptive`                                    | non-sparql           | — |

`expected_gap` lets the catalog flag CQs whose query is correctly modelled
but whose answer needs data that has not yet been ingested (e.g. PMI scores,
historical events). These count as *partial* coverage rather than failures,
matching the dissertation's distinction between data gaps and modelling gaps.

## Concrete bindings used in queries

To make every query immediately runnable, parameterised CQs (e.g. *"the
biography of artist X"*) are pre-bound to representative individuals:

| Slot | Default binding |
|---|---|
| Artist X | `vkb:buonarroti-michelagnolo` |
| Artist Y | `vkb:sanzio-raffaello-raffaello-da-urbino` |
| Biography of X | `vkb:the_lives_1568_volume-9_michelangelo-bio` |
| Volume of X | `vkb:the_lives_1568_volume-9` |
| Cooccurrence C | `vkb:cooccurrence_agn-agn_1` |
| Entity / Artwork E | `vkb:Q1069665` (S. Felicita) |
| Location L | `vkb:florence` |

The full mapping lives in `cq_catalog.json` under `_concrete_bindings`. Edit
the `.rq` files directly to substitute different individuals.

## Property naming convention

The KG mixes ontology-canonical numeric IRIs (`viewsari:0001012` =
`artwork`) with friendly aliases (`viewsari:hasText`, `viewsari:involves`,
`viewsari:hasStartPage`). Each query uses whichever form is actually
populated for that property in the current KG; if both forms appear, the
query takes a `UNION`. Run `python scripts/evaluation/run_cq_evaluation.py
--parse-only` after any KG-shape change to catch property drift early.

## Output

Every run writes two files into `reports/`:

- `cq_evaluation_<UTC>.md` — human-readable report with the summary table,
  per-cluster coverage, query-complexity histogram, and per-CQ details.
- `cq_evaluation_<UTC>.json` — same data in machine-readable form for
  diff-ing across ontology iterations.
