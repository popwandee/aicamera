#!/usr/bin/env python3
"""
synthetic_lpr_script.py — Synthetic Thai License Plate Generator v3
=====================================================================
สร้างภาพป้ายทะเบียนไทย สำหรับ train DualBranchLPRNet

Output size: 300 × 100 px  (ตรงกับ dataset_thai ที่มีอยู่, ratio 3:1)
Model input: (B, 3, 75, 300) — training script resize อัตโนมัติ

Layout (ไม่มี THAILAND, ไม่มีเส้นนอน):
  ┌──────────────────────────────────────────────┐  ← border 4px
  │                                              │
  │          กข          1234                   │  ← main chars (large)
  │                                              │
  │               เชียงใหม่                      │  ← province (small)
  │                                              │
  └──────────────────────────────────────────────┘

Plate formats (n_prefix, n_consonants, n_digits):
  (0,2,4) กข 1234   — ~40%  ทั่วไปสองพยัญชนะ
  (1,2,4) 1กก 5367  — ~25%  มีเลขนำหน้า
  (0,1,4) ก 1234    — ~15%  หนึ่งพยัญชนะ
  (1,1,4) 1ก 1234   — ~10%  เลขนำ+หนึ่งพยัญชนะ
  (2,0,4) 15 7410   —  ~3%  เลขล้วน
  (0,2,3) กข 123    —  ~2%  สามหลัก

Plate types:
  white  (65%): พื้นขาว ตัวดำ  — ทะเบียนรถส่วนบุคคล
  yellow (20%): พื้นเหลือง ตัวดำ — รถบรรทุก/พาณิชย์
  green  (10%): พื้นเขียว ตัวขาว — ราชการ
  red     (5%): พื้นแดง ตัวขาว  — ป้ายแดง/ผู้ผลิต

Augmentations:
  - brightness / contrast
  - gaussian blur (motion, defocus)
  - perspective warp เบาๆ (max 4% skew)
  - gaussian noise
  - JPEG compression
  - night mode (dark plate + headlight glare)

ชื่อไฟล์: {prefix+พยัญชนะ}_{ตัวเลข}{จังหวัด}_{id:06d}.jpg
  เช่น  กข_1234เชียงใหม่_000001.jpg  →  plate_text = 'กข1234เชียงใหม่'
       1กก_5367เชียงใหม่_000002.jpg  →  plate_text = '1กก5367เชียงใหม่'
  จังหวัดต้องตรงกับ province_map.py (short form)

Usage:
  # macOS (ใช้ font Ayuthaya ที่มีอยู่ใน macOS)
  python3 synthetic_lpr_script.py --count 5000 --output-dir ./synthetic_new

  # ระบุ font เอง
  python3 synthetic_lpr_script.py \\
      --font /Library/Fonts/Ayuthaya.ttf \\
      --count 5000 --augment-factor 3

  # Ubuntu / Jetson AGX Xavier
  python3 synthetic_lpr_script.py \\
      --font /usr/share/fonts/truetype/tlwg/Loma.ttf \\
      --count 5000

  # ต่อจาก run ก่อนหน้า (ไม่ overwrite)
  python3 synthetic_lpr_script.py --count 2000 --start-id 15001

Requirements:
  pip install Pillow numpy tqdm
"""

from __future__ import annotations

import argparse
import io
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ── Output dimensions ──────────────────────────────────────────────────────────
# ตรงกับ dataset_thai/train/*.jpg ที่มีอยู่ (training script resize ไปที่ 75×300 เอง)
OUT_W, OUT_H = 300, 100

# ── Character sets (ต้องตรงกับ lprnet_dual_branch.py LPR_CHARS) ───────────────
DIGITS     = list('0123456789')
CONSONANTS = list('กขคฆงจฉชซญฎฐณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ')  # 38 ตัว

