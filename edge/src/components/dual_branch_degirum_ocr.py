"""
dual_branch_degirum_ocr.py — DualBranchLPRNet OCR via degirum (NO hailo_platform)
==================================================================================
This replaces dual_branch_lpr_ocr.py (which uses hailo_platform directly).

WHY: hailo_platform.VDevice and degirum both open the Hailo-8 device through
different HAL layers.  They cannot coexist in the same process:
  - If hailo_platform opens first  → degirum gets HAILO_DEVICE_IN_USE
  - If degirum opens first         → hailo_platform gets HAILO_OUT_OF_PHYSICAL_DEVICES

SOLUTION: Use degirum for ALL models (vehicle detect, LP detect, DualBranch OCR).
  degirum manages the single shared device handle internally.

Usage::
    from edge.src.components.dual_branch_degirum_ocr import DualBranchDegirumOCR

    ocr = DualBranchDegirumOCR()
    ocr.load()          # dg.load_model(...)
    result = ocr.read_plate(plate_bgr_crop)
    # result → {'success': True, 'chars': 'กข1234', 'province': 'ชลบุรี', ...}

Prerequisites:
  - resources/DualBranchLPRNet_.../DualBranchLPRNet_...json   (degirum JSON config)
  - resources/DualBranchLPRNet_.../*_fixed.hef                (compiled model)

Preprocessing matches training exactly:
  BGR → RGB → resize(300,75) → uint8 HWC  (HEF is quantized; Hailo maps 0-255 → [-1,1] on-chip)
  Passed as uint8 RGB (HWC, no batch dim).  InputQuantEn=true — Hailo does on-chip dequant.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Vocabulary — MUST match training exactly
# Source: scripts/train_dualbranch_model/charset.py + lprnet_dual_branch.py
# ---------------------------------------------------------------------------
LPR_CHARS: List[str] = [
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'ก', 'ข', 'ค', 'ฆ', 'ง', 'จ', 'ฉ', 'ช',
    'ซ', 'ญ', 'ฎ', 'ฐ', 'ณ', 'ด', 'ต', 'ถ',
    'ท', 'ธ', 'น', 'บ', 'ป', 'ผ', 'ฝ', 'พ',
    'ฟ', 'ภ', 'ม', 'ย', 'ร', 'ล', 'ว', 'ศ',
    'ษ', 'ส', 'ห', 'ฬ', 'อ', 'ฮ',
]
assert len(LPR_CHARS) == 48
CTC_BLANK_IDX = 48   # blank is LAST (index 48 = len(LPR_CHARS))
LPR_NUM_CLASSES = 49  # 48 chars + 1 blank

PROVINCES: List[str] = [
    'กระบี่', 'กรุงเทพ', 'กาญจนบุรี', 'กาฬสินธุ์', 'กำแพงเพชร',
    'ขอนแก่น', 'จันทบุรี', 'ฉะเชิงเทรา', 'ชลบุรี', 'ชัยนาท',
    'ชัยภูมิ', 'ชุมพร', 'เชียงราย', 'เชียงใหม่', 'ตรัง',
    'ตราด', 'ตาก', 'นครนายก', 'นครปฐม', 'นครพนม',
    'นครราชสีมา', 'นครศรีธรรมราช', 'นครสวรรค์', 'นนทบุรี', 'นราธิวาส',
    'น่าน', 'บึงกาฬ', 'บุรีรัมย์', 'ปทุมธานี', 'ประจวบคีรีขันธ์',
    'ปราจีนบุรี', 'ปัตตานี', 'พระนครศรีอยุธยา', 'พะเยา', 'พังงา',
    'พัทลุง', 'พิจิตร', 'พิษณุโลก', 'เพชรบุรี', 'เพชรบูรณ์',
    'แพร่', 'ภูเก็ต', 'มหาสารคาม', 'มุกดาหาร', 'แม่ฮ่องสอน',
    'ยโสธร', 'ยะลา', 'ร้อยเอ็ด', 'ระนอง', 'ระยอง',
    'ราชบุรี', 'ลพบุรี', 'ลำปาง', 'ลำพูน', 'เลย',
    'ศรีสะเกษ', 'สกลนคร', 'สงขลา', 'สตูล', 'สมุทรปราการ',
    'สมุทรสงคราม', 'สมุทรสาคร', 'สระแก้ว', 'สระบุรี', 'สิงห์บุรี',
    'สุโขทัย', 'สุพรรณบุรี', 'สุราษฎร์ธานี', 'สุรินทร์', 'หนองคาย',
    'หนองบัวลำภู', 'อ่างทอง', 'อำนาจเจริญ', 'อุดรธานี', 'อุตรดิตถ์',
    'อุทัยธานี', 'อุบลราชธานี',
]
assert len(PROVINCES) == 77

# degirum model name = folder name in resources/
_DUALBRANCH_MODEL_NAME = (
    "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503"
)

# ---------------------------------------------------------------------------
# Preprocessing
# HEF was compiled WITH quantization (Hailo input type = UINT8).
# Hailo's on-chip dequantization maps uint8 [0-255] → model float range [-1,1].
# Therefore: pass plain uint8 RGB to degirum with InputQuantEn=true.
# ---------------------------------------------------------------------------
def preprocess_for_lprnet(plate_bgr: np.ndarray) -> np.ndarray:
    """BGR crop → (75, 300, 3) uint8 RGB for degirum with InputQuantEn=true.

    The HEF was compiled with quantization — Hailo expects UINT8 on the wire
    and applies scale/zero_point internally to recover the [-1,1] float range
    that the model was trained with.  We must NOT pre-normalise here.
    """
    rgb = cv2.cvtColor(plate_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (300, 75), interpolation=cv2.INTER_LINEAR)
    return resized  # (75, 300, 3) uint8 — degirum passes straight to Hailo


# ---------------------------------------------------------------------------
# CTC greedy decode
# ---------------------------------------------------------------------------
def ctc_greedy_decode(logits: np.ndarray) -> str:
    """
    Greedy CTC decode from shape (1, T, C) or (T, C).
    T=38 time steps, C=49 classes (48 chars + blank at index 48).
    """
    if logits.ndim == 3:
        logits = logits[0]              # → (T, C)
    best_path = np.argmax(logits, axis=-1).tolist()
    decoded, prev = [], -1
    for idx in best_path:
        if idx != prev:
            if idx != CTC_BLANK_IDX and 0 <= idx < len(LPR_CHARS):
                decoded.append(LPR_CHARS[idx])
            prev = idx
    return ''.join(decoded)


# ---------------------------------------------------------------------------
# Province decode
# ---------------------------------------------------------------------------
def province_decode(
    logits: np.ndarray,
    threshold: float = 0.5,
) -> Tuple[str, float]:
    """Argmax over 77-element province logits → (province_name, confidence)."""
    if logits.ndim > 1:
        logits = logits.flatten()
    # Guard NaN/Inf (can occur when province tensor contains extreme quantized values)
    logits = np.where(np.isfinite(logits), logits, 0.0)
    shifted = logits - logits.max()
    exp = np.exp(np.clip(shifted, -100.0, 0.0))
    probs = exp / (exp.sum() + 1e-9)
    idx = int(np.argmax(probs))
    conf = float(probs[idx])
    name = PROVINCES[idx] if (conf >= threshold and 0 <= idx < len(PROVINCES)) else ''
    return name, conf


# ===========================================================================
# Main class
# ===========================================================================
class DualBranchDegirumOCR:
    """
    DualBranchLPRNet OCR engine backed by degirum (same device handle as
    vehicle/LP detection models — no hailo_platform conflict).

    Architecture:
      plate_bgr → preprocess (uint8 RGB HWC) → degirum inference (InputQuantEn=true)
               → raw tensors → CTC decode + province argmax → text

    The degirum model is configured with:
      InputQuantEn=true  (HEF compiled with quantization — Hailo needs UINT8 input)
      OutputPostprocessType=None             (we apply our own postprocessing)
    """

    def __init__(
        self,
        model_name: str = _DUALBRANCH_MODEL_NAME,
        zoo_url: Optional[str] = None,
        province_threshold: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self._model_name = model_name
        self._province_threshold = province_threshold
        self._ready = False
        self._model = None

        # zoo_url defaults to project resources/
        if zoo_url is None:
            here = Path(__file__).resolve()
            for _ in range(8):
                candidate = here.parent / 'resources'
                if candidate.is_dir():
                    zoo_url = str(candidate)
                    break
                here = here.parent
            if zoo_url is None:
                # fallback: relative to project root via env or config
                try:
                    from edge.src.core.config import MODEL_ZOO_URL
                    zoo_url = MODEL_ZOO_URL
                except ImportError:
                    zoo_url = 'resources'
        self._zoo_url = zoo_url

    # ------------------------------------------------------------------
    # Public API (mirrors DualBranchLPROCR interface)
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load the model via degirum. Idempotent."""
        if self._ready:
            return True
        try:
            import degirum as dg
        except ImportError:
            self.logger.error(
                "[DualBranchDegirumOCR] degirum not installed — "
                "activate edge/venv_hailo"
            )
            return False
        try:
            self.logger.info(
                f"[DualBranchDegirumOCR] Loading '{self._model_name}' "
                f"from {self._zoo_url}"
            )
            self._model = dg.load_model(
                model_name=self._model_name,
                inference_host_address="@local",
                zoo_url=self._zoo_url,
            )
            self._ready = True
            self.logger.info("[DualBranchDegirumOCR] ✅ Model loaded via degirum")
            return True
        except Exception as e:
            self.logger.error(f"[DualBranchDegirumOCR] Load failed: {e}", exc_info=True)
            return False

    def is_ready(self) -> bool:
        return self._ready

    def read_plate(self, plate_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Run DualBranchLPRNet on a BGR plate crop.

        Returns dict:
          success (bool), text (str), chars (str), province (str),
          province_confidence (float), confidence (float),
          processing_time (float), error (str)
        """
        if not self._ready or self._model is None:
            return {'success': False, 'error': 'Model not loaded', 'text': '',
                    'chars': '', 'province': '', 'confidence': 0.0,
                    'province_confidence': 0.0, 'processing_time': 0.0}
        if plate_bgr is None or plate_bgr.size == 0:
            return {'success': False, 'error': 'Empty input', 'text': '',
                    'chars': '', 'province': '', 'confidence': 0.0,
                    'province_confidence': 0.0, 'processing_time': 0.0}

        t0 = time.perf_counter()
        try:
            # Preprocess: BGR → uint8 RGB (75×300×3)
            # HEF is quantized — Hailo needs UINT8; its internal quant params
            # map [0-255] → [-1,1] float that the model was trained on.
            input_arr = preprocess_for_lprnet(plate_bgr)  # (75, 300, 3) uint8

            # Inference — degirum passes uint8 array to Hailo as-is
            result = self._model(input_arr)  # (75, 300, 3) uint8

            # ------------------------------------------------------------------
            # Extract raw tensors from degirum result.
            # degirum with OutputPostprocessType=None exposes raw outputs.
            # The exact access method depends on degirum version:
            #   Option A: result.results → list of numpy arrays (one per output)
            #   Option B: result._inference_results → dict name→array
            #   Option C: result.results → list of dicts with 'data' key
            # We try each in order and log what we find.
            # ------------------------------------------------------------------
            lpr_logits, prov_logits = self._extract_tensors(result)

            chars    = ctc_greedy_decode(lpr_logits)
            province, prov_conf = province_decode(prov_logits, self._province_threshold)

            # Confidence proxy: mean of per-timestep softmax max
            lpr_2d = lpr_logits[0] if lpr_logits.ndim == 3 else lpr_logits
            # Guard against NaN/Inf in raw logits (bad tensor extraction)
            lpr_2d = np.where(np.isfinite(lpr_2d), lpr_2d, 0.0)
            shifted = lpr_2d - lpr_2d.max(axis=-1, keepdims=True)
            exp_vals = np.exp(np.clip(shifted, -100.0, 0.0))
            softmax = exp_vals / (exp_vals.sum(axis=-1, keepdims=True) + 1e-9)
            confidence = float(softmax.max(axis=-1).mean())

            text = f"{chars} {province}".strip() if province else chars
            elapsed = time.perf_counter() - t0

            self.logger.debug(
                f"[DualBranchDegirumOCR] '{text}'  conf={confidence:.3f}  "
                f"prov_conf={prov_conf:.3f}  t={elapsed*1000:.1f}ms"
            )
            return {
                'success':             bool(chars),
                'text':                text,
                'chars':               chars,
                'province':            province,
                'province_confidence': prov_conf,
                'confidence':          confidence,
                'processing_time':     elapsed,
                'error':               '' if chars else 'CTC produced empty sequence',
            }
        except Exception as e:
            self.logger.error(
                f"[DualBranchDegirumOCR] Inference error: {e}", exc_info=True
            )
            elapsed = time.perf_counter() - t0
            return {'success': False, 'error': str(e), 'text': '',
                    'chars': '', 'province': '', 'confidence': 0.0,
                    'province_confidence': 0.0, 'processing_time': elapsed}

    def cleanup(self):
        """Release the degirum model object."""
        self._model = None
        self._ready = False
        self.logger.info("[DualBranchDegirumOCR] Cleaned up")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_array_from_item(self, item) -> 'Optional[np.ndarray]':
        """Return the first numpy array found in a degirum result item.

        Handles three forms:
          - numpy array directly
          - dict  → tries common key names, then ANY value that is an array
          - object → tries common attribute names, then callable .numpy()
        """
        if isinstance(item, np.ndarray):
            return item

        if isinstance(item, dict):
            # Try well-known key names first
            for key in ('data', 'output', 'tensor', 'value', 'score',
                        'results', 'array', 'buf', 'buffer'):
                v = item.get(key)
                if isinstance(v, np.ndarray):
                    return v
            # Fall back: any value that is a numpy array
            for v in item.values():
                if isinstance(v, np.ndarray):
                    return v
            return None

        # Object with attributes
        for attr in ('data', 'output', 'array', 'tensor', 'value', 'numpy'):
            v = getattr(item, attr, None)
            if isinstance(v, np.ndarray):
                return v
        # Callable .numpy() (e.g. torch/tf tensors)
        fn = getattr(item, 'numpy', None)
        if callable(fn):
            try:
                v = fn()
                if isinstance(v, np.ndarray):
                    return v
            except Exception:
                pass
        return None

    def _classify_array(
        self, arr: 'np.ndarray'
    ) -> 'Tuple[str, np.ndarray]':
        """
        Given a raw array, decide whether it is an LPR or province tensor.

        Returns ('lpr', normalised_arr) or ('prov', normalised_arr) or ('?', arr).

        Normalisation:
          LPR  → squeezed to (T, C) where C == LPR_NUM_CLASSES (49)
          Prov → squeezed to (77,)
        """
        sq = np.squeeze(arr)                        # remove all size-1 dims
        # ---- Province: flat vector of length 77 ----
        if sq.ndim == 1 and sq.shape[0] == len(PROVINCES):
            return 'prov', sq
        # ---- LPR: (T, C) with C==49 ----
        if sq.ndim == 2 and sq.shape[1] == LPR_NUM_CLASSES:
            return 'lpr', sq[np.newaxis]            # → (1, T, C)
        # ---- LPR: already (1, T, C) ----
        if sq.ndim == 3 and sq.shape[2] == LPR_NUM_CLASSES:
            return 'lpr', sq
        # ---- LPR: flat (T*C,) ----
        if sq.ndim == 1 and sq.shape[0] == LPR_NUM_CLASSES * 38:
            return 'lpr', sq.reshape(1, 38, LPR_NUM_CLASSES)
        return '?', arr

    def _extract_tensors(
        self, result
    ) -> 'Tuple[np.ndarray, np.ndarray]':
        """
        Extract LPR (shape 1×T×C) and Province (shape 77) tensors from result.

        Strategy — try each source in order until BOTH tensors are found:
          1. result.results        → list of items  (A: ndarray, B: dict, C: object)
          2. result._inference_results / result.inference_results → dict {name: arr}
          3. Walk ALL non-dunder attributes looking for ndarray

        Tensors are identified by shape (NOT key/attr name), using _classify_array().
        """
        lpr_logits  = None
        prov_logits = None

        def _ingest(arr: np.ndarray):
            """Try to assign arr to lpr or prov slot."""
            nonlocal lpr_logits, prov_logits
            kind, normed = self._classify_array(arr)
            if kind == 'lpr' and lpr_logits is None:
                lpr_logits = normed
            elif kind == 'prov' and prov_logits is None:
                prov_logits = normed

        # ----------------------------------------------------------------
        # Source 1: result.results
        # ----------------------------------------------------------------
        try:
            raw = getattr(result, 'results', None)
            if isinstance(raw, (list, tuple)):
                for item in raw:
                    arr = self._extract_array_from_item(item)
                    if arr is not None:
                        _ingest(arr)
            elif isinstance(raw, np.ndarray):
                _ingest(raw)
        except Exception as e:
            self.logger.debug(f"[_extract_tensors] result.results failed: {e}")

        # ----------------------------------------------------------------
        # Source 2: _inference_results / inference_results dict
        # ----------------------------------------------------------------
        if lpr_logits is None or prov_logits is None:
            try:
                for attr in ('_inference_results', 'inference_results',
                             '_raw_results', 'raw_results'):
                    d = getattr(result, attr, None)
                    if isinstance(d, dict):
                        for arr in d.values():
                            if isinstance(arr, np.ndarray):
                                _ingest(arr)
                        break
            except Exception as e:
                self.logger.debug(f"[_extract_tensors] inference_results failed: {e}")

        # ----------------------------------------------------------------
        # Source 3: walk ALL non-dunder attributes
        # ----------------------------------------------------------------
        if lpr_logits is None or prov_logits is None:
            try:
                for attr in dir(result):
                    if attr.startswith('_') or lpr_logits is not None and prov_logits is not None:
                        continue
                    val = getattr(result, attr, None)
                    if val is None or callable(val):
                        continue
                    if isinstance(val, np.ndarray):
                        _ingest(val)
                    elif isinstance(val, (list, tuple)):
                        for item in val:
                            arr = self._extract_array_from_item(item)
                            if arr is not None:
                                _ingest(arr)
            except Exception as e:
                self.logger.debug(f"[_extract_tensors] attr walk failed: {e}")

        # ----------------------------------------------------------------
        # Fallback / diagnostics
        # ----------------------------------------------------------------
        if lpr_logits is None or prov_logits is None:
            self.logger.warning(
                "[DualBranchDegirumOCR] Could not locate %s tensor(s) — "
                "dumping result structure (see INFO log).",
                ('LPR' if lpr_logits is None else '') +
                ('+Province' if prov_logits is None else '')
            )
            self._log_result_structure(result)

        # Return zeros so callers don't crash — caller will see empty chars
        if lpr_logits is None:
            lpr_logits  = np.zeros((1, 38, LPR_NUM_CLASSES), dtype=np.float32)
        if prov_logits is None:
            prov_logits = np.zeros(len(PROVINCES), dtype=np.float32)

        return lpr_logits, prov_logits

    def _log_result_structure(self, result):
        """Dump the full degirum result structure at INFO level for debugging."""
        self.logger.info("[DualBranchDegirumOCR] ===== result structure =====")
        self.logger.info(f"  type(result) = {type(result).__qualname__}")
        for attr in dir(result):
            if attr.startswith('__'):
                continue
            try:
                val = getattr(result, attr)
                if callable(val):
                    continue
                if isinstance(val, np.ndarray):
                    self.logger.info(
                        f"  .{attr}: ndarray shape={val.shape} dtype={val.dtype} "
                        f"min={float(val.min()):.3f} max={float(val.max()):.3f}"
                    )
                elif isinstance(val, (list, tuple)) and val:
                    self.logger.info(
                        f"  .{attr}: {type(val).__name__}[{len(val)}]"
                    )
                    for i, item in enumerate(val[:4]):   # show first 4 items
                        if isinstance(item, np.ndarray):
                            self.logger.info(
                                f"    [{i}] ndarray shape={item.shape} "
                                f"dtype={item.dtype}"
                            )
                        elif isinstance(item, dict):
                            for k, v in item.items():
                                if isinstance(v, np.ndarray):
                                    self.logger.info(
                                        f"    [{i}]['{k}']: ndarray "
                                        f"shape={v.shape} dtype={v.dtype} "
                                        f"min={float(v.min()):.3f} "
                                        f"max={float(v.max()):.3f}"
                                    )
                                else:
                                    self.logger.info(
                                        f"    [{i}]['{k}']: "
                                        f"{type(v).__name__} = {repr(v)[:60]}"
                                    )
                        else:
                            self.logger.info(
                                f"    [{i}] {type(item).__name__}: "
                                f"{repr(item)[:60]}"
                            )
                elif isinstance(val, dict):
                    self.logger.info(
                        f"  .{attr}: dict keys={list(val.keys())[:8]}"
                    )
                else:
                    self.logger.info(f"  .{attr}: {repr(val)[:100]}")
            except Exception:
                pass
        self.logger.info("[DualBranchDegirumOCR] ===========================")
