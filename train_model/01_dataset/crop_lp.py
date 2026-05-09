#!/usr/bin/env python3
"""
crop_lp.py — Interactive LP crop + label tool for calibration data
=================================================================
Usage:
  python3 crop_lp.py ~/Downloads/train ~/Downloads/lp_crops

Controls (per image):
  Drag mouse  → select LP region
  SPACE/ENTER → confirm selection
  ESC         → skip this image (move to next)
  C           → re-crop same image (multiple LPs per image)
  Q           → quit and save progress

Output filename: {consonants}_{digits_province}_{id:06d}.jpg
  Input:  "กข 1234ชลบุรี"  →  กข_1234ชลบุรี_000001.jpg
  Input:  "กข1234 ชลบุรี"  →  same result (splits on first space)
  Input:  (empty)          →  skip crop

Resumes: counts existing files in DST so rerun won't overwrite.
"""

import sys
import cv2
import os
from pathlib import Path

# ── CLI args ──────────────────────────────────────────────────────────────────
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads/train"
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / "Downloads/lp_crops"
DST.mkdir(parents=True, exist_ok=True)

# ── Collect images ────────────────────────────────────────────────────────────
EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
images = sorted(p for p in SRC.iterdir() if p.suffix.lower() in EXTS)
print(f"Found {len(images)} images in {SRC}")

# Resume counter from existing crops
counter = len(list(DST.glob("*.jpg")))
if counter:
    print(f"Resuming from ID {counter + 1:06d}  ({counter} crops already saved)")

WIN = "LP Crop Tool"

def load_display(path, max_w=1400, max_h=900):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        # Try with IMREAD_UNCHANGED for webp
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None, 1.0
    if img.ndim == 4:          # BGRA → BGR
        img = img[:, :, :3]
    h, w = img.shape[:2]
    scale = min(1.0, max_w / w, max_h / h)
    disp = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1.0 else img.copy()
    return img, disp, scale

# ── Main loop ─────────────────────────────────────────────────────────────────
total_saved = 0
i = 0
while i < len(images):
    path = images[i]
    result = load_display(path)
    if result[0] is None:
        print(f"  [skip] cannot read {path.name}")
        i += 1
        continue

    orig, disp, scale = result
    h_o, w_o = orig.shape[:2]
    print(f"\n[{i+1}/{len(images)}] {path.name}  ({w_o}×{h_o})")

    keep_image = True
    while keep_image:
        # Draw instruction overlay
        overlay = disp.copy()
        cv2.putText(overlay, "Drag=select  SPACE=confirm  ESC=next  C=re-crop  Q=quit",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(WIN, overlay)

        roi = cv2.selectROI(WIN, overlay, fromCenter=False, showCrosshair=True)
        cv2.destroyAllWindows()

        rx, ry, rw, rh = roi
        if rw < 10 or rh < 5:      # ESC or trivial selection → next image
            keep_image = False
            break

        # Scale ROI back to original resolution
        x  = int(rx / scale);  y  = int(ry / scale)
        w  = int(rw / scale);  h  = int(rh / scale)
        crop = orig[y:y+h, x:x+w]

        # Preview crop
        prev = cv2.resize(crop, (300, 75))
        cv2.imshow("Crop preview (300×75)", prev)
        cv2.waitKey(100)

        # Label input in terminal
        try:
            text = input("  Plate text [consonants digits+province] e.g. 'กข 1234ชลบุรี'  > ").strip()
        except EOFError:
            text = ""
        cv2.destroyAllWindows()

        if not text:
            print("  (skipped — no label entered)")
        else:
            parts = text.split(None, 1)           # split on first whitespace only
            consonants   = parts[0]
            digits_prov  = parts[1] if len(parts) > 1 else parts[0]

            counter += 1
            total_saved += 1
            fname = f"{consonants}_{digits_prov}_{counter:06d}.jpg"
            out   = DST / fname
            cv2.imwrite(str(out), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"  ✅  {fname}  ({w}×{h} → saved)")

        # Ask: crop another LP from same image?
        again = input("  Another LP in this image? [y/N] > ").strip().lower()
        if again != 'y':
            keep_image = False

    i += 1

cv2.destroyAllWindows()
print(f"\n{'='*50}")
print(f"Done. {total_saved} new crops saved to {DST}")
print(f"Total in folder: {len(list(DST.glob('*.jpg')))} files")
