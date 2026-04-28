"""
link_persons_wikidata.py
========================
Matches Viewsari persons against Wikidata artists (from a SPARQL export)
and adds Wikidata QID + alt-label columns to viewsari_persons.csv.

Input:
    data/kg_foundation/persons/artists_before_1568.csv   (s,p,o triples from Wikidata)
    data/kg_foundation/persons/viewsari_persons.csv      (Viewsari person entities)

Output:
    data/kg_foundation/persons/viewsari_persons.csv      (updated in-place with new columns)

Usage:
    python src/network/link_persons_wikidata.py
"""

import csv
import difflib
import os
import re

BASE = os.path.join(os.path.dirname(__file__), os.pardir, "data", "kg_foundation", "persons")
WD_PATH = os.path.join(BASE, "artists_before_1568.csv")
PERSONS_PATH = os.path.join(BASE, "viewsari_persons.csv")

ROW_RE = re.compile(
    r'<http://www\.wikidata\.org/entity/(Q\d+)>,<([^>]+)>,"""(.+?)""@en"'
)


# ── Helpers ──────────────────────────────────────────────────────────────

def normalize(s: str) -> str:
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.lower().strip()
    s = re.sub(r"['\u2018\u2019`]", "'", s)
    s = re.sub(r"[,\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def flip_name(label: str) -> str:
    """'Surname, Firstname (alt)' -> 'firstname surname'"""
    base = re.sub(r"\s*\([^)]*\)", "", label).strip()
    parts = base.split(",", 1)
    if len(parts) == 2:
        return (parts[1].strip() + " " + parts[0].strip()).lower()
    return base.lower()


def extract_alt_names(label: str) -> list[str]:
    """Extract alternate names from parentheses, splitting on 'or'."""
    results = []
    for alt in re.findall(r"\(([^)]+)\)", label):
        for part in re.split(r",\s*or\s+|,\s+", alt):
            part = part.strip()
            if part and len(part) > 3:
                results.append(part.lower())
    return results


# ── Parse Wikidata triples ───────────────────────────────────────────────

def parse_wikidata(path: str):
    """Return name_to_qid, qid_altlabels dicts from the WD export."""
    with open(path, "r") as f:
        raw = f.read()

    name_to_qid: dict[str, str] = {}
    qid_altlabels: dict[str, list[str]] = {}

    for line in raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("s,"):
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        qid, pred, name = m.group(1), m.group(2), m.group(3).strip()

        if "description" in pred:
            continue

        name_to_qid[name.lower()] = qid

        if "altLabel" in pred:
            qid_altlabels.setdefault(qid, []).append(name)

    return name_to_qid, qid_altlabels


# ── Matching logic ───────────────────────────────────────────────────────

def match_person(label: str, name_to_qid: dict, wd_lookup: dict, wd_keys: list) -> str:
    """Try progressively looser strategies to find a QID for a person label."""

    # 1: exact match on full label
    if label.lower() in name_to_qid:
        return name_to_qid[label.lower()]

    # 2: flip "Surname, First" -> "first surname" (2+ words only)
    flipped = flip_name(label)
    if len(flipped.split()) >= 2:
        if flipped in name_to_qid:
            return name_to_qid[flipped]
        if normalize(flipped) in wd_lookup:
            return wd_lookup[normalize(flipped)]

    # 3: normalized match (multi-word)
    norm = normalize(label)
    if len(norm.split()) >= 2 and norm in wd_lookup:
        return wd_lookup[norm]
    norm_flip = normalize(flipped)
    if len(norm_flip.split()) >= 2 and norm_flip in wd_lookup:
        return wd_lookup[norm_flip]

    # 4: alternate names from parentheses — exact
    for alt in extract_alt_names(label):
        if alt in name_to_qid:
            return name_to_qid[alt]
        if normalize(alt) in wd_lookup:
            return wd_lookup[normalize(alt)]

    # 5: fuzzy on flipped name (>12 chars, 2+ words, cutoff 0.88)
    if len(norm_flip) > 12 and len(norm_flip.split()) >= 2:
        candidates = difflib.get_close_matches(norm_flip, wd_keys, n=1, cutoff=0.88)
        if candidates:
            return wd_lookup[candidates[0]]

    # 6: fuzzy on alt names (>10 chars, 2+ words, cutoff 0.83)
    for alt in extract_alt_names(label):
        norm_alt = normalize(alt)
        if len(norm_alt) > 10 and len(norm_alt.split()) >= 2:
            candidates = difflib.get_close_matches(norm_alt, wd_keys, n=1, cutoff=0.83)
            if candidates:
                return wd_lookup[candidates[0]]

    return ""


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print(f"Reading Wikidata artists from {WD_PATH}")
    name_to_qid, qid_altlabels = parse_wikidata(WD_PATH)

    # Build normalised lookup
    wd_lookup: dict[str, str] = {}
    for name, qid in name_to_qid.items():
        wd_lookup[normalize(name)] = qid
        wd_lookup[name] = qid
    wd_keys = list(wd_lookup.keys())

    print(f"  {len(name_to_qid)} name variants across {len(qid_altlabels)} QIDs with alt-labels")

    # Read persons
    print(f"Reading persons from {PERSONS_PATH}")
    with open(PERSONS_PATH, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        persons = list(reader)

    # Strip old generated columns if re-running
    while header and header[-1] in ("Wikidata QID", "Wikidata alt-labels"):
        header.pop()
        persons = [r[:-1] for r in persons]

    label_idx = header.index("rdfs:label")

    # Match
    matched = 0
    results = []
    for row in persons:
        label = row[label_idx].strip()
        qid = match_person(label, name_to_qid, wd_lookup, wd_keys)

        alt_labels = ""
        if qid and qid in qid_altlabels:
            alt_labels = "; ".join(qid_altlabels[qid])

        if qid:
            matched += 1
        results.append(row + [qid, alt_labels])

    print(f"Matched {matched}/{len(persons)} persons")

    # Write
    new_header = header + ["Wikidata QID", "Wikidata alt-labels"]
    with open(PERSONS_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(new_header)
        writer.writerows(results)

    print(f"Wrote {PERSONS_PATH}")


if __name__ == "__main__":
    main()
