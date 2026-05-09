#!/usr/bin/env python3
"""
test_dual_branch_lpr.py — Full pipeline test for DualBranchLPRNet on Hailo-8
==============================================================================
Mimics the real detection pipeline in detection_processor.py:

    1. Load models  (vehicle degirum + LP degirum + DualBranchDegirumOCR)
    2. Vehicle detection    (full frame → 640×640 letterbox → degirum yolov8)
    3. LP detection         (full frame → 640×640 letterbox → degirum yolov8)
    4. Crop plate           (+15% safe padding, same as crop_with_safe_padding())
    5. DualBranch OCR       (read_plate() → chars + province)
    6. Output table         (vehicle bbox | plate bbox | chars | province | conf | ms)
    7. Annotated image      (saved to test_output/)

Run on aicamera1/aicamera2 (inside venv_hailo):

    source edge/venv_hailo/bin/activate
    cd /home/camuser/aicamera
    python3 test_dual_branch_lpr.py --image /path/to/frame.jpg [--debug] [--save-crops]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Project root — add to sys.path so "edge.*" imports work
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Config (mirrors edge/src/core/config.py to avoid full Django/env stack)
# ---------------------------------------------------------------------------
RESOURCES_DIR = PROJECT_ROOT / "resources"
HEF_MODEL_PATH = "@local"           # degirum inference_host_address
MODEL_ZOO_URL  = str(RESOURCES_DIR)  # degirum zoo_url

VEHICLE_DETECTION_MODEL       = os.getenv("VEHICLE_DETECTION_MODEL",
                                           "yolov8n_relu6_car--640x640_quant_hailort_hailo8_1")
LICENSE_PLATE_DETECTION_MODEL = os.getenv("LICENSE_PLATE_DETECTION_MODEL",
                                           "yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1")
CONFIDENCE_THRESHOLD          = float(os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.5"))
PLATE_CONFIDENCE_THRESHOLD    = float(os.getenv("PLATE_CONFIDENCE_THRESHOLD", "0.3"))

PADDING_RATIO = 0.15           # same as detection_processor.py crop_with_safe_padding()
OUTPUT_DIR    = PROJECT_ROOT / "test_output"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("pipeline_test")


# ===========================================================================
# Helper: letterbox resize (mirrors detection_processor._resize_with_letterbox)
# ===========================================================================
def resize_with_letterbox(
    frame: np.ndarray,
    target_size: Tuple[int, int] = (640, 640),
    padding_color: Tuple[int, int, int] = (114, 114, 114),
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Resize while preserving aspect ratio.  Returns (resized_frame, mapping_info).
    mapping_info is used to map detection coordinates back to the original frame.
    """
    orig_h, orig_w = frame.shape[:2]
    target_w, target_h = target_size

    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_x = (target_w - new_w) // 2
    pad_y = (target_h - new_h) // 2

    canvas = np.full((target_h, target_w, 3), padding_color, dtype=np.uint8)
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

    mapping_info = {
        'scale':       scale,
        'padding':     (pad_x, pad_y),
        'orig_size':   (orig_w, orig_h),
        'target_size': (target_w, target_h),
        'new_size':    (new_w, new_h),
    }
    return canvas, mapping_info


def map_bbox_to_original(
    bbox: List[float],
    mapping_info: Dict[str, Any],
) -> List[float]:
    """Undo letterbox transform: model bbox -> original-frame bbox."""
    scale   = mapping_info['scale']
    pad_x, pad_y = mapping_info['padding']
    x1, y1, x2, y2 = bbox
    orig_x1 = (x1 - pad_x) / scale
    orig_y1 = (y1 - pad_y) / scale
    orig_x2 = (x2 - pad_x) / scale
    orig_y2 = (y2 - pad_y) / scale
    return [orig_x1, orig_y1, orig_x2, orig_y2]


