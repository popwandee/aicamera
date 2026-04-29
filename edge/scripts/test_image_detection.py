#!/usr/bin/env python3
#edge/scripts/test_image_detection.py
"""
Static image detection test script for AI Camera Edge.

This script loads the edge detection pipeline and runs vehicle, license plate,
and OCR inference on one or more image files.

Usage:
    python edge/scripts/test_image_detection.py --images image1.jpg image2.jpg
    python edge/scripts/test_image_detection.py --folder /path/to/images --output-dir ./results --save-annotations
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

import cv2

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(EDGE_ROOT))

from edge.src.components.detection_processor import DetectionProcessor
from edge.src.core.config import VEHICLE_DETECTION_MODEL, LICENSE_PLATE_DETECTION_MODEL, LICENSE_PLATE_OCR_MODEL


def setup_logger(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("image_detection_test")


def parse_args():
    parser = argparse.ArgumentParser(description="Test edge detection pipeline on static image files")
    parser.add_argument(
        "--images",
        nargs="+",
        default=[],
        help="List of image files to process"
    )
    parser.add_argument(
        "--folder",
        default=None,
        help="Folder containing image files to process"
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".jpg", ".jpeg", ".png", ".bmp"],
        help="Image file extensions to include when using --folder"
    )
    parser.add_argument(
        "--output-dir",
        default=str(EDGE_ROOT / "test_image_detection_results"),
        help="Directory to save annotated output images"
    )
    parser.add_argument(
        "--save-annotations",
        action="store_true",
        help="Save annotated images with detected boxes and OCR text"
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Run only vehicle and plate detection without OCR"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level"
    )
    return parser.parse_args()


def collect_image_paths(images: List[str], folder: str, extensions: List[str]) -> List[Path]:
    image_paths = []
    for image in images:
        path = Path(image)
        if path.exists() and path.is_file():
            image_paths.append(path.resolve())
    if folder:
        folder_path = Path(folder)
        if folder_path.exists() and folder_path.is_dir():
            for ext in extensions:
                image_paths.extend(sorted(folder_path.glob(f"*{ext}")))
    return [p for p in image_paths if p.exists()]


def annotate_image(frame, vehicle_boxes, plate_boxes, ocr_results):
    annotated = frame.copy()
    for vb in vehicle_boxes:
        if 'bbox' not in vb:
            continue
        x1, y1, x2, y2 = map(int, vb['bbox'])
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 192, 255), 2)
        label = f"Vehicle {vb.get('score', 0.0):.2f}"
        cv2.putText(annotated, label, (x1, max(y1 - 8, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 192, 255), 1)

    for pb in plate_boxes:
        if 'bbox' not in pb:
            continue
        x1, y1, x2, y2 = map(int, pb['bbox'])
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"Plate {pb.get('score', 0.0):.2f}"
        cv2.putText(annotated, label, (x1, min(y2 + 18, annotated.shape[0] - 2)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    for ocr in ocr_results:
        text = ocr.get('text', '')
        if not text:
            continue
        bbox = ocr.get('bbox', [])
        if len(bbox) == 4:
            x1, y1, x2, y2 = map(int, bbox)
            cv2.putText(annotated, text, (x1, max(y1 - 24, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    return annotated


def process_image(processor: DetectionProcessor, image_path: Path, save_annotations: bool, output_dir: Path, skip_ocr: bool, logger: logging.Logger):
    logger.info(f"Processing image: {image_path}")
    image = cv2.imread(str(image_path))
    if image is None:
        logger.warning(f"Failed to read image: {image_path}")
        return

    frame = processor.validate_and_enhance_frame(image)
    if frame is None:
        logger.warning(f"Image validation failed: {image_path}")
        return

    vehicle_boxes, mapping_info = processor.detect_vehicles(frame)
    logger.info(f"  Vehicles detected: {len(vehicle_boxes)}")

    plate_boxes = processor.detect_license_plates(frame, vehicle_boxes, mapping_info)
    logger.info(f"  License plates detected: {len(plate_boxes)}")

    ocr_results = []
    if not skip_ocr and plate_boxes:
        ocr_results = processor.perform_ocr(frame, plate_boxes)
        logger.info(f"  OCR results: {len(ocr_results)}")

    for idx, result in enumerate(ocr_results):
        logger.info(
            f"    Plate {idx}: text='{result.get('text', '')}', method={result.get('ocr_method', 'none')}, confidence={result.get('confidence', 0.0):.3f}"
        )

    if save_annotations:
        annotated = annotate_image(frame, vehicle_boxes, plate_boxes, ocr_results)
        output_dir.mkdir(parents=True, exist_ok=True)
        annotated_path = output_dir / f"annotated_{image_path.name}"
        cv2.imwrite(str(annotated_path), annotated)
        logger.info(f"  Saved annotated image: {annotated_path}")


def main():
    args = parse_args()
    logger = setup_logger(args.log_level)

    image_paths = collect_image_paths(args.images, args.folder, args.extensions)
    if not image_paths:
        logger.error("No valid input images found. Use --images or --folder.")
        return

    logger.info("Starting static image detection test")
    logger.info(f"Models: vehicle={VEHICLE_DETECTION_MODEL}, plate={LICENSE_PLATE_DETECTION_MODEL}, ocr={LICENSE_PLATE_OCR_MODEL}")
    logger.info(f"Images to process: {len(image_paths)}")

    processor = DetectionProcessor(logger=logger)
    if not processor.load_models():
        logger.warning("Model loading failed or incomplete. Detection may not work as expected.")
    else:
        logger.info("Detection models loaded successfully")

    for image_path in image_paths:
        process_image(
            processor,
            image_path,
            save_annotations=args.save_annotations,
            output_dir=Path(args.output_dir),
            skip_ocr=args.skip_ocr,
            logger=logger
        )

    logger.info("Static image detection test completed")


if __name__ == "__main__":
    main()
