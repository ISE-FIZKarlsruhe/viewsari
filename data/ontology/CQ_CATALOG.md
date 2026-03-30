# Viewsari Competency Question Catalog

This catalog provides the full set of competency questions (CQs) for the **Viewsari** ontology, derived from user stories collected across two requirements engineering phases. Each CQ is assigned a unique identifier and linked to the thematic cluster and persona from which it originated. CQs are the formal operationalization of user stories and serve as both the basis for ontology design decisions and the evaluation instrument for assessing ontology coverage.

- **Phase I CQs (CQI):** 29 ontology-focused questions, derived from 39 formally elicited questions based on 32 user stories across four personas.
- **Phase II CQs (CQII):** Extends the catalog to 74 questions, adding 15 further user stories addressing generative extraction provenance, bibliographic depth, and epistemic modeling.

## Personas

| Abbreviation | Persona |
|---|---|
| **Elena Rossi** | Art historian researcher |
| **Nazeera Marfi** | Professor of digital art history |
| **Aaron Warner** | Computer scientist / knowledge engineer |
| **John Saffron** | Art history student |

---

## Phase I Competency Questions (CQI)

### Cluster 1 — Artists and Co-occurrences

| ID | Competency Question | Persona |
|---|---|---|
| CQI.1 | Who co-occurred with whom in *The Lives*? | Elena Rossi |
| CQI.2 | Did artist X co-occur with artist Y? | Elena Rossi |
| CQI.3 | Which artists are mentioned together in the same passage? | Elena Rossi |
| CQI.4 | Where in the text did artists X and Y co-occur? (In which paragraph, biography, volume?) | Elena Rossi |
| CQI.5 | How frequently do two given artists co-occur across the entire corpus? | Elena Rossi |
| CQI.6 | Which artists have the highest co-occurrence frequency with artist X? | Elena Rossi |
| CQI.7 | What is the pointwise mutual information (PMI) score for the co-occurrence of artists X and Y? | Aaron Warner |
| CQI.8 | What is the network centrality of artist X in the co-occurrence network? | Aaron Warner |

### Cluster 2 — Persons and Attributes

| ID | Competency Question | Persona |
|---|---|---|
| CQI.9 | What are the birth and death dates of person X? | Elena Rossi |
| CQI.10 | Which persons mentioned in *The Lives* are identified as artists? | Elena Rossi |
| CQI.11 | Which persons mentioned in *The Lives* are not artists (e.g., patrons, clergy, scholars)? | Elena Rossi |
| CQI.12 | In which biography (biographies) does person X appear? | John Saffron |
| CQI.13 | Is person X linked to an external authority record (e.g., Wikidata)? | Aaron Warner |

### Cluster 3 — Artworks, Locations, and Entities

| ID | Competency Question | Persona |
|---|---|---|
| CQI.14 | Which artworks are mentioned in the biography of artist X? | Elena Rossi |
| CQI.15 | Which locations are associated with artist X? | Elena Rossi |
| CQI.16 | Which artworks were created in location L? | Elena Rossi |
| CQI.17 | Can students explore artist collaborations on a geographical map? | Nazeera Marfi |
| CQI.18 | Where is location X located on a map? | John Saffron |

### Cluster 4 — Bibliographic and Provenance

| ID | Competency Question | Persona |
|---|---|---|
| CQI.19 | Which paragraph and page in *The Lives* is the source of co-occurrence C? | Elena Rossi |
| CQI.20 | Which volume of *The Lives* contains the biography of artist X? | John Saffron |
| CQI.21 | What edition or translation of *The Lives* was used for extracting a given co-occurrence? | Elena Rossi |
| CQI.22 | What is the original text snippet associated with co-occurrence C? | Elena Rossi |
| CQI.23 | What licence is provided by the Viewsari dataset and where can the original source text be found? | Aaron Warner |

### Cluster 5 — Search and Data Reuse

