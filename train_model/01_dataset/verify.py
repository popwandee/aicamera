from pathlib import Path
from collections import Counter
import re

src = Path('dataset_thai/train')
provinces = []
for f in src.glob('*.jpg'):
    parts = f.stem.split('_')
    if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
        plate_text = ''.join(parts[:-1])
        # extract province: everything after last digit
        m = re.search(r'[^\d]+$', plate_text)
        if m:
            provinces.append(m.group())

c = Counter(provinces)
print(f"Total images: {len(list(src.glob('*.jpg')))}")
print(f"Provinces covered: {len(c)}/77")
print(f"Min per province: {min(c.values())}")
print(f"Max per province: {max(c.values())}")