#!/usr/bin/env python3
"""
synthetic_thai_plate.py — Thai License Plate Synthetic Generator v4
====================================================================
สร้างภาพป้ายทะเบียนไทย สำหรับ train DualBranchLPRNet
ใช้ฟอนต์ Sarun's ThangLuang (จำลองฟอนต์ป้ายทะเบียนจริงของกรมขนส่ง)

Output size : 300×100 px  (training script resize ไปที่ 75×300 เอง)
Model input : (B, 3, 75, 300) — GUARDRAIL: INPUT_H=75, INPUT_W=300

Layout (จากการศึกษาป้ายจริง):
  ┌────────────────────────────────────────────────┐  ← border 3 px
  │                                                │
  │      1กย              889                      │  ← main text (ใหญ่ ~68 px zone)
  │                                                │
  │           กรุงเทพมหานคร                        │  ← province (~20 px zone)
  │                                                │
  └────────────────────────────────────────────────┘

Font priority (auto-detect):
  1. Sarun's ThangLuang  — ฟอนต์ป้ายจริง DLT (recommended)
  2. Sarabun-Bold        — fallback Thai
  3. Ayuthaya            — macOS last-resort

Plate formats (n_prefix, n_consonants, n_digits):
  (1,2,3)  1กย 889   — 30%
  (1,2,4)  1กก 5367  — 25%
  (0,2,4)  กข 1234   — 20%
  (0,2,3)  กข 123    — 10%
  (0,1,4)  ก 1234    —  8%
  (1,1,4)  1ก 5678   —  4%
  (2,0,4)  15 7410   —  3%

Plate types:
  white  (65%): พื้นขาว ตัวดำ   — รถส่วนบุคคล
  yellow (20%): พื้นเหลือง ตัวดำ — รถบรรทุก/พาณิชย์
  green  (10%): พื้นเขียว ตัวขาว — ราชการ
  red     (5%): พื้นแดง ตัวขาว   — ป้ายแดง

Province: ใช้ชื่อเต็ม ตรงกับ train_model/02_train_pth/province_map.py PROVINCES
  เช่น 'กรุงเทพมหานคร', 'เชียงใหม่', 'นครราชสีมา'

Filename format (ตาม lp_crops จริง):
  {prefix+consonants}_{digits+province}_{id:06d}.jpg
  e.g.  1กย_889กรุงเทพมหานคร_000001.jpg
        กข_1234เชียงใหม่_000002.jpg

Usage:
  python3 synthetic_thai_plate.py --count 5000
  python3 synthetic_thai_plate.py --count 5000 --augment-factor 3
  python3 synthetic_thai_plate.py --font "/Users/sqh/Library/Fonts/Sarun's ThangLuang.ttf"
  python3 synthetic_thai_plate.py --count 2000 --start-id 15001
  python3 synthetic_thai_plate.py --count 5000 --province-balance

Requirements:
  pip install Pillow numpy tqdm
"""

from __future__ import annotations

import argparse
import io
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ── Output dimensions ──────────────────────────────────────────────────────────
OUT_W, OUT_H = 300, 100

# ── Character sets ─────────────────────────────────────────────────────────────
DIGITS     = list('0123456789')
CONSONANTS = list('กขคฆงจฉชซญฎฐณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ')  # 38 ตัว