| ID | Competency Question | Persona |
|---|---|---|
| CQI.24 | How can I execute semantic searches over the knowledge graph? | Aaron Warner |
| CQI.25 | How can I reuse the Viewsari data in my own project, and in what form can it be shared? | Nazeera Marfi |
| CQI.26 | Is there a SPARQL endpoint or an RDF dump available? | Aaron Warner |
| CQI.27 | Which external resources (ontologies, authority data) were used in constructing the knowledge graph? | Aaron Warner |
| CQI.28 | Which authority data (e.g., Wikidata, Iconclass) is connected to the resources? | Elena Rossi |
| CQI.29 | How can my students reuse data in the project course, and can the visualizations be modified and customized? | Nazeera Marfi |

---

## Phase II Competency Questions (CQII)

Phase II CQs address extended requirements that emerged as the scope expanded to include LLM-guided extraction, bibliographic depth, epistemic provenance, and out-of-knowledge-base (OOKB) entity handling.

### Cluster 1 — Artists, Collaborations, and Relationships

| ID | Competency Question | Persona |
|---|---|---|
| CQII.1 | What is the difference between a statistical co-occurrence and an explicitly typed relationship between two artists in the knowledge graph? | Aaron Warner |
| CQII.2 | How can I distinguish between different types of artist associations (statistical co-occurrence vs. explicit relationships) in order to build accurate computational models? | Aaron Warner |
| CQII.3 | Which artists have both a statistical co-occurrence and an explicit typed relationship with artist X? | Elena Rossi |
| CQII.4 | What is the Dice coefficient for the co-occurrence of artists X and Y, and how does it compare to the PMI score? | Aaron Warner |
| CQII.5 | How do I explore relationships between Renaissance artists, artworks, historical events, or locations so that I can identify patterns and trends for research or in a course? | Nazeera Marfi |

### Cluster 2 — Artworks

| ID | Competency Question | Persona |
|---|---|---|
| CQII.6 | Which artworks are explicitly named in the biography of artist X, and which are described only implicitly? | Elena Rossi |
| CQII.7 | What is the surface form by which artwork A is referred to in paragraph P, and is it an explicit, implicit, or coreferential mention? | Elena Rossi |
| CQII.8 | Which artworks in the knowledge graph are classified as out-of-knowledge-base (OOKB) entities — i.e., have no match in Wikidata? | Aaron Warner |
| CQII.9 | Which artworks co-occur with a specific artist in a particular volume, and what are the source paragraphs? | Elena Rossi |
| CQII.10 | Can I explore how artworks reflect collaborative effects, such as shared locations or artistic styles? | Nazeera Marfi |

### Cluster 3 — Locations

| ID | Competency Question | Persona |
|---|---|---|
| CQII.11 | Which locations are mentioned in co-occurrences involving artist X? | Elena Rossi |
| CQII.12 | Which artists were active in location L according to *The Lives*? | Elena Rossi |
| CQII.13 | Is location L linked to an external authority record (e.g., Wikidata, GeoNames)? | Aaron Warner |
| CQII.14 | Can students explore artist collaborations on a geographical map, filtered by location? | Nazeera Marfi |

### Cluster 4 — Historical Events

| ID | Competency Question | Persona |
|---|---|---|
| CQII.15 | Which historical events are associated with artist X in the knowledge graph? | Elena Rossi |
| CQII.16 | Which artworks were commissioned or destroyed as part of a specific historical event E? | Elena Rossi |
| CQII.17 | How can I identify cross-disciplinary connections between Renaissance art and other historical or cultural phenomena using the knowledge graph? | Nazeera Marfi |
| CQII.18 | Can information about historical events be enriched from external sources such as Wikidata, and if so, which properties are aligned? | Aaron Warner |

### Cluster 5 — Evidence and Bibliographic Information