# ── Province list (ต้องตรงกับ province_map.py PROVINCES — 77 จังหวัด) ─────────
PROVINCES = [
    # ⚠️  ต้องตรงกับ province_map.py PROVINCES ทุกตัว (long form 'กรุงเทพมหานคร')
    'กระบี่',          'กรุงเทพมหานคร',   'กาญจนบุรี',       'กาฬสินธุ์',
    'กำแพงเพชร',       'ขอนแก่น',         'จันทบุรี',        'ฉะเชิงเทรา',
    'ชลบุรี',          'ชัยนาท',          'ชัยภูมิ',         'ชุมพร',
    'เชียงราย',        'เชียงใหม่',        'ตรัง',            'ตราด',
    'ตาก',             'นครนายก',         'นครปฐม',          'นครพนม',
    'นครราชสีมา',      'นครศรีธรรมราช',   'นครสวรรค์',       'นนทบุรี',
    'นราธิวาส',        'น่าน',            'บึงกาฬ',          'บุรีรัมย์',
    'ปทุมธานี',        'ประจวบคีรีขันธ์', 'ปราจีนบุรี',      'ปัตตานี',
    'พระนครศรีอยุธยา', 'พะเยา',           'พังงา',           'พัทลุง',
    'พิจิตร',          'พิษณุโลก',        'เพชรบุรี',        'เพชรบูรณ์',
    'แพร่',            'ภูเก็ต',          'มหาสารคาม',       'มุกดาหาร',
    'แม่ฮ่องสอน',      'ยโสธร',           'ยะลา',            'ร้อยเอ็ด',
    'ระนอง',           'ระยอง',           'ราชบุรี',         'ลพบุรี',
    'ลำปาง',           'ลำพูน',           'เลย',             'ศรีสะเกษ',
    'สกลนคร',          'สงขลา',           'สตูล',            'สมุทรปราการ',
    'สมุทรสงคราม',     'สมุทรสาคร',       'สระแก้ว',         'สระบุรี',
    'สิงห์บุรี',       'สุโขทัย',         'สุพรรณบุรี',      'สุราษฎร์ธานี',
    'สุรินทร์',        'หนองคาย',         'หนองบัวลำภู',     'อ่างทอง',
    'อำนาจเจริญ',      'อุดรธานี',        'อุตรดิตถ์',       'อุทัยธานี',
    'อุบลราชธานี',
]
assert len(PROVINCES) == 77, f"จำนวนจังหวัดต้องเป็น 77, ได้ {len(PROVINCES)}"

# ── Plate styles: (bg_rgb, text_rgb, border_rgb) ───────────────────────────────
PLATE_STYLES = {
    #          พื้นหลัง               ตัวอักษร          ขอบ
    'white':  ((255, 255, 255),   (15,  15,  15),   (15,  15,  15)),
    'yellow': ((255, 204,   0),   (15,  15,  15),   (15,  15,  15)),
    'green':  ((0,  105,  55),   (245, 245, 245),  (245, 245, 245)),
    'red':    ((185,  25,  20),  (245, 245, 245),  (245, 245, 245)),
}
PLATE_TYPE_WEIGHTS = [0.65, 0.20, 0.10, 0.05]

# รูปแบบป้าย: (n_prefix_digits, n_consonants, n_digits)
# v3: รองรับป้ายที่มีตัวเลขนำหน้าพยัญชนะ เช่น 1กก 5367, 2กล 4944
# ใช้ตัวเลขซ้ำ tuple เพื่อควบคุมสัดส่วน
PLATE_FORMATS = [
    (0, 2, 4),   # กข 1234   — ~40%  ทั่วไปสองพยัญชนะ
    (0, 2, 4),
    (0, 2, 4),
    (0, 2, 4),
    (1, 2, 4),   # 1กก 5367  — ~25%  มีเลขนำหน้า+สองพยัญชนะ
    (1, 2, 4),
    (1, 2, 4),
    (0, 1, 4),   # ก 1234    — ~15%  หนึ่งพยัญชนะ
    (0, 1, 4),
    (1, 1, 4),   # 1ก 1234   — ~10%  เลขนำ+หนึ่งพยัญชนะ
    (1, 1, 4),
    (2, 0, 4),   # 15 7410   —  ~3%  เลขล้วน (ป้ายรถราชการบางประเภท)
    (0, 2, 3),   # กข 123    —  ~2%  สามหลัก
]

