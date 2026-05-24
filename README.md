# Viewsari

A provenance-aware knowledge graph and web platform built from Giorgio Vasari's *Le Vite de' piu eccellenti pittori, scultori, e architettori* (1568), via the Du Vere 1912 English translation digitized by Project Gutenberg.

Viewsari combines a formal OWL ontology, an LLM-based entity-recognition-and-linking pipeline (ObliquER), a manually annotated gold-standard corpus, and a populated RDF knowledge graph, all designed to keep the *interpretive activity* that produced every extracted statement visible at the level of the graph.

> *Knowledge extracted from interpretative texts is not discovered but constructed; therefore, knowledge graphs must model and make visible the construction process itself.*

---

## Dissertation contributions → repository map

The repository is the artifact side of the dissertation. Each conceptual contribution (**C1–C4**), empirical contribution (**E1–E4**), and research question (**RQ1–RQ3**) listed in the Introduction is implemented by a concrete part of this codebase. The tables below map each contribution to the files and directories that operationalize it, alongside the dissertation chapter that documents it.

### Empirical contributions

| | Contribution | What lives here | Chapter |
|---|---|---|---|
| **E1** | **The Viewsari ontology** — OWL 2 DL, three-layer architecture (bibliographic / structural / content), integrating PROV-O and the W3C Web Annotation Ontology. | [`data/ontology/`](data/ontology/) — source OWL ([`viewsari_ontology.rdf`](data/ontology/viewsari_ontology.rdf)), [WIDOCO docs](data/ontology/viewsari_ontology_docs/doc/), [ontology README](data/ontology/README.md), [`reasoning/`](data/ontology/reasoning/) examples. CQ catalog: [`CQ_CATALOG.md`](data/ontology/CQ_CATALOG.md). | Methodology |
| **E2** | **The ObliquER pipeline** — modular generative extraction; every step is a PROV-O activity in the graph; modular prompts (content vs. template); explicit / implicit / coreferent / generic mention typology. | [`obliquer/`](obliquer/) git submodule (source under `obliquer/src/`, prompts under `obliquer/data/viewsari/prompts/`, per-strategy runs under `obliquer/data/viewsari/prompting_results/`). Ingestion into the KG: [`src/kg_population/ingest_ner_results.py`](src/kg_population/ingest_ner_results.py). KG explorer build: [`src/extract_content/build_ner_explorer.py`](src/extract_content/build_ner_explorer.py). | Methodology |
| **E3** | **The Viewsari knowledge graph and web interface** — populated KG with 100% provenance coverage; web app for non-technical exploration; interactive graph visualization. | KG: [`data/kg/viewsari_kg.ttl`](data/kg/viewsari_kg.ttl), inferred closure [`viewsari_kg.inferred.ttl`](data/kg/viewsari_kg.inferred.ttl). Explorer JSONs: [`data/kg/explorer/`](data/kg/explorer/). KG build pipeline: [`src/kg_population/`](src/kg_population/). Runtime KB: [`data/kb/kb.json`](data/kb/kb.json). Web app: [`app/`](app/). | Methodology, Results |
| **E4** | **Transferability pilot** — Viewsari ontology and ObliquER reconfigured for 19th-century German documentary sources (Illuminati order), linked to FactGrid. Only the prompt content layer is modified. | Transferability runs and prompts are documented from the ObliquER side in [`obliquer/`](obliquer/). | Generalization |

### Conceptual contributions