| ID | Competency Question | Persona |
|---|---|---|
| CQII.19 | How can I distinguish between work-level, expression-level, and manifestation-level bibliographic metadata in order to properly cite and attribute sources across different editions and translations? | Elena Rossi |
| CQII.20 | Which edition and translation of *The Lives* is the source of a given extracted entity or co-occurrence? | Elena Rossi |
| CQII.21 | What is the direct web URL to the paragraph in the Project Gutenberg edition from which entity E or co-occurrence C was extracted? | Elena Rossi |
| CQII.22 | Is the extracted information derived from Du Vere's 1912 English translation, the 1568 Italian edition, or another version? | Elena Rossi |
| CQII.23 | How does the choice of translation (Du Vere's English vs. the original Italian) affect the entities and co-occurrences that appear in the knowledge graph? | Elena Rossi |
| CQII.24 | For co-occurrences involving artist X, can I compare the English translation's web manifestation with the Italian edition's web manifestation? | Elena Rossi |

### Cluster 6 — Linked Data Enrichment

| ID | Competency Question | Persona |
|---|---|---|
| CQII.25 | Which entities in the knowledge graph are linked to Wikidata, and what properties are mapped? | Aaron Warner |
| CQII.26 | Which entities are classified as OOKB, meaning they have no matching entry in Wikidata or other authority sources? | Aaron Warner |
| CQII.27 | Can I perform a federated SPARQL query combining Viewsari data with an external endpoint (e.g., Wikidata)? | Aaron Warner |
| CQII.28 | How can I use Viewsari as a research tool for cross-disciplinary research that connects findings from *The Lives* to broader historical or cultural knowledge? | Nazeera Marfi |

### Cluster 7 — User Interaction and Exploration

| ID | Competency Question | Persona |
|---|---|---|
| CQII.29 | How can I apply FAIR principles to the Viewsari data to bring it into my own project and share it with my students? | Nazeera Marfi |
| CQII.30 | How can I use Viewsari as an interactive visualization platform in my lectures to communicate complex relationships and historical patterns? | Nazeera Marfi |
| CQII.31 | Can I conduct a proof-of-concept project reusing Viewsari as a system, finding its working concept applicable to my own research? | Nazeera Marfi |
| CQII.32 | How can I integrate Viewsari into my teaching curriculum? | Nazeera Marfi |
| CQII.33 | How can I explore relationships between artists, artworks, or locations so that I can identify trends and accumulations of collaborations in a certain city or place? | John Saffron |

### Cluster 8 — Extraction Provenance and Epistemic Modeling

| ID | Competency Question | Persona |
|---|---|---|
| CQII.34 | Which extraction activity (NER run, LLM prompt run) generated entity E, and what software agent was used? | Aaron Warner |
| CQII.35 | What was the prompt template used in the extraction run that produced entity E? | Aaron Warner |
| CQII.36 | Which entities were extracted by a statistical method (co-occurrence / NER) versus a generative LLM-based method? | Aaron Warner |
| CQII.37 | What model version and timestamp are associated with extraction run R? | Aaron Warner |
| CQII.38 | How are implicit entity mentions distinguished from explicit ones in the ontology, and can I query them separately? | Aaron Warner |
| CQII.39 | For a given extraction result, can I trace back the provenance chain from the entity through the annotation, the paragraph, the page, the volume, and the translation to the original work? | Elena Rossi |
| CQII.40 | Does the knowledge graph allow me to assess whether a claimed relationship between two artists is supported by explicit textual evidence, an implicit inference, or purely statistical co-occurrence? | Elena Rossi |
| CQII.41 | How does the ontology represent the epistemic weight of a co-occurrence derived from PMI compared to an implicit mention inferred by an LLM? | Aaron Warner |

---

## Summary: CQ Coverage by Cluster

| # | Cluster | Phase I | Phase II | Total |
|---|---|---|---|---|
| 1 | Artists, collaborations, and relationships | CQI.1–8 | CQII.1–5 | 13 |
| 2 | Artworks | CQI.14–16 | CQII.6–10 | 8 |
| 3 | Locations | CQI.15–18 | CQII.11–14 | 7 |
| 4 | Historical events | — | CQII.15–18 | 4 |
| 5 | Evidence and bibliographic information | CQI.19–23 | CQII.19–24 | 11 |
| 6 | Linked data enrichment | CQI.13, 27–28 | CQII.25–28 | 7 |
| 7 | User interaction and exploration | CQI.24–26, 29 | CQII.29–33 | 9 |
| 8 | Extraction provenance and epistemic modeling | — | CQII.34–41 | 8 |
| — | Persons and attributes (cross-cutting) | CQI.9–13 | — | 5 |
| | **Total** | **29** | **41** | **70+** |

> **Note:** Some CQs address multiple clusters. The exact count of 74 Phase II CQs reported in the dissertation (Section 7.3.2) includes additional sub-questions generated via OntoChat from the extended user stories, which are subsumed under the entries above.
