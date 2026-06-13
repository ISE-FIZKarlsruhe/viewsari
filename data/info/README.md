# Viewsari — project description

**Viewsari** is a provenance-aware knowledge graph of Giorgio Vasari's *The Lives of the Most Eminent Painters, Sculptors, and Architects* (*Le vite de' più eccellenti pittori, scultori e architettori*), built as part of doctoral research at the Karlsruhe Institute of Technology (KIT) / FIZ Karlsruhe (ISE group).

The name combines *view* and *Vasari*, foregrounding that interpretive reasoning — as Vasari himself demonstrated — can shape an entire field for centuries, and that the provenance of interpretation is therefore constitutive of scholarly knowledge.

> *Knowledge extracted from interpretative texts is not discovered but constructed; therefore, knowledge graphs must model and make visible the construction process itself.*

This page is the high-level description. For the full contribution-to-file map (which conceptual contribution C1–C4, empirical contribution E1–E4, or research question RQ1–RQ3 a given directory implements), see the [top-level README](../../README.md#dissertation-contributions--repository-map).

---

## Overview

Cultural heritage materials, once digitized, remain largely unstructured: human-readable, but not systematically queryable, linkable, or analyzable. Large language models have improved access to such content, yet they cannot guarantee epistemic traceability — outputs are generated rather than retrieved, and the conditions of their production are typically undocumented. Viewsari addresses this gap.

The project proposes a **modeling paradigm** in which knowledge extraction from historical text is treated as an interpretive activity. Rather than producing unqualified facts, the Viewsari pipeline records the agents, prompts, software versions, and source contexts responsible for each extracted statement, making the interpretation — not just its output — part of the knowledge graph.

The approach is positioned in the **neuro-symbolic space**: the Viewsari ontology (symbolic component) provides a formal schema that structures and constrains extraction tasks assigned to a large language model (neural component). The ontology defines entity types, provenance relations, and mention typologies that all extracted statements must satisfy, ensuring outputs remain traceable to their source evidence.

---

## The case study: Vasari's *The Lives*

Vasari's *Lives* (first published 1550, expanded 1568) is one of the founding documents of art history as a discipline. It presents biographies of prominent painters, sculptors, and architects of the Italian Renaissance, written in a narrative style characterized by:

- **indirect and implicit entity references** (artworks described without title or artist)
- **attributions and opinions** presented as facts
- **long-tail and out-of-knowledge-base (OOKB) entities** absent from standard knowledge bases
- **multiple editions and translations** (1568 Italian original; Du Vere 1912 English translation)

These properties make *The Lives* a demanding and representative testbed for interpretive knowledge extraction.

---

## Components and where to find them

The repository is the artifact side of the project. The mapping below points each component to the directory that implements it; for full traceability into individual scripts, see the [top-level README](../../README.md#dissertation-contributions--repository-map).

### Viewsari ontology *(E1, C1, C4)*

A modular, provenance-aware OWL 2 DL ontology developed using the eXtreme Design methodology, with a three-layer architecture:

- **Bibliographic layer** — work / edition / translation / volume / biography / page (FRBR, FaBiO)
- **Structural layer** — paragraph, text chunk, position selector (DoCO, OA)
- **Content layer** — persons, artworks, locations, organizations, co-occurrences, mentions (explicit / implicit / coreferent / generic), extraction activities, prompt entities

Reused vocabularies include PROV-O, OA (Web Annotation), FaBiO, FRBR, DoCO, CIDOC CRM, and Dublin Core.

→ Lives in [`data/ontology/`](../ontology/) — source OWL, WIDOCO docs, reasoning examples, and the [CQ catalog](../ontology/CQ_CATALOG.md).

### ObliquER pipeline *(E2, C2)*

An LLM-based entity recognition and linking pipeline for implicit and long-tail entities. Key features:

- **Formal task definition** grounded in the Viewsari ontology schema
- **Modular prompt architecture** separating domain-specific content (entity definitions, mention typology, few-shot examples) from structural templates
- **Dynamic chunking** for paragraph-level processing
- **Entity linking** with candidate generation, global cluster aggregation, and OOKB tagging
- **Post-processing** pipeline: UIMA CAS export → mention ID assignment → union-find coreference clustering → OOKB classification
- **PROV-O activities** generated for every extraction run, harmonized with the KG schema

Evaluated on a gold-standard corpus of 232 annotated paragraphs across 16 biographies, manually annotated in INCEpTION (stratified sampling, random seed 42, capped at 10–25 paragraphs per biography).

→ Lives in [`obliquer/`](../../obliquer/) (git submodule). Ingestion into the KG: [`src/kg_population/ingest_ner_results.py`](../../src/kg_population/ingest_ner_results.py).

### Viewsari knowledge graph and web interface *(E3, C3)*

A populated KG with 100% provenance coverage, deployed with a web interface for non-technical exploration:

- Person entities extracted from the index of names, linked to Wikidata
- Artwork entities from the gold-standard entity linking layer, with OOKB nodes for entries with no Wikidata match
- Co-occurrence instances with PMI and Dice coefficient scores
- Web Annotation layer for paragraph-level mention anchoring
- Per-extraction PROV-O activities (one per ObliquER NER run)
- FRBR-level bibliographic layer for both the 1568 Italian and 1912 English editions

→ KG turtle: [`data/kg/viewsari_kg.ttl`](../kg/viewsari_kg.ttl). Web app: [`app/`](../../app/). Explorer JSONs: [`data/kg/explorer/`](../kg/explorer/). Runtime KB: [`data/kb/kb.json`](../kb/kb.json).

### Transferability pilot *(E4, C4)*

The Viewsari ontology and ObliquER pipeline are reconfigured for person, location, and organization extraction from a 19th-century German-language documentary corpus on the Illuminati order, linked to the FactGrid Wikibase. Only the prompt content layer is modified; templates, post-processing, and ontology core remain unchanged.

→ Pilot runs and prompts are documented from the ObliquER side in [`obliquer/`](../../obliquer/).

---

## Requirements engineering

Ontology design is driven by the **competency questions (CQs)** in [`CQ_CATALOG.md`](../ontology/CQ_CATALOG.md), derived from user stories across four personas (a curator, a senior art historian, a graduate student, a software engineer). CQs are organized into thematic clusters covering:

1. Artists, collaborations, and relationships
2. Artworks
3. Locations
4. Historical events
5. Evidence and bibliographic information
6. Linked-data enrichment
7. User interaction and exploration
8. Extraction provenance and epistemic modeling

CQ coverage against the populated KG is evaluated by [`src/evaluation/run_cq_evaluation.py`](../../src/evaluation/run_cq_evaluation.py); see [`src/evaluation/README.md`](../../src/evaluation/README.md).

---

## Research questions

The project is structured around three research questions, summarized here. The full repository mapping (which Cs and Es answer which RQ) is in the [top-level README](../../README.md#research-questions).

- **RQ1** — What representational commitments must a knowledge graph make to remain accountable to the interpretive act that produced it, and how can these be operationalized in a provenance-aware ontology?
- **RQ2** — Under what conditions can LLMs, treated as interpretive agents, recognize and link implicit and out-of-knowledge-base entity mentions that lie beyond surface form-baselines?
- **RQ3** — Which design patterns recur across provenance-aware KGs in the digital humanities, and to what extent does the Viewsari methodology transfer to structurally distinct interpretive corpora?

---

## Transferability beyond Vasari

The methodology is exercised beyond the Vasari corpus through:

- **FactGrid + the Illuminati pilot** — 19th-century German documentary sources, ontology + ObliquER reconfigured (E4)
- **MemO / NFDI4Memory** — indexing historical research data within the German National Research Data Infrastructure
- **ArtPedia** — a contemporary art-description dataset used as a cross-domain benchmark for ObliquER

---

## Publications

See [`PUBLICATIONS.md`](./PUBLICATIONS.md) for the list of associated peer-reviewed publications.

---

## License

Dataset and ontology licensing information is available in the repository. The Project Gutenberg edition of *The Lives* used as the source corpus is in the public domain.

---

## Contact

Sarah Rebecca Ondraszek  
ISE Research Group, FIZ Karlsruhe / Karlsruhe Institute of Technology (KIT)  
GitHub: [ISE-FIZKarlsruhe/viewsari](https://github.com/ISE-FIZKarlsruhe/viewsari)