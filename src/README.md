# Viewsari offline pipelines (`src/`)

Everything under `src/` is **offline**: KG construction, ObliquER → KG ingestion, prebuilt-KB assembly, explorer-graph generation, network statistics, evaluation. None of these modules are imported by the FastAPI app at request time — the runtime serves prebuilt JSON (`data/kb/kb.json`, `data/kg/explorer/`) and queries GraphDB over HTTP. Rebuilds are explicit steps, not on the request path.

See the [top-level README](../README.md) for the contribution map and headline evaluation numbers, and [`evaluation/README.md`](evaluation/README.md) for the CQ-coverage and KG-metrics pipelines in detail.

## Layout

```
src/
├── kg_population/      KG build, namespace migration, GraphDB ingestion        — E3
├── extract_content/    Corpus parsing, OCR, index scraping, explorer JSONs     — case study, E2 → E3
├── network/            PMI / Dice co-occurrence, Wikidata linking, RDF-star    — E3
├── evaluation/         CQ coverage + KG population metrics                     — RQ1 / E1 / E3
├── data_statistics/    Notebook-based corpus statistics                        — case study
├── data/               Local symlinks / staging used by the scripts above
└── full_stats.py       Aggregated stats runner
```

## Subdirectory map

### `kg_population/` — build the KG and load it into GraphDB *(E3)*

| Script | Purpose |
|---|---|
| [`rebuild_kg.py`](kg_population/rebuild_kg.py) | End-to-end rebuild from backup: namespace migration, foundation layer, GT + ObliquER ingestion. Single entry point for "rebuild everything." |
| [`build_viewsari_kg.py`](kg_population/build_viewsari_kg.py) | Initial KG construction (used by `rebuild_kg.py`). |
| [`build_kg_ttl.py`](kg_population/build_kg_ttl.py) | Foundation (bibliographic + structural) layer from the CSV seeds in `data/kg_foundation/`. |
| [`ingest_annotations.py`](kg_population/ingest_annotations.py) | Ground-truth mentions → KG as `oa:Annotation` + `prov:Entity` with the GT NER/EL activities. |
| [`ingest_ner_results.py`](kg_population/ingest_ner_results.py) | ObliquER NER runs → KG; each extraction reified as a `prov:Activity` with its prompt as a `prov:Entity` (operationalizes **C2**). |
| [`build_kb.py`](kg_population/build_kb.py) | KG → `data/kb/kb.json` (runtime KB consumed by the web app). |
| [`build_reasoner_test.py`](kg_population/build_reasoner_test.py) | Small-KG sanity checks for the reasoner. |
| [`rebuild_pages_paragraphs.py`](kg_population/rebuild_pages_paragraphs.py) | Refresh page / paragraph nodes without a full rebuild. |
| [`rewrite_hasbodyvalue.py`](kg_population/rewrite_hasbodyvalue.py) | One-off migration: `oa:hasBodyValue` → `oa:hasBody → oa:TextualBody → rdf:value`. |
| [`populate_biographies.ipynb`](kg_population/populate_biographies.ipynb) | Biography-seeding notebook (manual / exploratory). |
| [`setup_graphdb.sh`](kg_population/setup_graphdb.sh) | Create the GraphDB repository and import `viewsari_kg.ttl`. |
| [`graphdb-repo-config.ttl`](kg_population/graphdb-repo-config.ttl) | Declarative GraphDB repository configuration. |

Typical rebuild:

```bash
python src/kg_population/rebuild_kg.py          # write data/kg/viewsari_kg.ttl
python src/evaluation/materialise_inferences.py # write viewsari_kg.inferred.ttl (closure rules R1–R3)
python src/kg_population/build_kb.py            # regenerate data/kb/kb.json
bash src/kg_population/setup_graphdb.sh         # re-import into GraphDB
```

### `extract_content/` — corpus parsing and explorer JSONs *(case study, E2 → E3)*

