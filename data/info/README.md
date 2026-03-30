# Viewsari

**Viewsari** is a provenance-aware knowledge graph of Giorgio Vasari's *The Lives of the Most Eminent Painters, Sculptors, and Architects* (*Le vite de' più eccellenti pittori, scultori e architettori*), developed as part of a doctoral dissertation at the Karlsruhe Institute of Technology (KIT) / FIZ Karlsruhe (ISE group).

The name combines *view* and *Vasari*, foregrounding that interpretive reasoning — as Vasari himself demonstrated — can shape an entire field for centuries, and that the provenance of interpretation is therefore constitutive of scholarly knowledge.

> *Knowledge extracted from interpretative texts is not discovered but constructed; therefore, knowledge graphs must model the construction process itself.*

---

## Overview

Cultural heritage materials, once digitized, remain largely unstructured: human-readable, but not systematically queryable, linkable, or analyzable. Large language models have improved access to such content, yet they cannot guarantee epistemic traceability — outputs are generated rather than retrieved, and the conditions of their production are typically undocumented. Viewsari addresses this gap.

The project proposes a **modeling paradigm** in which knowledge extraction from historical text is treated as an interpretive activity. Rather than producing unqualified facts, the Viewsari pipeline records the agents, prompts, software versions, and source contexts responsible for each extracted statement, making the interpretation — not just its output — part of the knowledge graph.

The approach is positioned in the **neuro-symbolic space**: the Viewsari ontology (symbolic component) provides a formal schema that structures and constrains extraction tasks assigned to a large language model (neural component). The ontology defines entity types, provenance relations, and uncertainty classes that all extracted statements must satisfy, ensuring outputs are traceable to their source evidence.

---

## The Case Study: Vasari's *The Lives*

Vasari's *Lives* (first published 1550, expanded 1568) is one of the founding documents of art history as a discipline. It presents biographies of prominent painters, sculptors, and architects of the Italian Renaissance, written in a narrative style characterized by:

- **indirect and implicit entity references** (artworks described without title or artist)
- **attributions and opinions** presented as facts
- **long-tail and out-of-knowledge-base entities** absent from standard knowledge bases
- **multiple editions and translations** (including the 1568 Italian edition and Du Vere's 1912 English translation)

These properties make *The Lives* a demanding and representative testbed for interpretive knowledge extraction.

---

## Components

### Viewsari Ontology
A modular, provenance-aware ontology built using the **eXtreme Design (XD)** methodology and **Ontology Design Patterns (ODPs)**. It models:

- persons, artworks, locations, historical events, and co-occurrences
- explicit, implicit, and coreferential entity mentions
- out-of-knowledge-base (OOKB) entities with no Wikidata match
- a three-layer bibliographic structure (work / expression / manifestation) aligned with FRBR and FaBiO
- extraction provenance via PROV-O: software agents, prompt templates, model versions, timestamps
- web manifestations linking directly to paragraph-level sources in the Project Gutenberg edition

Reused vocabularies include PROV-O, OA (Web Annotation), FaBiO, FRBR, DoCO, CIDOC CRM, and Dublin Core.

### ObliquER Pipeline
An LLM-based entity recognition and linking pipeline designed for implicit and long-tail entities. Key features:

- **Formal task definition** grounded in the Viewsari ontology schema
- **Prompt engineering** for zero-shot and few-shot extraction of explicit, implicit, and coreferential mentions
- **Dynamic chunking** for paragraph-level processing
- **Entity linking** with candidate generation, global cluster aggregation, and OOKB tagging
- **Post-processing** pipeline: UIMA CAS export → mention ID assignment → union-find coreference clustering → OOKB classification
- Evaluated on a **gold standard corpus** of 221 annotated paragraphs across 16 biographies, manually annotated in INCEpTION (stratified sampling, random seed 42, capped at 10–25 paragraphs per biography)

### Knowledge Graph
The populated Viewsari knowledge graph covers the full *Lives* corpus and includes:

- person entities extracted from the index of names, linked to Wikidata
- co-occurrence instances with PMI and Dice coefficient scores
- Web Annotation layer for paragraph-level mention anchoring
- provenance activities for each extraction run
- FRBR-level bibliographic layer for both the 1568 Italian and 1912 English editions
- RDF serialization via RML and ROBOT templates

---

## Requirements Engineering

Ontology design is driven by **74 competency questions (CQs)** across two requirements engineering phases, derived from 47 user stories across four personas (Dr. Elena Rossi, Prof. Nazeera Marfi, Aaron Warner, John Saffron). CQs are organized into eight thematic clusters:

1. Artists, collaborations, and relationships
2. Artworks
3. Locations
4. Historical events
5. Evidence and bibliographic information
6. Linked data enrichment
7. User interaction and exploration
8. Extraction provenance and epistemic modeling

The full CQ catalog is available in [`CQ_CATALOG.md`](./CQ_CATALOG.md).

---

## Research Questions

**RQ1** — In what way can semantic technologies model the heterogeneous content, provenance, and interpretive complexity of historical texts?

**RQ2** — How can NLP methods, and LLMs in particular, be used to extract and link both explicitly and implicitly mentioned entities?

**RQ3** — What are the common challenges in modeling complex, multilingual historical sources, and how can a generalizable approach be drawn to make the methodology repeatable and transferable?

---

## Transferability

The methodology is evaluated beyond Vasari through applications to:

- **FactGrid / HisQu** — historical sources modeled with Viewsari patterns
- **MemO and NFDI4Memory** — indexing historical research data within the German National Research Data Infrastructure
- **ArtPedia** — a contemporary art-description dataset used as a cross-domain benchmark for ObliquER

---

## Repository Structure

```
viewsari/
├── ontology/          # Viewsari OWL ontology and modular components
├── pipeline/          # ObliquER extraction and linking scripts
├── data/              # Corpus, ground truth annotations, sampled paragraphs
├── kg/                # RDF knowledge graph serialization
├── evaluation/        # SPARQL queries for CQ coverage, evaluation scripts
├── docs/              # Annotation guidelines, ontology documentation
└── demo/              # Interactive web visualization
```

---

## Citation

If you use Viewsari in your research, please cite the dissertation:

```
Sarah Rebecca Ondraszek. Modeling Interpretation in the Age of GenAI:
Semantic Technologies for Digital Humanities Research Based on Giorgio Vasari's
The Lives. Doctoral dissertation, Karlsruher Institut für Technologie (KIT), 2026.
```

See [`PUBLICATIONS.md`](./PUBLICATIONS.md) for the full list of associated peer-reviewed publications.

---

## License

Dataset and ontology licensing information is available in the repository. The Project Gutenberg edition of *The Lives* used as source corpus is in the public domain.

---

## Contact

Sarah Rebecca Ondraszek  
ISE Research Group, FIZ Karlsruhe / Karlsruhe Institute of Technology (KIT)  
GitHub: [ISE-FIZKarlsruhe/viewsari](https://github.com/ISE-FIZKarlsruhe/viewsari)
