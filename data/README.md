# Viewsari — `data/` layer

This directory is the **static data layer** of the Viewsari repository. It holds:

- the populated knowledge graph (**E3**),
- the OWL ontology that gives the graph its schema (**E1**),
- the CSV seed files used by the offline build pipeline,
- the source corpus (PDFs, OCR'd text, facsimile pages, Index of Names) from the 1912 Du Vere translation of Giorgio Vasari's *Le Vite* as digitized by Project Gutenberg,
- pre-computed co-occurrence tables and explorer JSONs used by the website,
- the project description and publications list under [`info/`](info/).


For the full repo-wide mapping of contributions (C1–C4, E1–E4) and research questions (RQ1–RQ3) to files, see the [top-level README](../README.md#dissertation-contributions--repository-map). For details on the offline build that produces the contents of [`kg_foundation/`](kg_foundation/), see [`src/kg_population/`](../src/kg_population/).

---

## Layout

```
data/
├── kg/                    # The knowledge graph (E3)
│   ├── viewsari_kg.ttl              # Full KG (~1.3M triples, 175 MB)
│   ├── viewsari_kg.inferred.ttl     # Materialized closure (R1/R2/R3 applied)
│   └── explorer/                    # D3 explorer JSONs (per biography / artwork / person)
│       └── ner/                         # ObliquER per-strategy NER explorer graphs
│
├── ontology/              # OWL ontology + WIDOCO docs (E1, C1, C4)
│   ├── viewsari_ontology.rdf        # Source OWL/RDF-XML
│   ├── viewsari_ontology_docs/      # WIDOCO HTML docs (served at /ontology/docs)
│   ├── reasoning/                   # Small-KG examples for reasoner tests
│   ├── CQ_CATALOG.md                # Competency-question catalog (input to RQ1 evaluation)
│   ├── po-no-swrlb.rdf              # Punning-free variant for tooling
│   ├── catalog-v001.xml             # Protégé catalog
│   └── README.md
│
├── kg_foundation/         # CSV seeds for the KG build (bibliographic + structural layer)
│   ├── viewsari_volumes.csv         # 20 rows  (10 volumes × expression + manifestation)
│   ├── viewsari_biographies.csv     # 288 rows (144 biographies × expr + man)
│   ├── viewsari_pages.csv           # 6,258 rows (3,129 pages × expr + man)
│   ├── viewsari_paragraphs.csv      # 3,479 rows (one per merged paragraph)
│   ├── viewsari_activities.csv      # Activity seeds (NER, coref, EL, ObliquER)
│   ├── persons/                     # Person + annotation + textchunk + selector seeds
│   │   ├── viewsari_persons.csv         # 443 person entities
│   │   ├── viewsari_annotations.csv     # 24,827 oa:Annotation rows
│   │   ├── viewsari_textchunks.csv      # 24,827 doco:TextChunk rows
│   │   └── viewsari_selectors.csv       # 24,827 oa:TextPositionSelector rows
│   └── cooccurrences/               # Co-occurrence annotation seeds (analogous structure)
│
├── kb/
│   └── kb.json                      # Prebuilt KB used by the web app at runtime
│
├── lives_pdfs/            # Source corpus — original Gutenberg PDFs (10 volumes)
├── ocr/                   # OCR'd text per volume
├── facsimile_pages/       # Per-page HTML facsimiles, by volume (numbered 1–10)
├── index_of_names/        # Per-volume Index-of-Names CSVs (NER + coref index)
├── cooccurrences/         # Per-volume co-occurrence tables + results/
├── archive/               # Archived intermediates (ER snapshots, centralities, KG backups)
├── img/                   # Site imagery (logos, splash images)
└── info/
    ├── README.md                    # Project description
    └── PUBLICATIONS.md              # Associated peer-reviewed publications
```

---

## What lives where, by contribution

| Contribution | Files / dirs |
|---|---|
| **E1** — Viewsari ontology | [`ontology/`](ontology/), see [`ontology/README.md`](ontology/README.md) |
| **E3** — Viewsari KG | [`kg/viewsari_kg.ttl`](kg/viewsari_kg.ttl), [`kg/viewsari_kg.inferred.ttl`](kg/viewsari_kg.inferred.ttl), [`kg/explorer/`](kg/explorer/), [`kb/kb.json`](kb/kb.json) |
| Foundation (used to build E3) | [`kg_foundation/`](kg_foundation/) — CSV seeds; built by [`src/kg_population/build_kg_ttl.py`](../src/kg_population/build_kg_ttl.py) |
| Source corpus (case-study chapter) | [`lives_pdfs/`](lives_pdfs/), [`ocr/`](ocr/), [`facsimile_pages/`](facsimile_pages/), [`index_of_names/`](index_of_names/) |
| Co-occurrence inputs (referenced in case-study chapter, used by the GT co-occurrence explorer) | [`cooccurrences/`](cooccurrences/) |
| RQ1 / E1 evaluation inputs | [`ontology/CQ_CATALOG.md`](ontology/CQ_CATALOG.md), evaluated by [`src/evaluation/run_cq_evaluation.py`](../src/evaluation/run_cq_evaluation.py) |

---

## Knowledge graph (`kg/`)

| File | Description |
|---|---|
| `viewsari_kg.ttl` | Full populated KG, Turtle. Three-layer ontology (bibliographic / structural / content) instantiated over Vasari's *The Lives*. ~1.3M triples, ~175 MB. |
| `viewsari_kg.inferred.ttl` | Materialised closure produced by [`src/evaluation/materialise_inferences.py`](../src/evaluation/materialise_inferences.py); adds the artwork / co-occurrence / person → paragraph edges required by five Phase-I CQs. |
| `explorer/*.json` | D3-ready explorer graphs consumed by the website's GT co-occurrence explorer ([`app/routers/explore.py`](../app/routers/explore.py)). |
| `explorer/ner/*/bio_*.json` | Per-strategy ObliquER explorer graphs (one folder per prompting strategy, one JSON per biography), consumed by the ObliquER KG explorer ([`app/routers/obliquer.py`](../app/routers/obliquer.py)). |

**Namespace:** `vkb:` = `https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#`.

### Headline counts in the populated KG

| Class | Ontology ID | Count |
|---|---|---|
| Person | `viewsari:0001013` | 443 |
| Artwork | `viewsari:0001012` | 852 |
| Co-occurrence | `viewsari:0001025` | 541 |
| Mention (`oa:Annotation`) | — | 57,685 (GT 2,439 + ObliquER 55,246) |

Provenance coverage of the populated KG is reported by [`src/evaluation/run_kg_evaluation.py`](../src/evaluation/run_kg_evaluation.py); latest output: [`src/evaluation/kg_metrics.json`](../src/evaluation/kg_metrics.json).

---

## Foundation CSVs (`kg_foundation/`)

CSV seeds consumed by [`src/kg_population/build_kg_ttl.py`](../src/kg_population/build_kg_ttl.py) to instantiate the bibliographic and structural layers of the ontology. Every row maps to one or more classes; see the table inside the script for the column-to-property mapping.

**Bibliographic / structural rows:**

| File | Rows | Primary class |
|---|---:|---|
| `viewsari_volumes.csv` | 20 | `viewsari:volume` / `viewsari:volume_web_representation` |
| `viewsari_biographies.csv` | 288 | `viewsari:biography` / `viewsari:biography_web_representation` |
| `viewsari_pages.csv` | 6,258 | `viewsari:page` / `viewsari:page_web_representation` |
| `viewsari_paragraphs.csv` | 3,479 | `doco:Paragraph` |

**Person / annotation rows (under `kg_foundation/persons/`):**

| File | Rows | Primary class |
|---|---:|---|
| `viewsari_persons.csv` | 443 | `viewsari:person` |
| `viewsari_textchunks.csv` | 24,827 | `doco:TextChunk` |
| `viewsari_selectors.csv` | 24,827 | `oa:TextPositionSelector` |
| `viewsari_annotations.csv` | 24,827 | `oa:Annotation`, `prov:Entity` |
| `viewsari_activities.csv` | — | `prov:Activity` (NER, coref, EL, ObliquER) |

**Co-occurrence rows (under `kg_foundation/cooccurrences/`):** analogous shape to `persons/`, with `viewsari:cooccurrence` as the head class.

### Conventions for multi-valued columns

Several columns hold space-separated lists of URIs (`prov:used` in `viewsari_activities.csv`; `rdf:type` cells containing comma-separated values such as `oa:Annotation, prov:Entity`). When loading into a triple store these must be split into individual triples.

### Provenance chain in the seeds

```
paragraphs + index_of_names
        ↓  prov:used
  NER activity  →  prov:wasGeneratedBy  →  annotations (oa:Annotation, prov:Entity)
                                                  ↓  prov:used (by coref activity)
                                           coref activity  →  prov:wasGeneratedBy  →  persons
```

---

## Source corpus

| Dir | Contents |
|---|---|
| [`lives_pdfs/`](lives_pdfs/) | Original Project Gutenberg PDFs, one per volume (10 volumes total). |
| [`ocr/`](ocr/) | OCR'd text per volume, produced by [`src/extract_content/ocr_facsimile.py`](../src/extract_content/ocr_facsimile.py). |
| [`facsimile_pages/`](facsimile_pages/) | Per-page HTML facsimiles by volume, sliced from the Gutenberg HTML by [`src/extract_content/extract_facsimile_pages.py`](../src/extract_content/extract_facsimile_pages.py). |
| [`index_of_names/`](index_of_names/) | Per-volume Index-of-Names CSVs (NER + coref index over the printed back-of-book indices). Used as the controlled vocabulary for person extraction and as input to [`src/kg_population/build_kg_ttl.py`](../src/kg_population/build_kg_ttl.py). |

### `index_of_names/{0–9}.csv`

One row per named-entity mention. File `0.csv` = Volume 1, …, `9.csv` = Volume 10.

| Column | Type | Description |
|---|---|---|
| `page` | integer | Page on which this mention occurs |
| `index_name` | string | Canonical name from the index; pipe-separated (`|`) for ambiguous corefs |
| `position` | string | Character offsets within the paragraph, formatted as `(start, end)` |
| `reference` | string | Surface string (name, pronoun, or coreferent phrase) |
| `paragraph` | float | Volume-global paragraph ID |

---

## Co-occurrence tables (`cooccurrences/`)

Per-volume co-occurrence CSVs plus a `results/` subdir holding aggregated PMI / Dice tables. Computed by [`src/network/compute_pmi.py`](../src/network/compute_pmi.py) and [`src/network/compute_dice.py`](../src/network/compute_dice.py); the underlying per-biography analysis lives in [`src/network/biography_pmi-dice.ipynb`](../src/network/biography_pmi-dice.ipynb).

The KG-side co-occurrence layer (`viewsari:cooccurrence` instances with `viewsari:involves` to participating persons and `viewsari:inParagraph` to the source paragraph) is built from [`kg_foundation/cooccurrences/`](kg_foundation/cooccurrences/).

---

## Ontology vocabulary dependencies

See [`ontology/README.md`](ontology/README.md) for the full vocabulary table. At a glance:

| Prefix | Namespace | Used for |
|---|---|---|
| `viewsari` | `https://viewsari.ise.fiz-karlsruhe.de/ontology/` | Domain classes and properties |
| `fabio` | `http://purl.org/spar/fabio/` | FRBR-aligned bibliographic types |
| `frbr` | `http://purl.org/vocab/frbr/core#` | Work / Expression / Manifestation |
| `doco` | `http://purl.org/spar/doco/` | Document components |
| `dct` | `http://purl.org/dc/terms/` | `isPartOf`, `hasPart` |
| `oa` | `http://www.w3.org/ns/oa#` | Web Annotation |
| `prov` | `http://www.w3.org/ns/prov#` | Provenance |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` | Labels, class hierarchy |
| `owl` | `http://www.w3.org/2002/07/owl#` | `sameAs`, ontology imports |