# ── Province list: ชื่อเต็ม ตรงกับ 02_train_pth/province_map.py PROVINCES ─────
PROVINCES = [
    'กระบี่',             'กรุงเทพมหานคร',    'กาญจนบุรี',       'กาฬสินธุ์',
    'กำแพงเพชร',          'ขอนแก่น',          'จันทบุรี',        'ฉะเชิงเทรา',
    'ชลบุรี',             'ชัยนาท',           'ชัยภูมิ',         'ชุมพร',
    'เชียงราย',           'เชียงใหม่',         'ตรัง',            'ตราด',
    'ตาก',                'นครนายก',          'นครปฐม',          'นครพนม',
    'นครราชสีมา',         'นครศรีธรรมราช',    'นครสวรรค์',       'นนทบุรี',
    'นราธิวาส',           'น่าน',             'บึงกาฬ',          'บุรีรัมย์',
    'ปทุมธานี',           'ประจวบคีรีขันธ์',  'ปราจีนบุรี',      'ปัตตานี',
    'พระนครศรีอยุธยา',    'พะเยา',            'พังงา',           'พัทลุง',
    'พิจิตร',             'พิษณุโลก',         'เพชรบุรี',        'เพชรบูรณ์',
    'แพร่',               'ภูเก็ต',           'มหาสารคาม',       'มุกดาหาร',
    'แม่ฮ่องสอน',         'ยโสธร',            'ยะลา',            'ร้อยเอ็ด',
    'ระนอง',              'ระยอง',            'ราชบุรี',         'ลพบุรี',
    'ลำปาง',              'ลำพูน',            'เลย',             'ศรีสะเกษ',
    'สกลนคร',             'สงขลา',            'สตูล',            'สมุทรปราการ',
    'สมุทรสงคราม',        'สมุทรสาคร',        'สระแก้ว',         'สระบุรี',
    'สิงห์บุรี',          'สุโขทัย',          'สุพรรณบุรี',      'สุราษฎร์ธานี',
    'สุรินทร์',           'หนองคาย',          'หนองบัวลำภู',     'อ่างทอง',
    'อำนาจเจริญ',         'อุดรธานี',         'อุตรดิตถ์',       'อุทัยธานี',
    'อุบลราชธานี',
]
assert len(PROVINCES) == 77, f'จำนวนจังหวัดต้องเป็น 77 ได้ {len(PROVINCES)}'

# ── Plate styles: (bg_rgb, text_rgb, border_rgb) ───────────────────────────────
PLATE_STYLES = {
    'white':  ((255, 255, 255), (10,  10,  10),  (10,  10,  10)),
    'yellow': ((255, 204,   0), (10,  10,  10),  (10,  10,  10)),
    'green':  ((0,   105,  55), (245, 245, 245), (245, 245, 245)),
    'red':    ((185,  25,  20), (245, 245, 245), (245, 245, 245)),
}
PLATE_TYPE_WEIGHTS = [0.65, 0.20, 0.10, 0.05]

# ── Plate formats: (n_prefix_digits, n_consonants, n_digits) ─────────────────
PLATE_FORMATS = [
    (1, 2, 3),  # 1กย 889   — 30%
    (1, 2, 3),
    (1, 2, 3),
    (1, 2, 4),  # 1กก 5367  — 25%
    (1, 2, 4),
    (1, 2, 4),
    (0, 2, 4),  # กข 1234   — 20%
    (0, 2, 4),
    (0, 2, 4),
    (0, 2, 3),  # กข 123    — 10%
    (0, 2, 3),
    (0, 1, 4),  # ก 1234    —  8%
    (0, 1, 4),
    (1, 1, 4),  # 1ก 5678   —  4%
    (2, 0, 4),  # 15 7410   —  3%
]

# ── Font search order ──────────────────────────────────────────────────────────
FONT_SEARCH = [
    "/Users/sqh/Library/Fonts/Sarun's ThangLuang.ttf",    # installed
    "/Users/sqh/Downloads/Sarun's ThangLuang.ttf",         # downloaded
    "/Library/Fonts/Sarun's ThangLuang.ttf",
    '/usr/local/share/fonts/ThangLuang.ttf',
    '/usr/share/fonts/truetype/thangluang/ThangLuang.ttf',
    '/Users/sqh/Library/Fonts/Sarabun-Bold.ttf',           # fallback
    '/usr/share/fonts/truetype/tlwg/Sarabun-Bold.ttf',
    '/System/Library/Fonts/Supplemental/Ayuthaya.ttf',
    '/Library/Fonts/Ayuthaya.ttf',
]

