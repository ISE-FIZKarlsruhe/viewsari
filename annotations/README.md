# Annotation JSON schema

This directory describes the **gold-standard annotation JSON** format that the rest of the project consumes — the same format produced by the manual annotation effort in INCEpTION and shipped under [`obliquer/data/viewsari/ground_truth/`](../obliquer/data/viewsari/ground_truth/). It is used in three places:

- as the **GT input** to ObliquER evaluation (**E2**),
- as the **mention seed** ingested into the KG by [`src/kg_population/ingest_annotations.py`](../src/kg_population/ingest_annotations.py) (**E3**),
- as the **paragraph-level source** read by the website's biography viewer ([`app/routers/biography.py`](../app/routers/biography.py)) to render colour-coded mention spans (**C3** — provenance made inspectable at the point of use).

Place one JSON annotation file per biography here. Files should be named `{slug}_enriched.json` and grouped under a volume directory (e.g. `3/botticelli_enriched.json`). The loader strips the `_enriched` suffix to derive the slug and uses the parent directory name as the volume number.

By default the website reads these files from the `obliquer` submodule (`./obliquer/data/viewsari/ground_truth`); set `ANNOTATIONS_DIR` in `.env` to override.

## Schema

Each file must be a JSON array of paragraph objects:

```json
[
  {
    "paragraph_id": 284,
    "biography": "Sandro Botticelli",
    "page": "248-249",
    "candidate_negative": false,
    "text": "Full paragraph text...",
    "mentions": [
      {
        "mention_id": "m_0018",
        "type": "explicit artwork mention",
        "surface_form": "S. Marco",
        "entity_id": "e_0018",
        "wikidata_id": "https://www.wikidata.org/wiki/Q573881",
        "ookb": false,
        "ookb_uri": null,
        "refers_to": null,
        "start_offset": 112,
        "end_offset": 119,
        "label": "Basilica of San Marco",
        "wga_id": null
      }
    ]
  }
]
```

### Mention types

The `type` field maps directly to the `viewsari:mention` taxonomy in the ontology (operationalizing **C1**: explicit, implicit, coreferent, and generic mentions are kept distinct rather than collapsed into a single annotation class):

| JSON value | Ontology class |
|---|---|
| `"explicit artwork mention"` | `viewsari:explicit_artwork_mention ⊑ viewsari:explicit_mention` |
| `"implicit artwork mention"` | `viewsari:implicit_artwork_mention ⊑ viewsari:implicit_mention` |
| `"coreferent"` | `viewsari:coreferent` |
| `"generic mention"` | `viewsari:generic_mention` |

### Entity identity

The `entity_id` field is **not** used as a stable identifier; identity in the KG is determined solely by `wikidata_id` (Wikidata-linked) or `ookb_uri` (out-of-knowledge-base). Cross-biography consolidation follows the same rule: same QID / OOKB fragment = same entity.

### URL convention

The `slug` is the filename with the `_enriched` suffix removed and is used in URLs: `/biography/{slug}/{paragraph_id}`.
