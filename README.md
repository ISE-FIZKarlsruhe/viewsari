# Viewsari

A provenance-aware knowledge graph and web platform built from Giorgio Vasari's *Le Vite de' piu eccellenti pittori, scultori, e architettori* (1568), the foundational document of Western art history.

Viewsari combines a formal OWL ontology, an LLM-based entity extraction pipeline (ObliquER), a manually annotated gold-standard corpus, and a populated RDF knowledge graph to make Vasari's artwork references computationally accessible, queryable, and explorable.

## Architecture

```
viewsari/
├── app/                    # FastAPI web application
│   ├── main.py             # Entry point
│   ├── routers/            # Route handlers
│   │   ├── index.py        # Homepage
│   │   ├── biography.py    # Biography paragraph viewer
│   │   ├── annotations.py  # Annotation corpus browser
│   │   ├── kb.py           # Knowledge base browser
│   │   ├── kb_resource.py  # Person / textchunk pages (queries GraphDB)
│   │   ├── sparql.py       # SPARQL endpoint proxy (queries GraphDB)
│   │   ├── obliquer.py     # ObliquER pages + explorer API
│   │   ├── explore.py      # GT KG explorer
│   │   ├── ontology.py     # Ontology overview
│   │   ├── publications.py # Publications list
│   │   ├── volume.py       # Volume pages
│   │   └── about.py        # About page
│   ├── templates/          # Jinja2 HTML templates
│   ├── static/             # Static assets (JS, images)
│   └── data/               # Data loading backend
├── scripts/                # Offline build & ingestion scripts
├── data/                   # KG foundation, ontology, facsimile pages
│   ├── kg/                 # viewsari_kg.ttl (the KG) + explorer JSONs
│   ├── kb/                 # kb.json (prebuilt knowledge base)
│   ├── kg_foundation/      # CSV seed files (paragraphs, biographies, etc.)
│   └── ontology/           # OWL ontology + WIDOCO docs
├── obliquer/               # ObliquER submodule (extraction pipeline + GT)
│   └── data/viewsari/
│       ├── ground_truth/   # Gold-standard annotation JSONs
│       └── prompting_results/  # LLM extraction runs
├── nginx/                  # Reverse proxy config
├── Dockerfile              # Python 3.12 container
├── docker-compose.yml      # Web + GraphDB + Nginx
└── requirements.txt        # Python dependencies
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
bash scripts/setup_graphdb.sh

# Or manually:
curl -X POST http://localhost:7200/rest/repositories \
  -H "Content-Type: multipart/form-data" \
  -F "config=@scripts/graphdb-repo-config.ttl"
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
| Artwork | `viewsari:0001012` | 825 | From GT entity linking (Wikidata or OOKB linked) |
| Co-occurrence | `viewsari:0001025` | 541 | Person pairs within a single paragraph |
| Mention | `oa:Annotation` | 57,684 | GT (2,438) + ObliquER (55,246) |

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
- `oa:hasBodyValue` — surface form (literal text span)
- `oa:hasTarget` — `doco:TextChunk` with `oa:hasSource` (paragraph) + `oa:hasSelector` (`oa:TextPositionSelector` with start/end offsets)
- `prov:wasGeneratedBy` — the NER activity that produced the mention
- `viewsari:0001032` — paragraph anchor

No `oa:hasBody` is used. The mention-to-entity link is modeled exclusively through PROV: `entity prov:wasDerivedFrom mention`.

## Offline build scripts

All scripts live in `scripts/` and require `rdflib`. They are not needed at runtime.

| Script | Purpose |
|---|---|
| `rebuild_kg.py` | One-shot KG rebuild from backup: namespace migration, ObliquER + GT ingestion |
| `ingest_annotations.py` | Ingest GT annotations into the KG |
| `ingest_ner_results.py` | Ingest ObliquER NER results into the KG |
| `build_kb.py` | Build `data/kb/kb.json` from the KG (persons, artworks, co-occurrences, ObliquER mentions) |
| `build_ner_explorer.py` | Build D3-ready explorer graph JSONs from ObliquER response files |
| `build_kg_ttl.py` | Build the foundation KG layer from CSV seed files |
| `link_persons_wikidata.py` | Link person entities to Wikidata |
| `setup_graphdb.sh` | Create GraphDB repository and import KG |

### Rebuilding the KG

```bash
python scripts/rebuild_kg.py       # Full rebuild from backup
python scripts/build_kb.py         # Regenerate kb.json
python scripts/build_ner_explorer.py --run oss_v3  # Regenerate explorer graphs
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
| `rebuild_kg.py` | `viewsari_kg.ttl` | GraphDB (SPARQL + person/textchunk pages) |
| `build_kb.py` | `kb.json` | KB browser, entity pages, homepage stats |
| `build_ner_explorer.py` | `explorer/ner/*/bio_*.json` | ObliquER KG explorer |

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
