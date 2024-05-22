# Entity Extraction
Viewsari uses the translated English edition of The Lives for all
knowledge extraction and engineering steps. Gaston C. Du Vere wrote said translation in 1912
based on the 1568 edition. A digital edition of Du Vere’s translation is available in ten volumes, each containing a subset of all biographies.
For entity extraction, [the previous project team](https://github.com/ISE-FIZKarlsruhe/vasari_nlp/) conducted experiments on entity 
recognition and entity linking
They extracted the following entities: persons, organizations, places, and miscellaneous (all following the CoNLL 2003 dataset, partially linked
to Wikidata), as well as artwork references, motifs, terms, and dates. 
[In another project step](https://github.com/ISE-FIZKarlsruhe/vasari_network), they modeled relationships between artists through co-reference resolution and statistical association from the cooccurrence of names in
paragraphs to create the social network.

In Viewsari, we plan to extend this example set of entities through further extraction steps.