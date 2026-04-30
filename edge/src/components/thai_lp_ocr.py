#!/usr/bin/env python3
"""
Thai License Plate OCR — Tesseract-based recognizer.

Handles preprocessing, character recognition (Thai + English + digits),
province matching, and plate format validation.

Uses Tesseract 5 (LSTM) with tha+eng language pack.
- Lightweight: system binary, no large model downloads
- Stable on ARM64 (RPi5 / aarch64)
- Thai consonants + digits + province names recognized via --psm 7 + --psm 8

Only this file changes between OCR iterations — vehicle/plate detection
and Hailo inference are untouched.
"""

import re
import logging
import os
import subprocess
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Province dictionary — all 77 Thai provinces
# ---------------------------------------------------------------------------
THAI_PROVINCES = {
    'กรุงเทพมหานคร', 'กระบี่', 'กาญจนบุรี', 'กาฬสินธุ์',
    'กำแพงเพชร', 'ขอนแก่น', 'จันทบุรี', 'ฉะเชิงเทรา',
    'ชลบุรี', 'ชัยนาท', 'ชัยภูมิ', 'ชุมพร', 'เชียงราย',
    'เชียงใหม่', 'ตรัง', 'ตราด', 'ตาก', 'นครนายก',
    'นครปฐม', 'นครพนม', 'นครราชสีมา', 'นครศรีธรรมราช',
    'นครสวรรค์', 'นนทบุรี', 'นราธิวาส', 'น่าน',
    'บึงกาฬ', 'บุรีรัมย์', 'ปทุมธานี', 'ประจวบคีรีขันธ์',
    'ปราจีนบุรี', 'ปัตตานี', 'พระนครศรีอยุธยา', 'พะเยา',
    'พังงา', 'พัทลุง', 'พิจิตร', 'พิษณุโลก', 'เพชรบุรี',
    'เพชรบูรณ์', 'แพร่', 'ภูเก็ต', 'มหาสารคาม', 'มุกดาหาร',
    'แม่ฮ่องสอน', 'ยโสธร', 'ยะลา', 'ร้อยเอ็ด', 'ระนอง',
    'ระยอง', 'ราชบุรี', 'ลพบุรี', 'ลำปาง', 'ลำพูน',
    'เลย', 'ศรีสะเกษ', 'สกลนคร', 'สงขลา', 'สตูล',
    'สมุทรปราการ', 'สมุทรสงคราม', 'สมุทรสาคร', 'สระแก้ว',
    'สระบุรี', 'สิงห์บุรี', 'สุโขทัย', 'สุพรรณบุรี',
    'สุราษฎร์ธานี', 'สุรินทร์', 'หนองคาย', 'หนองบัวลำภู',
    'อ่างทอง', 'อำนาจเจริญ', 'อุดรธานี', 'อุตรดิตถ์',
    'อุทัยธานี', 'อุบลราชธานี',
}

# Thai plate formats:
#   Standard:  1-3 Thai consonants + 1-4 digits  + optional province
#   Mixed:     1 digit + 1-2 Thai consonants + 1-4 digits + optional province
_PLATE_RE = re.compile(r'(\d?[ก-ฮ]{1,3})\s*(\d{1,4})\s*(.+)?$')

