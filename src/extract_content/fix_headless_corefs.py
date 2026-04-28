#!/usr/bin/env python3
"""Resolve headless coreferent mentions in the Viewsari ground truth.

A headless coreferent mention is a coref annotation whose `entity_id` does
not appear in any explicit or implicit artwork mention in the same
biography — typically because the annotator forgot to set `refers_to` and
left the link target unfilled. These chains inflate the per-biography
Entity column without contributing to the artwork-mention column.

The script finds every such chain, attempts to identify the most plausible
antecedent in an earlier paragraph of the same biography by matching the
head noun of the coreferent's surface form against the surface forms of
prior explicit/implicit mentions, and rewrites both the coref's
`entity_id` (now equal to the antecedent's) and its `refers_to` field
(now equal to the antecedent's `mention_id`).

Cases where the antecedent paragraph is not in the ground-truth corpus
(sampling artefacts) are reported but left untouched.

Usage
-----

    # Dry run — print proposed changes, do not modify files
    python src/extract_content/fix_headless_corefs.py

    # Apply changes in place; original is preserved as <file>.bak
    python src/extract_content/fix_headless_corefs.py --apply

    # Restrict to a single biography
    python src/extract_content/fix_headless_corefs.py --bio lippi --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from glob import glob
from pathlib import Path

GT_GLOB = "obliquer/data/viewsari/ground_truth/*/*_enriched.json"

# Head-noun synonyms that license a match between a coref's surface and an
# antecedent's surface. The keys are normalised head nouns extracted from
# coref surfaces; the values are tokens that may appear in the antecedent.
# Generic deictic surfaces (it / that / this / these / those / which) match
# any artwork antecedent and use the empty list as a wildcard.
HEAD_SYNONYMS: dict[str, list[str]] = {
    "edifice":  ["edifice", "building", "church", "temple", "tomb", "chapel",
                 "palace", "structure", "bridge", "loggia", "vault"],
    "chapel":   ["chapel"],
    "predella": ["predella"],
    "design":   ["design", "drawing", "cartoon", "model", "plan", "sketch"],
    "work":     [],   # any artwork
    "panel":    ["panel", "altarpiece", "altar-piece", "tavola"],
    "fresco":   ["fresco"],
    "statue":   ["statue", "sculpture", "figure", "marble"],
    "picture":  ["picture", "painting"],
    "painting": ["painting", "picture"],
    "tomb":     ["tomb", "sepulchre"],
    "loggia":   ["loggia"],
    "dome":     ["dome", "cupola"],
    "facade":   ["facade", "façade"],
    "door":     ["door", "gate"],
    "fountain": ["fountain"],
    "altar":    ["altar", "altarpiece", "altar-piece"],
}

DETERMINERS = ("the ", "this ", "that ", "these ", "those ", "which ", "an ", "a ")
DEICTIC = {"it", "that", "this", "these", "those", "which", "they", "them"}


def head_noun(surface: str) -> str | None:
    """Reduce a surface form to a normalised head noun, or 'any' for deictics."""
    s = (surface or "").strip().lower()
    for det in DETERMINERS:
        if s.startswith(det):
            s = s[len(det):]
            break
    s = s.strip(" .,;:'\"")
    if not s:
        return None
    if s in DEICTIC:
        return "any"
    # take the last alphabetic word as the head
    tokens = re.findall(r"[a-zàâçéèêëîïôûùüÿñæœÀ-ſ-]+", s)
    return tokens[-1] if tokens else None


def matches(coref_head: str, antecedent_surface: str) -> bool:
    if coref_head == "any":
        return True
    a = (antecedent_surface or "").lower()
    syns = HEAD_SYNONYMS.get(coref_head, [coref_head])
    if not syns:
        return True   # keys with empty list are wildcards too
    return any(syn in a for syn in syns)


def find_antecedent(coref_para_id: int, coref_surface: str,
                    paragraphs: list[dict]) -> tuple[dict, dict] | None:
    """Return (antecedent_paragraph, antecedent_mention) or None."""
    head = head_noun(coref_surface)
    if head is None:
        return None
    earlier = sorted(
        [p for p in paragraphs if p["paragraph_id"] < coref_para_id],
        key=lambda p: p["paragraph_id"],
        reverse=True,                         # most recent first
    )
    for prev in earlier:
        # Iterate prior mentions in reverse textual order so that the
        # closest antecedent wins on ties.
        for m in reversed(prev.get("mentions", [])):
            t = (m.get("type") or "").lower()
            if t not in ("explicit artwork mention", "implicit artwork mention"):
                continue
            if not m.get("entity_id"):
                continue
            if matches(head, m.get("surface_form", "")):
                return prev, m
    return None


def collect_headless(paragraphs: list[dict]) -> list[tuple[dict, dict]]:
    """Return [(paragraph, mention), …] for every coref whose entity_id
    never appears on an explicit/implicit mention in this biography."""
    artwork_eids: set[str] = set()
    for p in paragraphs:
        for m in p.get("mentions", []):
            t = (m.get("type") or "").lower()
            if t in ("explicit artwork mention", "implicit artwork mention"):
                if m.get("entity_id"):
                    artwork_eids.add(m["entity_id"])
    headless = []
    for p in paragraphs:
        for m in p.get("mentions", []):
            if (m.get("type") or "").lower() != "coreferent":
                continue
            eid = m.get("entity_id")
            if eid and eid not in artwork_eids:
                headless.append((p, m))
    return headless


def process_file(path: Path, apply: bool) -> tuple[int, int, int]:
    """Returns (n_resolved, n_unresolved, n_total)."""
    paragraphs = json.loads(path.read_text())
    headless = collect_headless(paragraphs)

    bio = path.stem.replace("_enriched", "")
    if not headless:
        print(f"[{bio:<14}] no headless corefs")
        return 0, 0, 0

    print(f"\n[{bio:<14}] {len(headless)} headless coref(s):")

    n_resolved = n_unresolved = 0
    for p, m in headless:
        ante = find_antecedent(p["paragraph_id"], m.get("surface_form", ""),
                               paragraphs)
        if ante is None:
            n_unresolved += 1
            print(f"  para {p['paragraph_id']:>4}  m {m['mention_id']}  "
                  f"surface={m.get('surface_form')!r:<30}  "
                  f"→ no antecedent in GT (Category A — leaving unchanged)")
            continue
        ante_p, ante_m = ante
        old_eid = m.get("entity_id")
        new_eid = ante_m.get("entity_id")
        new_refers = ante_m.get("mention_id")
        print(f"  para {p['paragraph_id']:>4}  m {m['mention_id']}  "
              f"surface={m.get('surface_form')!r:<30}  "
              f"→ link to para {ante_p['paragraph_id']} m {new_refers} "
              f"(surface={ante_m.get('surface_form')!r:<60})")
        print(f"    eid {old_eid} → {new_eid}, refers_to {m.get('refers_to')!r} → {new_refers!r}")
        if apply:
            m["entity_id"] = new_eid
            m["refers_to"] = new_refers
        n_resolved += 1

    if apply and n_resolved > 0:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(json.dumps(paragraphs, indent=2, ensure_ascii=False) + "\n")
        print(f"  ✔ wrote {n_resolved} fix(es) to {path}  (backup: {backup.name})")

    return n_resolved, n_unresolved, len(headless)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Write changes in place (default: dry run).")
    ap.add_argument("--bio", default=None,
                    help="Restrict to a single biography (matched against "
                         "the file stem before _enriched.json).")
    args = ap.parse_args()

    files = sorted(glob(GT_GLOB))
    if args.bio:
        files = [f for f in files if args.bio in Path(f).stem]
        if not files:
            print(f"No files match --bio {args.bio}", file=sys.stderr)
            return 1

    if not args.apply:
        print("=== DRY RUN — no files modified. Pass --apply to write. ===")

    grand_resolved = grand_unresolved = grand_total = 0
    for f in files:
        r, u, t = process_file(Path(f), apply=args.apply)
        grand_resolved += r
        grand_unresolved += u
        grand_total += t

    print(f"\nSummary: {grand_resolved} resolved, {grand_unresolved} left "
          f"(Category A) of {grand_total} headless chains across "
          f"{len(files)} biographies.")
    if not args.apply:
        print("(Re-run with --apply to write changes.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