# ── Layout constants (px) สำหรับ 300×100 ─────────────────────────────────────
# ตัวอักษรใหญ่สุดเหมือนป้ายจริง — MAIN_H ครองพื้นที่หลัก
BORDER   = 3    # ขอบรอบป้าย
TOP_PAD  = 4    # ช่องว่างบน
MAIN_H   = 68   # zone ตัวหลัก (ใหญ่ขึ้นเพื่อให้ตัวอักษรใกล้เคียงป้ายจริง)
DIV_H    = 2    # เส้นแบ่งบางๆ แทนคลื่น (ไม่มีคลื่น)
PROV_H   = 18   # zone ชื่อจังหวัด
BOT_PAD  = 2
# ตรวจสอบ: 3 + 4 + 68 + 2 + 18 + 2 + 3 = 100 ✓

SIDE_PAD = 5    # margin ซ้าย-ขวา

# สัดส่วน zone (จากป้ายจริง): prefix+cons | gap | digits
LEFT_RATIO  = 0.40   # ~113 px
GAP_RATIO   = 0.18   # ~51 px
RIGHT_RATIO = 0.42   # ~119 px


# ── Font utilities ─────────────────────────────────────────────────────────────

def find_font(override: Optional[str] = None) -> Optional[str]:
    if override:
        if Path(override).exists():
            return override
        print(f'WARNING: ไม่พบ font ที่ระบุ: {override}')
    for p in FONT_SEARCH:
        if Path(p).exists():
            return p
    return None


def _fit_font(font_path: str, text: str, max_w: int, max_h: int,
              size_start: int = 72) -> ImageFont.FreeTypeFont:
    """หา font size ใหญ่ที่สุดที่พอดีกับ box"""
    dummy = Image.new('RGB', (1, 1))
    d     = ImageDraw.Draw(dummy)
    size  = size_start
    while size > 8:
        font = ImageFont.truetype(font_path, size)
        bb   = d.textbbox((0, 0), text, font=font)
        if (bb[2] - bb[0]) <= max_w and (bb[3] - bb[1]) <= max_h:
            return font
        size -= 1
    return ImageFont.truetype(font_path, 8)


# ── Main plate renderer ────────────────────────────────────────────────────────

