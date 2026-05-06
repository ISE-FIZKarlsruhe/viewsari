# Viewsari knowledge graph

> *Modeling Interpretation in the Age of Generative AI:*
> *Semantic Technologies for Digital Humanities Research Based on Giorgio Vasari's* The Lives

This repository contains the data transformation pipeline that produces the CSV seed files
for the **Viewsari Knowledge Graph** — a provenance-aware, FRBR-structured knowledge graph
built from Giorgio Vasari's *Le Vite de' più eccellenti pittori, scultori e architettori*
(1568 edition), specifically the Gaston du C. de Vere English translation (1912),
as digitized by Project Gutenberg.

---

## Repository layout

```
viewsari/
├── build_viewsari_kg.py            ← the transformation pipeline (this script)
├── README.md                       ← you are here
├── prefixes.json
│
├── data/
│   ├── archive/
│   │   ├── biographies/
│   │   ├── centralities/
│   │   ├── ER/
│   │   ├── knowledge-graph/
│   │   ├── metadata/
│   │   ├── person_references/
│   │   ├── test/
│   │   └── volumes/            ← paragraph text CSVs (0.csv–9.csv)
│   │       ├── 0.csv           ← Volume 1 paragraph texts
│   │       └── …               ← … through 9.csv (Volume 10)
│   │
│   ├── cooccurrences/
│   └── index_of_names/         ← NER + coreference index CSVs (0.csv–9.csv)
│       ├── 0.csv               ← Volume 1 index
│       └── …                   ← … through 9.csv (Volume 10)
│
├── kg_foundation/              ← generated KG seed CSVs (output of this script)
│   ├── persons/                ← annotation-layer files (person entities + evidence)
│   │   ├── viewsari_persons.csv
│   │   ├── viewsari_annotations.csv
│   │   ├── viewsari_textchunks.csv
│   │   ├── viewsari_selectors.csv
│   │   └── viewsari_activities.csv
│   │
│   ├── viewsari_volumes.csv
│   ├── viewsari_biographies.csv
│   ├── viewsari_pages.csv
│   └── viewsari_paragraphs.csv
│
└── ontology/
    └── viewsari_ontology.rdf
```

---

## Input file formats

### `data/paragraph_texts/{0–9}.csv`

One row per paragraph fragment. Paragraphs that span a page break appear as
multiple consecutive rows sharing the same `paragraph_id`.

| Column         | Type    | Description                                              |
|----------------|---------|----------------------------------------------------------|
| `page`         | integer | Printed page number (matches Gutenberg `#Page_N` anchor) |
| `paragraph_id` | integer | Volume-global sequential paragraph identifier            |
| `text`         | string  | Text fragment for this page slice of the paragraph       |

### `data/index_names/{0–9}.csv`

One row per named-entity mention, produced by running NER and coreference
resolution against the paragraph texts using the volume's Index of Names as
a controlled vocabulary. File `0.csv` = Volume 1, `1.csv` = Volume 2, etc.

| Column       | Type    | Description                                                           |
|--------------|---------|-----------------------------------------------------------------------|
| `page`       | integer | Page on which this mention occurs                                     |
| `index_name` | string  | Canonical name from the index; pipe-separated (`\|`) for ambiguous corefs |
| `position`   | string  | Character offsets within the paragraph, formatted as `(start, end)`   |
| `reference`  | string  | The actual surface string (name, pronoun, or coreferent phrase)        |
| `paragraph`  | float   | Volume-global paragraph ID (matches `paragraph_id` in text files)     |

---

## Pipeline stages

The script runs five sequential stages. All outputs are written as UTF-8 CSV
files with full quoting. Each file maps directly to one or more classes in the
Viewsari ontology.

### Stage 1 — Volumes (`viewsari_volumes.csv`)

Produces **20 rows** (10 volumes × expression + manifestation).

Every volume is modelled at two FRBR levels:

- **Expression** (`viewsari:volume`, `fabio:BookSeries`)
  — represents the intellectual content of a volume in the 1568 edition.
  `frbr:is part of` points upward to the edition expression node
  (`viewsari:#0001029`).

- **Manifestation** (`viewsari:volume web representation`, `fabio:WebSite`)
  — represents the Gutenberg HTML file for that volume.
  `rdfs:seeAlso` carries the full Gutenberg URL.
  `frbr:is part of` points to the manifestation-collection node
  (`viewsari:#0001031`).