# Tesseract config for single-line plate crops
# --psm 7 = single text line; --oem 3 = LSTM + legacy
_TESS_CFG_LINE = '--oem 3 --psm 7'
# --psm 8 = single word (fallback for very small crops)
_TESS_CFG_WORD = '--oem 3 --psm 8'
_TESS_LANG = 'tha+eng'


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess_plate_crop(crop: np.ndarray) -> np.ndarray:
    """Upscale, deskew, and normalise contrast of a plate crop before OCR."""
    if crop is None or crop.size == 0:
        return crop

    # 1. Resize to minimum height 64px, keep aspect ratio
    h, w = crop.shape[:2]
    if h < 64:
        scale = 64 / h
        crop = cv2.resize(crop, (int(w * scale), 64), interpolation=cv2.INTER_CUBIC)

    # 2. Deskew via Hough lines (only for small angles to avoid over-rotation)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=30)
    if lines is not None:
        angles = [l[0][1] for l in lines[:5]]
        angle_deg = np.degrees(np.median(angles)) - 90
        if abs(angle_deg) < 15:
            M = cv2.getRotationMatrix2D(
                (crop.shape[1] // 2, crop.shape[0] // 2), angle_deg, 1.0)
            crop = cv2.warpAffine(
                crop, M, (crop.shape[1], crop.shape[0]),
                borderMode=cv2.BORDER_REPLICATE)

    # 3. CLAHE on L channel — normalise contrast under varied lighting
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l_ch = clahe.apply(l_ch)
    crop = cv2.cvtColor(cv2.merge([l_ch, a_ch, b_ch]), cv2.COLOR_LAB2BGR)

    return crop


def _prepare_for_tess(crop: np.ndarray) -> np.ndarray:
    """
    Scale to 300px tall, binarise, add white border.
    Tesseract LSTM needs high-resolution input; border prevents edge clipping.
    """
    h, w = crop.shape[:2]
    target_h = 300
    if h < target_h:
        scale = target_h / h
        crop = cv2.resize(crop, (int(w * scale), target_h), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Otsu binarisation works well for plate images (high contrast text)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Ensure text is dark on white background (invert if needed)
    if np.mean(bw) < 128:
        bw = cv2.bitwise_not(bw)

    # Add white padding so Tesseract does not clip characters at edges
    pad = 20
    bw = cv2.copyMakeBorder(bw, pad, pad, pad, pad,
                             cv2.BORDER_CONSTANT, value=255)
    return bw


# Keep old name as alias so external test scripts still work
def _binarise_for_tess(crop: np.ndarray) -> np.ndarray:
    return _prepare_for_tess(crop)


# ---------------------------------------------------------------------------
# Postprocessing
# ---------------------------------------------------------------------------

# Below-baseline vowels commonly dropped by Tesseract — strip for province matching
_BELOW_VOWELS = str.maketrans('', '', 'ุูิีั็')


def _norm_prov(text: str) -> str:
    """Strip below-baseline vowels for lenient province matching."""
    return text.translate(_BELOW_VOWELS)


def validate_thai_plate(text: str) -> dict:
    """
    Parse and validate a raw OCR string against Thai plate format.

    Uses re.search so it finds the plate pattern even if there is noise
    before it (common with Tesseract PSM 11 output).

    Thai plate structure: 1-3 Thai consonants + 1-4 digits + province name.
    Returns a dict with 'valid', structured fields, and 'formatted' string.
    """
    text = text.strip()
    m = _PLATE_RE.search(text)
    if not m:
        return {'valid': False, 'raw': text, 'formatted': text}

    letters = m.group(1)
    numbers = m.group(2)
    province_raw = (m.group(3) or '').strip()

    # Match province with and without below-baseline vowels
    province_matched = None
    norm_raw = _norm_prov(province_raw)
    for p in THAI_PROVINCES:
        norm_p = _norm_prov(p)
        if province_raw and (
            p in province_raw or province_raw in p
            or norm_p in norm_raw or norm_raw in norm_p
        ):
            province_matched = p
            break

    # Only include province in formatted output if it was confirmed against THAI_PROVINCES.
    # Unconfirmed text is often OCR noise — don't propagate it into the final plate string.
    formatted = f'{letters} {numbers}'
    if province_matched:
        formatted += f' {province_matched}'

    return {
        'valid': True,
        'letters': letters,
        'numbers': numbers,
        'province': province_matched or province_raw,
        'province_confirmed': province_matched is not None,
        'formatted': formatted,
        'raw': text,
    }


# ---------------------------------------------------------------------------
# ThaiLPROCR — Tesseract wrapper
# ---------------------------------------------------------------------------

class ThaiLPROCR:
    """
    Synchronous Thai license plate OCR using Tesseract 5 (tha+eng).

    Loaded once during service startup. No large model downloads required —
    models are part of the system package tesseract-ocr-tha.

    Install on device:
        sudo apt install tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng
        pip install pytesseract
    """

    # Tesseract binary path (overridable for devices where it's not on PATH)
    TESSERACT_CMD = '/usr/bin/tesseract'

    def __init__(self, logger: Optional[logging.Logger] = None, log: Optional[logging.Logger] = None):
        self._pytesseract = None
        self._ready = False
        self._log = logger or log or logging.getLogger(__name__)

    def load(self) -> bool:
        """Verify Tesseract is available — call once at startup."""
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = self.TESSERACT_CMD

            # Quick sanity check
            version = pytesseract.get_tesseract_version()
            langs = pytesseract.get_languages()
            if 'tha' not in langs:
                self._log.error(
                    f'ThaiLPROCR: Thai language pack missing '
                    f'(langs={langs}). Run: sudo apt install tesseract-ocr-tha'
                )
                return False

            self._pytesseract = pytesseract
            self._ready = True
            self._log.info(f'ThaiLPROCR: Tesseract {version} ready (langs: tha+eng)')
            return True
        except ImportError:
            self._log.warning(
                'ThaiLPROCR: pytesseract not installed. Run: pip install pytesseract'
            )
            return False
        except Exception as e:
            self._log.error(f'ThaiLPROCR: load failed: {e}')
            return False

    def is_ready(self) -> bool:
        return self._ready

    def read_plate(self, crop: np.ndarray) -> dict:
        """
        Run OCR on a plate crop (after preprocess_plate_crop).

        Tries two Tesseract PSM modes and picks the result with more content.
        Returns dict with 'text', 'confidence', 'validation', 'success'.
        """
        if not self._ready or self._pytesseract is None:
            return {'success': False, 'text': '', 'confidence': 0.0,
                    'error': 'ThaiLPROCR not loaded'}
        try:
            bw = _prepare_for_tess(crop)

            # PSM 11 = sparse text (finds text anywhere — best for plates)
            # PSM 6  = uniform block (fallback for clean single-zone crops)
            cfg11 = '--oem 3 --psm 11'
            cfg6  = '--oem 3 --psm 6'

            text11 = self._pytesseract.image_to_string(
                bw, lang=_TESS_LANG, config=cfg11
            ).strip()
            text6 = self._pytesseract.image_to_string(
                bw, lang=_TESS_LANG, config=cfg6
            ).strip()

            # Prefer the result that has more Thai consonants (key signal for plates)
            def thai_count(t): return sum(1 for c in t if 'ก' <= c <= 'ฮ')
            raw_text = text11 if thai_count(text11) >= thai_count(text6) else text6

            if not raw_text:
                return {'success': False, 'text': '', 'confidence': 0.0,
                        'error': 'No text detected'}

            # Collapse multi-line output to a single string (PSM 11 may return newlines)
            raw_text = ' '.join(raw_text.split())

            # Estimate confidence via image_to_data
            data = self._pytesseract.image_to_data(
                bw, lang=_TESS_LANG, config=cfg11,
                output_type=self._pytesseract.Output.DICT
            )
            confs = [c for c in data['conf'] if isinstance(c, (int, float)) and c >= 0]
            avg_conf = float(np.mean(confs)) / 100.0 if confs else 0.5

            validation = validate_thai_plate(raw_text)

            return {
                'success': True,
                'text': validation.get('formatted', raw_text),
                'confidence': avg_conf,
                'raw_text': raw_text,
                'validation': validation,
            }
        except Exception as e:
            self._log.warning(f'ThaiLPROCR: read_plate error: {e}')
            return {'success': False, 'text': '', 'confidence': 0.0, 'error': str(e)}
