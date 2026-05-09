#!/usr/bin/env python3
"""
crop_plate_for_test.py — Interactive plate cropper for DualBranchLPRNet testing
Run on Mac:  python3 crop_plate_for_test.py <image.jpg>
Click and drag on the plate region, press ENTER to save crop, ESC to quit.
Saves crops to: test_plate_crops/
"""
import sys, cv2, os
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python3 crop_plate_for_test.py <image_path>")
    sys.exit(1)

img_path = sys.argv[1]
img = cv2.imread(img_path)
if img is None:
    print(f"Cannot read: {img_path}"); sys.exit(1)

# Scale for display if image is too large
h, w = img.shape[:2]
scale = min(1.0, 1200 / w, 800 / h)
disp = cv2.resize(img, (int(w*scale), int(h*scale)))

out_dir = Path("test_plate_crops"); out_dir.mkdir(exist_ok=True)
roi = cv2.selectROI("Select plate region (ENTER=save, ESC=quit)", disp, showCrosshair=True)
cv2.destroyAllWindows()

if roi[2] > 0 and roi[3] > 0:
    x, y, rw, rh = [int(v/scale) for v in roi]
    crop = img[y:y+rh, x:x+rw]
    out = out_dir / f"plate_crop_{Path(img_path).stem}.jpg"
    cv2.imwrite(str(out), crop)
    print(f"Saved crop {crop.shape} → {out}")
    print(f"\nTest with:")
    print(f"  python3 test_dual_branch_lpr.py --image {out}")
else:
    print("No region selected.")
