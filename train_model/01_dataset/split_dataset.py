"""
split_dataset.py — Split LP crop images into train / test / calib sets.

Usage:
    python3 split_dataset.py --src lp_crops \
                             --train dataset_thai/train \
                             --test  dataset_thai/test \
                             --calib dataset_thai/calib \
                             --ratio 0.75 0.20 0.05 --seed 42

Groups by plate key ({consonants}_{digits}{province}) so that all augmented
copies of the same plate land in the same split — no data leakage.
"""

import argparse
import re
import shutil
from collections import Counter
from pathlib import Path
import random


def parse_args():
    p = argparse.ArgumentParser(description="Split LP crops into train/test/calib.")
    p.add_argument("--src",   required=True, help="Source directory of .jpg images")
    p.add_argument("--train", required=True, help="Destination train directory")
    p.add_argument("--test",  required=True, help="Destination test directory")
    p.add_argument("--calib", required=True, help="Destination calib directory")
    p.add_argument("--ratio", type=float, nargs=3, default=[0.75, 0.20, 0.05],
                   metavar=("TRAIN", "TEST", "CALIB"),
                   help="Split ratios (must sum to 1.0). Default: 0.75 0.20 0.05")
    p.add_argument("--seed",  type=int, default=42, help="Random seed")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be copied without actually copying")
    return p.parse_args()


def plate_key(path: Path) -> str:
    """Return the plate text key (stem without the trailing _XXXXXX id)."""
    stem = path.stem
    # Filename format: {consonants}_{digits}{province}_{id:06d}
    # The id is the last underscore-separated token, always 6 digits.
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 6:
        return parts[0]
    # Fallback: treat whole stem as key (no id suffix found)
    return stem


def extract_province(key: str) -> str:
    """Extract the province from a plate key like 'กข_1234เชียงใหม่'."""
    # Province is the trailing non-ASCII/non-digit run after the digits
    m = re.search(r"[^\d]+$", key)
    return m.group() if m else "unknown"


def split_keys(keys: list, ratios: list, seed: int) -> tuple:
    """Shuffle keys and split into (train, test, calib) groups."""
    rng = random.Random(seed)
    shuffled = keys[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = round(n * ratios[0])
    n_test  = round(n * ratios[1])
    train = shuffled[:n_train]
    test  = shuffled[n_train:n_train + n_test]
    calib = shuffled[n_train + n_test:]
    return train, test, calib


def copy_files(files: list, dst: Path, dry_run: bool) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in files:
        target = dst / f.name
        if not target.exists():
            if not dry_run:
                shutil.copy2(f, target)
            copied += 1
        # Skip silently if already present (idempotent re-runs)
    return copied


def main():
    args = parse_args()

    ratio_sum = sum(args.ratio)
    if abs(ratio_sum - 1.0) > 0.001:
        raise ValueError(f"Ratios must sum to 1.0, got {ratio_sum:.4f}")

    src  = Path(args.src)
    dst_train = Path(args.train)
    dst_test  = Path(args.test)
    dst_calib = Path(args.calib)

    all_files = sorted(src.glob("*.jpg"))
    if not all_files:
        print(f"[split_dataset] No .jpg files found in {src}")
        return

    # Group files by plate key
    groups: dict[str, list] = {}
    for f in all_files:
        k = plate_key(f)
        groups.setdefault(k, []).append(f)

    unique_keys = sorted(groups.keys())
    print(f"[split_dataset] Source : {src}")
    print(f"[split_dataset] Files  : {len(all_files)} images, {len(unique_keys)} unique plate keys")

    train_keys, test_keys, calib_keys = split_keys(unique_keys, args.ratio, args.seed)

    splits = [
        ("train", train_keys, dst_train),
        ("test",  test_keys,  dst_test),
        ("calib", calib_keys, dst_calib),
    ]

    for name, keys, dst in splits:
        files = [f for k in keys for f in groups[k]]
        n_copied = copy_files(files, dst, args.dry_run)

        provinces = Counter(extract_province(k) for k in keys)
        marker = " [DRY RUN]" if args.dry_run else ""
        print(
            f"[split_dataset] {name:6s}{marker}: "
            f"{len(keys):5d} plates / {len(files):6d} images → {dst}  "
            f"({len(provinces)} provinces, {n_copied} new files copied)"
        )

    print("[split_dataset] Done.")


if __name__ == "__main__":
    main()
