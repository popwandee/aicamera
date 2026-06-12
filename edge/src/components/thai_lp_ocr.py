#!/usr/bin/env python3
"""
Thai License Plate OCR — Tesseract-based recognizer.

Handles preprocessing, character recognition (Thai + English + digits),
province matching, and plate format validation.

Uses Tesseract 5 (LSTM) with tha+eng language pack.
- Lightweight: system binary, no large model downloads
- Stable on ARM64 (RPi5 / aarch64)
- Three-mode OCR pipeline with short-circuit on valid result

Only this file changes between OCR iterations — vehicle/plate detection
and Hailo inference are untouched.
"""

import os
import re
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Camera identity — NoIR flag
# ---------------------------------------------------------------------------
# aicamera2 (AICAMERA_ID=2) uses IMX708 NoIR (no IR-cut filter).
# Near-IR bleeds into R channel → BGR2GRAY degrades binarization on white plates.
# G-channel has least IR contamination → use it for all binarization paths.
# Determined once at module load from env, not per-crop, because the plate crop
# is a neutral white rectangle that doesn't trigger the r>b*1.35 heuristic.
_IS_NOIR_CAMERA: bool = os.environ.get('AICAMERA_ID', '1') == '2'

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
#
# [^\dก-ฮ]* between consonants and digits: tolerates stray vowel marks
# (e.g. "จระ 4173" from Tesseract where ะ is mis-attached to ร).
# Consonants are ก-ฮ (U+0E01-U+0E2E); vowels/tone marks are outside this range.
_PLATE_RE = re.compile(r'(\d?[ก-ฮ]{1,3})[^\dก-ฮ]*(\d{1,4})\s*(.+)?$')

_TESS_LANG = 'tha+eng'


# ---------------------------------------------------------------------------
# Preprocessing helpers
# ---------------------------------------------------------------------------