| Script | Purpose |
|---|---|
| [`extract_facsimile_pages.py`](extract_content/extract_facsimile_pages.py) | Slice the Project Gutenberg HTML into per-page facsimile files (consumed by the biography viewer). |
| [`extract_volume_content.ipynb`](extract_content/extract_volume_content.ipynb) | Per-volume parsing (manual). |
| [`ocr_facsimile.py`](extract_content/ocr_facsimile.py) | OCR pipeline for the facsimile pages. |
| [`parse_names.py`](extract_content/parse_names.py) | Index-of-Names parser. |
| [`scrape_indices.py`](extract_content/scrape_indices.py) | Index scraper. |
| [`scrape_bibliography_info.ipynb`](extract_content/scrape_bibliography_info.ipynb) | Bibliography enrichment notebook. |
| [`get_references.py`](extract_content/get_references.py) | Cross-reference extractor. |
| [`fix_headless_corefs.py`](extract_content/fix_headless_corefs.py) | Coref cleanup (orphaned mentions without an antecedent). |
| [`build_ner_explorer.py`](extract_content/build_ner_explorer.py) | ObliquER response files → D3-ready explorer JSONs under `data/kg/explorer/ner/`. Powers the KG explorer (operationalizes **C3** — inspection of the hermeneutic chain). |
| [`build_explorer_graphs.py`](extract_content/build_explorer_graphs.py) | Ground-truth co-occurrence explorer JSONs. |

### `network/` — co-occurrence statistics and Wikidata linking *(E3)*

| Script | Purpose |
|---|---|
| [`compute_pmi.py`](network/compute_pmi.py) | PMI co-occurrence scores → `data/cooccurrences/`. |
| [`compute_dice.py`](network/compute_dice.py) | Dice coefficient scores (complementary to PMI). |
| [`biography_pmi-dice.ipynb`](network/biography_pmi-dice.ipynb) | Per-biography network analysis. |
| [`calculate_closest_positions.ipynb`](network/calculate_closest_positions.ipynb) | Surface-form proximity analysis. |
| [`convert_kg_rdfstar.ipynb`](network/convert_kg_rdfstar.ipynb) | RDF-star export of the KG. |
| [`link_persons_wikidata.py`](network/link_persons_wikidata.py) | Person → Wikidata QID linker (contributes 320 of 443 persons; see [README §Headline numbers](../README.md#knowledge-graph--population-metrics-e3)). |

### `evaluation/` — CQ coverage and KG metrics *(RQ1 / E1 / E3)*

Two runners that produce the dissertation's evaluation tables. See [`evaluation/README.md`](evaluation/README.md) for the full layout, closure-rule details, runner flags, and classification rubric.

| Runner | Output |
|---|---|
| [`run_cq_evaluation.py`](evaluation/run_cq_evaluation.py) | Every CQ in `data/ontology/CQ_CATALOG.md` → SPARQL → classified fully / partial / un- / non-SPARQL. Reports under `evaluation/reports/`. |
| [`run_kg_evaluation.py`](evaluation/run_kg_evaluation.py) | KG population metrics (instance counts, provenance coverage, external linking, ObliquER activity coverage). Reports under `evaluation/kg_reports/`; latest snapshot in `evaluation/kg_metrics.json`. |
| [`materialise_inferences.py`](evaluation/materialise_inferences.py) | Apply closure rules R1–R3 (`inferences.ru`) and write `data/kg/viewsari_kg.inferred.ttl`. Required by five Phase-I CQs. |

### `data_statistics/` — corpus statistics notebooks *(case study)*

| Notebook | Purpose |
|---|---|
| [`stats.ipynb`](data_statistics/stats.ipynb) | Top-level corpus statistics (volumes, biographies, mentions, types). |
| [`index-stats.ipynb`](data_statistics/index-stats.ipynb) | Index-of-Names statistics. |

Aggregated runner: [`full_stats.py`](full_stats.py).

### `data/` — local staging

Symlinks / working copies used by scripts in this directory so they can be run from `src/`. Authoritative data lives in the top-level [`data/`](../data/).

## Runtime data flow

| Offline pipeline | Output | Runtime consumer |
|---|---|---|
| `kg_population/rebuild_kg.py` | `data/kg/viewsari_kg.ttl` | GraphDB (SPARQL endpoint, person and textchunk pages) |
| `kg_population/build_kb.py` | `data/kb/kb.json` | KB browser, entity pages, homepage stats |
| `extract_content/build_ner_explorer.py` | `data/kg/explorer/ner/*/bio_*.json` | ObliquER KG explorer |
| `extract_content/build_explorer_graphs.py` | `data/kg/explorer/cooccurrence/*.json` | GT co-occurrence explorer |
| `network/compute_pmi.py` / `compute_dice.py` | `data/cooccurrences/*.csv` | Network analysis, KG seeding |

The web app never imports anything from `src/`. Rebuilds are explicit operator steps.

## Dependencies

All scripts use the top-level [`requirements.txt`](../requirements.txt). Key dependencies: `rdflib` (KG manipulation), `httpx` (GraphDB HTTP), `pandas` (notebooks and stats), `beautifulsoup4` (Gutenberg HTML), `wikidataintegrator` (Wikidata linking).
