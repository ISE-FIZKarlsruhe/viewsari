"""
build_viewsari_kg.py
====================
Transforms raw source data into a set of CSV files that seed the
Viewsari Knowledge Graph. Each CSV corresponds to a distinct class
in the Viewsari ontology / supporting vocabularies (FaBiO, FRBR,
DoCO, PROV-O, Web Annotation).

Input files expected in INPUT_DIR
──────────────────────────────────
  paragraph_texts/
    0.csv … 9.csv   — paragraph text per volume
                      columns: page, paragraph_id, text

  index_names/
    0.csv … 9.csv   — NER + coref index per volume (0 = Vol 1, etc.)
                      columns: page, index_name, position, reference, paragraph

Output files written to OUTPUT_DIR
────────────────────────────────────
  viewsari_volumes.csv
  viewsari_biographies.csv
  viewsari_pages.csv
  viewsari_paragraphs.csv
  viewsari_persons.csv
  viewsari_textchunks.csv
  viewsari_selectors.csv
  viewsari_annotations.csv
  viewsari_activities.csv

Usage
─────
  python build_viewsari_kg.py \
      --para-dir  data/paragraph_texts \
      --index-dir data/index_names \
      --output    output/

Dependencies: pandas >= 1.5
"""

import argparse
import csv
import os
import re

import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

# Gutenberg eBook IDs, one per volume (1-indexed)
GUTENBERG_IDS = {
    1: "25326", 2: "25759", 3: "26860", 4: "28420",
    5: "28421", 6: "28422", 7: "32361", 8: "32362",
    9: "32363", 10: "33203",
}

# Ontology namespace
VIEWSARI_NS = "https://viewsari.ise.fiz-karlsruhe.de/ontology/#"

# Top-level work / manifestation-collection nodes (fixed ontology IRIs)
EDITION_EXPR_NODE  = f"{VIEWSARI_NS}0001029"   # edition expression (parent of all volumes)
EDITION_MANIF_NODE = f"{VIEWSARI_NS}0001031"   # manifestation collection (Gutenberg)

# ── Helpers ──────────────────────────────────────────────────────────────────

def gutenberg_url(vol: int) -> str:
    eid = GUTENBERG_IDS[vol]
    return f"https://www.gutenberg.org/files/{eid}/{eid}-h/{eid}-h.htm"


