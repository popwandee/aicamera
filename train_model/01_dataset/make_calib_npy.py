#!/usr/bin/env python3
"""
make_calib_npy.py — Build a calibration NPY for HEF compilation (Step 04).

Usage:
    python3 make_calib_npy.py \
        --src dataset_thai/train \
        --count 1024 \
        --output ../04_compile_onnx_hef/calib.npy

Output shape: (N, 3, 75, 300)  float32  values in [0, 1]
  N   = --count (capped at available images)
  3   = RGB channels
  75  = model input height
  300 = model input width
"""

import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np

MODEL_H = 75
MODEL_W = 300


def parse_args():
    p = argparse.ArgumentParser(description="Generate calibration NPY for Hailo HEF compile")
    p.add_argument("--src", required=True, help="Directory containing .jpg calibration images")
    p.add_argument("--count", type=int, default=1024, help="Number of images to sample (default 1024)")
    p.add_argument("--output", required=True, help="Output .npy path")
    p.add_argument("--seed", type=int, default=42, help="Random seed for reproducible sampling")
    return p.parse_args()


def main():
    args = parse_args()

    src = Path(args.src)
    if not src.is_dir():
        sys.exit(f"[ERROR] --src does not exist or is not a directory: {src}")

    all_paths = sorted(src.glob("*.jpg")) + sorted(src.glob("*.png"))
    if not all_paths:
        sys.exit(f"[ERROR] No .jpg/.png files found in {src}")

    random.seed(args.seed)
    random.shuffle(all_paths)
    selected = all_paths[: args.count]

    if len(selected) < args.count:
        print(
            f"[WARN] Only {len(selected)} images found; requested {args.count}. "
            "Using all available."
        )

    print(f"[INFO] Sampling {len(selected)} images from {src}")

    imgs = []
    failed = 0
    for p in selected:
        raw = cv2.imread(str(p))
        if raw is None:
            failed += 1
            continue
        rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (MODEL_W, MODEL_H), interpolation=cv2.INTER_LINEAR)
        imgs.append(resized.astype(np.float32) / 255.0)

    if failed:
        print(f"[WARN] Skipped {failed} unreadable images")

    if not imgs:
        sys.exit("[ERROR] No images could be loaded — check --src path and file integrity")

    # Stack to (N, H, W, C) then transpose to (N, C, H, W) for Hailo DFC
    calib = np.stack(imgs).transpose(0, 3, 1, 2)  # (N, 3, 75, 300)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(out), calib)

    print(f"[OK] Saved {out}  shape={calib.shape}  dtype={calib.dtype}")
    print(f"     value range: [{calib.min():.4f}, {calib.max():.4f}]")


if __name__ == "__main__":
    main()