# ── Font paths ─────────────────────────────────────────────────────────────────
# TH Sarabun ก่อน — เลข 0 กลม ไม่มีขีด (ป้ายไทยจริงใช้เลขกลม)
# Ayuthaya มีเลข 0 มีขีดกลาง → ใช้เป็น fallback เท่านั้น
FONT_SEARCH = [
    # TH Sarabun New — ลำดับแรก (เลข 0 กลมถูกต้อง)
    '/Users/sqh/Library/Fonts/Sarabun-Bold.ttf',
    # Ubuntu / Jetson (apt install fonts-thai-tlwg) — เลข 0 กลม
    '/usr/share/fonts/truetype/tlwg/Sarabun-Bold.ttf',
    # macOS fallback — Ayuthaya มีเลข 0 มีขีด (ใช้ถ้าไม่มีทางเลือกอื่น)
    '/Users/sqh/Library/Fonts/Sarabun-SemiBold.ttf',
    '/Users/sqh/Library/Fonts/Sarabun-ExtraBold.ttf',
]


def find_font(override: Optional[str] = None) -> Optional[str]:
    if override and Path(override).exists():
        return override
    if override:
        print(f"WARNING: ไม่พบ font ที่ระบุ: {override}")
    for p in FONT_SEARCH:
        if Path(p).exists():
            return p
    return None


# ── Layout constants v4 (px) สำหรับ 300×100 ──────────────────────────────────
# ป้ายทะเบียนจริง: main text ใหญ่มาก, มีเส้นคลื่นคั่น, จังหวัดเล็กกว่า
BORDER      = 4     # ขอบรอบป้าย (px)
TOP_PAD     = 5     # padding ด้านบนของ inner area
MAIN_H      = 52    # ความสูงของ zone ตัวหลัก (พยัญชนะ+ตัวเลข)
WAVE_H      = 8     # ความสูงของ zone เส้นคลื่นคั่น (wavy separator)
GAP_H       = 2     # ช่องว่างเล็กน้อยระหว่าง wave กับ province
PROV_H      = 24    # ความสูง zone ชื่อจังหวัด
SIDE_PAD    = 6     # margin ด้านข้าง inner area (each side)
# ตรวจสอบ: BORDER + TOP_PAD + MAIN_H + WAVE_H + GAP_H + PROV_H + BORDER
# = 4 + 5 + 52 + 8 + 2 + 24 + 5 = 100 px ✓

# ── Zone proportions (สัดส่วนความกว้างของแต่ละ zone) ───────────────────────
# ป้ายจริง: หมวดอักษร ~38%, ช่องว่างกลาง ~20%, ตัวเลข ~42%
LEFT_RATIO  = 0.38   # zone พยัญชนะ+prefix (ฝั่งซ้าย)
GAP_RATIO   = 0.20   # ช่องว่างระหว่างหมวดกับตัวเลข
RIGHT_RATIO = 0.42   # zone ตัวเลข (ฝั่งขวา)


def _autofit_font(font_path: str, text: str, max_w: int, max_h: int,
                  size_hint: int = 48) -> ImageFont.FreeTypeFont:
    """หา font size ที่พอดีกับ box — ลดทีละ 1px เพื่อ precision สูง"""
    dummy = Image.new('RGB', (1, 1))
    ddraw = ImageDraw.Draw(dummy)
    size  = size_hint
    while size > 8:
        font = ImageFont.truetype(font_path, size)
        bbox = ddraw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            return font
        size -= 1
    return ImageFont.truetype(font_path, 8)


