"""
OCR all facsimile pages and save word-level bounding boxes as JSON.

Output: data/ocr/<vol>/<page>.json with structure:
{
  "width": <image_width>,
  "height": <image_height>,
  "words": [
    {"t": "word", "x": left, "y": top, "w": width, "h": height},
    ...
  ]
}

Usage:
    python scripts/ocr_facsimile.py
"""

import json
import sys
from pathlib import Path

import pytesseract
from PIL import Image

FAC_DIR = Path(__file__).resolve().parent.parent / "data" / "facsimile_pages"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "ocr"


def ocr_page(img_path: Path) -> dict:
    img = Image.open(img_path)
    w_img, h_img = img.size
    data = pytesseract.image_to_data(img, lang="ita+eng", output_type=pytesseract.Output.DICT)

    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if not text or conf < 30:
            continue
        words.append({
            "t": text,
            "x": data["left"][i],
            "y": data["top"][i],
            "w": data["width"][i],
            "h": data["height"][i],
        })

    return {"width": w_img, "height": h_img, "words": words}


def main():
    if not FAC_DIR.exists():
        print(f"Facsimile directory not found: {FAC_DIR}")
        sys.exit(1)

    total = 0
    for vol_dir in sorted(FAC_DIR.iterdir()):
        if not vol_dir.is_dir():
            continue
        vol = vol_dir.name
        out_vol = OUT_DIR / vol
        out_vol.mkdir(parents=True, exist_ok=True)

        pages = sorted(vol_dir.glob("*.png"))
        for page_path in pages:
            page_num = page_path.stem
            out_path = out_vol / f"{page_num}.json"

            # Skip if already processed
            if out_path.exists():
                print(f"  skip vol {vol} p.{page_num} (exists)")
                continue

            print(f"  OCR vol {vol} p.{page_num} ...", end="", flush=True)
            result = ocr_page(page_path)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f)
            print(f" {len(result['words'])} words")
            total += 1

    print(f"\nDone — processed {total} pages.")


if __name__ == "__main__":
    main()
