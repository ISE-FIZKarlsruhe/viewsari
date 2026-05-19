# Viewsari

A provenance-aware knowledge graph and web platform built from Giorgio Vasari's *Le Vite de' piu eccellenti pittori, scultori, e architettori* (1568), the foundational document of Western art history.

Viewsari combines a formal OWL ontology, an LLM-based entity extraction pipeline (ObliquER), a manually annotated gold-standard corpus, and a populated RDF knowledge graph to make Vasari's artwork references computationally accessible, queryable, and explorable.

## Architecture

The repository is split into four top-level concerns:

- **`app/`** — FastAPI web application (runtime). Reads prebuilt JSON, queries GraphDB over HTTP. No `rdflib` is loaded at request time.
- **`src/`** — Offline pipelines. Build the KG, ingest annotations, populate GraphDB, run evaluations, compute statistics.
- **`data/`** — Static data layer. Source corpora (PDFs, OCR, facsimile pages), the ontology, the KG (`.ttl`), the prebuilt knowledge base (`kb.json`), and CSV seed files.
- **`obliquer/`** — Git submodule containing the ObliquER LLM extraction pipeline and the gold-standard ground truth.

```
viewsari/
├── app/                            # FastAPI web application (runtime)
│   ├── main.py                         # Entry point: lifespan, static mounts, router includes
│   ├── routers/                        # Route handlers (one per page/feature)
│   │   ├── index.py                        # Homepage with KB stats
│   │   ├── biography.py                    # Biography paragraph viewer + facsimile pages
│   │   ├── annotations.py                  # Annotation corpus browser (per-bio stats)
│   │   ├── kb.py                           # Knowledge base browser (persons / artworks / mentions)
│   │   ├── kb_resource.py                  # Person + textchunk detail pages (queries GraphDB)
│   │   ├── sparql.py                       # SPARQL proxy + query editor UI
│   │   ├── obliquer.py                     # ObliquER about page + KG explorer API
│   │   ├── explore.py                      # GT co-occurrence graph explorer
│   │   ├── ontology.py                     # Ontology overview page
│   │   ├── publications.py                 # Publications list
│   │   ├── volume.py                       # Volume landing pages
│   │   └── about.py                        # About page
│   ├── data/                           # Runtime data-access layer
│   │   ├── base.py                         # Shared loader interface
│   │   └── json_backend.py                 # Loads kb.json + explorer graphs
│   ├── templates/                      # Jinja2 templates (base.html, page templates, fragments)
│   └── static/                         # Static assets (logo, viewer.js, splash images)
│
├── src/                            # Offline pipelines (not loaded at runtime)
│   ├── kg_population/                  # KG build + GraphDB ingestion
│   │   ├── rebuild_kg.py                   # End-to-end rebuild from backup
│   │   ├── build_viewsari_kg.py            # Initial KG construction
│   │   ├── build_kg_ttl.py                 # Foundation layer from CSV seeds
│   │   ├── ingest_annotations.py           # GT mentions → KG
│   │   ├── ingest_ner_results.py           # ObliquER NER runs → KG
│   │   ├── build_kb.py                     # KG → kb.json (runtime KB)
│   │   ├── build_reasoner_test.py          # Reasoner sanity checks
│   │   ├── rebuild_pages_paragraphs.py     # Page/paragraph refresh
│   │   ├── populate_biographies.ipynb      # Biography seeding notebook
│   │   ├── setup_graphdb.sh                # Create repo + import KG
│   │   └── graphdb-repo-config.ttl         # GraphDB repository config
│   ├── extract_content/                # Corpus parsing + explorer building
│   │   ├── extract_facsimile_pages.py      # Slice Gutenberg HTML into per-page facsimiles
│   │   ├── extract_volume_content.ipynb    # Volume parsing notebook
│   │   ├── ocr_facsimile.py                # OCR pipeline for facsimile pages
│   │   ├── parse_names.py                  # Index-of-Names parser
│   │   ├── scrape_indices.py               # Index scraper
│   │   ├── scrape_bibliography_info.ipynb  # Bibliography enrichment
│   │   ├── get_references.py               # Cross-reference extractor
│   │   ├── fix_headless_corefs.py          # Coref cleanup
│   │   ├── build_ner_explorer.py           # ObliquER → D3 explorer JSONs
│   │   └── build_explorer_graphs.py        # GT co-occurrence explorer JSONs
│   ├── network/                        # Network statistics + Wikidata linking
│   │   ├── compute_pmi.py                  # PMI co-occurrence scores
│   │   ├── compute_dice.py                 # Dice coefficient scores
│   │   ├── biography_pmi-dice.ipynb        # Per-biography network analysis
│   │   ├── calculate_closest_positions.ipynb
│   │   ├── convert_kg_rdfstar.ipynb        # RDF-star export
│   │   └── link_persons_wikidata.py        # Person → Wikidata QID linker
│   ├── evaluation/                     # CQ + KG evaluation
│   │   ├── run_cq_evaluation.py            # Competency-question coverage (§10.2.3)
│   │   ├── run_kg_evaluation.py            # KG population metrics (§9.3)
│   │   ├── materialise_inferences.py       # Apply closure rules
│   │   ├── inferences.ru                   # SPARQL Update inference rules
│   │   ├── cq_catalog.json                 # Competency-question catalog
│   │   ├── kg_metrics.json                 # Latest metrics output
│   │   ├── queries/ + kg_queries/          # CQ query files
│   │   ├── reports/ + kg_reports/          # Evaluation reports
│   │   └── README.md
│   ├── data_statistics/                # Notebook-based corpus statistics
│   │   ├── stats.ipynb                     # Top-level stats
│   │   ├── index-stats.ipynb               # Index-of-Names stats
│   │   └── new.csv
│   ├── data/                           # Local symlinks/staging used by src scripts
│   └── full_stats.py                   # Aggregated stats runner
│
├── data/                           # Static data layer
│   ├── kg/                             # The knowledge graph
│   │   ├── viewsari_kg.ttl                 # Full KG (~1.3M triples, 175 MB)
│   │   ├── viewsari_kg.inferred.ttl        # Materialised closure
│   │   └── explorer/                       # D3 explorer JSONs (NER + co-occurrence)
│   ├── kb/
│   │   └── kb.json                         # Prebuilt KB used by web app
│   ├── kg_foundation/                  # CSV seed files for KG build
│   │   ├── viewsari_volumes.csv
│   │   ├── viewsari_biographies.csv
│   │   ├── viewsari_pages.csv
│   │   ├── viewsari_paragraphs.csv
│   │   ├── viewsari_activities.csv
│   │   ├── persons/                        # Person/annotation/textchunk seeds
│   │   └── cooccurrences/                  # Co-occurrence seeds
│   ├── ontology/                       # OWL ontology + documentation
│   │   ├── viewsari_ontology.rdf           # Source OWL file
│   │   ├── viewsari_ontology_docs/doc/     # WIDOCO HTML docs (served at /ontology/docs)
│   │   ├── reasoning/                      # Small-KG examples for reasoner tests
│   │   ├── CQ_CATALOG.md                   # Competency-question catalog
│   │   ├── catalog-v001.xml                # Protégé catalog
│   │   └── po-no-swrlb.rdf                 # Punning-free variant for tooling
│   ├── facsimile_pages/                # Per-page HTML facsimiles, by volume
│   ├── lives_pdfs/                     # Original Gutenberg PDFs (10 volumes)
│   ├── ocr/                            # OCR'd text per volume
│   ├── index_of_names/                 # Per-volume Index-of-Names CSVs
│   ├── cooccurrences/                  # PMI/Dice tables
│   ├── archive/                        # Archived intermediates (ER, centralities, KG snapshots)
│   ├── img/                            # Site imagery
│   ├── info/                           # PUBLICATIONS.md, README
│   └── README.md
│
├── obliquer/                       # ObliquER pipeline (git submodule)
│   ├── src/                            # Extraction pipeline source
│   ├── data/viewsari/
│   │   ├── ground_truth/                   # Gold-standard annotation JSONs
│   │   ├── prompting_results/              # Per-strategy LLM run outputs
│   │   ├── prompts/                        # Jinja prompt templates
│   │   ├── volumes/ + volumes_original_split/  # Source paragraphs
│   │   ├── inception_kb/ + UIMA_inception_dump/  # INCEpTION exports
│   │   ├── archive/ + eval/                # Snapshots and evaluation
│   │   └── sampled_paragraphs.csv
│   ├── requirements.txt
│   └── README.md
│
├── annotations/                    # Working annotation tables (mirrors of index_of_names)
├── docs/                           # Thesis-side docs (e.g., evaluation_outline.tex)
├── nginx/                          # Reverse proxy
│   ├── nginx.conf                      # Production config
│   └── nginx-init.conf                 # First-boot config
├── Dockerfile                      # Python 3.12 container for the web app
├── docker-compose.yml              # Web + GraphDB + Nginx stack
├── requirements.txt                # Python dependencies
├── RUNBOOK.md                      # Operational runbook
├── SRO.bib                         # BibTeX references
└── README.md                       # This file
```

