# View-sariNew Perspectives on Historical Network Analysis in Giorgio Vasari’s The Lives Using Knowledge Graphs

## Introduction

Interconnectivity has become ubiquitous on the Web and in everyday life. This is also evident in the (digital) humanities. Network analysis – an integral part of the toolbox of various humanities disciplines – uncovers hidden information, allowing for a different way of approaching data, formulating new research questions, and answering them in equally innovative ways.

Novel knowledge graph technologies can help to further embed data from (historical) social networks in a broader, contextual web of information (Dörpinghaus et al. 2022). This project builds directly on these efforts and aims to offer new perspectives through an interdisciplinary, multi-layered knowledge graph that uncovers potentially hidden connections, patterns or biases. It includes considerations of classical network analysis, such as identifying frequently co-occurring artists, but also considers connections between them and their artworks, contemporary events, etc., and follows paradigms of historical research, thus allowing for context-dependent interpretation through the provided material and evidence (Novak et al. 2014, 244; Kuczera 2022, 15).

## Triple count

```sparql
# counts all triples in a triple store and returns
# the total number together with a current timestamp

PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT (NOW() AS ?date) (xsd:integer(COUNT(*)) AS ?count) WHERE {
   ?s ?p ?o
}

```
