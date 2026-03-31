"""
extract_facsimile_pages.py

Uses the embedded PDF page labels (present in Internet Archive scans) to
map printed page numbers to PDF page indices.  Only the pages that overlap
with annotation ground truth are converted to PNG.

Usage:
    python scripts/extract_facsimile_pages.py

Dependencies:
    pip install pymupdf

Output:
    data/facsimile_pages/{vol}/{page}.png   — one PNG per needed printed page
    data/facsimile_pages/{vol}/mapping.json — label→pdf-index mapping (needed pages only)
"""

import json
import sys
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    sys.exit("pymupdf not found. Run: pip install pymupdf")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
PDF_DIR = ROOT / "data" / "lives_pdfs"
GT_DIR  = ROOT / "obliquer" / "data" / "viewsari" / "ground_truth"
OUT_DIR = ROOT / "data" / "facsimile_pages"

# Image resolution (DPI). 150 is a good balance of quality vs file size.
DPI = 150
MATRIX = fitz.Matrix(DPI / 72, DPI / 72)


# ── Step 1: collect pages needed per volume from ground truth ─────────────────
def collect_needed_pages() -> dict[str, set[int]]:
    needed: dict[str, set[int]] = {}
    for jf in sorted(GT_DIR.rglob("*.json")):
        vol = jf.parent.name
        if not vol.isdigit():
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Warning: could not read {jf}: {e}")
            continue
        for para in data:
            page_str = str(para.get("page", ""))
            for part in page_str.split("-"):
                part = part.strip()
                if part.isdigit():
                    needed.setdefault(vol, set()).add(int(part))
    return needed


# ── Step 2: build label→pdf-index mapping using PDF page labels ──────────────
def build_label_mapping(doc: fitz.Document) -> dict[int, int]:
    """
    Read embedded page labels from the PDF.  Internet Archive scans label
    each printed text page with its printed page number (e.g. "196").
    Illustration plates and front matter have empty or non-numeric labels.

    Returns {printed_page_number: 0-based pdf page index}.
    """
    mapping: dict[int, int] = {}
    for pdf_idx in range(doc.page_count):
        label = doc[pdf_idx].get_label()
        if label and label.isdigit():
            page_num = int(label)
            if page_num not in mapping:  # first occurrence wins
                mapping[page_num] = pdf_idx
    return mapping


# ── Step 3: extract only the needed pages as PNGs ────────────────────────────
def extract_pages(doc: fitz.Document, mapping: dict[int, int],
                  needed: set[int], out_dir: Path) -> tuple[int, int]:
    """Returns (extracted_count, skipped_count)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted = 0
    skipped = 0
    for printed_page in sorted(needed):
        pdf_idx = mapping.get(printed_page)
        if pdf_idx is None:
            print(f"    ✗ p.{printed_page}: no label in PDF, skipping")
            skipped += 1
            continue
        out_path = out_dir / f"{printed_page}.png"
        if out_path.exists():
            extracted += 1
            continue
        try:
            pix = doc[pdf_idx].get_pixmap(matrix=MATRIX, colorspace=fitz.csRGB)
            pix.save(str(out_path))
            extracted += 1
        except Exception as e:
            print(f"    ✗ p.{printed_page} (PDF idx {pdf_idx}): {e}")
            skipped += 1
    return extracted, skipped


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    needed_by_vol = collect_needed_pages()
    print(f"Volumes with annotations: {sorted(needed_by_vol)}\n")

    for vol, needed_pages in sorted(needed_by_vol.items()):
        pdf_path = PDF_DIR / f"livesofmostemine{int(vol):02d}vasauoft.pdf"
        if not pdf_path.exists():
            print(f"Vol {vol}: PDF not found at {pdf_path}, skipping")
            continue

        print(f"Vol {vol}: {len(needed_pages)} pages needed  ({pdf_path.name})")
        doc = fitz.open(str(pdf_path))

        # Build mapping from page labels — only reads labels, no OCR parsing
        mapping = build_label_mapping(doc)
        print(f"  {len(mapping)} labeled pages in PDF")

        # How many of our needed pages have labels?
        found = needed_pages & set(mapping.keys())
        missing = needed_pages - found
        if missing:
            print(f"  ⚠ {len(missing)} needed pages have no label: {sorted(missing)}")

        # Save mapping (only the needed pages)
        out_vol_dir = OUT_DIR / vol
        out_vol_dir.mkdir(parents=True, exist_ok=True)
        needed_mapping = {str(p): mapping[p] for p in sorted(found)}
        (out_vol_dir / "mapping.json").write_text(
            json.dumps(needed_mapping, indent=2), encoding="utf-8"
        )

        # Verify a sample
        sample = sorted(found)[len(found) // 2] if found else None
        if sample:
            text = doc[mapping[sample]].get_text()[:80].replace('\n', ' ')
            print(f"  Sample: p.{sample} → PDF[{mapping[sample]}]: {text!r}")

        n, s = extract_pages(doc, mapping, needed_pages, out_vol_dir)
        print(f"  Extracted {n}/{len(needed_pages)} pages → {out_vol_dir}\n")
        doc.close()

    print("Done.")


if __name__ == "__main__":
    main()
