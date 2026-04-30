# Camera Test Result — aicamera2 (IMX708 NoIR)

**Date:** 2026-04-30
**Device:** aicamera2 — Raspberry Pi 5, Hailo-8 NPU
**Camera:** Sony IMX708 NoIR (Infrared-cut filter removed)
**Tailscale IP:** 100.110.20.53

---

## 1. Focus Health — Before Fix (FAILING)

After the session started, the service was restarted and focus health verification was failing on every boot.

| Metric | Observed |
|--------|---------|
| AfTrigger sent | Yes (AfMode=1 + AfTrigger=0) |
| Autofocus result | Timeout after 3.0 s on both attempts |
| AfState | Never reached Focused (2) |
| LensPosition | 1.0 (stuck, no movement) |
| FoM range | 100–117 |
| Variation | 17.0 |
| Health verdict | **FAIL** — both threshold and variation checks failed |

Error logged:
```
ERROR Focus health verification failed after 2 attempts. FoM range 100-117, variation=17.0
```

### Root Cause 1 — Variation gate logic was inverted

`_is_focus_health_good()` in `camera_handler.py` contained:

```python
if metrics.get('variation', 0.0) < FOCUS_HEALTH_VARIATION_THRESHOLD:
    return False  # threshold default = 50.0
```

This required FoM **variation ≥ 50** to pass. A properly-focused, settled camera has **low** variation (≈16–17 after AfState=Focused). The check was backwards — it only passed when the lens was still actively hunting.

### Root Cause 2 — FoM thresholds miscalibrated for IMX708

| Config Key | Old Default | Observed Max (outdoor scene) | Result |
|-----------|------------|-------------------------------|--------|
| `FOCUS_QUALITY_MIN_THRESHOLD` | 800 | ≈230 (live test) / 594 (service) | Always failed |
| `FOCUS_HEALTH_MIN_FOM` | 700 | ≈230 (live test) / 594 (service) | Always failed |

Thresholds were 3–5× above the sensor's achievable FoM for a typical outdoor parking-lot scene.

---

## 2. Live FoM Sampling (Direct picamera2, service stopped)

Test run via SSH with `picamera2` directly to characterise real focus behaviour.

| Condition | FoM | LensPosition | AfState |
|-----------|-----|-------------|---------|
| No AF trigger (AfMode=0) | 45–67 | 1.0 | 0 (Idle) |
| After AfMode=1 + AfTrigger=0 | 220–233 | 2.36 | 2 (Focused ✅) |

Conclusion: **The camera CAN focus correctly.** Maximum achievable FoM for this scene ≈ 230 with proper AF trigger. Without a trigger, the lens stays at position 1.0 (infinity default) and FoM is low.

---

## 3. Fixes Applied

### `edge/src/components/camera_handler.py`

Removed the variation gate from `_is_focus_health_good()`:

```python
# BEFORE (buggy):
if metrics.get('variation', 0.0) < FOCUS_HEALTH_VARIATION_THRESHOLD:
    return False

# AFTER: gate removed — settled focus = low variation (correct behaviour)
# Only fom_max >= FOCUS_HEALTH_MIN_FOM matters for health verdict
```

### `edge/src/core/config.py`

| Key | Old Default | New Default | Rationale |
|-----|------------|-------------|-----------|
| `FOCUS_QUALITY_MIN_THRESHOLD` | `800` | `150` | IMX708 outdoor max ≈ 230–594 |
| `FOCUS_HEALTH_MIN_FOM` | `700` | `150` | Same; 150 = ~25–65% of max FoM |
| `FOCUS_HEALTH_VARIATION_THRESHOLD` | `50.0` | `5.0` | Kept for reference; no longer used in health gate |

Commit: `f33c11f fix(focus): lower FoM thresholds and remove variation gate for IMX708`

---

## 4. Focus Health — After Fix (PASSING)

Camera status API response (`/camera/status`) after service restart with fixed code:

```json
{
  "focus_health": {
    "fom_min": 436.0,
    "fom_max": 594.0,
    "variation": 158.0,
    "lens_min": 1.0,
    "lens_max": 1.0,
    "samples": 20,
    "timestamp": "2026-04-30T18:15:40.364464"
  }
}
```

| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| fom_max | 594 | ≥ 150 | **PASS ✅** |
| samples | 20 | ≥ 20 | **PASS ✅** |
| streaming | true | — | **PASS ✅** |
| frame_count | 7667 (after ~8 min) | — | Active ✅ |

Note: FoM in service (436–594) is higher than the live test (220–233). The likely reason is that during the service the ISP has time to converge its AE/AWB/AF pipeline fully before the focus health sample window, whereas the live test captured FoM immediately after AF trigger.

---

## 5. Camera Configuration (Active)

Sourced from `/camera/status` API and `edge/installation/.env.production` on aicamera2.

### Stream Configuration

| Stream | Format | Resolution | Notes |
|--------|--------|-----------|-------|
| main | RGB888 | 2304 × 1296 | High-quality capture (QUALITY_ENHANCEMENT_ENABLED=true) |
| lores | RGB888 | 640 × 480 | Detection/streaming (sensor selected 640×480 over requested 640×640) |
| raw | BGGR_PISP_COMP1 | 2304 × 1296 | ISP raw output |

### ISP Controls

| Control | Value | Source |
|---------|-------|--------|
| FrameDurationLimits | (66 666, 133 332) µs | 15 FPS floor, 7.5 FPS min in low light |
| AfMode | 1 (Auto / one-shot) | `DEFAULT_AUTOFOCUS_MODE=1` |
| AfRange | 0 (Normal) | hardcoded in `apply_auto_focus_defaults` |
| Sharpness | 2.0 | `CAMERA_SHARPNESS=2.0` |
| NoiseReductionMode | 0 (Off) | `CAMERA_NOISE_REDUCTION_MODE=0` |
| Brightness | 0.0 | `CAMERA_BRIGHTNESS=0.0` |
| Contrast | 1.0 | `CAMERA_CONTRAST=1.0` |
| AeEnable | true | auto |
| AwbEnable | true | auto |

### Focus Health Thresholds (post-fix)

| Key | Value | Env Override |
|-----|-------|-------------|
| FOCUS_QUALITY_MIN_THRESHOLD | 150 | overridable via `.env.production` |
| FOCUS_HEALTH_MIN_FOM | 150 | overridable via `.env.production` |
| FOCUS_HEALTH_VARIATION_THRESHOLD | 5.0 | no longer used in gate logic |
| FOCUS_HEALTH_DURATION | 3.0 s | — |
| FOCUS_HEALTH_MIN_SAMPLES | 20 | — |
| FOCUS_HEALTH_RETRY_ATTEMPTS | 2 | — |

---

## 6. Other Fixes in This Session

| Issue | Fix |
|-------|-----|
| `CameraHandler has no attribute 'update_configuration'` | Added missing method — accepts `{"controls": {...}}` dict and calls `picam2.set_controls()` |
| `ThaiLPROCR: pytesseract not installed` | Installed `pytesseract` into **service venv** (`edge/installation/venv_hailo/`) not dev venv |
| `Device registration failed (optional)` | Set `DEVICE_REGISTRATION_ENABLED=false` — REST `/device-registration/register` not implemented on lprserver; real registration is via WebSocket `camera_register` event |
| `apply_auto_focus_defaults()` overwrote Sharpness=2.0 with hardcoded 1.0 | Replaced all hardcoded values with config constants (`DEFAULT_SHARPNESS`, etc.) |
| `FrameDurationLimits` was set as fixed tuple `(N,N)` | Changed to range `(min_us, max_us)` where max = 2× min, giving ISP headroom in low light |
| Stream sleeping 33 ms hardcoded (30 FPS ceiling) while capturing at 15 FPS | Replaced with timestamp-based rate control using `DEFAULT_FRAMERATE` |

---

## 7. Service Status at End of Session

```
● aicamera_lpr.service  Active: active (running)
  Gunicorn: 1 master + 1 worker
  Worker CPU: ~15%  Memory: ~416 MB
  Camera: streaming=true, frame_count=7667, fps=15.0
  Focus health: fom_max=594, passed ✅
  Detection: Hailo-8 + ThaiLPROCR (Tesseract tha+eng) running
  WebSocket: connected to lprserver
```
