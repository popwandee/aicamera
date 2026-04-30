# 2026/04/26 Analysis & Hypotheses
## Updated: 2026/04/30 แก้ไขปัญหาแล้ว ปรับไปใช้ Tesseract OCR และจัดทำแผนการพัฒนา LPRNet ขึ้นมาเอง จาก Synthetic Auto-Generate data

## What the Logs Tell Us

### Pipeline execution timeline (Run 2, venv_hailo)

```
16:47:34,044  model loading completed
16:47:34,044  Processing image...
16:47:36,672  Vehicles detected: 1          → +2.6s  (Hailo vehicle inference)
16:47:37,930  License plates detected: 1    → +1.3s  (Hailo plate inference)
16:47:39,349  OCR results: 0               → +1.4s  (OCR stage ran, returned nothing)
16:47:39,350  test completed
16:47:47,651  EasyOCR loaded (background)   → +8.3s after completion (too late)
```

**Key observation:** OCR stage took 1.4 seconds and returned 0 results — it did not error out or skip, it ran and found nothing. EasyOCR finished loading 8 seconds *after* the script completed.

---

## Hypotheses — Ordered by Probability

### Hypothesis 1 (Most Likely): Hailo OCR model input pipeline bug
**Probability: HIGH**

The Hailo OCR model (`yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1`) expects a **256×128 cropped plate image**. The `DetectionProcessor.perform_ocr()` method must crop the plate region from the frame using the bbox from `detect_license_plates()`, then resize to 256×128 before passing to the model.

Likely failure modes:
- Plate crop is empty or zero-sized (bbox coordinates wrong format — absolute vs normalized)
- Crop resize produces an invalid tensor
- Model runs but confidence threshold filters all results out

**How to verify:**
```python
# Add debug prints to perform_ocr():
print(f"plate_boxes passed to OCR: {plate_boxes}")
print(f"plate crop shape: {crop.shape}")
print(f"raw OCR model output: {raw_output}")
```

---

### Hypothesis 2 (Likely): EasyOCR not ready → fallback path also fails
**Probability: MEDIUM-HIGH**

EasyOCR loads asynchronously and takes ~6-7 seconds. The OCR stage runs at ~1.4 seconds post-detection — EasyOCR is still loading at that point. If the code logic is:

```
try Hailo OCR → if fails → try EasyOCR → if not ready → return []
```

Then both paths could silently return nothing if Hailo OCR also fails. The 0 result could be the fallback returning empty rather than raising an error.

**How to verify:** Check `perform_ocr()` return path when EasyOCR is not yet initialized.

---

### Hypothesis 3 (Possible): Bbox format mismatch between plate detector and OCR
**Probability: MEDIUM**

`detect_license_plates()` returns `plate_boxes` with a `bbox` field. If the plate detector returns **normalized coordinates** [0.0–1.0] but the OCR crop code treats them as **pixel coordinates**, the crop will be a 0×0 or 1×1 pixel region — producing an empty/noise input that yields 0 detections.

**How to verify:**
```python
# In test script, after detect_license_plates():
for pb in plate_boxes:
    print(f"plate bbox: {pb.get('bbox')} — score: {pb.get('score')}")
```

---

### Hypothesis 4 (Possible): Hailo chip resource conflict with live service
**Probability: MEDIUM**

The service log shows `HAILO_STREAM_ABORT` errors repeatedly. When the test script attempts to load the OCR model onto the same Hailo-8 chip that the service is using (even in its crash-loop state), there may be a resource lock conflict. Vehicle and plate models loaded first (before the chip entered abort state for that cycle), but the OCR model inference hit the abort.

**Evidence against this:** No explicit `HAILO_STREAM_ABORT` error appears in the test script log for the OCR stage, only `OCR results: 0`. But the error could be swallowed in `perform_ocr()`'s exception handler.

**How to verify:** Stop the service before running the test script, then retry:
```bash
sudo systemctl stop aicamera_lpr.service
source edge/venv_hailo/bin/activate
python edge/scripts/test_image_detection.py --images <image> --save-annotations
sudo systemctl start aicamera_lpr.service
```

---

### Hypothesis 5 (Less Likely): OCR confidence threshold too high
**Probability: LOW-MEDIUM**

The OCR model may be running correctly and producing output, but a post-processing confidence filter discards all results. Thai plates may score below the configured threshold.

**How to verify:** Search `detection_processor.py` for confidence thresholds applied after OCR inference.

---

## Secondary Issue: HAILO_STREAM_ABORT in Live Service

This is a **separate, serious problem** that should be investigated in parallel.

```
ERROR HAILO_STREAM_ABORT detected — Hailo VDMA ring is in aborted state.
Scheduling model reinitialization...
WARNING Vehicle detection model not loaded: models_loaded=False (logged 87 times)
```

The service reinitializes models (evidenced by repeated `HailoRT logging configured` lines every ~10 seconds) but keeps hitting ABORT. Causes:

- **Memory pressure:** Pi5 RAM exhaustion causing VDMA buffer allocation failure
- **Thermal throttling:** Hailo-8 overheating after 22h uptime
- **HailoRT firmware crash:** requires `hailortcli fw-update` or chip reset
- **Competing process:** test script run during service operation may have destabilized the chip

Check:
```bash
sudo hailortcli monitor          # real-time chip health
vcgencmd measure_temp            # Pi5 CPU temp
free -h                          # RAM
journalctl -u aicamera_lpr.service -n 100 --no-pager
```

---

## Files Likely Needing Inspection

| File | Why |
|---|---|
| `edge/src/components/detection_processor.py` | `perform_ocr()` implementation — the OCR return path |
| `edge/src/core/config.py` | OCR confidence thresholds, `AUTOFOCUS_TRIGGER_BEFORE_CAPTURE` flag |
| `edge/src/components/camera_handler.py` (refactored) | Hailo ABORT interaction |