def draw_plate(prefix: str, consonants: str, digits: str,
               province: str, plate_type: str,
               font_path: str) -> Image.Image:
    """
    วาดป้ายทะเบียนไทย 300×100 px — ThangLuang font, ไม่มีเส้นคลื่น, พื้นเรียบ

    prefix     : ตัวเลขนำหน้า ('', '1', '2', '15')
    consonants : พยัญชนะ ('กย', 'กข', 'ก', '')
    digits     : ตัวเลขหลัง ('889', '1234')
    province   : ชื่อเต็ม เช่น 'กรุงเทพมหานคร', 'เชียงใหม่'
    plate_type : 'white' | 'yellow' | 'green' | 'red'
    """
    bg_rgb, text_rgb, border_rgb = PLATE_STYLES[plate_type]

    img  = Image.new('RGB', (OUT_W, OUT_H), color=bg_rgb)
    draw = ImageDraw.Draw(img)

    # ── ขอบป้าย ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, OUT_W - 1, OUT_H - 1], outline=border_rgb, width=BORDER)

    # ── inner dimensions ───────────────────────────────────────────────────────
    x_left_edge = BORDER + SIDE_PAD
    inner_w     = OUT_W - 2 * (BORDER + SIDE_PAD)   # ~284 px
    y_main_top  = BORDER + TOP_PAD                   # y = 7

    left_w  = int(inner_w * LEFT_RATIO)
    gap_w   = int(inner_w * GAP_RATIO)
    right_w = inner_w - left_w - gap_w

    x_left  = x_left_edge
    x_right = x_left_edge + left_w + gap_w

    left_text  = f'{prefix}{consonants}'   # e.g. '1กย', 'กข', '15', 'ก'
    right_text = digits                    # e.g. '889', '1234'

    # ── หา font size เดียวกันสำหรับทั้งสองฝั่ง (ใหญ่ที่สุดที่พอดี) ───────────
    dummy = Image.new('RGB', (1, 1))
    dd    = ImageDraw.Draw(dummy)
    size  = 78   # เริ่มสูงมาก (ThangLuang มี metrics ต่างจาก Sarabun)
    while size > 10:
        font   = ImageFont.truetype(font_path, size)
        bb_l   = dd.textbbox((0, 0), left_text,  font=font)
        bb_r   = dd.textbbox((0, 0), right_text, font=font)
        wl, hl = bb_l[2] - bb_l[0], bb_l[3] - bb_l[1]
        wr, hr = bb_r[2] - bb_r[0], bb_r[3] - bb_r[1]
        if wl <= left_w and wr <= right_w and max(hl, hr) <= MAIN_H - 2:
            break
        size -= 1
    font_main = ImageFont.truetype(font_path, size)

    # ── วาด left text — ตัวอักษรหมวด (centered ใน left zone) ────────────────
    bb = dd.textbbox((0, 0), left_text, font=font_main)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]
    lx = x_left + (left_w - lw) // 2
    ly = y_main_top + (MAIN_H - lh) // 2 - bb[1]
    draw.text((lx, ly), left_text, fill=text_rgb, font=font_main)

    # ── วาด right text — ตัวเลข (centered ใน right zone) ────────────────────
    bb = dd.textbbox((0, 0), right_text, font=font_main)
    rw, rh = bb[2] - bb[0], bb[3] - bb[1]
    rx = x_right + (right_w - rw) // 2
    ry = y_main_top + (MAIN_H - rh) // 2 - bb[1]
    draw.text((rx, ry), right_text, fill=text_rgb, font=font_main)

    # ── เส้นแบ่งบางๆ (ไม่ใช่คลื่น) ───────────────────────────────────────────
    y_div = BORDER + TOP_PAD + MAIN_H + DIV_H // 2
    draw.line([(x_left_edge, y_div), (OUT_W - (BORDER + SIDE_PAD), y_div)],
              fill=border_rgb, width=1)

    # ── ชื่อจังหวัด (ใหญ่ที่สุดที่ใส่ใน PROV_H ได้) ─────────────────────────
    y_prov_top = BORDER + TOP_PAD + MAIN_H + DIV_H
    prov_size_hint = max(8, int(size * 0.42))
    font_prov = _fit_font(font_path, province,
                          max_w=inner_w - 8, max_h=PROV_H - 2,
                          size_start=prov_size_hint)

    bb = dd.textbbox((0, 0), province, font=font_prov)
    pw, ph = bb[2] - bb[0], bb[3] - bb[1]
    px = (OUT_W - pw) // 2
    py = y_prov_top + (PROV_H - ph) // 2 - bb[1]
    draw.text((px, py), province, fill=text_rgb, font=font_prov)

    return img


# ── Perspective warp ───────────────────────────────────────────────────────────

def _perspective_coeffs(src_pts, dst_pts):
    matrix = []
    for (x1, y1), (x2, y2) in zip(src_pts, dst_pts):
        matrix += [
            [x1, y1, 1, 0, 0, 0, -x2 * x1, -x2 * y1],
            [0, 0, 0, x1, y1, 1, -y2 * x1, -y2 * y1],
        ]
    A = np.array(matrix, dtype=np.float64)
    b = np.array([c for pt in dst_pts for c in pt], dtype=np.float64)
    try:
        return np.linalg.solve(A, b).tolist()
    except np.linalg.LinAlgError:
        return None


