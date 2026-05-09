"""
Thai province mapping for dual-branch LPRNet province classifier.
All 77 provinces as they appear in synthetic plate filenames/labels.

Current synthetic dataset uses only 8 provinces (marked with *).
Expand synthetic_thai_plate.py PROVINCES list to increase coverage.
"""

PROVINCES = [
    'กระบี่',             #  0
    'กรุงเทพ',            #  1  * (กรุงเทพมหานคร — short form used in filenames)
    'กาญจนบุรี',          #  2
    'กาฬสินธุ์',          #  3
    'กำแพงเพชร',          #  4
    'ขอนแก่น',            #  5  *
    'จันทบุรี',           #  6
    'ฉะเชิงเทรา',         #  7
    'ชลบุรี',             #  8  *
    'ชัยนาท',             #  9
    'ชัยภูมิ',            # 10
    'ชุมพร',              # 11
    'เชียงราย',           # 12
    'เชียงใหม่',          # 13  *
    'ตรัง',               # 14
    'ตราด',               # 15
    'ตาก',                # 16
    'นครนายก',            # 17
    'นครปฐม',             # 18
    'นครพนม',             # 19
    'นครราชสีมา',         # 20  *
    'นครศรีธรรมราช',      # 21
    'นครสวรรค์',          # 22
    'นนทบุรี',            # 23  *
    'นราธิวาส',           # 24
    'น่าน',               # 25
    'บึงกาฬ',             # 26
    'บุรีรัมย์',          # 27
    'ปทุมธานี',           # 28
    'ประจวบคีรีขันธ์',    # 29
    'ปราจีนบุรี',         # 30
    'ปัตตานี',            # 31
    'พระนครศรีอยุธยา',    # 32
    'พะเยา',              # 33
    'พังงา',              # 34
    'พัทลุง',             # 35
    'พิจิตร',             # 36
    'พิษณุโลก',           # 37
    'เพชรบุรี',           # 38
    'เพชรบูรณ์',          # 39
    'แพร่',               # 40
    'ภูเก็ต',             # 41  *
    'มหาสารคาม',          # 42
    'มุกดาหาร',           # 43
    'แม่ฮ่องสอน',         # 44
    'ยโสธร',              # 45
    'ยะลา',               # 46
    'ร้อยเอ็ด',           # 47
    'ระนอง',              # 48
    'ระยอง',              # 49
    'ราชบุรี',            # 50
    'ลพบุรี',             # 51
    'ลำปาง',              # 52
    'ลำพูน',              # 53
    'เลย',                # 54
    'ศรีสะเกษ',           # 55
    'สกลนคร',             # 56
    'สงขลา',              # 57
    'สตูล',               # 58
    'สมุทรปราการ',        # 59  *
    'สมุทรสงคราม',        # 60
    'สมุทรสาคร',          # 61
    'สระแก้ว',            # 62
    'สระบุรี',            # 63
    'สิงห์บุรี',          # 64
    'สุโขทัย',            # 65
    'สุพรรณบุรี',         # 66
    'สุราษฎร์ธานี',       # 67
    'สุรินทร์',           # 68
    'หนองคาย',            # 69
    'หนองบัวลำภู',        # 70
    'อ่างทอง',            # 71
    'อำนาจเจริญ',         # 72
    'อุดรธานี',           # 73
    'อุตรดิตถ์',          # 74
    'อุทัยธานี',          # 75
    'อุบลราชธานี',        # 76
]

PROVINCE_TO_IDX = {p: i for i, p in enumerate(PROVINCES)}
N_PROVINCES     = len(PROVINCES)   # 77
UNKNOWN_PROV    = -1               # used as ignore_index in CrossEntropyLoss


def extract_province(plate_text: str) -> str:
    """
    Extract province substring from a full plate text.
    Plate format: 1-2 consonants + 3-4 digits + province_name
    e.g. 'กง9964นครนายก' → 'นครนายก'
    Returns '' if no province found (short plates without province).
    """
    last_digit = -1
    for i, ch in enumerate(plate_text):
        if ch.isdigit():
            last_digit = i
    if last_digit < 0:
        return ''
    return plate_text[last_digit + 1:]


def province_label(plate_text: str) -> int:
    """
    Return province index (0-76) for a plate text, or UNKNOWN_PROV (-1) if not found.
    Used as label for CrossEntropyLoss(ignore_index=UNKNOWN_PROV).
    """
    prov = extract_province(plate_text)
    return PROVINCE_TO_IDX.get(prov, UNKNOWN_PROV)


if __name__ == '__main__':
    print(f'N_PROVINCES : {N_PROVINCES}')
    tests = ['กง9964นครนายก', 'กข1234ชลบุรี', 'กก5678กรุงเทพ', 'ก123']
    for t in tests:
        prov = extract_province(t)
        idx  = province_label(t)
        print(f'  {t:<20} → province="{prov}"  idx={idx}')
