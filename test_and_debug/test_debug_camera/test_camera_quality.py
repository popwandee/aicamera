#!/usr/bin/env python3
"""
Camera Quality Test Script
Measures frame sharpness (Laplacian variance), FPS, and FocusFoM on the real device.

Usage (on aicamera1 or aicamera2):
    source /home/camuser/aicamera/edge/venv_hailo/bin/activate
    python test_and_debug/test_debug_camera/test_camera_quality.py
"""

import sys
import time
import cv2
import numpy as np

sys.path.insert(0, '/home/camuser/aicamera')


def measure_frame_quality(frame: np.ndarray) -> dict:
    if frame is None:
        return {}
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) if len(frame.shape) == 3 else frame
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    tenengrad = float(np.mean(sobelx ** 2 + sobely ** 2))
    return {
        'laplacian_var': round(laplacian_var, 2),
        'tenengrad': round(tenengrad, 2),
        'mean_brightness': round(float(gray.mean()), 2),
        'shape': frame.shape,
    }


def run_quality_test(duration: int = 30, target_fps: int = 15):
    from edge.src.components.camera_handler import CameraHandler

    print("=== Camera Quality Test ===")
    print(f"Duration: {duration}s  Target FPS: {target_fps}")

    handler = CameraHandler()
    if not handler.initialize_camera():
        print("FAIL: camera initialize failed")
        return
    if not handler.start_camera():
        print("FAIL: camera start failed")
        return

    print("OK: camera started — waiting 2s for AE/AF to settle")
    time.sleep(2)

    laplacians = []
    metadata_list = []
    frame_count = 0
    start = time.time()
    frame_interval = 1.0 / target_fps

    while time.time() - start < duration:
        t0 = time.time()

        frame_data = handler.capture_frame(source="buffer", stream_type="main", include_metadata=True)

        if isinstance(frame_data, dict):
            frame = frame_data.get('frame')
            meta = frame_data.get('metadata', {})
        elif isinstance(frame_data, np.ndarray):
            frame = frame_data
            meta = {}
        else:
            time.sleep(0.01)
            continue

        if frame is not None:
            q = measure_frame_quality(frame)
            laplacians.append(q['laplacian_var'])
            metadata_list.append({
                'FocusFoM': meta.get('FocusFoM', 0),
                'LensPos': meta.get('LensPosition'),
                'AeLocked': meta.get('AeLocked'),
                **q,
            })
            frame_count += 1

        elapsed = time.time() - t0
        wait = frame_interval - elapsed
        if wait > 0:
            time.sleep(wait)

    actual_duration = time.time() - start
    actual_fps = frame_count / actual_duration if actual_duration > 0 else 0

    print(f"\n=== Results ===")
    print(f"Frames : {frame_count}")
    print(f"FPS    : {actual_fps:.2f} (target {target_fps})")

    if laplacians:
        lap_arr = np.array(laplacians)
        print(f"\nSharpness (Laplacian Variance):")
        print(f"  Mean : {lap_arr.mean():.2f}  (target ≥ 100)")
        print(f"  Min  : {lap_arr.min():.2f}")
        print(f"  Max  : {lap_arr.max():.2f}")
        print(f"  Std  : {lap_arr.std():.2f}  (low = stable, high = jitter)")

        fom_values = [m['FocusFoM'] for m in metadata_list if m['FocusFoM'] > 0]
        if fom_values:
            fom_arr = np.array(fom_values)
            print(f"\nFocusFoM:")
            print(f"  Mean : {fom_arr.mean():.0f}  (target ≥ 700)")
            print(f"  Min  : {fom_arr.min():.0f}")
            print(f"  Max  : {fom_arr.max():.0f}")
            print(f"  Std  : {fom_arr.std():.0f}")

        sharpness_ok = lap_arr.mean() >= 100
        fom_ok = (np.mean(fom_values) >= 700) if fom_values else False
        print(f"\nSharpness : {'PASS' if sharpness_ok else 'FAIL'}")
        print(f"FocusFoM  : {'PASS' if fom_ok else 'FAIL (or no FoM data)'}")

    handler.close_camera()


if __name__ == "__main__":
    run_quality_test(duration=30, target_fps=15)