## Quick start

### Prerequisites

- Docker and Docker Compose
- Git LFS (`brew install git-lfs` / `apt install git-lfs`)

### Local development

```bash
git clone https://github.com/ISE-FIZKarlsruhe/viewsari.git
cd viewsari
git lfs pull
git submodule update --init --recursive

cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9000
```

### Production deployment

```bash
git clone https://github.com/ISE-FIZKarlsruhe/viewsari.git
cd viewsari
git lfs pull
git submodule update --init --recursive

# Start all services
docker compose up --build -d

# Set up GraphDB repository and import the KG
bash src/kg_population/setup_graphdb.sh

# Or manually:
curl -X POST http://localhost:7200/rest/repositories \
  -H "Content-Type: multipart/form-data" \
  -F "config=@src/kg_population/graphdb-repo-config.ttl"
curl -X POST http://localhost:7200/repositories/viewsari/statements \
  -H "Content-Type: text/turtle" --data-binary @data/kg/viewsari_kg.ttl
```

The website is served at `http://localhost:9000`, GraphDB Workbench at `http://localhost:7200`.

## Knowledge graph

The Viewsari KG is serialized as Turtle at `data/kg/viewsari_kg.ttl` (~1.3M triples, 175 MB).

**Namespace:** `vkb:` = `https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#`

