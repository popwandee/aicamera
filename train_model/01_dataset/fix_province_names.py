#!/usr/bin/env python3
import signal, sys
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

"""
fix_province_names.py — Rename dataset files that use non-canonical province strings.

Canonical source: province_map.py (always trust that file).

Fixes applied:
  ' กรุงเทพมหานคร' →  'กรุงเทพมหานคร'   (leading space)
  'กรุงเทพ'        →  'กรุงเทพมหานคร'   (short form → full form)
                       uses negative lookahead so files already containing
                       'กรุงเทพมหานคร' are NOT double-expanded
  'สกกลนคร'        →  'สกลนคร'           (typo)

Usage:
    python3 fix_province_names.py --src dataset_thai/train [--dry-run]
    python3 fix_province_names.py --src dataset_thai/test  [--dry-run]
"""

import argparse
import re
from pathlib import Path


def fix_stem(stem: str) -> str:
    # 1. strip leading space before full form
    stem = stem.replace(' กรุงเทพมหานคร', 'กรุงเทพมหานคร')
    # 2. short form → full form, only when NOT already followed by มหานคร
    stem = re.sub(r'กรุงเทพ(?!มหานคร)', 'กรุงเทพมหานคร', stem)
    # 3. typo fix
    stem = stem.replace('สกกลนคร', 'สกลนคร')
    return stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='Dataset directory (train or test)')
    ap.add_argument('--dry-run', action='store_true', help='Print renames without executing')
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        raise SystemExit(f'[ERROR] Not a directory: {src}')

    renamed = 0
    skipped = 0
    for p in sorted(src.glob('*.jpg')):
        new_stem = fix_stem(p.stem)
        if new_stem == p.stem:
            continue
        new_path = p.with_name(new_stem + p.suffix)
        if new_path.exists():
            print(f'[SKIP] target exists: {new_path.name}')
            skipped += 1
            continue
        if args.dry_run:
            print(f'[DRY]  {p.name}  →  {new_path.name}')
        else:
            p.rename(new_path)
            print(f'[OK]   {p.name}  →  {new_path.name}')
        renamed += 1

    label = 'Would rename' if args.dry_run else 'Renamed'
    print(f'\n{label}: {renamed}  |  Skipped (target exists): {skipped}')


if __name__ == '__main__':
    main()
