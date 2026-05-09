"""
dual_branch_lpr_ocr.py — DualBranchLPRNet OCR Engine for Hailo-8
=================================================================
Vocabs and architecture sourced from:
  scripts/train_dualbranch_model/charset.py
  scripts/train_dualbranch_model/province_map.py
  scripts/train_dualbranch_model/lprnet_dual_branch.py

Input  : BGR plate crop (any size)  →  resized to [1, 75, 300, 3] float32 NHWC
         Normalization: (px/255 - 0.5) / 0.5  → [-1, 1]  (matches training)
Output1: lpr_logits  shape (1, 38, 49) from conv13  — CTC, blank at index 48
Output2: prov_logits shape (77,) from fc1            — argmax → province name
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
# CTC Character vocabulary — 48 printable chars, blank at index 48
# Source: scripts/train_dualbranch_model/charset.py  CHARS[:48]
# ---------------------------------------------------------------------------
LPR_CHARS: List[str] = [
    # Digits — indices 0-9
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    # Thai consonants sorted by Unicode U+0E01-U+0E2E — indices 10-47
    'ก', 'ข', 'ค', 'ฆ', 'ง', 'จ', 'ฉ', 'ช',
    'ซ', 'ญ', 'ฎ', 'ฐ', 'ณ', 'ด', 'ต', 'ถ',
    'ท', 'ธ', 'น', 'บ', 'ป', 'ผ', 'ฝ', 'พ',
    'ฟ', 'ภ', 'ม', 'ย', 'ร', 'ล', 'ว', 'ศ',
    'ษ', 'ส', 'ห', 'ฬ', 'อ', 'ฮ',
]
assert len(LPR_CHARS) == 48, f"Expected 48 LPR chars, got {len(LPR_CHARS)}"

# CTC blank is the LAST index (48), NOT 0
CTC_BLANK_IDX = 48  # == len(LPR_CHARS)

# Total HEF output classes = 49  (48 printable + 1 blank)
LPR_NUM_CLASSES = 49

# ---------------------------------------------------------------------------
# Province vocabulary — 77 provinces in training index order
# Source: scripts/train_dualbranch_model/province_map.py  PROVINCES list
# NOTE: uses 'กรุงเทพ' (short form used in filenames), not 'กรุงเทพมหานคร'
# ---------------------------------------------------------------------------
PROVINCES: List[str] = [
    'กระบี่',           #  0
    'กรุงเทพ',          #  1  * short form used in training filenames
    'กาญจนบุรี',        #  2
    'กาฬสินธุ์',        #  3
    'กำแพงเพชร',        #  4
    'ขอนแก่น',          #  5
    'จันทบุรี',         #  6
    'ฉะเชิงเทรา',       #  7
    'ชลบุรี',           #  8
    'ชัยนาท',           #  9
    'ชัยภูมิ',          # 10
    'ชุมพร',            # 11
    'เชียงราย',         # 12
    'เชียงใหม่',        # 13
    'ตรัง',             # 14
    'ตราด',             # 15
    'ตาก',              # 16
    'นครนายก',          # 17
    'นครปฐม',           # 18
    'นครพนม',           # 19
    'นครราชสีมา',       # 20
    'นครศรีธรรมราช',    # 21
    'นครสวรรค์',        # 22
    'นนทบุรี',          # 23
    'นราธิวาส',         # 24
    'น่าน',             # 25
    'บึงกาฬ',           # 26
    'บุรีรัมย์',        # 27
    'ปทุมธานี',         # 28
    'ประจวบคีรีขันธ์',  # 29
    'ปราจีนบุรี',       # 30
    'ปัตตานี',          # 31
    'พระนครศรีอยุธยา',  # 32
    'พะเยา',            # 33
    'พังงา',            # 34
    'พัทลุง',           # 35
    'พิจิตร',           # 36
    'พิษณุโลก',         # 37
    'เพชรบุรี',         # 38
    'เพชรบูรณ์',        # 39
    'แพร่',             # 40
    'ภูเก็ต',           # 41
    'มหาสารคาม',        # 42
    'มุกดาหาร',         # 43
    'แม่ฮ่องสอน',       # 44
    'ยโสธร',            # 45
    'ยะลา',             # 46
    'ร้อยเอ็ด',         # 47
    'ระนอง',            # 48
    'ระยอง',            # 49
    'ราชบุรี',          # 50
    'ลพบุรี',           # 51
    'ลำปาง',            # 52
    'ลำพูน',            # 53
    'เลย',              # 54
    'ศรีสะเกษ',         # 55
    'สกลนคร',           # 56
    'สงขลา',            # 57
    'สตูล',             # 58
    'สมุทรปราการ',      # 59
    'สมุทรสงคราม',      # 60
    'สมุทรสาคร',        # 61
    'สระแก้ว',          # 62
    'สระบุรี',          # 63
    'สิงห์บุรี',        # 64
    'สุโขทัย',          # 65
    'สุพรรณบุรี',       # 66
    'สุราษฎร์ธานี',     # 67
    'สุรินทร์',         # 68
    'หนองคาย',          # 69
    'หนองบัวลำภู',      # 70
    'อ่างทอง',          # 71
    'อำนาจเจริญ',       # 72
    'อุดรธานี',         # 73
    'อุตรดิตถ์',        # 74
    'อุทัยธานี',        # 75
    'อุบลราชธานี',      # 76
]
assert len(PROVINCES) == 77, f"Expected 77 provinces, got {len(PROVINCES)}"

# Default HEF path (relative to project root)
_DEFAULT_HEF_RELATIVE = (
    "resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503/"
    "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef"
)

MODEL_W = 300
MODEL_H = 75


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess_for_lprnet(image: np.ndarray) -> np.ndarray:
    """
    Preprocess a BGR plate crop for DualBranchLPRNet inference.

    Pipeline (matches training):
      BGR → RGB → resize(300, 75) → float32/255 → (x-0.5)/0.5 → NHWC [1,75,300,3]

    Returns float32 NHWC array in range [-1, 1].
    """
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    # BGR → RGB
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Resize to model input (W=300, H=75)
    resized = cv2.resize(rgb, (MODEL_W, MODEL_H), interpolation=cv2.INTER_LINEAR)

    # Normalize: (x/255 - 0.5) / 0.5  →  [-1, 1]
    arr = resized.astype(np.float32) / 255.0
    arr = (arr - 0.5) / 0.5

    # Add batch dim: [H, W, C] → [1, H, W, C]
    return arr[np.newaxis, :, :, :]


# ---------------------------------------------------------------------------
# CTC greedy decode
# ---------------------------------------------------------------------------

def ctc_greedy_decode(logits: np.ndarray) -> str:
    """
    Greedy CTC decode.  Blank is at index CTC_BLANK_IDX (48, the last index).

    Args:
        logits: float32 array shape [1, T, C] or [T, C]

    Returns:
        Decoded plate character string (digits + Thai consonants).
    """
    if logits.ndim == 3:
        logits = logits[0]          # [T, C]

    best_path = np.argmax(logits, axis=-1)  # [T]

    decoded: List[int] = []
    prev = -1
    for idx in best_path.tolist():
        if idx != prev:
            if idx != CTC_BLANK_IDX and 0 <= idx < len(LPR_CHARS):
                decoded.append(idx)
            prev = idx

    return ''.join(LPR_CHARS[i] for i in decoded)


def province_decode(logits: np.ndarray,
                    threshold: float = 0.5) -> Tuple[str, float]:
    """
    Argmax + softmax confidence for province branch.

    Returns:
        (province_name, confidence)  — province is '' if below threshold.
    """
    flat = logits.flatten()
    idx  = int(np.argmax(flat))

    # Softmax for calibrated probability
    exp  = np.exp(flat - flat.max())
    conf = float(exp[idx] / exp.sum())

    province = PROVINCES[idx] if idx < len(PROVINCES) else '?'
    if conf < threshold:
        province = ''
    return province, conf


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class DualBranchLPROCR:
    """
    Hailo-8 CTC OCR engine backed by DualBranchLPRNet.

    Loads the .hef via hailo_platform (ROUND_ROBIN scheduler so it can coexist
    with degirum vehicle/LP detection models on the same device).

    Usage::

        ocr = DualBranchLPROCR()
        ocr.load()
        result = ocr.read_plate(plate_bgr_crop)
        # → {'success': True, 'text': 'กข 1234', 'chars': 'กข1234',
        #    'province': 'ชลบุรี', 'province_confidence': 0.82,
        #    'confidence': 0.91, 'processing_time': 0.002}
    """

    def __init__(
        self,
        hef_path: Optional[str] = None,
        province_threshold: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.province_threshold = province_threshold
        self._hef_path = self._resolve_hef(hef_path)

        self._ready = False
        self._vdevice = None
        self._network_group = None
        self._ng_params = None
        self._input_vstreams_params = None
        self._output_vstreams_params = None

        # Tensor names (auto-detected from HEF shape)
        self._input_name: Optional[str] = None
        self._lpr_output_name: Optional[str] = None   # 3-D: (1, T, 49)
        self._prov_output_name: Optional[str] = None  # 1-D: (77,)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_hef(self, hef_path: Optional[str]) -> str:
        if hef_path and Path(hef_path).exists():
            return str(hef_path)
        # Walk up from this file to find project root
        here = Path(__file__).resolve()
        for _ in range(8):
            candidate = here.parent / _DEFAULT_HEF_RELATIVE
            if candidate.exists():
                return str(candidate)
            here = here.parent
        env = os.environ.get('DUALBRANCH_HEF_PATH', '')
        return env if env else _DEFAULT_HEF_RELATIVE

    def _detect_tensors(self, in_info, out_info):
        """
        Detect tensor names by shape — do NOT rely on name strings.
          3-D output (batch, T, C) e.g. (1, 38, 49) -> CTC/LPR branch (conv13)
          1-D output (N,)          e.g. (77,)        -> Province branch (fc1)
        """
        self._input_name = in_info[0].name if in_info else None
        for o in out_info:
            shape = o.shape
            if len(shape) == 3:
                self._lpr_output_name = o.name
                self.logger.info(
                    f"[DualBranchLPROCR] -> LPR/CTC tensor (3-D {shape}): {o.name}")
            elif len(shape) == 1:
                self._prov_output_name = o.name
                self.logger.info(
                    f"[DualBranchLPROCR] -> Province tensor (1-D {shape}): {o.name}")
            else:
                self.logger.warning(
                    f"[DualBranchLPROCR] Unexpected output tensor: {o.name} {shape}")
        # Fallback — if shape detection missed (should not happen with this HEF)
        if not self._lpr_output_name and out_info:
            self._lpr_output_name = out_info[0].name
            self.logger.warning(
                f"[DualBranchLPROCR] LPR fallback to first output: {self._lpr_output_name}")
        if not self._prov_output_name and len(out_info) > 1:
            self._prov_output_name = out_info[1].name
            self.logger.warning(
                f"[DualBranchLPROCR] Prov fallback to second output: {self._prov_output_name}")
        # Sanity check — both must be different tensors
        if (self._lpr_output_name and self._prov_output_name
                and self._lpr_output_name == self._prov_output_name):
            self.logger.error(
                "[DualBranchLPROCR] TENSOR COLLISION: LPR and Province both mapped to "
                f"'{self._lpr_output_name}' -- CTC decode will be WRONG! "
                "HEF must have two outputs: shape (1,T,49) for LPR and (77,) for Province."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Open Hailo-8, configure HEF, prepare vstream params. Idempotent."""
        if self._ready:
            return True
        if not Path(self._hef_path).exists():
            self.logger.error(f"[DualBranchLPROCR] HEF not found: {self._hef_path}")
            return False
        try:
            from hailo_platform import (
                VDevice, HEF, ConfigureParams,
                InputVStreamParams, OutputVStreamParams,
                HailoStreamInterface, FormatType,
            )
            try:
                from hailo_platform import HailoSchedulingAlgorithm
                _has_sched = True
            except ImportError:
                _has_sched = False

            params = VDevice.create_params()
            if _has_sched:
                from hailo_platform import HailoSchedulingAlgorithm
                params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
                self.logger.info("[DualBranchLPROCR] Scheduler: ROUND_ROBIN")

            self._vdevice = VDevice(params)
            hef_obj = HEF(self._hef_path)

            # Inspect and detect tensor names/shapes
            in_info  = hef_obj.get_input_vstream_infos()
            out_info = hef_obj.get_output_vstream_infos()
            self._detect_tensors(in_info, out_info)

            configure_params = ConfigureParams.create_from_hef(
                hef=hef_obj, interface=HailoStreamInterface.PCIe
            )
            ngs = self._vdevice.configure(hef_obj, configure_params)
            self._network_group = ngs[0]
            self._ng_params = self._network_group.create_params()

            # Use float32 input — matches training normalization ([-1, 1])
            self._input_vstreams_params = InputVStreamParams.make(
                self._network_group,
                quantized=False,
                format_type=FormatType.FLOAT32,
            )
            self._output_vstreams_params = OutputVStreamParams.make(
                self._network_group,
                quantized=False,
                format_type=FormatType.FLOAT32,
            )

            self._ready = True
            self.logger.info(
                f"[DualBranchLPROCR] ✅ Loaded: {Path(self._hef_path).name}  "
                f"lpr={self._lpr_output_name}  prov={self._prov_output_name}"
            )
            return True

        except Exception as e:
            self.logger.error(f"[DualBranchLPROCR] Load failed: {e}", exc_info=True)
            self._do_cleanup()
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
        if not self._ready:
            return {'success': False, 'error': 'Model not loaded', 'text': ''}
        if plate_bgr is None or plate_bgr.size == 0:
            return {'success': False, 'error': 'Empty input', 'text': ''}

        t0 = time.perf_counter()
        try:
            from hailo_platform import InferVStreams

            input_arr = preprocess_for_lprnet(plate_bgr)  # float32 NHWC [-1,1]

            with InferVStreams(
                self._network_group,
                self._input_vstreams_params,
                self._output_vstreams_params,
            ) as infer:
                # Do NOT call ng.activate() — scheduler handles activation
                raw: Dict[str, np.ndarray] = infer.infer(
                    {self._input_name: input_arr}
                )

            lpr_logits  = raw.get(self._lpr_output_name,  np.zeros((1, 38, 49)))
            prov_logits = raw.get(self._prov_output_name, np.zeros(77)) if self._prov_output_name else np.zeros(77)

            chars    = ctc_greedy_decode(lpr_logits)
            province, prov_conf = province_decode(prov_logits, self.province_threshold)

            # Confidence proxy: mean of per-timestep max logit (post-softmax)
            lpr_2d = lpr_logits[0] if lpr_logits.ndim == 3 else lpr_logits
            softmax_max = np.exp(lpr_2d - lpr_2d.max(axis=-1, keepdims=True))
            softmax_max = softmax_max / softmax_max.sum(axis=-1, keepdims=True)
            confidence  = float(softmax_max.max(axis=-1).mean())

            # Format: "กข 1234 ชลบุรี"
            text = chars
            if province:
                text = f"{chars} {province}"

            elapsed = time.perf_counter() - t0
            self.logger.debug(
                f"[DualBranchLPROCR] '{text}'  conf={confidence:.3f}"
                f"  prov_conf={prov_conf:.3f}  t={elapsed*1000:.1f}ms"
            )

            return {
                'success':             bool(chars),
                'text':                text.strip(),
                'chars':               chars,
                'province':            province,
                'province_confidence': prov_conf,
                'confidence':          confidence,
                'processing_time':     elapsed,
                'error':               '' if chars else 'CTC produced empty sequence',
            }

        except Exception as e:
            self.logger.error(f"[DualBranchLPROCR] Inference error: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'text': ''}

    def _do_cleanup(self):
        self._ready = False
        self._network_group = None
        if self._vdevice is not None:
            try:
                self._vdevice.release()
            except Exception:
                pass
            self._vdevice = None

    def cleanup(self):
        self._do_cleanup()
        self.logger.info("[DualBranchLPROCR] Cleaned up")

    def __del__(self):
        try:
            self._do_cleanup()
        except Exception:
            pass