def slugify(name: str) -> str:
    """Return a URL-safe slug for a person name."""
    s = clean_name(name).lower()
    s = re.sub(r"['''\u2019]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def clean_name(name: str) -> str:
    """Fix common encoding artefacts from the source files."""
    s = str(name).strip()
    s = s.replace("ï¿½", "ò")   # UTF-8 mojibake for ò (Niccolò, Forlò …)
    s = s.replace("Ã©", "é")
    return s


def parse_position(pos_str: str):
    """'(397, 472)' -> (397, 472)"""
    m = re.match(r"\((\d+),\s*(\d+)\)", str(pos_str))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def write_csv(path: str, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)
    print(f"  wrote {len(rows)-1:>6} rows → {os.path.basename(path)}")


# ── Biography metadata ───────────────────────────────────────────────────────
# (name, slug, start_page, volume)
# Start pages are the printed page numbers embedded in the Gutenberg HTML as
# #Page_N anchors, matching the 1568 Du Vere edition pagination.

BIOGRAPHIES = [
    # VOL 1
    ("Giovanni Cimabue", "cimabue", 1, 1),
    ("Arnolfo di Lapo", "arnolfo-di-lapo", 11, 1),
    ("Niccola and Giovanni of Pisa", "niccola-giovanni-pisa", 27, 1),
    ("Andrea Tafi", "andrea-tafi", 45, 1),
    ("Gaddo Gaddi", "gaddo-gaddi", 53, 1),
    ("Margaritone", "margaritone", 61, 1),
    ("Giotto", "giotto", 69, 1),
    ("Agostino and Agnolo of Siena", "agostino-agnolo-siena", 95, 1),
    ("Stefano and Ugolino Sanese", "stefano-ugolino-sanese", 107, 1),
    ("Pietro Laurati", "pietro-laurati", 115, 1),
    ("Andrea Pisano", "andrea-pisano", 121, 1),
    ("Buonamico Buffalmacco", "buffalmacco", 133, 1),
    ("Ambrogio Lorenzetti", "ambrogio-lorenzetti", 153, 1),
    ("Pietro Cavallini", "pietro-cavallini", 159, 1),
    ("Simone Sanese", "simone-sanese", 165, 1),
    ("Taddeo Gaddi", "taddeo-gaddi", 175, 1),
    ("Andrea di Cione Orcagna", "andrea-orcagna", 187, 1),
    ("Tommaso Giottino", "giottino", 201, 1),
    ("Giovanni dal Ponte", "giovanni-dal-ponte", 209, 1),
    ("Agnolo Gaddi", "agnolo-gaddi", 215, 1),
    # VOL 2
    ("Berna", "berna", 1, 2),
    ("Duccio", "duccio", 9, 2),
    ("Antonio Viniziano", "antonio-viniziano", 17, 2),
    ("Jacopo di Casentino", "jacopo-casentino", 23, 2),
    ("Spinello Aretino", "spinello-aretino", 27, 2),
    ("Gherardo Starnina", "starnina", 43, 2),
    ("Lippo", "lippo", 51, 2),
    ("Don Lorenzo Monaco", "don-lorenzo-monaco", 55, 2),
    ("Taddeo Bartoli", "taddeo-bartoli", 63, 2),
    ("Lorenzo di Bicci", "lorenzo-di-bicci", 69, 2),
    ("Brunelleschi", "brunelleschi", 77, 2),
    ("Dello", "dello", 137, 2),
    ("Nanni d'Antonio di Banco", "nanni-di-banco", 143, 2),
    ("Luca della Robbia", "luca-della-robbia", 151, 2),
    ("Paolo Uccello", "paolo-uccello", 167, 2),
    ("Lorenzo Ghiberti", "ghiberti", 181, 2),
    ("Masolino da Panicale", "masolino", 213, 2),
    ("Parri Spinelli", "parri-spinelli", 219, 2),
    ("Masaccio", "masaccio", 225, 2),
    ("Filippo Brunelleschi", "filippo-brunelleschi-second", 251, 2),
    ("Donatello", "donatello", 261, 2),
    ("Michelozzo Michelozzi", "michelozzo", 323, 2),
    # VOL 3 — page numbers verified against Gutenberg #26860
    ("Antonio Filarete and Simone", "filarete-simone", 1, 3),
    ("Giuliano da Maiano", "giuliano-da-maiano", 9, 3),
    ("Piero della Francesca", "piero-della-francesca", 15, 3),
    ("Fra Giovanni da Fiesole (Fra Angelico)", "fra-angelico", 25, 3),
    ("Leon Battista Alberti", "alberti", 41, 3),
    ("Lazzaro Vasari", "lazzaro-vasari", 49, 3),
    ("Antonello da Messina", "antonello-da-messina", 57, 3),
    ("Alesso Baldovinetti", "baldovinetti", 65, 3),
    ("Vellano da Padova", "vellano", 71, 3),
    ("Fra Filippo Lippi", "fra-filippo-lippi", 77, 3),
    ("Paolo Romano and Maestro Mino and Chimenti Camicia", "paolo-romano", 89, 3),
    ("Andrea dal Castagno and Domenico Viniziano", "andrea-dal-castagno", 95, 3),
    ("Gentile da Fabriano and Vittore Pisanello", "gentile-pisanello", 107, 3),
    ("Pesello and Francesco Peselli", "pesello-peselli", 115, 3),
    ("Benozzo Gozzoli", "benozzo-gozzoli", 119, 3),
    ("Francesco di Giorgio and Lorenzo Vecchietto", "francesco-di-giorgio", 127, 3),
    ("Galasso Ferrarese", "galasso-ferrarese", 133, 3),
    ("Antonio Rossellino and Bernardo Rossellino", "rossellino", 137, 3),
    ("Desiderio da Settignano", "desiderio-da-settignano", 145, 3),
    ("Mino da Fiesole", "mino-da-fiesole", 151, 3),
    ("Lorenzo Costa", "lorenzo-costa", 159, 3),
    ("Ercole Ferrarese", "ercole-ferrarese", 165, 3),
    ("Jacopo Giovanni and Gentile Bellini", "bellini", 171, 3),
    ("Cosimo Rosselli", "cosimo-rosselli", 185, 3),
    ("Cecca", "cecca", 191, 3),
    ("Don Bartolommeo della Gatta", "don-bartolommeo-della-gatta", 201, 3),
    ("Gherardo", "gherardo", 211, 3),
    ("Domenico Ghirlandajo", "ghirlandajo", 217, 3),
    ("Antonio and Piero Pollaiuolo", "pollaiuolo", 235, 3),
    ("Sandro Botticelli", "botticelli", 245, 3),
    ("Benedetto da Maiano", "benedetto-da-maiano", 255, 3),
    ("Andrea Verrocchio", "verrocchio", 265, 3),
    ("Andrea Mantegna", "mantegna", 277, 3),
    # VOL 4
    ("Filippino Lippi", "filippino-lippi", 1, 4),
    ("Bernardino Pinturicchio", "pinturicchio-v4", 17, 4),
    ("Francesco Francia", "france-francia-v4", 33, 4),
    ("Pietro Perugino", "perugino-v4", 43, 4),
    ("Luca Signorelli", "luca-signorelli", 83, 4),
    ("Bramante da Urbino", "bramante", 109, 4),
    ("Raphael of Urbino", "raphael", 125, 4),
    ("Guglielmo da Marcilla", "guglielmo-da-marcilla", 221, 4),
    ("Simone del Pollaiuolo", "simone-del-pollaiuolo", 229, 4),
    ("Andrea dal Monte Sansovino", "andrea-sansovino", 235, 4),
    ("Benedetto da Rovezzano", "benedetto-da-rovezzano", 255, 4),
    ("Baccio da Montelupo and Raffaello", "baccio-montelupo", 261, 4),
    ("Lorenzetto and Boccaccino", "lorenzetto-boccaccino", 269, 4),
    ("Baldassarre Peruzzi", "peruzzi", 275, 4),
    ("Giovanfrancesco Penni and Others", "giovanfrancesco-penni", 299, 4),
    ("Andrea del Sarto", "andrea-del-sarto", 307, 4),
    ("Domenico Puligo", "domenico-puligo", 379, 4),
    # VOL 5
    ("Andrea da Fiesole and Others", "andrea-da-fiesole", 1, 5),
    ("Vincenzio da San Gimignano and Timoteo da Urbino", "vincenzio-timoteo", 7, 5),
    ("Valerio Vicentino and Others", "valerio-vicentino", 23, 5),
    ("Marc Antonio Bolognese and Others", "marcantonio-bolognese", 39, 5),
    ("Antonio da San Gallo the Elder", "antonio-san-gallo-elder", 55, 5),
    ("Giulio Romano", "giulio-romano", 63, 5),
    ("Fra Sebastiano Viniziano del Piombo", "sebastiano-del-piombo", 121, 5),
    ("Perino del Vaga", "perino-del-vaga", 141, 5),
    ("Giovanni Antonio Lappoli", "lappoli", 187, 5),
    ("Niccolo Soggi", "niccolo-soggi", 193, 5),
    ("Lorenzo Lotto", "lorenzo-lotto", 199, 5),
    # VOL 6
    ("Fra Giocondo and Liberale and Others", "fra-giocondo", 1, 6),
    ("Francesco Granacci", "granacci", 23, 6),
    ("Baccio d'Agnolo", "baccio-d-agnolo", 33, 6),
    ("Antonio da San Gallo the Younger", "antonio-san-gallo-younger", 47, 6),
    ("Jacopo Sansovino", "jacopo-sansovino", 117, 6),
    ("Battista Franco", "battista-franco", 145, 6),
    ("Giovan Francesco Rustici", "rustici", 151, 6),
    ("Fra Giovanni Agnolo Montorsoli", "montorsoli", 167, 6),
    ("Francesco de' Rossi Salviati", "salviati", 191, 6),
    ("Daniello Ricciarelli", "daniello-ricciarelli", 245, 6),
    ("Taddeo Zuccaro", "taddeo-zuccaro", 259, 6),
    ("Giorgio Vasari", "vasari", 277, 6),
    ("Domenico Beccafumi", "beccafumi", 373, 6),
    # VOL 7
    ("Niccolò called Tribolo", "tribolo", 1, 7),
    ("Pierino da Vinci", "pierino-da-vinci", 61, 7),
    ("Baccio Bandinelli", "baccio-bandinelli", 75, 7),
    ("Giuliano Bugiardini", "bugiardini", 161, 7),
    ("Cristofano Gherardi", "cristofano-gherardi", 171, 7),
    ("Jacopo da Pontormo", "pontormo", 189, 7),
    ("Simone Mosca", "simone-mosca", 245, 7),
    ("Girolamo and Bartolommeo Genga and Giovan Battista San Marino", "genga", 253, 7),
    ("Michele Sanmicheli", "sanmicheli", 267, 7),
    ("Giovanni Antonio Bazzi called Il Sodoma", "sodoma", 307, 7),
    # VOL 8
    ("Bastiano da San Gallo called Aristotile", "aristotile-san-gallo", 1, 8),
    ("Benvenuto Garofalo and Girolamo da Carpi and Other Lombards", "garofalo", 13, 8),
    ("Ridolfo David and Benedetto Ghirlandajo", "ridolfo-ghirlandajo", 45, 8),
    ("Giovanni da Udine", "giovanni-da-udine", 55, 8),
    ("Battista Franco", "battista-franco-v8", 69, 8),
    ("Giovan Francesco Rustici", "rustici-v8", 79, 8),
    ("Fra Giovanni Agnolo Montorsoli", "montorsoli-v8", 97, 8),
    ("Francesco de' Rossi Salviati", "salviati-v8", 121, 8),
    ("Daniello Ricciarelli", "daniello-v8", 173, 8),
    ("Taddeo Zuccaro", "taddeo-zuccaro-v8", 185, 8),
    # VOL 9
    ("Michelagnolo Buonarroti", "michelagnolo", 1, 9),
    # VOL 10
    ("Agnolo Bronzino", "bronzino", 1, 10),
    ("Academicians of Design", "academicians-design", 65, 10),
    ("Description of Festive Preparations", "festive-preparations", 155, 10),
    ("Giorgio Vasari", "vasari-v10", 167, 10),
]

VOLUME_SUBTITLES = {
    1: "Cimabue to Agnolo Gaddi",
    2: "Berna to Michelozzo Michelozzi",
    3: "Filarete and Simone to Mantegna",
    4: "Filippino Lippi to Domenico Puligo",
    5: "Andrea da Fiesole to Lorenzo Lotto",
    6: "Fra Giocondo to Niccolo Soggi",
    7: "Tribolo to Il Sodoma",
    8: "Bastiano da San Gallo to Taddeo Zucchero",
    9: "Michelagnolo Buonarroti",
    10: "Agnolo Bronzino to Index",
}


# ── FRBR helpers ─────────────────────────────────────────────────────────────

def vol_expr_id(v):   return f"viewsari:the_lives_1568_volume-{v}"
def vol_manif_id(v):  return f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{v}"
def bio_expr_id(slug, v):  return f"viewsari:the_lives_1568_volume-{v}_{slug}-bio"
def bio_manif_id(slug, v): return f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{v}_{slug}-bio"
def page_expr_id(slug, v, p):  return f"viewsari:the_lives_1568_volume-{v}_{slug}-bio_page_{p}"
def page_manif_id(slug, v, p): return f"viewsari:the_lives_1568_gutenberg_web_version_of_volume-{v}_{slug}-bio_page_{p}"


# ── Build biography page-range lookup ────────────────────────────────────────

def build_bio_lookup(para_dir: str):
    """
    Returns a dict mapping (vol, page) -> (bio_slug, bio_expr_id).
    Also returns per-volume max page from the paragraph text files.
    """
    # Derive ranges from BIOGRAPHIES list; last bio per vol needs max page
    # from actual data.
    vol_max_page = {}
    for v in range(1, 11):
        path = os.path.join(para_dir, f"{v-1}.csv")
        df = pd.read_csv(path)
        vol_max_page[v] = int(df["page"].max())

    # Build sorted list of (start_page, end_page, slug) per volume
    from collections import defaultdict
    vol_bios = defaultdict(list)
    for name, slug, start, v in BIOGRAPHIES:
        vol_bios[v].append((start, slug))

    bio_ranges = {}   # vol -> [(start, end, slug), ...]
    for v, entries in vol_bios.items():
        entries_sorted = sorted(entries, key=lambda x: x[0])
        ranges = []
        for i, (start, slug) in enumerate(entries_sorted):
            end = entries_sorted[i+1][0] - 1 if i+1 < len(entries_sorted) else vol_max_page[v]
            ranges.append((start, end, slug))
        bio_ranges[v] = ranges

    # Build fast (vol, page) lookup
    lookup = {}
    for v, ranges in bio_ranges.items():
        for start, end, slug in ranges:
            for p in range(start, end + 1):
                lookup[(v, p)] = (slug, bio_expr_id(slug, v))

    return lookup, vol_max_page, bio_ranges


# ── Stage 1: Volumes ──────────────────────────────────────────────────────────

def build_volumes(output_dir: str):
    rows = [["instance_id", "rdf_type_1", "rdf_type_2", "rdfs:label",
             "frbr:is part of", "frbr:has embodiment", "rdfs:seeAlso", "level"]]
    for v in range(1, 11):
        expr_id  = vol_expr_id(v)
        manif_id = vol_manif_id(v)
        subtitle = VOLUME_SUBTITLES[v]
        url      = gutenberg_url(v)
        rows.append([expr_id, "viewsari:volume", "fabio:BookSeries",
                     f"The Lives, 1568 Edition, Volume {v}: {subtitle}",
                     EDITION_EXPR_NODE, manif_id, "", "expression"])
        rows.append([manif_id, "viewsari:volume web representation", "fabio:WebSite",
                     f"Gutenberg Web Version of The Lives, Volume {v}",
                     EDITION_MANIF_NODE, "", url, "manifestation"])
    write_csv(os.path.join(output_dir, "viewsari_volumes.csv"), rows)


# ── Stage 2: Biographies ──────────────────────────────────────────────────────

def build_biographies(output_dir: str):
    rows = [["instance_id", "rdf:type", "rdf_type_2", "rdfs:label",
             "frbr:is part of", "frbr:has embodiment", "rdfs:seeAlso",
             "start_page", "vol", "level"]]
    for name, slug, start, v in BIOGRAPHIES:
        expr_id  = bio_expr_id(slug, v)
        manif_id = bio_manif_id(slug, v)
        url      = gutenberg_url(v)
        rows.append([expr_id, "viewsari:biography", "fabio:Expression",
                     f"Life of {name}", vol_expr_id(v), manif_id, "",
                     start, v, "expression"])
        rows.append([manif_id, "viewsari:biography web representation", "fabio:WebPage",
                     f"Gutenberg Web Version of Life of {name} (Volume {v})",
                     vol_manif_id(v), "", f"{url}#Page_{start}",
                     start, v, "manifestation"])
    write_csv(os.path.join(output_dir, "viewsari_biographies.csv"), rows)


# ── Stage 3: Pages ────────────────────────────────────────────────────────────

def build_pages(output_dir: str, bio_ranges: dict):
    """One expression + manifestation pair per printed page per biography."""
    rows = [["instance_id", "rdf:type", "rdf_type_2", "rdfs:label",
             "frbr:is part of", "frbr:has embodiment", "rdfs:seeAlso",
             "page_number", "biography_slug", "vol", "level"]]

    # Build name lookup for labels
    name_lookup = {(v, slug): name for name, slug, _, v in BIOGRAPHIES}

    for v in range(1, 11):
        url = gutenberg_url(v)
        for start, end, slug in bio_ranges[v]:
            artist = name_lookup.get((v, slug), slug)
            for p in range(start, end + 1):
                expr_id  = page_expr_id(slug, v, p)
                manif_id = page_manif_id(slug, v, p)
                rows.append([expr_id, "viewsari:page", "fabio:Expression",
                              f"The Lives, 1568, Vol. {v}, Life of {artist}, Page {p}",
                              bio_expr_id(slug, v), manif_id, "",
                              p, slug, v, "expression"])
                rows.append([manif_id, "viewsari:page web representation", "fabio:WebPage",
                              f"Gutenberg Web Version of Life of {artist}, Page {p}",
                              bio_manif_id(slug, v), "", f"{url}#Page_{p}",
                              p, slug, v, "manifestation"])
    write_csv(os.path.join(output_dir, "viewsari_pages.csv"), rows)


# ── Stage 4: Paragraphs ───────────────────────────────────────────────────────

def build_paragraphs(para_dir: str, output_dir: str, bio_lookup: dict):
    """
    Merge page-split paragraphs, compute character counts,
    link to page web representation and biography expression.
    """
    rows = [["instance_id", "rdf:type", "rdfs:label", "dct:isPartOf",
             "viewsari:has start page", "viewsari:has end page",
             "viewsari:has length in characters", "viewsari:has text",
             "frbr:is part of", "vol", "paragraph_id"]]

    for i in range(10):
        v   = i + 1
        df  = pd.read_csv(os.path.join(para_dir, f"{i}.csv"))
        df["page"]         = df["page"].astype(int)
        df["paragraph_id"] = df["paragraph_id"].astype(int)

        def merge_group(grp):
            grp = grp.sort_values("page")
            pages = list(grp["page"])
            text  = grp["text"].iloc[0].rstrip()
            for t in grp["text"].iloc[1:]:
                text += t          # continuation fragments include leading space
            return pd.Series({"start_page": pages[0], "end_page": pages[-1], "text": text})

        merged = df.groupby("paragraph_id", sort=True).apply(merge_group).reset_index()
        merged["paragraph_id"] = merged["paragraph_id"].astype(int)

        for _, row in merged.iterrows():
            para_id  = int(row["paragraph_id"])
            start_p  = int(row["start_page"])
            end_p    = int(row["end_page"])
            text     = str(row["text"])
            char_len = len(text)

            slug, b_expr = bio_lookup.get((v, start_p), ("unknown", f"viewsari:unknown-vol{v}"))
            para_expr   = f"viewsari:the_lives_1568_volume-{v}_paragraph-{para_id}"
            start_manif = page_manif_id(slug, v, start_p)
            end_manif   = page_manif_id(slug, v, end_p)

            rows.append([para_expr, "doco:Paragraph",
                         f"The Lives, 1568, Vol. {v}, Paragraph {para_id}",
                         page_expr_id(slug, v, start_p),
                         start_manif, end_manif,
                         char_len, text, b_expr, v, para_id])

    write_csv(os.path.join(output_dir, "viewsari_paragraphs.csv"), rows)


# ── Stage 5: Persons, TextChunks, Selectors, Annotations, Activities ─────────

def build_annotation_layer(index_dir: str, output_dir: str, bio_lookup: dict):
    """
    Process the NER + coref index files to produce:
      - viewsari_persons.csv          (one entity per unique resolved name)
      - viewsari_textchunks.csv       (one per individual mention span)
      - viewsari_selectors.csv        (character-offset selectors)
      - viewsari_annotations.csv      (OA annotations linking spans to paragraphs)
      - viewsari_activities.csv       (NER and coref provenance activities)
    """

    # ── Pass 1: collect unique persons (expand pipe-separated ambiguous names) ──
    person_registry = {}   # slug -> canonical cleaned label

    vol_dfs = {}
    for i in range(10):
        v  = i + 1
        df = pd.read_csv(os.path.join(index_dir, f"{i}.csv"))
        df["paragraph"] = df["paragraph"].astype(int)
        expanded = []
        for _, row in df.iterrows():
            for part in [p.strip() for p in str(row["index_name"]).split("|")]:
                r = row.copy()
                r["index_name"] = part
                expanded.append(r)
        df_exp = pd.DataFrame(expanded)
        vol_dfs[v] = df_exp
        for name in df_exp["index_name"].unique():
            slug = slugify(name)
            if slug not in person_registry:
                person_registry[slug] = clean_name(name)

    # ── Pass 2: build all four linked tables ─────────────────────────────────
    person_to_annots = {}   # slug -> [annot_uri, ...]

    chunk_rows  = [["instance_id", "rdf:type", "rdfs:label", "dct:isPartOf", "oa:hasSelector"]]
    sel_rows    = [["instance_id", "rdf:type", "oa:start", "oa:end", "dct:isPartOf"]]
    annot_rows  = [["instance_id", "rdf:type", "oa:hasTarget", "oa:hasBodyValue",
                    "prov:wasGeneratedBy", "prov:used", "oa:hasSource"]]

    counter = 0
    for v in range(1, 11):
        df = vol_dfs[v]
        for (para_id, index_name), group in df.groupby(["paragraph", "index_name"], sort=False):
            slug       = slugify(index_name)
            para_id    = int(para_id)
            para_expr  = f"viewsari:the_lives_1568_volume-{v}_paragraph-{para_id}"

            for _, row in group.iterrows():
                counter   += 1
                start, end = parse_position(row["position"])
                ref_text   = str(row["reference"])
                page       = int(row["page"])

                bio_slug, _ = bio_lookup.get((v, page), ("unknown", ""))
                pg_manif    = page_manif_id(bio_slug, v, page)

                chunk_id  = f"viewsari:textchunk_{counter}"
                sel_id    = f"viewsari:position-selector_{counter}"
                annot_id  = f"viewsari:annotation_{counter}"

                chunk_rows.append([chunk_id, "doco:TextChunk",
                                   f"Text mention of {clean_name(index_name)}, "
                                   f"Vol. {v}, Para. {para_id}",
                                   para_expr, sel_id])

                sel_rows.append([sel_id, "doco:TextPositionSelector",
                                 start, end, chunk_id])

                annot_rows.append([annot_id, "oa:Annotation, prov:Entity",
                                   chunk_id, ref_text,
                                   "viewsari:named_entity_recognition_run_1",
                                   para_expr, para_expr])

                person_to_annots.setdefault(slug, []).append(annot_id)

    # ── Persons ───────────────────────────────────────────────────────────────
    person_rows = [["instance_id", "rdf:type", "rdfs:label", "prov:wasGeneratedBy"]]
    for slug, label in sorted(person_registry.items()):
        person_rows.append([f"viewsari:{slug}", "viewsari:person", label,
                            "viewsari:coreference_reconciliation_run_1"])

    # ── Activities ────────────────────────────────────────────────────────────
    # NER used: all 10 index-of-names entities + all unique paragraphs in annotations
    para_used = sorted(
        {r[5] for r in annot_rows[1:]},
        key=lambda x: (int(re.search(r"volume-(\d+)", x).group(1)),
                       int(re.search(r"paragraph-(\d+)", x).group(1)))
    )
    ner_used = " ".join(
        [f"viewsari:index_of_names_{v}" for v in range(1, 11)] + para_used
    )

    # Coref used: all annotation URIs
    all_annots = sorted(
        {r[0] for r in annot_rows[1:]},
        key=lambda x: int(x.split("_")[-1])
    )
    coref_used = " ".join(all_annots)

    activity_rows = [
        ["instance_id", "rdf:type", "rdfs:label", "prov:wasAssociatedWith", "prov:used"],
        ["viewsari:named_entity_recognition_run_1", "prov:Activity",
         "Named Entity Recognition Run 1", "viewsari:python_script_for_ner_1", ner_used],
        ["viewsari:coreference_reconciliation_run_1", "prov:Activity",
         "Coreference Reconciliation Run 1", "viewsari:python_script_for_ner_2", coref_used],
    ]

    persons_dir = os.path.join(output_dir, "persons")
    os.makedirs(persons_dir, exist_ok=True)
    write_csv(os.path.join(persons_dir, "viewsari_persons.csv"),     person_rows)
    write_csv(os.path.join(persons_dir, "viewsari_textchunks.csv"),  chunk_rows)
    write_csv(os.path.join(persons_dir, "viewsari_selectors.csv"),   sel_rows)
    write_csv(os.path.join(persons_dir, "viewsari_annotations.csv"), annot_rows)
    write_csv(os.path.join(persons_dir, "viewsari_activities.csv"),  activity_rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build Viewsari KG seed CSVs")
    parser.add_argument("--para-dir",  default="data/archive/volumes",
                        help="Directory containing paragraph text CSVs (0.csv–9.csv)")
    parser.add_argument("--index-dir", default="data/index_of_names",
                        help="Directory containing NER/coref index CSVs (0.csv–9.csv)")
    parser.add_argument("--output",    default="kg_foundation/",
                        help="Directory to write output CSVs")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print("Building Viewsari KG seed data …\n")

    print("Stage 1 — Volumes")
    build_volumes(args.output)

    print("Stage 2 — Biographies")
    build_biographies(args.output)

    print("Stage 3 — Pages (bio ranges + Gutenberg anchors)")
    bio_lookup, vol_max_page, bio_ranges = build_bio_lookup(args.para_dir)
    build_pages(args.output, bio_ranges)

    print("Stage 4 — Paragraphs (merge page-split fragments)")
    build_paragraphs(args.para_dir, args.output, bio_lookup)

    print("Stage 5 — Annotation layer (persons / chunks / selectors / annotations / activities)")
    build_annotation_layer(args.index_dir, args.output, bio_lookup)

    print("\nDone.")


if __name__ == "__main__":
    main()