The two levels are linked by `frbr:has embodiment` on the expression row.

---

### Stage 2 — Biographies (`viewsari_biographies.csv`)

Produces **288 rows** (144 biographies × expression + manifestation).

The 144 biographies are drawn from the printed tables of contents of all
10 volumes. Start pages are the Du Vere printed page numbers embedded in
the Gutenberg HTML as `#Page_N` anchors.

- **Expression** (`viewsari:biography`, `fabio:Expression`)
  — `frbr:is part of` → volume expression.

- **Manifestation** (`viewsari:biography web representation`, `fabio:WebPage`)
  — `rdfs:seeAlso` → `{volume_url}#Page_{start_page}` (Gutenberg anchor).
  — `frbr:is part of` → volume web representation.

---

### Stage 3 — Pages (`viewsari_pages.csv`)

Produces **6,258 rows** (3,129 pages × expression + manifestation),
covering **every printed page** within every biography across all 10 volumes.

Page ranges are derived from biography start pages: each biography ends on
the page before the next biography begins. The last biography in each volume
extends to the maximum page number attested in the paragraph text data.

- **Expression** (`viewsari:page`, `fabio:Expression`)
  — `frbr:is part of` → biography expression.

- **Manifestation** (`viewsari:page web representation`, `fabio:WebPage`)
  — `rdfs:seeAlso` → `{volume_url}#Page_{N}`.
  — `frbr:is part of` → biography web representation.

---

### Stage 4 — Paragraphs (`viewsari_paragraphs.csv`)

Produces **3,479 rows** (one per merged paragraph across all 10 volumes).

**Key transformation — merging page-split fragments:**
Paragraphs that span a page break are stored as multiple rows in the source
files. This stage groups all fragments by `paragraph_id`, sorts them by page,
and concatenates the text (continuation fragments retain their leading
whitespace as the natural join point). The result is a single row per
paragraph with a `start_page` and `end_page`.

| Output column                     | Derivation                                                  |
|-----------------------------------|-------------------------------------------------------------|
| `dct:isPartOf`                    | Page expression for the start page                          |
| `viewsari:has start page`         | Page *web representation* URI for start page                |
| `viewsari:has end page`           | Page *web representation* URI for end page                  |
| `viewsari:has length in characters` | `len()` of merged text                                    |
| `viewsari:has text`               | Full concatenated paragraph text                            |
| `frbr:is part of`                 | Biography expression containing this paragraph              |

For single-page paragraphs `viewsari:has start page` and `viewsari:has end page`
are identical, which is the correct representation.

---

### Stage 5 — Annotation layer

This stage processes the NER + coreference index files and produces five
interlinked tables modelling named-entity extraction as a provenance-aware
Web Annotation structure.

#### `viewsari_persons.csv` — 443 rows

One `viewsari:person` entity per unique resolved name across all volumes.

**Pipe-separated ambiguity:** Some index entries record two equally possible
identities for a set of mentions (e.g. `Lippi, Fra Filippo|Lippi, Filippo (Filippino)`).
These are **split** into two separate person entities, each receiving all
the mentions from that ambiguous entry. This preserves the unresolved coref
rather than silently collapsing it.

**Cross-volume identity:** A person mentioned across multiple volumes (e.g.
Giotto appears in Vols 1, 2, 9, 10) maps to a single URI determined by the
slug of their canonical index name.

`prov:wasGeneratedBy` → `viewsari:coreference_reconciliation_run_1`

#### `viewsari_textchunks.csv` — 24,827 rows

One `doco:TextChunk` per individual mention (each row in the index files,
after pipe-expansion). Links back to its paragraph via `dct:isPartOf` and
to its position selector via `oa:hasSelector`.

#### `viewsari_selectors.csv` — 24,827 rows

One `oa:TextPositionSelector` per mention, carrying `oa:start` and `oa:end`
as character offsets within the containing paragraph text. Linked to its
TextChunk via `dct:isPartOf`.

#### `viewsari_annotations.csv` — 24,827 rows

One `oa:Annotation, prov:Entity` per mention, tying together:

| Property                | Points to                                      |
|-------------------------|------------------------------------------------|
| `oa:hasTarget`          | `doco:TextChunk`                               |
| `oa:hasBodyValue`       | Surface string (pronoun, name variant, phrase) |
| `prov:wasGeneratedBy`   | NER activity                                   |
| `prov:used`             | Paragraph expression                           |
| `oa:hasSource`          | Paragraph expression                           |