def _draw_wavy_line(
    draw: 'ImageDraw.ImageDraw',
    x0: int, x1: int, y_center: int,
    amplitude: float, color: tuple, width: int = 1,
) -> None:
    """วาดเส้นคลื่น (sine wave) — จำลองเส้นคั่นป้ายทะเบียนจริง"""
    n_cycles = 3.0   # จำนวนรอบ
    n_steps  = 80    # ความละเอียด segments
    pts = []
    for i in range(n_steps + 1):
        t = i / n_steps
        x = x0 + (x1 - x0) * t
        y = y_center + amplitude * math.sin(2 * math.pi * n_cycles * t)
        pts.append((int(x), int(y)))
    for j in range(len(pts) - 1):
        draw.line([pts[j], pts[j + 1]], fill=color, width=width)


def draw_plate(
    prefix: str,
    consonants: str,
    digits: str,
    province: str,
    plate_type: str,
    font_path: str,
) -> Image.Image:
    """
    วาดป้ายทะเบียนไทย 300×100 px — v4 zone-based layout

    ป้ายถูกแบ่งออกเป็น 2 zone หลัก (เหมือนป้ายจริง):
      [  prefix+consonants  ][    gap    ][   digits   ]
      [              wavy separator line               ]
      [                    province                    ]

    prefix    : ตัวเลขนำหน้า ('' | '1' | '2' | '15')
    consonants: พยัญชนะหมวด ('' | 'กข' | 'ก')
    digits    : ตัวเลขหลัง ('1234' | '5367' | '123')
    """
    bg_rgb, text_rgb, border_rgb = PLATE_STYLES[plate_type]

    img  = Image.new('RGB', (OUT_W, OUT_H), color=bg_rgb)
    draw = ImageDraw.Draw(img)

    # ── ขอบป้าย ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, OUT_W - 1, OUT_H - 1], outline=border_rgb, width=BORDER)

    # ── inner dimensions ───────────────────────────────────────────────────────
    x_left_edge = BORDER + SIDE_PAD
    inner_w     = OUT_W - 2 * (BORDER + SIDE_PAD)   # ~276px
    y_main_top  = BORDER + TOP_PAD                  # y = 9

    # ── แบ่ง zone ──────────────────────────────────────────────────────────────
    left_w  = int(inner_w * LEFT_RATIO)              # ~105px
    gap_w   = int(inner_w * GAP_RATIO)               # ~55px
    right_w = inner_w - left_w - gap_w               # ~116px

    x_left  = x_left_edge                            # start ของ zone ซ้าย
    x_right = x_left_edge + left_w + gap_w           # start ของ zone ขวา

    # ── ข้อความ ────────────────────────────────────────────────────────────────
    left_text  = f'{prefix}{consonants}'             # '1กก' | 'กข' | 'ก' | '15'
    right_text = digits                              # '1234' | '5367'

    # ── หา font size ที่พอดีทั้งสอง zone (ใช้ขนาดเดียวกัน) ──────────────────
    # target: ตัวอักษรสูง ~82% ของ MAIN_H ≈ 43px สำหรับ MAIN_H=52
    dummy  = Image.new('RGB', (1, 1))
    ddraw  = ImageDraw.Draw(dummy)
    size   = 62   # เริ่มต้นสูง แล้วลดจนพอดี
    while size > 10:
        font   = ImageFont.truetype(font_path, size)
        bbox_l = ddraw.textbbox((0, 0), left_text,  font=font)
        bbox_r = ddraw.textbbox((0, 0), right_text, font=font)
        wl = bbox_l[2] - bbox_l[0]
        hl = bbox_l[3] - bbox_l[1]
        wr = bbox_r[2] - bbox_r[0]
        hr = bbox_r[3] - bbox_r[1]
        fits_w = (wl <= left_w) and (wr <= right_w)
        fits_h = max(hl, hr) <= MAIN_H - 2
        if fits_w and fits_h:
            break
        size -= 1
    font_main = ImageFont.truetype(font_path, size)

    # ── วาด left text (centered ใน left zone) ─────────────────────────────────
    bbox = ddraw.textbbox((0, 0), left_text, font=font_main)
    lw   = bbox[2] - bbox[0]
    lh   = bbox[3] - bbox[1]
    lx   = x_left + (left_w - lw) // 2
    ly   = y_main_top + (MAIN_H - lh) // 2 - bbox[1]
    draw.text((lx, ly), left_text, fill=text_rgb, font=font_main)

    # ── วาด right text (centered ใน right zone) ────────────────────────────────
    bbox = ddraw.textbbox((0, 0), right_text, font=font_main)
    rw   = bbox[2] - bbox[0]
    rh   = bbox[3] - bbox[1]
    rx   = x_right + (right_w - rw) // 2
    ry   = y_main_top + (MAIN_H - rh) // 2 - bbox[1]
    draw.text((rx, ry), right_text, fill=text_rgb, font=font_main)

    # ── เส้นคลื่นคั่น (wavy separator) ────────────────────────────────────────
    y_wave = BORDER + TOP_PAD + MAIN_H + WAVE_H // 2
    _draw_wavy_line(
        draw,
        x0=x_left_edge, x1=OUT_W - (BORDER + SIDE_PAD),
        y_center=y_wave, amplitude=2.5,
        color=border_rgb, width=1,
    )

    # ── ชื่อจังหวัด ────────────────────────────────────────────────────────────
    y_prov_top = BORDER + TOP_PAD + MAIN_H + WAVE_H + GAP_H
    # province font = ~55% ของ main font size
    prov_size_hint = max(8, int(size * 0.55))
    font_prov = _autofit_font(font_path, province,
                               max_w=inner_w, max_h=PROV_H - 2,
                               size_hint=prov_size_hint)

    bbox = ddraw.textbbox((0, 0), province, font=font_prov)
    pw   = bbox[2] - bbox[0]
    ph   = bbox[3] - bbox[1]
    px   = (OUT_W - pw) // 2
    py   = y_prov_top + (PROV_H - ph) // 2 - bbox[1]
    draw.text((px, py), province, fill=text_rgb, font=font_prov)

    return img