| | Contribution | Where it is operationalized in the repo |
|---|---|---|
| **C1** | **The pre-interpretive entity assumption (PIEA)** — articulates the assumption that mention-to-referent resolution can be treated as completed prior to representation; rejects it via a three-layer ontology (bibliographic / structural / content) maintaining the distinction between mention, referent, and bibliographic source. | The three-layer split is the structure of the ontology in [`data/ontology/`](data/ontology/) and the class layout summarized in [Ontology](#ontology) below. The mention typology lives under `viewsari:mention` (explicit / implicit / coreferent / generic). |
| **C2** | **The provenance gap in generative information extraction** — provenance must be a first-class part of the schema, not a post-hoc transparency layer. | Every ObliquER extraction is reified as a PROV-O activity in [`data/kg/viewsari_kg.ttl`](data/kg/viewsari_kg.ttl). Ingestion code: [`src/kg_population/ingest_ner_results.py`](src/kg_population/ingest_ner_results.py). Prompt text is stored as `prov:Entity` with full `.j2` text in `rdfs:comment`. |
| **C3** | **Hermeneutic provenance is categorically distinct from explainable AI** — the provenance humanities scholarship requires is hermeneutic (on what textual basis, under which convention, by which agent), not mechanistic (which input tokens drove this output). | Made inspectable by the web KG explorer: per-extraction activity nodes, prompt-text panels, clickable mention spans, source paragraph anchors. Routers: [`app/routers/biography.py`](app/routers/biography.py), [`app/routers/obliquer.py`](app/routers/obliquer.py), [`app/routers/kb_resource.py`](app/routers/kb_resource.py). |
| **C4** | **Computational Provenance (COMP-PROV) as an ontology design pattern** — reifies extraction agent, prompt, model version, and run as first-class entities linked to every assertion. | Pattern realized in the content layer of [`data/ontology/`](data/ontology/) (extraction activities, prompt entities, agents). Same pattern instantiated in the transferability pilot (E4). |

### Research questions

| | Question | Answered by |
|---|---|---|
| **RQ1** | What representational commitments must a knowledge graph make to remain accountable to the interpretive act that produced it, and how can these commitments be operationalized in a provenance-aware ontology? | **C1** + **E1** → [`data/ontology/`](data/ontology/), [`data/kg/viewsari_kg.ttl`](data/kg/viewsari_kg.ttl) |
| **RQ2** | Under what conditions can LLMs, treated as interpretive agents, recognize and link implicit and out-of-knowledge-base entity mentions that lie beyond span-level supervised baselines? | **C2** + **C3** + **E2** + **E3** → [`obliquer/`](obliquer/), [`src/extract_content/`](src/extract_content/), [`app/`](app/) |
| **RQ3** | Which design patterns recur across provenance-aware KGs in the digital humanities, and to what extent does the Viewsari methodology transfer to structurally distinct interpretive corpora? | **C4** + **E4** → comparative pattern analysis (documented in the dissertation Generalization chapter); reconfiguration documented in [`obliquer/`](obliquer/) for the 19th-century German pilot. |

### Evaluation map (where the numbers come from)

| Concern | Where to look |
|---|---|
| **Competency-question coverage** (RQ1 / E1) — every CQ from [`data/ontology/CQ_CATALOG.md`](data/ontology/CQ_CATALOG.md) translated into SPARQL and classified as fully / partially / un- / non-SPARQL-answerable. | [`src/evaluation/run_cq_evaluation.py`](src/evaluation/run_cq_evaluation.py), queries under [`src/evaluation/queries/`](src/evaluation/queries/), reports under [`src/evaluation/reports/`](src/evaluation/reports/), catalog [`src/evaluation/cq_catalog.json`](src/evaluation/cq_catalog.json). |
| **KG population metrics** (E3) — entity counts, provenance-coverage strict/loose, external linking ratios, ObliquER activity coverage. | [`src/evaluation/run_kg_evaluation.py`](src/evaluation/run_kg_evaluation.py), queries under [`src/evaluation/kg_queries/`](src/evaluation/kg_queries/), reports under [`src/evaluation/kg_reports/`](src/evaluation/kg_reports/), latest metrics in [`src/evaluation/kg_metrics.json`](src/evaluation/kg_metrics.json). |
| **Inference closure rules** (R1–R3) needed by 5 Phase-I CQs. | [`src/evaluation/inferences.ru`](src/evaluation/inferences.ru), [`src/evaluation/materialise_inferences.py`](src/evaluation/materialise_inferences.py). |
| **ObliquER NER/EL performance** (RQ2 / E2) — per-strategy F1 against the gold standard. | Run outputs and eval under [`obliquer/`](obliquer/) (`prompting_results/`, `eval/`). Gold standard: `obliquer/data/viewsari/ground_truth/`. |
| **Corpus statistics** (case study chapter) — mention-type distribution, per-biography counts, Wikidata / OOKB percentages, top entities. | [`src/data_statistics/stats.ipynb`](src/data_statistics/stats.ipynb), [`src/data_statistics/index-stats.ipynb`](src/data_statistics/index-stats.ipynb), [`src/full_stats.py`](src/full_stats.py). |
| **Co-occurrence / network analysis** (motivating prior work referenced in the case study). | [`src/network/compute_pmi.py`](src/network/compute_pmi.py), [`src/network/compute_dice.py`](src/network/compute_dice.py), [`src/network/biography_pmi-dice.ipynb`](src/network/biography_pmi-dice.ipynb), pre-computed tables under [`data/cooccurrences/`](data/cooccurrences/). |
| **Wikidata linking** of person entities. | [`src/network/link_persons_wikidata.py`](src/network/link_persons_wikidata.py). |

### Evaluation results (headline numbers)

#### Ontology — competency-question coverage (RQ1 / E1)

Over the 70 CQs in [`data/ontology/CQ_CATALOG.md`](data/ontology/CQ_CATALOG.md); latest run [`src/evaluation/reports/cq_evaluation_20260428_083554.md`](src/evaluation/reports/cq_evaluation_20260428_083554.md):

| Status | Count | % of all 70 | % of SPARQL-only (52) |
|---|---|---|---|
| Fully answerable | 52 | 74.3% | 100.0% |
| Partially answerable | 0 | 0.0% | 0.0% |
| Unanswerable | 0 | 0.0% | 0.0% |
| Non-SPARQL (descriptive) | 18 | 25.7% | n/a |

All 13 thematic clusters reach 100% coverage on the SPARQL-answerable subset. Complexity mix: 28 multi-hop, 15 simple, 9 aggregation.

#### Knowledge graph — population metrics (E3)

From [`src/evaluation/kg_reports/kg_evaluation_20260428_060320.md`](src/evaluation/kg_reports/kg_evaluation_20260428_060320.md) (closure-materialized KG):

| Metric | Value |
|---|---|
| Total triples | 1,340,791 |
| `oa:Annotation` mentions | 83,154 |
| `viewsari:mention` instances | 57,685 |
| Triples per mention | 9.12 |
| Provenance coverage (annotation → SoftwareAgent) | **100%** (83,154 / 83,154) |
| Provenance coverage — strict (paragraph + activity + agent) | 66.4% (55,246 / 83,154) |
| NER activities · entity-linking activities | 6,961 · 1 |
| Pages with Project Gutenberg web manifestation | 92.3% (volumes + biographies: 100%) |

Mention typology: explicit 9,588 · implicit 27,098 · coreferent 14,445 · generic 6,554. External linking: persons 320/443 (72.2%) to Wikidata, artworks 272/813 (33.5%); 541 artworks remain OOKB.

#### ObliquER — entity recognition and linking (RQ2 / E2)

From the ObliquER CIKM '26 paper. Primary model: `openai/gpt-oss-120b`.

**Entity recognition on Viewsari** (span-level, SemEval-2013 task 9.1 matching):

| Eval mode | P | R | F1 |
|---|---|---|---|
| Strict | 0.27 | 0.37 | 0.31 |
| Exact | 0.29 | 0.41 | 0.34 |
| Type | 0.54 | 0.75 | 0.63 |
| Partial | 0.45 | 0.62 | 0.52 |

95% bootstrap CIs (n = 1000): Strict F1 [0.28, 0.34], Type F1 [0.59, 0.66]. Against zero-shot baselines on Viewsari (Strict F1, all mentions): ObliquER **0.32**, GLiNER2 0.09, UniNER 0.02 — 95% CIs do not overlap. Prior explicit-only UniNER baseline on Vasari (Santini et al. 2022): F1 = 0.556. On ArtPedia (transferability): Strict F1 0.22 · Partial F1 0.38 · Type F1 0.47.

**Entity linking on Viewsari** (gold mentions, P / R / F1):

| Subset | KB-linked | OOKB | Cand. recall |
|---|---|---|---|
| All | 0.38 / 0.47 / **0.42** | 0.73 / 0.60 / **0.66** | 0.68 |
| Explicit | 0.63 / 0.45 / 0.53 | 0.64 / 0.36 / 0.46 | 0.69 |
| Implicit | 0.29 / 0.48 / 0.36 | 0.83 / 0.60 / 0.70 | 0.67 |

End-to-end (NER → EL, no gold mentions): KB-linked F1 0.33 (All) / 0.41 (Expl.) / 0.30 (Impl.); OOKB F1 0.75 (All). On ArtPedia EL with gold mentions: KB-linked F1 = **0.75** vs. ReFinED 0.04 / BLINK 0.16 / GENRE 0.16.

**Annotation reliability** (25-paragraph double-annotated sample): span F1 0.83 partial / 0.43 exact; token-level κ = 0.70 ("substantial"); type κ on matched spans 0.89 partial / 0.70 exact; Wikidata-QID agreement F1 = 0.84; OOKB-classification agreement F1 = 0.90.

**Ground-truth corpus** — Viewsari: 232 paragraphs, 961 entities (398 Wikidata-linked, 545 OOKB), 1,010 mentions, 56.7% OOKB entities. ArtPedia synthetic implicit split: 7,618 paragraphs, 2,679 entities, 21,774 mentions, 0.26% OOKB entities.

---

## Repository layout

The repository is split into four top-level concerns:

- **`app/`** — FastAPI web application (runtime). Reads prebuilt JSON, queries GraphDB over HTTP. No `rdflib` is loaded at request time. *(E3, C3)*
- **`src/`** — Offline pipelines. Build the KG, ingest annotations, populate GraphDB, run evaluations, compute statistics. *(E2 ingestion, E3 build, evaluation for RQ1/RQ2)*
- **`data/`** — Static data layer. Source corpora (PDFs, OCR, facsimile pages), the ontology, the KG (`.ttl`), the prebuilt knowledge base (`kb.json`), and CSV seed files. *(E1 + E3 artifacts)*
- **`obliquer/`** — Git submodule containing the ObliquER LLM extraction pipeline and the gold-standard ground truth. *(E2; reconfigured for E4)*

```
viewsari/
├── app/                            # FastAPI web application (runtime) — E3
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
│   ├── kg_population/                  # KG build + GraphDB ingestion — E3
│   │   ├── rebuild_kg.py                   # End-to-end rebuild from backup
│   │   ├── build_viewsari_kg.py            # Initial KG construction
│   │   ├── build_kg_ttl.py                 # Foundation layer from CSV seeds
│   │   ├── ingest_annotations.py           # GT mentions → KG
│   │   ├── ingest_ner_results.py           # ObliquER NER runs → KG (E2 → E3)
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
│   │   ├── build_ner_explorer.py           # ObliquER → D3 explorer JSONs (E2 → E3)
│   │   └── build_explorer_graphs.py        # GT co-occurrence explorer JSONs
│   ├── network/                        # Network statistics + Wikidata linking
│   │   ├── compute_pmi.py                  # PMI co-occurrence scores
│   │   ├── compute_dice.py                 # Dice coefficient scores
│   │   ├── biography_pmi-dice.ipynb        # Per-biography network analysis
│   │   ├── calculate_closest_positions.ipynb
│   │   ├── convert_kg_rdfstar.ipynb        # RDF-star export
│   │   └── link_persons_wikidata.py        # Person → Wikidata QID linker
│   ├── evaluation/                     # CQ + KG evaluation — RQ1, E1, E3
│   │   ├── run_cq_evaluation.py            # Competency-question coverage (Evaluation chapter)
│   │   ├── run_kg_evaluation.py            # KG population metrics
│   │   ├── materialise_inferences.py       # Apply closure rules
│   │   ├── inferences.ru                   # SPARQL Update inference rules
│   │   ├── cq_catalog.json                 # Competency-question catalog
│   │   ├── kg_metrics.json                 # Latest metrics output
│   │   ├── queries/ + kg_queries/          # CQ query files
│   │   ├── reports/ + kg_reports/          # Evaluation reports
│   │   └── README.md
│   ├── data_statistics/                # Notebook-based corpus statistics (case-study chapter)
│   │   ├── stats.ipynb                     # Top-level stats
│   │   ├── index-stats.ipynb               # Index-of-Names stats
│   │   └── new.csv
│   ├── data/                           # Local symlinks/staging used by src scripts
│   └── full_stats.py                   # Aggregated stats runner
│
├── data/                           # Static data layer — E1 ontology, E3 KG, source corpus
│   ├── kg/                             # The knowledge graph (E3)
│   │   ├── viewsari_kg.ttl                 # Full KG (~1.3M triples, 175 MB)
│   │   ├── viewsari_kg.inferred.ttl        # Materialized closure
│   │   └── explorer/                       # D3 explorer JSONs (NER + co-occurrence)
│   ├── kb/
│   │   └── kb.json                         # Prebuilt KB used by web app
│   ├── kg_foundation/                  # CSV seed files for KG build (bibliographic + structural layer)
│   │   ├── viewsari_volumes.csv
│   │   ├── viewsari_biographies.csv
│   │   ├── viewsari_pages.csv
│   │   ├── viewsari_paragraphs.csv
│   │   ├── viewsari_activities.csv
│   │   ├── persons/                        # Person/annotation/textchunk seeds
│   │   └── cooccurrences/                  # Co-occurrence seeds
│   ├── ontology/                       # OWL ontology + documentation — E1, C1
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
│   ├── info/                           # Project description + PUBLICATIONS.md
│   └── README.md
│
├── obliquer/                       # ObliquER pipeline (git submodule) — E2, reconfigured for E4
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
├── docs/                           # Auxiliary docs (e.g. evaluation_outline.tex)
├── nginx/                          # Reverse proxy
│   ├── nginx.conf                      # Production config
│   └── nginx-init.conf                 # First-boot config
├── Dockerfile                      # Python 3.12 container for the web app
├── docker-compose.yml              # Web + GraphDB + Nginx stack
├── requirements.txt                # Python dependencies
├── RUNBOOK.md                      # Operational runbook
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

## Knowledge graph (E3)

The Viewsari KG is serialized as Turtle at [`data/kg/viewsari_kg.ttl`](data/kg/viewsari_kg.ttl) (~1.3M triples, 175 MB), with a materialized closure at [`data/kg/viewsari_kg.inferred.ttl`](data/kg/viewsari_kg.inferred.ttl).

**Namespace:** `vkb:` = `https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#`

### Entity types

| Class | Ontology ID | Count | Description |
|---|---|---|---|
| Person | `viewsari:0001013` | 443 | Consolidated across biographies via coreference resolution |
| Artwork | `viewsari:0001012` | 852 | From GT entity linking (Wikidata or OOKB linked) |
| Co-occurrence | `viewsari:0001025` | 541 | Person pairs within a single paragraph |
| Mention | `oa:Annotation` | 57,685 | GT (2,439) + ObliquER (55,246) |

### Provenance model (PROV-O) — operationalizes C2

**Ground truth** (two activities):
- `vkb:ground_truth_annotation_run_2` (`viewsari:0001022` NER activity) — produces mentions, `prov:used` 232 paragraphs
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

### Annotation model (OA) — operationalizes C1

Mentions are `oa:Annotation` + `prov:Entity` instances:
- `oa:hasBody` → `oa:TextualBody` resource carrying the surface form via `rdf:value` (`dc:format "text/plain"`, `dc:language "en"`)
- `oa:hasTarget` — `doco:TextChunk` with `oa:hasSource` (paragraph) + `oa:hasSelector` (`oa:TextPositionSelector` with start/end offsets)
- `prov:wasGeneratedBy` — the NER activity that produced the mention
- `viewsari:0001032` — paragraph anchor

The mention-to-entity link is modeled exclusively through PROV: `entity prov:wasDerivedFrom mention`. The mention and the referent are kept separate as a structural commitment (C1, PIEA).

## Offline build scripts

All scripts live under `src/` and require `rdflib`. They are not needed at runtime.

| Script | Purpose | Contribution |
|---|---|---|
| `src/kg_population/rebuild_kg.py` | One-shot KG rebuild from backup: namespace migration, ObliquER + GT ingestion | E3 |
| `src/kg_population/ingest_annotations.py` | Ingest GT annotations into the KG | E3 |
| `src/kg_population/ingest_ner_results.py` | Ingest ObliquER NER results into the KG | E2 → E3 |
| `src/kg_population/build_kb.py` | Build `data/kb/kb.json` from the KG | E3 |
| `src/kg_population/build_kg_ttl.py` | Build the foundation KG layer from CSV seeds | E3 |
| `src/kg_population/setup_graphdb.sh` | Create GraphDB repository and import KG | E3 |
| `src/extract_content/build_ner_explorer.py` | Build D3-ready explorer graph JSONs from ObliquER response files | E2 → E3 (C3 inspection) |
| `src/extract_content/build_explorer_graphs.py` | Build co-occurrence explorer graphs | E3 |
| `src/extract_content/extract_facsimile_pages.py` | Slice the Gutenberg HTML into per-page facsimile pages | case study |
| `src/extract_content/ocr_facsimile.py` | OCR pipeline for the facsimile pages | case study |
| `src/network/link_persons_wikidata.py` | Link person entities to Wikidata | E3 |
| `src/evaluation/run_cq_evaluation.py` | Competency-question coverage evaluation | RQ1 / E1 |
| `src/evaluation/run_kg_evaluation.py` | Knowledge-graph population metrics | E3 |
| `src/evaluation/materialise_inferences.py` | Apply closure rules to write `viewsari_kg.inferred.ttl` | RQ1 / E1 |

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

## Website features (E3, C3)

Each surface makes a different layer of the provenance chain inspectable; this is the C3 "hermeneutic provenance is inspectable, not just present" commitment in practice:

- **Biography viewer** — facsimile pages, annotated paragraph text with color-coded mention spans, provenance graphs, Wikidata image integration
- **Knowledge base** — browsable persons, artworks (GT), ObliquER explicit/implicit mentions, co-occurrences with search and source filters
- **KG explorer** — D3 force-directed graph of ObliquER extraction results per biography, with per-extraction activity nodes, prompt-text viewing, pinnable nodes, clickable info panels
- **SPARQL endpoint** — browser-based query editor proxying GraphDB, with pre-built example queries
- **Annotation corpus** — per-biography statistics with mention-type distribution, Wikidata/OOKB percentages
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

The Viewsari ontology ([`data/ontology/`](data/ontology/)) is a three-layer OWL vocabulary that operationalizes **C1** (rejection of PIEA) and the **C4** COMP-PROV pattern:

1. **Bibliographic layer** — volumes, editions, translations (FRBR / FaBiO)
2. **Structural layer** — biographies, pages, paragraphs (DoCO + Web Annotation positioning)
3. **Content layer** — mentions, artworks, persons, extraction activities, prompts (OA, PROV-O)

WIDOCO documentation is served at `/ontology/docs`. See [`data/ontology/README.md`](data/ontology/README.md) for the full layer breakdown, class tables, and design decisions.

## License

This project is part of doctoral research at FIZ Karlsruhe / KIT ISE.