#### `viewsari_activities.csv` — 2 rows

Two `prov:Activity` instances modelling the two-stage extraction process:

**`viewsari:named_entity_recognition_run_1`**
— Generated all 24,827 annotations.
— `prov:used`: all 10 index-of-names entities + 2,001 unique paragraphs
  that contributed at least one mention.
— `prov:wasAssociatedWith`: `viewsari:python_script_for_ner_1`

**`viewsari:coreference_reconciliation_run_1`**
— Generated all 443 person entities by resolving the NER annotations.
— `prov:used`: all 24,827 annotation URIs (consuming the NER output as input).
— `prov:wasAssociatedWith`: `viewsari:python_script_for_ner_2`

The full provenance chain reads:

```
paragraphs + index_of_names
        ↓  prov:used
  NER activity  →  prov:wasGeneratedBy  →  annotations (oa:Annotation, prov:Entity)
                                                  ↓  prov:used (by coref activity)
                                           coref activity  →  prov:wasGeneratedBy  →  persons
```

---

## Running the script

```bash
pip install pandas

# From the repo root:
python build_viewsari_kg.py

# Or with explicit paths (defaults match the repo structure):
python build_viewsari_kg.py \
    --para-dir  data/archive/volumes \
    --index-dir data/index_of_names \
    --output    kg_foundation/
```

All nine CSV files will be written to `output/`.

---

## Output summary

| File                          | Rows   | Primary class                          |
|-------------------------------|--------|----------------------------------------|
| `viewsari_volumes.csv`        | 20     | `viewsari:volume` / `viewsari:volume web representation` |
| `viewsari_biographies.csv`    | 288    | `viewsari:biography` / `viewsari:biography web representation` |
| `viewsari_pages.csv`          | 6,258  | `viewsari:page` / `viewsari:page web representation` |
| `viewsari_paragraphs.csv`     | 3,479  | `doco:Paragraph`                       |
| `viewsari_persons.csv`        | 443    | `viewsari:person`                      |
| `viewsari_textchunks.csv`     | 24,827 | `doco:TextChunk`                       |
| `viewsari_selectors.csv`      | 24,827 | `oa:TextPositionSelector`            |
| `viewsari_annotations.csv`    | 24,827 | `oa:Annotation`, `prov:Entity`         |
| `viewsari_activities.csv`     | 2      | `prov:Activity`                        |
| **Total**                     | **59,971** |                                    |

---

## Ontology and vocabulary dependencies

| Prefix    | Namespace                                      | Used for                          |
|-----------|------------------------------------------------|-----------------------------------|
| `viewsari` | `https://viewsari.ise.fiz-karlsruhe.de/ontology/` | Domain classes and properties |
| `fabio`   | `http://purl.org/spar/fabio/`                  | FRBR-aligned bibliographic types  |
| `frbr`    | `http://purl.org/vocab/frbr/core#`             | Work / Expression / Manifestation |
| `doco`    | `http://purl.org/spar/doco/`                   | Document components               |
| `dct`     | `http://purl.org/dc/terms/`                    | `isPartOf`, `hasPart`             |
| `oa`      | `http://www.w3.org/ns/oa#`                     | Web Annotation                    |
| `prov`    | `http://www.w3.org/ns/prov#`                   | Provenance                        |
| `rdfs`    | `http://www.w3.org/2000/01/rdf-schema#`        | Labels, class hierarchy           |
| `owl`     | `http://www.w3.org/2002/07/owl#`               | `sameAs`, ontology imports        |

---

## Notes on multi-valued columns

Several columns contain space-separated lists of URIs
(e.g. `prov:used` in `viewsari_activities.csv`,
`prov:wasGeneratedBy` referenced across tables).
When loading into a triple store these must be split into
individual triples. The same applies to `rdf:type` cells
containing comma-separated values such as `oa:Annotation, prov:Entity`.

---

## Citation

If you use this pipeline or the resulting data, please cite:

> Ondraszek, S. R. (2026). *Modeling Interpretation in the Age of Generative AI:
> Semantic Technologies for Digital Humanities Research Based on Giorgio Vasari's*
> The Lives. Doctoral dissertation, Karlsruhe Institute of Technology /
> FIZ Karlsruhe.