### Entity types

| Class | Ontology ID | Count | Description |
|---|---|---|---|
| Person | `viewsari:0001013` | 443 | Consolidated across biographies via coreference resolution |
| Artwork | `viewsari:0001012` | 852 | From GT entity linking (Wikidata or OOKB linked) |
| Co-occurrence | `viewsari:0001025` | 541 | Person pairs within a single paragraph |
| Mention | `oa:Annotation` | 57,685 | GT (2,439) + ObliquER (55,246) |

### Provenance model (PROV-O)

**Ground truth** (two activities):
- `vkb:ground_truth_annotation_run_2` (`viewsari:0001022` NER activity) — produces mentions, `prov:used` 270 paragraphs
- `vkb:ground_truth_entity_linking_run_1` (`viewsari:0001023` EL activity) — produces artwork entities via `prov:wasDerivedFrom` mentions
- Agent: `vkb:sarah_ondraszek` (`prov:Person`), date: March 2026

**ObliquER** (per-extraction activities):
- Parent runs: `vkb:ner_run_few_shot_v2`, `vkb:ner_run_ontology_guided_v2`
- Per-extraction sub-activities: `vkb:ner_run_{strategy}_vol{V}_p{N}_p{M}` with `prov:used` paragraphs + prompt entity, `prov:wasAssociatedWith` LLM agent, timestamps from `provenance.jsonl`
- Prompt text stored as `prov:Entity` with full `.j2` text in `rdfs:comment`
- No artwork entities (entity linking not yet performed for ObliquER)

### Entity identity

- **Wikidata-linked:** URI `vkb:{QID}` with `owl:sameAs` to Wikidata
- **OOKB:** URI `vkb:{fragment}` from the annotation's `ookb_uri`
- Cross-biography consolidation: same QID/OOKB fragment = same entity
- The `entity_id` field in GT JSON files is ignored; identity is determined solely by `wikidata_id` or `ookb_uri`

### Annotation model (OA)

Mentions are `oa:Annotation` + `prov:Entity` instances:
- `oa:hasBody` → `oa:TextualBody` resource carrying the surface form via `rdf:value` (`dc:format "text/plain"`, `dc:language "en"`)
- `oa:hasTarget` — `doco:TextChunk` with `oa:hasSource` (paragraph) + `oa:hasSelector` (`oa:TextPositionSelector` with start/end offsets)
- `prov:wasGeneratedBy` — the NER activity that produced the mention
- `viewsari:0001032` — paragraph anchor

The mention-to-entity link is modeled exclusively through PROV: `entity prov:wasDerivedFrom mention`.

## Offline build scripts

All scripts live under `src/` and require `rdflib`. They are not needed at runtime.