# ── Perspective warp (เบาๆ — จำลองมุมกล้องเล็กน้อย) ──────────────────────────
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
    """
    Keystoning เบาๆ — จำลองการถ่ายจากมุมเล็กน้อย
    skew ≤ 0.04 = สมจริง, > 0.06 = บิดเบี้ยวเกินจริง
    """
    w, h = img.size
    dx = int(w * skew * random.uniform(-1.0, 1.0))
    dy = int(h * skew * random.uniform(-1.0, 1.0))

    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [
        (max(0, dx // 2),       max(0, dy // 2)),
        (min(w, w - dx // 2),   max(0, -dy // 2)),
        (min(w, w + dx // 3),   min(h, h - dy // 3)),
        (max(0, -dx // 3),      min(h, h + dy // 3)),
    ]
    coeffs = _perspective_coeffs(dst, src)
    if coeffs is None:
        return img
    return img.transform(
        (w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC,
    )


# ── Augmentation ───────────────────────────────────────────────────────────────
def augment(img: Image.Image, night_mode: bool = False) -> Image.Image:
    """Augmentation สมจริง — ไม่บิดเบี้ยวมากเกินไป"""

    # Brightness
    if random.random() < 0.70:
        lo = 0.40 if night_mode else 0.65
        hi = 0.75 if night_mode else 1.40
        img = ImageEnhance.Brightness(img).enhance(random.uniform(lo, hi))

    # Contrast
    if random.random() < 0.55:
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.60, 1.50))

    # Blur (motion / defocus) — ความน่าจะเป็นต่ำ และ radius ต่ำ
    if random.random() < 0.35:
        radius = random.uniform(0.2, 1.2)   # ลดลงจาก 1.8 → 1.2
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))

    # Perspective warp เบาๆ — max skew 3-4% เท่านั้น
    if random.random() < 0.25:             # ลดจาก 0.38 → 0.25
        skew = random.uniform(0.01, 0.04)  # ลดจาก 0.09 → 0.04
        img = perspective_warp(img, skew=skew)

    # Gaussian noise
    if random.random() < 0.40:
        arr   = np.array(img, dtype=np.float32)
        sigma = random.uniform(3.0, 18.0)
        noise = np.random.normal(0.0, sigma, arr.shape)
        arr   = np.clip(arr + noise, 0.0, 255.0).astype(np.uint8)
        img   = Image.fromarray(arr)

    # Night mode: สีมืดลง + จำลอง headlight ฉาย
    if night_mode:
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.10, 0.40))
        if random.random() < 0.35:
            arr      = np.array(img, dtype=np.float32)
            sx       = random.randint(30, OUT_W - 30)
            sw       = random.randint(20, 50)
            x0, x1  = max(0, sx - sw // 2), min(OUT_W, sx + sw // 2)
            arr[:, x0:x1] = np.clip(
                arr[:, x0:x1] + random.uniform(60.0, 160.0), 0, 255
            )
            img = Image.fromarray(arr.astype(np.uint8))

    # JPEG compression artifacts
    if random.random() < 0.40:
        q   = random.randint(40, 90)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=q)
        buf.seek(0)
        img = Image.open(buf).copy()

    # Sharpness variation
    if random.random() < 0.25:
        img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.4, 2.0))

    return img


# ── CLI ────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='สร้างป้ายทะเบียนไทย Synthetic สำหรับ DualBranchLPRNet',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument('--output-dir',      default='./synthetic_new',
                   help='Folder สำหรับบันทึก .jpg')
    p.add_argument('--count',           type=int,   default=5000,
                   help='จำนวนป้ายพื้นฐาน (ก่อน augmentation)')
    p.add_argument('--augment-factor',  type=int,   default=3,
                   help='สำเนา augmented ต่อป้าย (รวม = count × factor)')
    p.add_argument('--night-ratio',     type=float, default=0.20,
                   help='สัดส่วนภาพที่ใช้ night augmentation')
    p.add_argument('--font',            default=None,
                   help='Path ไปยัง Thai TTF font (auto-detect ถ้าไม่ระบุ)')
    p.add_argument('--seed',            type=int,   default=42)
    p.add_argument('--start-id',        type=int,   default=1,
                   help='ID เริ่มต้น (ป้องกัน overwrite ถ้า run ต่อ)')
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

    # ── ตรวจสอบ font ─────────────────────────────────────────────────────────
    font_path = find_font(args.font)
    if font_path is None:
        print('\n⚠  ไม่พบ Thai font — ตัวอักษรจะแสดงเป็นกล่องสี่เหลี่ยม (□□)')
        print('   ติดตั้ง font ก่อน:')
        print('   macOS:   font Ayuthaya มีใน macOS อยู่แล้ว — ควร detect อัตโนมัติ')
        print('            ถ้าไม่เจอ: brew install --cask font-noto-sans-thai')
        print('   Ubuntu:  sudo apt install fonts-thai-tlwg')
        print('   หรือ:    download THSarabunNew.ttf วางใน folder นี้\n')
        sys.exit(1)

    print(f'Font: {font_path}')
    print(f'Output size: {OUT_W}×{OUT_H} px  (ตรงกับ dataset_thai)')

    # ── Province sampling ─────────────────────────────────────────────────────
    if args.province_balance:
        reps      = (args.count // len(PROVINCES)) + 2
        prov_list = (PROVINCES * reps)[:args.count]
        random.shuffle(prov_list)
    else:
        # น้ำหนักตามสัดส่วนจริง (กรุงเทพและปริมณฑลมากกว่า)
        weights = [1.0] * 77
        for name, w in [('กรุงเทพมหานคร', 2.5), ('ชลบุรี', 1.8), ('นครราชสีมา', 1.6),
                        ('เชียงใหม่', 1.5), ('สมุทรปราการ', 1.4), ('นนทบุรี', 1.4),
                        ('ปทุมธานี', 1.3), ('ขอนแก่น', 1.3), ('สงขลา', 1.2)]:
            if name in PROVINCES:
                weights[PROVINCES.index(name)] = w
        tw = sum(weights)
        weights = [x / tw for x in weights]
        prov_list = random.choices(PROVINCES, weights=weights, k=args.count)

    plate_types    = list(PLATE_STYLES.keys())
    total_out      = args.count * args.augment_factor
    counter        = args.start_id
    generated      = 0
    t0             = time.time()

    # ── Progress bar ──────────────────────────────────────────────────────────
    try:
        from tqdm import tqdm
        pbar = tqdm(total=total_out, unit='img', desc='Generating')
    except ImportError:
        pbar = None

    print(f'\nสร้าง {args.count:,} ป้าย × {args.augment_factor} augmentation'
          f' = {total_out:,} ภาพ')
    print(f'บันทึกที่: {out_dir.resolve()}\n')

    for i in range(args.count):
        # ── สุ่มรูปแบบป้าย ──────────────────────────────────────────────────
        n_pre, n_cons, n_digs = random.choice(PLATE_FORMATS)
        prefix   = ''.join(random.choices(DIGITS,      k=n_pre))   # เลขนำหน้า
        cons     = ''.join(random.choices(CONSONANTS,  k=n_cons))  # พยัญชนะ
        digs     = ''.join(random.choices(DIGITS,      k=n_digs))  # ตัวเลขหลัง
        province = prov_list[i]
        p_type   = random.choices(plate_types, weights=PLATE_TYPE_WEIGHTS)[0]

        # ── วาดป้ายพื้นฐาน ──────────────────────────────────────────────────
        try:
            base_img = draw_plate(prefix, cons, digs, province, p_type, font_path)
        except Exception as e:
            print(f'\n  [SKIP] draw_plate: {e}')
            continue

        # ── สร้าง augmented copies ───────────────────────────────────────────
        for _ in range(args.augment_factor):
            is_night = random.random() < args.night_ratio
            try:
                aug_img = augment(base_img.copy(), night_mode=is_night)
            except Exception as e:
                print(f'\n  [SKIP] augment: {e}')
                continue

            # ชื่อไฟล์: {prefix+พยัญชนะ}_{ตัวเลข+จังหวัด}_{id:06d}.jpg
            # เช่น: กข_1234เชียงใหม่_000001.jpg  หรือ  1กก_5367เชียงใหม่_000002.jpg
            part1    = prefix + cons          # e.g. '1กก' หรือ 'กข'
            part2    = digs   + province      # e.g. '5367เชียงใหม่'
            fname    = f'{part1}_{part2}_{counter:06d}.jpg'
            out_path = out_dir / fname
            try:
                aug_img.save(str(out_path), format='JPEG', quality=93, optimize=True)
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
                print(f'  {generated:6d}/{total_out}  ({100*generated/total_out:.1f}%)'
                      f'  {rate:.0f} img/s  ETA {eta:.1f} min')

    if pbar:
        pbar.close()

    elapsed  = time.time() - t0
    rate_avg = generated / elapsed if elapsed > 0 else 0

    print(f'\n✅ เสร็จ!  {generated:,} ภาพ  →  {out_dir.resolve()}')
    print(f'   เวลา: {elapsed:.1f}s  ({rate_avg:.0f} img/s)')
    print(f'   --start-id สำหรับ run ต่อ: {counter}')

    # ── Province coverage summary ─────────────────────────────────────────────
    from collections import Counter
    cov = Counter(prov_list)
    covered   = len(cov)
    min_count = min(cov.values()) * args.augment_factor
    max_count = max(cov.values()) * args.augment_factor
    print(f'\n   ครอบคลุม {covered}/77 จังหวัด')
    print(f'   ภาพต่อจังหวัด: min={min_count}  max={max_count}')
    if covered < 77:
        missing = [p for p in PROVINCES if p not in cov]
        print(f'   จังหวัดที่หายไป: {missing[:5]}{"..." if len(missing) > 5 else ""}')
        print(f'   → ใช้ --province-balance เพื่อบังคับครบ 77 จังหวัด')


if __name__ == '__main__':
    main()