def perspective_warp(img: Image.Image, skew: float = 0.03) -> Image.Image:
    w, h   = img.size
    dx     = int(w * skew * random.uniform(-1.0, 1.0))
    dy     = int(h * skew * random.uniform(-1.0, 1.0))
    src    = [(0, 0), (w, 0), (w, h), (0, h)]
    dst    = [
        (max(0,  dx // 2),     max(0,  dy // 2)),
        (min(w, w - dx // 2),  max(0, -dy // 2)),
        (min(w, w + dx // 3),  min(h,  h - dy // 3)),
        (max(0, -dx // 3),     min(h,  h + dy // 3)),
    ]
    coeffs = _perspective_coeffs(dst, src)
    if coeffs is None:
        return img
    return img.transform(
        (w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC,
    )


# ── Augmentation ───────────────────────────────────────────────────────────────

def augment(img: Image.Image, night_mode: bool = False) -> Image.Image:
    if random.random() < 0.70:
        lo = 0.35 if night_mode else 0.65
        hi = 0.75 if night_mode else 1.40
        img = ImageEnhance.Brightness(img).enhance(random.uniform(lo, hi))

    if random.random() < 0.55:
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.60, 1.55))

    if random.random() < 0.35:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 1.2)))

    if random.random() < 0.25:
        img = perspective_warp(img, skew=random.uniform(0.01, 0.04))

    if random.random() < 0.40:
        arr   = np.array(img, dtype=np.float32)
        sigma = random.uniform(3.0, 18.0)
        noise = np.random.normal(0.0, sigma, arr.shape)
        img   = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    if night_mode:
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.10, 0.40))
        if random.random() < 0.35:
            arr     = np.array(img, dtype=np.float32)
            sx      = random.randint(30, OUT_W - 30)
            sw      = random.randint(20, 50)
            x0, x1 = max(0, sx - sw // 2), min(OUT_W, sx + sw // 2)
            arr[:, x0:x1] = np.clip(arr[:, x0:x1] + random.uniform(60.0, 160.0), 0, 255)
            img = Image.fromarray(arr.astype(np.uint8))

    if random.random() < 0.40:
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=random.randint(40, 90))
        buf.seek(0)
        img = Image.open(buf).copy()

    if random.random() < 0.25:
        img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.4, 2.0))

    return img


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='สร้างป้ายทะเบียนไทย Synthetic — ThangLuang font v4',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument('--output-dir',       default='./synthetic_new')
    p.add_argument('--count',            type=int,   default=5000)
    p.add_argument('--augment-factor',   type=int,   default=3,
                   help='สำเนา augmented ต่อป้าย')
    p.add_argument('--night-ratio',      type=float, default=0.15)
    p.add_argument('--font',             default=None,
                   help="Path ไปยัง ThangLuang TTF (auto-detect ถ้าไม่ระบุ)")
    p.add_argument('--seed',             type=int,   default=42)
    p.add_argument('--start-id',         type=int,   default=1)
    p.add_argument('--province-balance', action='store_true',
                   help='บังคับให้ครบทุก 77 จังหวัด เท่าๆ กัน')
    return p.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    font_path = find_font(args.font)
    if font_path is None:
        print('\n⚠  ไม่พบ Thai font')
        print("   ดาวน์โหลด Sarun's ThangLuang จาก f0nt.com แล้วใส่ใน ~/Library/Fonts/")
        print('   หรือใช้: --font /path/to/ThangLuang.ttf')
        sys.exit(1)

    font_name      = Path(font_path).name
    is_thangluang  = 'thangluang' in font_name.lower() or 'thangl' in font_name.lower()
    print(f'Font : {font_path}')
    if not is_thangluang:
        print('       ⚠  ไม่ใช่ ThangLuang — ตัวอักษรอาจไม่เหมือนป้ายจริง')
    print(f'Output: {OUT_W}×{OUT_H} px  →  {out_dir.resolve()}')

    # ── Province sampling ─────────────────────────────────────────────────────
    if args.province_balance:
        reps      = (args.count // len(PROVINCES)) + 2
        prov_list = (PROVINCES * reps)[:args.count]
        random.shuffle(prov_list)
    else:
        weights = [1.0] * 77
        heavy   = {
            'กรุงเทพมหานคร': 2.5, 'ชลบุรี': 1.8, 'นครราชสีมา': 1.6,
            'เชียงใหม่': 1.5,     'สมุทรปราการ': 1.4, 'นนทบุรี': 1.4,
            'ปทุมธานี': 1.3,      'ขอนแก่น': 1.3, 'สงขลา': 1.2,
        }
        for name, w in heavy.items():
            if name in PROVINCES:
                weights[PROVINCES.index(name)] = w
        tw      = sum(weights)
        weights = [x / tw for x in weights]
        prov_list = random.choices(PROVINCES, weights=weights, k=args.count)

    plate_types = list(PLATE_STYLES.keys())
    total_out   = args.count * args.augment_factor
    counter     = args.start_id
    generated   = 0
    t0          = time.time()

    try:
        from tqdm import tqdm
        pbar = tqdm(total=total_out, unit='img', desc='Generating')
    except ImportError:
        pbar = None

    print(f'\nสร้าง {args.count:,} ป้าย × {args.augment_factor} aug = {total_out:,} ภาพ\n')

    for i in range(args.count):
        n_pre, n_cons, n_digs = random.choice(PLATE_FORMATS)
        prefix = ''.join(random.choices(DIGITS,     k=n_pre))
        cons   = ''.join(random.choices(CONSONANTS, k=n_cons))
        digs   = ''.join(random.choices(DIGITS,     k=n_digs))
        prov   = prov_list[i]
        p_type = random.choices(plate_types, weights=PLATE_TYPE_WEIGHTS)[0]

        try:
            base_img = draw_plate(prefix, cons, digs, prov, p_type, font_path)
        except Exception as e:
            print(f'\n  [SKIP] draw_plate: {e}')
            continue

        for _ in range(args.augment_factor):
            is_night = random.random() < args.night_ratio
            try:
                aug_img = augment(base_img.copy(), night_mode=is_night)
            except Exception as e:
                print(f'\n  [SKIP] augment: {e}')
                continue

            part1 = prefix + cons    # e.g. '1กย', 'กข', ''
            part2 = digs   + prov    # e.g. '889กรุงเทพมหานคร', '1234เชียงใหม่'
            fname = f'{part1}_{part2}_{counter:06d}.jpg'
            try:
                aug_img.save(str(out_dir / fname),
                             format='JPEG', quality=93, optimize=True)
            except Exception as e:
                print(f'\n  [SKIP] save {fname}: {e}')
                continue

            counter   += 1
            generated += 1
            if pbar:
                pbar.update(1)
            elif generated % 1000 == 0:
                elapsed = time.time() - t0
                rate    = generated / elapsed if elapsed > 0 else 0
                eta     = (total_out - generated) / rate / 60 if rate > 0 else 0
                print(f'  {generated:6d}/{total_out}  {rate:.0f} img/s  ETA {eta:.1f} min')

    if pbar:
        pbar.close()

    elapsed = time.time() - t0
    rate    = generated / elapsed if elapsed > 0 else 0
    print(f'\n✅ เสร็จ!  {generated:,} ภาพ  →  {out_dir.resolve()}')
    print(f'   เวลา: {elapsed:.1f}s  ({rate:.0f} img/s)')
    print(f'   --start-id สำหรับ run ต่อ: {counter}')

    from collections import Counter
    cov = Counter(prov_list)
    print(f'\n   ครอบคลุม {len(cov)}/77 จังหวัด')
    print(f'   ภาพต่อจังหวัด: min={min(cov.values()) * args.augment_factor}'
          f'  max={max(cov.values()) * args.augment_factor}')
    missing = [p for p in PROVINCES if p not in cov]
    if missing:
        print(f'   จังหวัดที่หาย: {missing[:5]}{"..." if len(missing) > 5 else ""}')
        print('   → ใช้ --province-balance เพื่อบังคับครบ 77 จังหวัด')


if __name__ == '__main__':
    main()
