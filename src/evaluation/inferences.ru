# Closure rules for the Viewsari KG.
#
# Materialises the per-instance entity → viewsari:0001032 → paragraph edge
# wherever it can be reconstructed without changing the upstream pipeline.
# Apply with scripts/evaluation/materialise_inferences.py.
#
# Three rules (executed in order so later rules can chain off earlier ones):
#
#   R1  artwork closure via Web Annotation derivation
#       artwork → wasDerivedFrom → mention → 0001032 → paragraph
#       ⇒ artwork → 0001032 → paragraph
#       (most artworks already carry the edge; this is a defensive INSERT
#        for any artwork whose provenance was written before the edge became
#        standard.)
#
#   R2  cooccurrence closure via rdfs:label parse
#       cooccurrence rdfs:label "... Vol. N, Para. M"
#       ⇒ cooccurrence → 0001032 → vkb:the_lives_1568_volume-N_paragraph-M
#       (replaces the activity-level prov:used scan, which fans out across
#        every paragraph the run ever touched.)
#
#   R3  person closure via cooccurrence participation
#       person ← involves ← cooccurrence → 0001032 → paragraph
#       ⇒ person → 0001032 → paragraph
#       (gives persons the same paragraph anchor that cooccurrences gain in
#        R2; not exhaustive — only paragraphs in which the person co-occurs
#        with someone — but it is the closure justified by current evidence.)

PREFIX viewsari: <https://viewsari.ise.fiz-karlsruhe.de/ontology/#>
PREFIX vkb:      <https://viewsari.ise.fiz-karlsruhe.de/kb/1.0#>
PREFIX prov:     <http://www.w3.org/ns/prov#>
PREFIX oa:       <http://www.w3.org/ns/oa#>
PREFIX rdfs:     <http://www.w3.org/2000/01/rdf-schema#>

# ---------------------------------------------------------------------------
# R1: artwork closure
# ---------------------------------------------------------------------------
INSERT {
  ?entity viewsari:0001032 ?paragraph .
}
WHERE {
  ?entity prov:wasDerivedFrom ?mention .
  ?mention a oa:Annotation ;
           viewsari:0001032 ?paragraph .
  FILTER NOT EXISTS { ?entity viewsari:0001032 ?paragraph }
}  ;

# ---------------------------------------------------------------------------
# R2: cooccurrence closure (parse "Vol. N, Para. M" out of the label)
# ---------------------------------------------------------------------------
INSERT {
  ?cooc viewsari:0001032 ?paragraph .
}
WHERE {
  ?cooc a viewsari:0001025 ;
        rdfs:label ?label .
  FILTER (REGEX(?label, "Vol\\.\\s*\\d+,\\s*Para\\.\\s*\\d+"))
  BIND (REPLACE(?label, "^.*Vol\\.\\s*(\\d+),\\s*Para\\.\\s*(\\d+).*$", "$1") AS ?volNum)
  BIND (REPLACE(?label, "^.*Vol\\.\\s*(\\d+),\\s*Para\\.\\s*(\\d+).*$", "$2") AS ?paraNum)
  BIND (IRI(CONCAT(STR(vkb:the_lives_1568_volume-), ?volNum,
                   "_paragraph-", ?paraNum)) AS ?paragraph)
  FILTER NOT EXISTS { ?cooc viewsari:0001032 ?paragraph }
}  ;

# ---------------------------------------------------------------------------
# R3: person closure (chains off R2)
# ---------------------------------------------------------------------------
INSERT {
  ?person viewsari:0001032 ?paragraph .
}
WHERE {
  ?cooc a viewsari:0001025 ;
        viewsari:involves ?person ;
        viewsari:0001032 ?paragraph .
  ?person a viewsari:0001013 .
  FILTER NOT EXISTS { ?person viewsari:0001032 ?paragraph }
}
