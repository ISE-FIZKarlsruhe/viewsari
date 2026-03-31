Place one JSON annotation file per biography here. Files should be named {slug}.json.

Each file must be a JSON array of paragraph objects with the following schema:

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

The `slug` is the filename without `.json` and is used in URLs: `/biography/{slug}/{paragraph_id}`.