def _grey(crop: np.ndarray, noir: bool) -> np.ndarray:
    """Convert BGR crop to greyscale: G-channel for NoIR, standard luma for colour."""
    return crop[:, :, 1].copy() if noir else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def _mode_a_gray(crop: np.ndarray, noir: bool) -> np.ndarray:
    """
    Mode A — fast greyscale (no binarization).
    2× LANCZOS4 upscale + channel-aware greyscale.
    Input crop is already CLAHE-normalised by preprocess_plate_crop().
    At ~80px input height, 2× → ~160px gives ~100px character height —
    adequate for Tesseract LSTM PSM 11 (sparse text scan).
    """
    h, w = crop.shape[:2]
    crop_up = cv2.resize(crop, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
    return _grey(crop_up, noir)


def _mode_b_adaptive(crop: np.ndarray, noir: bool,
                     scale: float = 3.0, pad: int = 30) -> np.ndarray:
    """
    Mode B — adaptive threshold binarization.
    3× LANCZOS4 upscale + unsharp mask + per-region adaptive Gaussian threshold.
    3× gives ~240px output height from the typical 80px preprocessed input, so
    Thai consonant strokes are ~96px tall — reliably resolved by PSM 6.
    2× (160px) is borderline for "จ"/"ร" on smaller raw crops (< 60px height).
    Image size at 3×: ~510×240px + padding ≈ 570×300px — ~2 s under 30 fps load.
    Block size ~10% of width adapts to local contrast without small-block noise.
    PSM 6 (uniform text block) is the correct mode for binary plate images.
    """
    h, w = crop.shape[:2]
    crop = cv2.resize(crop, (int(w * scale), int(h * scale)),
                      interpolation=cv2.INTER_LANCZOS4)
    blurred = cv2.GaussianBlur(crop, (0, 0), sigmaX=1.0)
    crop = cv2.addWeighted(crop, 1.4, blurred, -0.4, 0)

    gray = _grey(crop, noir)
    _w = gray.shape[1]
    block = max(51, (_w // 10) | 1)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, block, 5)
    if np.mean(bw) < 128:
        bw = cv2.bitwise_not(bw)
    return cv2.copyMakeBorder(bw, pad, pad, pad, pad,
                              cv2.BORDER_CONSTANT, value=255)


def _mode_c_otsu(crop: np.ndarray, noir: bool,
                 scale: float = 2.0, pad: int = 30) -> np.ndarray:
    """
    Mode C — Otsu binarization with adaptive fallback.
    2× LANCZOS4 upscale + unsharp mask + Otsu threshold.
    CLAHE was already applied by preprocess_plate_crop(), which pre-separates
    the bimodal histogram that Otsu relies on.
    Falls back to adaptive when fill_ratio is degenerate (< 0.1 or > 0.9),
    which happens when dark car-body padding dominates the crop.
    PSM 6 is used (not PSM 11) — binarized text blocks need uniform-mode scan.
    """
    h, w = crop.shape[:2]
    crop = cv2.resize(crop, (int(w * scale), int(h * scale)),
                      interpolation=cv2.INTER_LANCZOS4)
    blurred = cv2.GaussianBlur(crop, (0, 0), sigmaX=1.0)
    crop = cv2.addWeighted(crop, 1.4, blurred, -0.4, 0)

    gray = _grey(crop, noir)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    fill_ratio = np.mean(bw) / 255.0
    if fill_ratio < 0.1 or fill_ratio > 0.9:
        _w = gray.shape[1]
        block = max(51, (_w // 10) | 1)
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, block, 5)
        logger.debug(f'[TESS_PREP] Otsu degenerate fill={fill_ratio:.2f}'
                     f' → adaptive block={block} noir={noir}')

    if np.mean(bw) < 128:
        bw = cv2.bitwise_not(bw)
    return cv2.copyMakeBorder(bw, pad, pad, pad, pad,
                              cv2.BORDER_CONSTANT, value=255)


def preprocess_plate_crop(crop: np.ndarray) -> np.ndarray:
    """Upscale, deskew, and normalise contrast of a plate crop before OCR."""
    if crop is None or crop.size == 0:
        return crop

    # 1. Resize to minimum height 80px — gives CLAHE more pixels to work with
    h, w = crop.shape[:2]
    if h < 80:
        scale = 80 / h
        crop = cv2.resize(crop, (int(w * scale), 80), interpolation=cv2.INTER_LANCZOS4)

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
    """Backward-compatible alias — Mode C binarization."""
    return _mode_c_otsu(crop, noir=_IS_NOIR_CAMERA)


# Keep old name so external test scripts still work
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

    # Only include province in formatted output if confirmed against THAI_PROVINCES.
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

    Three-mode pipeline with short-circuit on valid result:
      Mode A  2× greyscale + PSM 11  (fast, no binarization — primary path)
      Mode B  adaptive BW + PSM 6    (robust for uneven illumination)
      Mode C  Otsu BW + PSM 6        (fallback, CLAHE already applied upstream)

    Loaded once during service startup. No large model downloads required.

    Install on device:
        sudo apt install tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng
        pip install pytesseract
    """

    TESSERACT_CMD = '/usr/bin/tesseract'
    # 5 s per call: the detection service runs Hailo inference at 30 fps on the
    # same RPi5 cores, pushing Tesseract subprocess time from ~0.3 s (idle) to
    # ~2.5 s (loaded).  2 s timed out in field tests; 5 s gives safe headroom.
    _TIMEOUT = 5
    _CFG_BASE = '--oem 3'

    def __init__(self, logger: Optional[logging.Logger] = None,
                 log: Optional[logging.Logger] = None):
        self._pytesseract = None
        self._ready = False
        self._log = logger or log or logging.getLogger(__name__)

    def load(self) -> bool:
        """Verify Tesseract is available — call once at startup."""
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = self.TESSERACT_CMD
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
            self._log.info(
                f'ThaiLPROCR: Tesseract {version} ready (langs: tha+eng) '
                f'noir_camera={_IS_NOIR_CAMERA}'
            )
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
        Multi-mode OCR on a plate crop (after preprocess_plate_crop).

        Runs Mode A first; if a valid Thai plate is found, returns immediately.
        Falls through to Mode B (adaptive) then Mode C (Otsu) for difficult crops.
        When no mode yields a valid plate, picks the result with the most Thai
        consonants as a best-effort partial result.

        Input crop is expected to be ~80-100px tall, CLAHE-normalised, padded.
        Returns dict with 'text', 'confidence', 'validation', 'success'.
        """
        if not self._ready or self._pytesseract is None:
            return {'success': False, 'text': '', 'confidence': 0.0,
                    'error': 'ThaiLPROCR not loaded'}

        def _run(img: np.ndarray, psm: int) -> str:
            cfg = f'{self._CFG_BASE} --psm {psm}'
            try:
                return self._pytesseract.image_to_string(
                    img, lang=_TESS_LANG, config=cfg, timeout=self._TIMEOUT
                ).strip()
            except RuntimeError:
                self._log.warning(f'ThaiLPROCR: PSM {psm} timed out')
                return ''

        def _thai_count(t: str) -> int:
            return sum(1 for c in t if 'ก' <= c <= 'ฮ')

        def _clean(t: str) -> str:
            return ' '.join(t.split())

        def _conf_from_validation(v: dict) -> float:
            # Analytical confidence: avoids an extra image_to_data Tesseract call.
            # The detection service runs at 30 fps and keeps the CPU busy; each
            # additional call costs 2-3 s under load.
            if v.get('province_confirmed'):
                return 0.85
            if v.get('valid'):
                return 0.65
            return 0.0

        def _make_result(text: str, v: dict) -> dict:
            return {
                'success': True,
                'text': v.get('formatted', text),
                'confidence': _conf_from_validation(v),
                'raw_text': text,
                'validation': v,
            }

        try:
            # ── Mode A: 2× greyscale + PSM 11 ──────────────────────────────
            # Primary path. No binarization — avoids Otsu/adaptive artefacts.
            # Works reliably on colour camera crops ≥ 80px input height.
            # For NoIR camera: G-channel prevents R-channel IR bleed degrading contrast.
            gray_a = _mode_a_gray(crop, noir=_IS_NOIR_CAMERA)
            text_a = _clean(_run(gray_a, psm=11))
            val_a  = validate_thai_plate(text_a)
            self._log.debug(f'[TESS_A] psm11 grey: {repr(text_a)}')

            if val_a.get('valid'):
                self._log.debug(f'[TESS_HIT] mode=A result={repr(text_a)}')
                return _make_result(text_a, val_a)

            # ── Mode B: adaptive threshold + PSM 11 ────────────────────────
            # More robust for uneven illumination (padded car-body margins,
            # NoIR colour shift, overcast vs direct sun).
            # PSM 11 (sparse text) is faster than PSM 6 on binarized images
            # under 30 fps load, and produces better consonant detection for
            # Thai plates where the text is not a perfectly uniform block.
            bw_b   = _mode_b_adaptive(crop, noir=_IS_NOIR_CAMERA)
            text_b = _clean(_run(bw_b, psm=11))
            val_b  = validate_thai_plate(text_b)
            self._log.debug(f'[TESS_B] psm11 adaptive: {repr(text_b)}')

            if val_b.get('valid'):
                self._log.debug(f'[TESS_HIT] mode=B result={repr(text_b)}')
                return _make_result(text_b, val_b)

            # ── Mode C: Otsu binarize + PSM 6 ──────────────────────────────
            # Last resort. CLAHE was applied upstream → Otsu histogram is
            # pre-separated. Falls back to adaptive inside if fill_ratio degenerates.
            bw_c   = _mode_c_otsu(crop, noir=_IS_NOIR_CAMERA)
            text_c = _clean(_run(bw_c, psm=6))
            val_c  = validate_thai_plate(text_c)
            self._log.debug(f'[TESS_C] psm6 otsu: {repr(text_c)}')

            if val_c.get('valid'):
                self._log.debug(f'[TESS_HIT] mode=C result={repr(text_c)}')
                return _make_result(text_c, val_c)

            # ── No valid plate — best-effort fallback ───────────────────────
            all_texts = [text_a, text_b, text_c]
            best = max(all_texts, key=lambda t: (_thai_count(t), len(t)))
            if not best:
                return {'success': False, 'text': '', 'confidence': 0.0,
                        'error': 'No text detected'}

            val = validate_thai_plate(best)
            self._log.debug(
                f'[TESS_FALLBACK] no valid plate; best={repr(best)} '
                f'modes=[{repr(text_a)}, {repr(text_b)}, {repr(text_c)}]'
            )
            return _make_result(best, val)

        except Exception as e:
            self._log.warning(f'ThaiLPROCR: read_plate error: {e}')
            return {'success': False, 'text': '', 'confidence': 0.0, 'error': str(e)}