# ===========================================================================
# Helper: safe crop with padding (mirrors detection_processor.crop_with_safe_padding)
# ===========================================================================
def crop_with_safe_padding(
    frame: np.ndarray,
    bbox: List[float],
    padding_ratio: float = 0.15,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Crop bbox region with +/-padding_ratio expansion, clamped to frame edges."""
    x1, y1, x2, y2 = bbox
    frame_h, frame_w = frame.shape[:2]

    region_w = x2 - x1
    region_h = y2 - y1
    pad_w = int(region_w * padding_ratio)
    pad_h = int(region_h * padding_ratio)

    crop_x1 = max(0, int(x1 - pad_w))
    crop_y1 = max(0, int(y1 - pad_h))
    crop_x2 = min(frame_w, int(x2 + pad_w))
    crop_y2 = min(frame_h, int(y2 + pad_h))

    cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]

    crop_info = {
        'original_bbox': bbox,
        'crop_bbox':     [crop_x1, crop_y1, crop_x2, crop_y2],
        'padding_applied': (pad_w, pad_h),
        'padding_ratio': padding_ratio,
    }
    return cropped, crop_info


# ===========================================================================
# Helper: plate quality gate
# ===========================================================================
def check_plate_quality(plate: np.ndarray) -> Dict[str, Any]:
    """Return {'is_acceptable': bool, 'reason': str}."""
    if plate is None or plate.size == 0:
        return {'is_acceptable': False, 'reason': 'empty crop'}
    h, w = plate.shape[:2]
    if w < 30 or h < 10:
        return {'is_acceptable': False, 'reason': f'too small ({w}x{h})'}
    if h > w:
        return {'is_acceptable': False, 'reason': f'portrait orientation ({w}x{h})'}
    return {'is_acceptable': True, 'reason': 'ok'}


# ===========================================================================
# Step 1a — Degirum model loading (vehicle + LP detection models)
# ===========================================================================
def load_degirum_models(args: argparse.Namespace):
    """
    Load vehicle + LP detection models via degirum.
    IMPORTANT: Must be called (and inference run) BEFORE load_dual_branch_ocr().
    Both libraries access the same Hailo-8 device. NOTE: With DualBranchDegirumOCR, device sharing is no longer an issue.
    All models use degirum — one shared HAL layer, no hailo_platform conflict.
    """
    log.info("=" * 60)
    log.info("STEP 1a -- Loading degirum detection models")
    log.info("=" * 60)

    # Configure HailoRT logging to suppress C++ noise
    try:
        from edge.config.hailort_logging import configure_hailort_logging
        configure_hailort_logging()
        log.debug("HailoRT logging configured")
    except Exception as e:
        log.debug(f"hailort_logging not found ({e}), skipping")

    try:
        import degirum as dg
    except ImportError:
        log.critical("degirum not found -- activate venv_hailo first")
        raise SystemExit(1)

    log.info(f"Loading vehicle model:  {VEHICLE_DETECTION_MODEL}")
    vehicle_model = dg.load_model(
        model_name=VEHICLE_DETECTION_MODEL,
        inference_host_address=HEF_MODEL_PATH,
        zoo_url=MODEL_ZOO_URL,
    )
    log.info("  OK  Vehicle model loaded")

    log.info(f"Loading LP detect model: {LICENSE_PLATE_DETECTION_MODEL}")
    lp_model = dg.load_model(
        model_name=LICENSE_PLATE_DETECTION_MODEL,
        inference_host_address=HEF_MODEL_PATH,
        zoo_url=MODEL_ZOO_URL,
    )
    log.info("  OK  LP detection model loaded")
    return vehicle_model, lp_model


# ===========================================================================
# Step 1b — DualBranchDegirumOCR loading (same degirum device as vehicle/LP)
# ===========================================================================
def load_dual_branch_ocr():
    """
    Load DualBranchLPRNet via degirum — same device handle as vehicle/LP models.
    NO hailo_platform used anywhere.  Resolves HAILO_OUT_OF_PHYSICAL_DEVICES.
    Can be called at any point (before or after degirum detections).
    """
    log.info("=" * 60)
    log.info("STEP 1b -- Loading DualBranchDegirumOCR (degirum, same device)")
    log.info("=" * 60)

    try:
        from edge.src.components.dual_branch_degirum_ocr import DualBranchDegirumOCR
    except ImportError as e:
        log.critical(f"Cannot import DualBranchDegirumOCR: {e}")
        raise SystemExit(1)

    dual_ocr = DualBranchDegirumOCR(zoo_url=MODEL_ZOO_URL, logger=log)
    if not dual_ocr.load():
        log.critical("DualBranchDegirumOCR.load() failed -- check degirum JSON + HEF in resources/")
        raise SystemExit(1)
    log.info("  OK  DualBranchDegirumOCR loaded via degirum")
    return dual_ocr


# ===========================================================================
# Step 2 — Vehicle detection
# ===========================================================================
def detect_vehicles(
    frame: np.ndarray,
    vehicle_model,
    conf_threshold: float = CONFIDENCE_THRESHOLD,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (detections, mapping_info).
    Each detection: {'bbox': [x1,y1,x2,y2], 'score': float, 'label': str}
    """
    log.info("\nSTEP 2 -- Vehicle detection")

    model_frame, mapping_info = resize_with_letterbox(frame, (640, 640))
    rgb_frame = cv2.cvtColor(model_frame, cv2.COLOR_BGR2RGB)

    t0 = time.perf_counter()
    results = vehicle_model(rgb_frame)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    raw_boxes = getattr(results, 'results', [])
    detections = []
    for box in raw_boxes:
        score = box.get('score', 0.0)
        if score >= conf_threshold:
            bbox_model = box.get('bbox', [0, 0, 0, 0])
            bbox_orig  = map_bbox_to_original(bbox_model, mapping_info)
            detections.append({
                'bbox':  bbox_orig,
                'score': score,
                'label': box.get('label', 'vehicle'),
            })

    log.info(f"  Raw: {len(raw_boxes)}, Filtered (conf>={conf_threshold}): "
             f"{len(detections)}  [{elapsed_ms:.1f} ms]")
    for i, d in enumerate(detections):
        x1, y1, x2, y2 = [int(v) for v in d['bbox']]
        log.info(f"  Vehicle #{i}: [{x1},{y1},{x2},{y2}]  score={d['score']:.3f}  label={d['label']}")

    return detections, mapping_info


# ===========================================================================
# Step 3 — License plate detection
# ===========================================================================
def detect_plates(
    frame: np.ndarray,
    lp_model,
    conf_threshold: float = PLATE_CONFIDENCE_THRESHOLD,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (plate_boxes, mapping_info).
    Each plate_box: {'bbox': [x1,y1,x2,y2], 'score': float}
    """
    log.info("\nSTEP 3 -- License plate detection")

    model_frame, mapping_info = resize_with_letterbox(frame, (640, 640))
    rgb_frame = cv2.cvtColor(model_frame, cv2.COLOR_BGR2RGB)

    t0 = time.perf_counter()
    results = lp_model(rgb_frame)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    raw_boxes = getattr(results, 'results', [])
    plates = []
    for box in raw_boxes:
        score = box.get('score', 0.0)
        if score >= conf_threshold:
            bbox_model = box.get('bbox', [0, 0, 0, 0])
            bbox_orig  = map_bbox_to_original(bbox_model, mapping_info)
            plates.append({
                'bbox':  bbox_orig,
                'score': score,
                'label': box.get('label', 'lp'),
            })

    log.info(f"  Raw: {len(raw_boxes)}, Filtered (conf>={conf_threshold}): "
             f"{len(plates)}  [{elapsed_ms:.1f} ms]")
    for i, p in enumerate(plates):
        x1, y1, x2, y2 = [int(v) for v in p['bbox']]
        log.info(f"  Plate  #{i}: [{x1},{y1},{x2},{y2}]  score={p['score']:.3f}")

    return plates, mapping_info


# ===========================================================================
# Steps 4+5 — Crop + DualBranch OCR
# ===========================================================================
def run_ocr_on_plates(
    frame: np.ndarray,
    plate_boxes: List[Dict[str, Any]],
    dual_ocr,
    args: argparse.Namespace,
) -> List[Dict[str, Any]]:
    """
    For each detected plate:
      - crop with 15% safe padding
      - quality check
      - run DualBranchDegirumOCR.read_plate()
    Returns list of result dicts.
    """
    log.info("\nSTEP 4+5 -- Crop & DualBranch OCR")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ocr_results = []

    if not plate_boxes:
        log.warning("  No plates to process -- skipping OCR")
        return ocr_results

    for i, plate_box in enumerate(plate_boxes):
        bbox = plate_box['bbox']
        log.info(f"\n  --- Plate #{i} ---")

        # Step 4a: Crop with 15% padding
        plate_crop, crop_info = crop_with_safe_padding(frame, bbox, padding_ratio=PADDING_RATIO)
        if plate_crop.size == 0:
            log.warning(f"  Plate #{i}: empty crop, skipping")
            continue

        log.debug(f"  Crop: {crop_info['crop_bbox']}  size={plate_crop.shape[1]}x{plate_crop.shape[0]}")

        # Step 4b: Quality gate
        quality = check_plate_quality(plate_crop)
        if not quality['is_acceptable']:
            log.warning(f"  Plate #{i}: quality check failed -- {quality['reason']}, skipping OCR")
            ocr_results.append({
                'plate_idx': i,
                'plate_bbox': bbox,
                'plate_score': plate_box['score'],
                'crop_info': crop_info,
                'plate_crop': plate_crop,
                'success': False,
                'reason': quality['reason'],
                'chars': '',
                'province': '',
                'province_confidence': 0.0,
                'confidence': 0.0,
                'processing_time': 0.0,
            })
            continue

        # Step 4c: Optionally save crop for inspection
        if args.save_crops:
            crop_path = OUTPUT_DIR / f"plate_crop_{i}.jpg"
            cv2.imwrite(str(crop_path), plate_crop)
            log.info(f"  Saved crop -> {crop_path}")

        # Step 5: DualBranch OCR
        t0 = time.perf_counter()
        ocr = dual_ocr.read_plate(plate_crop)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        result = {
            'plate_idx':          i,
            'plate_bbox':         bbox,
            'plate_score':        plate_box['score'],
            'crop_info':          crop_info,
            'plate_crop':         plate_crop,
            'success':            ocr.get('success', False),
            'chars':              ocr.get('chars', ''),
            'province':           ocr.get('province', ''),
            'province_confidence': ocr.get('province_confidence', 0.0),
            'confidence':         ocr.get('confidence', 0.0),
            'processing_time':    elapsed_ms,
            'raw_ocr':            ocr,
        }
        ocr_results.append(result)

        status = "OK" if result['success'] else "WARN"
        log.info(f"  [{status}] chars='{result['chars']}'  province='{result['province']}'  "
                 f"conf={result['confidence']:.3f}  prov_conf={result['province_confidence']:.3f}  "
                 f"[{elapsed_ms:.1f} ms]")

    return ocr_results


# ===========================================================================
# Step 6 — Print results table
# ===========================================================================
def print_results_table(
    vehicle_detections: List[Dict],
    ocr_results: List[Dict],
):
    log.info("\n" + "=" * 80)
    log.info("PIPELINE RESULTS")
    log.info("=" * 80)

    log.info(f"\nVehicles detected: {len(vehicle_detections)}")
    for i, v in enumerate(vehicle_detections):
        x1, y1, x2, y2 = [int(c) for c in v['bbox']]
        log.info(f"  [{i}] bbox=[{x1},{y1},{x2},{y2}]  score={v['score']:.3f}  label={v['label']}")

    log.info(f"\nPlates processed: {len(ocr_results)}")
    header = (f"  {'#':>2}  {'PlateBox':28}  {'Score':6}  "
              f"{'Chars':12}  {'Province':20}  {'Conf':6}  {'ProvConf':8}  {'ms':7}  OK")
    log.info(header)
    log.info("  " + "-" * (len(header) - 2))

    for r in ocr_results:
        x1, y1, x2, y2 = [int(c) for c in r['plate_bbox']]
        bbox_str = f"[{x1},{y1},{x2},{y2}]"
        ok = "YES" if r['success'] else "NO"
        prov_conf = r.get('province_confidence', 0.0)
        log.info(
            f"  {r['plate_idx']:>2}  {bbox_str:28}  {r['plate_score']:6.3f}  "
            f"{r['chars']:12}  {r['province']:20}  {r['confidence']:6.3f}  "
            f"{prov_conf:8.3f}  {r['processing_time']:7.1f}  {ok}"
        )

    n_ok = sum(1 for r in ocr_results if r['success'])
    log.info(f"\nSummary: {n_ok}/{len(ocr_results)} plates OCR'd successfully")
    log.info("=" * 80)


# ===========================================================================
# Step 7 — Annotated image
# ===========================================================================
def save_annotated_image(
    frame: np.ndarray,
    vehicle_detections: List[Dict],
    ocr_results: List[Dict],
    output_path: Path,
):
    """
    Draw bounding boxes on the frame and save:
      Blue  box: vehicle detection
      Red   box: plate bbox (original coords)
      Thin  box: plate crop bbox (with padding)
      Green text: OCR result
    """
    vis = frame.copy()
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness  = 2

    # Vehicles -- blue
    for v in vehicle_detections:
        x1, y1, x2, y2 = [int(c) for c in v['bbox']]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 80, 0), 2)
        label = f"vehicle {v['score']:.2f}"
        cv2.putText(vis, label, (x1, max(y1 - 8, 20)), font, 0.6, (255, 200, 0), 2, cv2.LINE_AA)

    # Plates -- red box + green OCR label
    for r in ocr_results:
        x1, y1, x2, y2 = [int(c) for c in r['plate_bbox']]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 80, 255), 2)

        # Crop box (faint dashed look via thin rect)
        cx1, cy1, cx2, cy2 = [int(c) for c in r['crop_info']['crop_bbox']]
        cv2.rectangle(vis, (cx1, cy1), (cx2, cy2), (80, 80, 255), 1)

        # OCR text overlay
        chars    = r['chars'] if r['chars'] else '?'
        province = r['province'] if r['province'] else ''
        display  = f"{chars} {province}".strip() if province else chars
        conf_str = f" ({r['confidence']:.2f})"
        text_full = display + conf_str

        (tw, th), baseline = cv2.getTextSize(text_full, font, font_scale, thickness)
        ty = max(y1 - 12, th + 4)
        cv2.rectangle(vis, (x1, ty - th - 4), (x1 + tw + 6, ty + baseline), (0, 0, 0), cv2.FILLED)
        text_color = (0, 255, 80) if r['success'] else (0, 180, 255)
        cv2.putText(vis, text_full, (x1 + 3, ty), font, font_scale, text_color, thickness, cv2.LINE_AA)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), vis)
    log.info(f"\n  Annotated image saved -> {output_path}")


# ===========================================================================
# Main
# ===========================================================================
def parse_args():
    p = argparse.ArgumentParser(description="DualBranchLPRNet Full Pipeline Test")
    p.add_argument(
        "--image", "-i", default=None,
        help="Path to input image (full camera frame). Omit to use a synthetic frame.",
    )
    p.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG-level logging",
    )
    p.add_argument(
        "--save-crops", action="store_true",
        help="Save each plate crop to test_output/plate_crop_N.jpg for visual inspection",
    )
    p.add_argument(
        "--vehicle-conf", type=float, default=CONFIDENCE_THRESHOLD,
        help=f"Vehicle detection confidence threshold (default {CONFIDENCE_THRESHOLD})",
    )
    p.add_argument(
        "--plate-conf", type=float, default=PLATE_CONFIDENCE_THRESHOLD,
        help=f"Plate detection confidence threshold (default {PLATE_CONFIDENCE_THRESHOLD})",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if not args.debug:
        logging.getLogger().setLevel(logging.INFO)

    log.info("=" * 62)
    log.info("  DualBranchLPRNet -- Full Pipeline Test")
    log.info("=" * 62)

    # Load input frame
    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            log.critical(f"Cannot read image: {args.image}")
            raise SystemExit(1)
        log.info(f"\nImage: {args.image}  size={frame.shape[1]}x{frame.shape[0]}")
    else:
        log.info("\nNo image supplied -- using synthetic 1920x1080 frame")
        log.info("(No real detections expected with synthetic frame)")
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        cv2.putText(frame, "SYNTHETIC TEST FRAME", (400, 540),
                    cv2.FONT_HERSHEY_SIMPLEX, 3, (200, 200, 200), 4)

    # Step 1a: Load degirum models (all degirum models share the same device handle)
    vehicle_model, lp_model = load_degirum_models(args)

    # Step 2: Vehicle detection (degirum — runs before hailo_platform locks device)
    vehicle_detections, _ = detect_vehicles(frame, vehicle_model, args.vehicle_conf)

    # Step 3: LP detection (degirum)
    plate_boxes, _ = detect_plates(frame, lp_model, args.plate_conf)

    # Step 1b: Load DualBranchDegirumOCR (degirum — same device as vehicle/LP)
    # No hailo_platform used, so load order no longer matters for device sharing.
    dual_ocr = load_dual_branch_ocr()

    # Steps 4+5: Crop + OCR
    ocr_results = run_ocr_on_plates(frame, plate_boxes, dual_ocr, args)

    print_results_table(vehicle_detections, ocr_results)

    stem     = Path(args.image).stem if args.image else "synthetic"
    out_path = OUTPUT_DIR / f"pipeline_result_{stem}.jpg"
    save_annotated_image(frame, vehicle_detections, ocr_results, out_path)

    # Cleanup
    log.info("\nCleaning up ...")
    try:
        dual_ocr.cleanup()
        log.info("  DualBranchDegirumOCR cleaned up OK")
    except Exception as e:
        log.warning(f"  cleanup warning: {e}")

    # Verdict
    n_ok = sum(1 for r in ocr_results if r['success'])
    if plate_boxes and n_ok > 0:
        log.info("\nPIPELINE TEST PASSED -- plates detected and OCR successful")
        return 0
    elif not plate_boxes:
        log.info("\nPIPELINE TEST INCONCLUSIVE -- no plates detected in this frame")
        log.info("  Try a frame with a visible Thai license plate.")
        return 0
    else:
        log.warning("\nPIPELINE TEST: plates detected but OCR returned no chars")
        log.warning("  Check DualBranchDegirumOCR preprocessing and degirum JSON config.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