| Script | Purpose |
|---|---|
| `src/kg_population/rebuild_kg.py` | One-shot KG rebuild from backup: namespace migration, ObliquER + GT ingestion |
| `src/kg_population/ingest_annotations.py` | Ingest GT annotations into the KG |
| `src/kg_population/ingest_ner_results.py` | Ingest ObliquER NER results into the KG |
| `src/kg_population/build_kb.py` | Build `data/kb/kb.json` from the KG (persons, artworks, co-occurrences, ObliquER mentions) |
| `src/kg_population/build_kg_ttl.py` | Build the foundation KG layer from CSV seed files |
| `src/kg_population/setup_graphdb.sh` | Create GraphDB repository and import KG |
| `src/extract_content/build_ner_explorer.py` | Build D3-ready explorer graph JSONs from ObliquER response files |
| `src/extract_content/build_explorer_graphs.py` | Build co-occurrence explorer graphs |
| `src/extract_content/extract_facsimile_pages.py` | Slice the Gutenberg HTML into per-page facsimile pages |
| `src/extract_content/ocr_facsimile.py` | OCR pipeline for the facsimile pages |
| `src/network/link_persons_wikidata.py` | Link person entities to Wikidata |
| `src/evaluation/run_cq_evaluation.py` | Competency-question coverage evaluation (§10.2.3) |
| `src/evaluation/run_kg_evaluation.py` | Knowledge-graph population metrics (§9.3) |
| `src/evaluation/materialise_inferences.py` | Apply closure rules to write `viewsari_kg.inferred.ttl` |

### Rebuilding the KG

```bash
python src/kg_population/rebuild_kg.py       # Full rebuild from backup
python src/kg_population/build_kb.py         # Regenerate kb.json
python src/extract_content/build_ner_explorer.py --run oss_v3  # Regenerate explorer graphs
```

After rebuilding, re-import into GraphDB:
```bash
curl -X DELETE http://localhost:7200/repositories/viewsari/statements
curl -X POST http://localhost:7200/repositories/viewsari/statements \
  -H "Content-Type: text/turtle" --data-binary @data/kg/viewsari_kg.ttl
```

## Runtime data flow

| Offline build | Output | Runtime consumer |
|---|---|---|
| `src/kg_population/rebuild_kg.py` | `viewsari_kg.ttl` | GraphDB (SPARQL + person/textchunk pages) |
| `src/kg_population/build_kb.py` | `kb.json` | KB browser, entity pages, homepage stats |
| `src/extract_content/build_ner_explorer.py` | `explorer/ner/*/bio_*.json` | ObliquER KG explorer |

No `rdflib` is loaded at request time. The web application queries GraphDB via HTTP (`httpx`) or reads prebuilt JSON files.

## Website features

- **Biography viewer** — facsimile pages, annotated paragraph text with color-coded mention spans, provenance graphs, Wikidata image integration
- **Knowledge base** — browsable persons, artworks (GT), ObliquER explicit/implicit mentions, co-occurrences with search and source filters
- **KG explorer** — D3 force-directed graph visualization of ObliquER extraction results per biography, with per-extraction activity nodes, prompt text viewing, pinnable nodes, clickable info panels
- **SPARQL endpoint** — browser-based query editor proxying GraphDB, with 10 pre-built example queries
- **Annotation corpus** — per-biography statistics with mention type distribution, Wikidata/OOKB percentages
- **Ontology overview** — interactive class hierarchy visualization, three-layer architecture documentation
- **ObliquER pipeline** — about page, interactive demo, extraction explorer

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANNOTATIONS_DIR` | `./obliquer/data/viewsari/ground_truth` | Path to GT annotation JSONs |
| `DATA_DIR` | `./data/kg_foundation` | Path to CSV foundation files |
| `GRAPHDB_URL` | `http://localhost:7200` | GraphDB endpoint |
| `GRAPHDB_REPO` | `viewsari` | GraphDB repository name |

## Docker services

| Service | Image | Port | Purpose |
|---|---|---|---|
| `viewsari` | Built from `Dockerfile` | 9000 (internal) | FastAPI web app |
| `graphdb` | `ontotext/graphdb:10.8.4` | 7200 | RDF triplestore + SPARQL |
| `nginx` | `nginx:alpine` | 9000 (exposed) | Reverse proxy |

## Ontology

The Viewsari ontology (`data/ontology/`) is a three-layer OWL vocabulary:

1. **Bibliographic layer** — volumes, editions, translations (FRBR/FaBiO)
2. **Document layer** — biographies, pages, paragraphs (DOCO)
3. **Content layer** — mentions, artworks, persons, extraction activities (OA, PROV-O)

WIDOCO documentation is served at `/ontology/docs`.

## License

This project is part of doctoral research at FIZ Karlsruhe / KIT ISE.

## Citation

```bibtex
@phdthesis{ondraszek2026viewsari,
  author = {Ondraszek, Sarah Rebecca},
  title  = {Modeling Interpretation in the Age of GenAI: Semantic Technologies
            for Digital Humanities Research Based on Giorgio Vasari's The Lives},
  school = {Karlsruher Institut f{\"u}r Technologie (KIT)},
  year   = {2026}
}
```
