"""
Thai License Plate character set for LPRNet.
Plate text from filename: parts[0]+parts[1] after split on '_'
e.g. 'ก_100ชลบุรี_062553' -> 'ก100ชลบุรี'
blank label is always the last index.
"""

CHARS = [
    # Digits index 0-9
    '0','1','2','3','4','5','6','7','8','9',
    # Thai consonants sorted by Unicode U+0E01-U+0E2E (index 10-47)
    'ก','ข','ค','ฆ','ง','จ','ฉ','ช',
    'ซ','ญ','ฎ','ฐ','ณ','ด','ต','ถ',
    'ท','ธ','น','บ','ป','ผ','ฝ','พ',
    'ฟ','ภ','ม','ย','ร','ล','ว','ศ',
    'ษ','ส','ห','ฬ','อ','ฮ',
    # Thai vowels/diacritics/tone marks U+0E30-U+0E4C (index 48-64)
    'ะ','ั','า','ำ','ิ','ี','ึ',
    'ุ','ู','เ','แ','โ','ใ',
    '็','่','้','์',
]

CHAR_TO_IDX = {c: i for i, c in enumerate(CHARS)}
BLANK_LABEL  = len(CHARS)      # 65
NUM_CLASSES  = len(CHARS) + 1  # 66
MAX_SEQ_LEN  = 38              # must be >= max plate text length (21)

if __name__ == '__main__':
    print(f'Total chars : {len(CHARS)}')
    print(f'BLANK_LABEL : {BLANK_LABEL}')
    print(f'NUM_CLASSES : {NUM_CLASSES}')
    for i, c in enumerate(CHARS):
        print(f'  [{i:2d}] {c}  U+{ord(c):04X}')
