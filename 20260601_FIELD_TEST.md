# Field Test Report — AI Camera LPR System
**Date:** 2026-06-01  
**Location:** TBD  
**Tester:** PWD Vision Works  
**Status:** 🟡 In Progress

---

## 1. Test Objectives

Validate the full end-to-end pipeline under real-world conditions:

```
Camera Frame Capture
    → Vehicle Detection (Hailo NPU)
    → Plate Detection (Hailo NPU)
    → OCR Pipeline (DualBranch/Tesseract)
    → Async OCR Queue Worker
    → WebSocket send (detection + image)
    → MQTT publish (health)
    → ws-service receive → backend-api → PostgreSQL
    → Frontend UI display
```

---

## 2. Test Environment

### 2.1 Hardware

| Device | Role | Camera | Tailscale IP | Status |
|--------|------|--------|-------------|--------|
| aicamera1 | Primary detection | IMX708 (color) | 100.126.178.74 | ☐ Ready |
| aicamera2 | Secondary / NoIR | IMX708 NoIR | 100.110.20.53  | ☐ Ready |
| lprserver | Server + DB + UI | — | 100.95.46.128  | ☐ Ready |

### 2.2 Software Versions

```bash
# Record before test — run on each device
# Edge (aicamera1 / aicamera2):
git -C ~/aicamera log --oneline -1
python3 --version
source ~/aicamera/edge/venv_hailo/bin/activate && python -c "import degirum; print(degirum.__version__)"
tesseract --version | head -1

# lprserver:
git -C ~/aicamera log --oneline -1
node --version
psql -U lpruser -d aicamera_app -c "SELECT COUNT(*) FROM detections;"
```

**aicamera1 commit:** `___________________________________________`  
**aicamera2 commit:** `___________________________________________`  
**lprserver commit:**  `___________________________________________`  

### 2.3 Configuration Checklist

**aicamera1 `.env.production`:**
- [ ] `AICAMERA_ID=1`
- [ ] `CAMERA_NAME=aicamera1`
- [ ] `CAMERA_LOCATION=` ___________________
- [ ] `CAMERA_IP=100.126.178.74`
- [ ] `WEBSOCKET_SERVER_URL=http://lprserver.tail605477.ts.net/ws/`
- [ ] `MQTT_BROKER_HOST=lprserver.tail605477.ts.net`
- [ ] `HEALTH_SENDER_INTERVAL=300`

**aicamera2 `.env.production`:**
- [ ] `AICAMERA_ID=2`
- [ ] `CAMERA_NAME=aicamera2`
- [ ] `CAMERA_LOCATION=` ___________________
- [ ] `CAMERA_IP=100.110.20.53`
- [ ] `WEBSOCKET_SERVER_URL=http://lprserver.tail605477.ts.net/ws/`
- [ ] `MQTT_BROKER_HOST=lprserver.tail605477.ts.net`
- [ ] `HEALTH_SENDER_INTERVAL=300`

---

## 3. Pre-Test System Check

Run these before driving begins. Record pass ✅ / fail ❌ / skip ➖.

### 3.1 Network Connectivity

```bash
# From each camera:
tailscale ping lprserver
tailscale ping aicamera1   # from aicamera2
tailscale ping aicamera2   # from aicamera1

# From lprserver:
curl -s http://localhost:3000/server/api/cameras | python3 -m json.tool | head -20
ss -tlnp | grep -E '3000|3001|1883|5432'
```

| Check | aicamera1 | aicamera2 | lprserver |
|-------|-----------|-----------|-----------|
| Tailscale ping lprserver | ☐ | ☐ | — |
| API /cameras returns data | — | — | ☐ |
| Ports 3000/3001/1883/5432 open | — | — | ☐ |

### 3.2 Service Status

```bash
# Edge:
sudo systemctl status aicamera_lpr.service
journalctl -u aicamera_lpr.service -n 30 --no-pager

# lprserver:
pm2 list   # or: sudo systemctl status backend-api ws-service mqtt-service
sudo systemctl status nginx
```

| Service | aicamera1 | aicamera2 | lprserver |
|---------|-----------|-----------|-----------|
| aicamera_lpr.service | ☐ active | ☐ active | — |
| backend-api :3000 | — | — | ☐ active |
| ws-service :3001 | — | — | ☐ active |
| mqtt-service | — | — | ☐ active |
| nginx | — | — | ☐ active |

### 3.3 Model Loading

```bash
# From edge service log — look for these lines:
# [DetectionProcessor] ✅ Vehicle model loaded
# [DetectionProcessor] ✅ LP detection model loaded
# [DualBranchDegirumOCR] ✅ Model loaded   (or ThaiLPROCR initialized)
# [OcrQueueWorker] ✅ Worker started
journalctl -u aicamera_lpr.service | grep -E "loaded|started|ERROR|WARN"
```

| Model | aicamera1 | aicamera2 |
|-------|-----------|-----------|
| Vehicle detection model | ☐ | ☐ |
| LP detection model | ☐ | ☐ |
| OCR model (Dual/Hailo) | ☐ | ☐ |
| ThaiLPROCR (Tesseract) | ☐ | ☐ |
| OCR queue worker | ☐ | ☐ |

### 3.4 Camera Stream

```bash
# Check FPS and resolution in log:
journalctl -u aicamera_lpr.service | grep -E "fps|FPS|resolution|frame"

# Or check health endpoint:
curl http://aicamera1.tail605477.ts.net:5000/health/ 2>/dev/null | python3 -m json.tool
curl http://aicamera2.tail605477.ts.net:5000/health/ 2>/dev/null | python3 -m json.tool
```

| Parameter | aicamera1 | aicamera2 | Expected |
|-----------|-----------|-----------|----------|
| FPS | | | 30 |
| Resolution | | | 1920×1080 |
| Health status | | | healthy |

### 3.5 WebSocket Registration

```bash
# lprserver — check camera registered:
curl -s http://localhost:3000/server/api/cameras | python3 -m json.tool
# Expect: cameras with cameraId "1" and "2", status active
```

| Camera | Registered in DB | cameraId correct | status |
|--------|-----------------|------------------|--------|
| aicamera1 | ☐ | ☐ `1` | |
| aicamera2 | ☐ | ☐ `2` | |

---

## 4. Test Scenarios

### Setup for each run
- Note exact plate number of test vehicle before each pass
- Record time of pass (HH:MM:SS)
- Use UI live feed at `http://lprserver.tail605477.ts.net/server/` to observe in real time

---

### Scenario A — Single Vehicle, Low Speed (~10 km/h)

> Simulates parking lot / gate entry. Camera has max time to process.

| Run | Time | Actual Plate | cam1 Detected | cam1 OCR Result | cam1 Correct? | cam2 Detected | cam2 OCR Result | cam2 Correct? | Notes |
|-----|------|-------------|---------------|----------------|:-------------:|---------------|----------------|:-------------:|-------|
| A-1 | | | ☐ | | ☐ | ☐ | | ☐ | |
| A-2 | | | ☐ | | ☐ | ☐ | | ☐ | |
| A-3 | | | ☐ | | ☐ | ☐ | | ☐ | |
| A-4 | | | ☐ | | ☐ | ☐ | | ☐ | |
| A-5 | | | ☐ | | ☐ | ☐ | | ☐ | |

**A Summary:** Detected ___/5 · OCR correct ___/5 detected

---

### Scenario B — Single Vehicle, Medium Speed (~30 km/h)

> Simulates normal road entry.

| Run | Time | Actual Plate | cam1 Detected | cam1 OCR Result | cam1 Correct? | cam2 Detected | cam2 OCR Result | cam2 Correct? | Notes |
|-----|------|-------------|---------------|----------------|:-------------:|---------------|----------------|:-------------:|-------|
| B-1 | | | ☐ | | ☐ | ☐ | | ☐ | |
| B-2 | | | ☐ | | ☐ | ☐ | | ☐ | |
| B-3 | | | ☐ | | ☐ | ☐ | | ☐ | |
| B-4 | | | ☐ | | ☐ | ☐ | | ☐ | |
| B-5 | | | ☐ | | ☐ | ☐ | | ☐ | |

**B Summary:** Detected ___/5 · OCR correct ___/5 detected

---

### Scenario C — Single Vehicle, Higher Speed (~60 km/h)

> Stress test for async OCR queue and frame buffering.

| Run | Time | Actual Plate | cam1 Detected | cam1 OCR Result | cam1 Correct? | cam2 Detected | cam2 OCR Result | cam2 Correct? | Notes |
|-----|------|-------------|---------------|----------------|:-------------:|---------------|----------------|:-------------:|-------|
| C-1 | | | ☐ | | ☐ | ☐ | | ☐ | |
| C-2 | | | ☐ | | ☐ | ☐ | | ☐ | |
| C-3 | | | ☐ | | ☐ | ☐ | | ☐ | |

**C Summary:** Detected ___/3 · OCR correct ___/3 detected

---

### Scenario D — Multiple Vehicle Types / Plate Styles

> Validate OCR across different plate formats.

| Run | Time | Plate Type | Actual Plate | cam1 OCR | Correct? | cam2 OCR | Correct? | Notes |
|-----|------|-----------|-------------|----------|:--------:|----------|:--------:|-------|
| D-1 | | Standard white | | | ☐ | | ☐ | |
| D-2 | | Old style (yellow) | | | ☐ | | ☐ | |
| D-3 | | Motorcycle | | | ☐ | | ☐ | |
| D-4 | | Government | | | ☐ | | ☐ | |
| D-5 | | Bangkok prov. | | | ☐ | | ☐ | |
| D-6 | | Upcountry prov. | | | ☐ | | ☐ | |

**D Summary:** Correct ___/6

---

### Scenario E — Night / Low Light (aicamera2 NoIR)

> Run after sunset. aicamera2 (NoIR) expected to perform better.

| Run | Time | Light Condition | cam1 Detected | cam1 OCR | cam2 Detected | cam2 OCR | Notes |
|-----|------|----------------|---------------|----------|---------------|----------|-------|
| E-1 | | Dusk | ☐ | | ☐ | | |
| E-2 | | Dark + street lamp | ☐ | | ☐ | | |
| E-3 | | Dark + headlights | ☐ | | ☐ | | |

**E Summary:** cam1 Detected ___/3 · cam2 Detected ___/3

---

## 5. Pipeline Latency Measurement

For 5 consecutive detections, record timestamps from logs:

```bash
# Edge log — note T1 (frame captured) and T2 (detection saved to edge DB)
journalctl -u aicamera_lpr.service | grep -E "detection|saved|sent" | tail -20

# lprserver — note T3 (ws-service received) and T4 (stored in PostgreSQL)
# Check backend-api log or:
psql -U lpruser -d aicamera_app \
  -c "SELECT license_plate, timestamp, created_at, created_at - timestamp AS latency \
      FROM detections ORDER BY created_at DESC LIMIT 10;"
```

| Detection | T1 Frame | T2 Edge DB | T3 WS Receive | T4 PostgreSQL | T1→T4 Latency |
|-----------|----------|-----------|---------------|---------------|---------------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| **Avg** | | | | | |

---

## 6. System Health During Test

Record at start, midpoint, and end of test session.

```bash
# Edge:
vcgencmd measure_temp            # CPU temperature
top -bn1 | grep "Cpu(s)"         # CPU usage
free -m | grep Mem               # RAM
df -h /                          # Disk

# Or from health endpoint:
curl -s http://aicamera1.tail605477.ts.net:5000/health/ | python3 -m json.tool
```

| Metric | cam1 Start | cam1 Mid | cam1 End | cam2 Start | cam2 Mid | cam2 End |
|--------|-----------|---------|---------|-----------|---------|---------|
| CPU Temp (°C) | | | | | | |
| CPU Usage (%) | | | | | | |
| RAM Used (MB) | | | | | | |
| Disk Free (%) | | | | | | |
| Avg FPS | | | | | | |
| OCR Queue drops | | | | | | |

```bash
# Check OCR queue drops:
journalctl -u aicamera_lpr.service | grep "OCR_QUEUE_DROP" | wc -l
```

---

## 7. Database Verification

After all passes, verify records in PostgreSQL:

```bash
ssh devuser@lprserver

# Total detections recorded during test session:
psql -U lpruser -d aicamera_app -c "
  SELECT c.camera_id, COUNT(*) as count, 
         MIN(d.timestamp) as first, MAX(d.timestamp) as last
  FROM detections d JOIN cameras c ON d.camera_id = c.id
  WHERE d.timestamp >= NOW() - INTERVAL '4 hours'
  GROUP BY c.camera_id ORDER BY c.camera_id;"

# Check for null/empty plates:
psql -U lpruser -d aicamera_app -c "
  SELECT COUNT(*) as total,
         COUNT(CASE WHEN license_plate IS NULL OR license_plate = '' THEN 1 END) as empty_plates,
         COUNT(CASE WHEN image_path IS NOT NULL THEN 1 END) as with_image
  FROM detections
  WHERE timestamp >= NOW() - INTERVAL '4 hours';"

# Sample results:
psql -U lpruser -d aicamera_app -c "
  SELECT d.license_plate, d.confidence, d.timestamp, c.camera_id
  FROM detections d JOIN cameras c ON d.camera_id = c.id
  WHERE d.timestamp >= NOW() - INTERVAL '4 hours'
  ORDER BY d.timestamp DESC LIMIT 20;"
```

| Metric | cam1 | cam2 | Total |
|--------|------|------|-------|
| Total detections stored | | | |
| Detections with image | | | |
| Empty/null plates | | | |
| Expected passes (from log) | | | |
| DB coverage (stored/expected) | | | |

---

## 8. UI Verification

Open `http://lprserver.tail605477.ts.net/server/` and check each page:

| Page | Check | Result |
|------|-------|--------|
| Dashboard | Live badge shows ● LIVE | ☐ |
| Dashboard | Both cameras show green status dot | ☐ |
| Dashboard | Detection feed updates in real time | ☐ |
| Dashboard | 24h chart shows today's bars | ☐ |
| Camera List | aicamera1 online, health data visible | ☐ |
| Camera List | aicamera2 online, health data visible | ☐ |
| Camera Detail (cam1) | Health log populates | ☐ |
| Camera Detail (cam1) | Detection table shows recent detections | ☐ |
| Detection List | All test detections visible | ☐ |
| Detection List | Plate text readable | ☐ |
| Detection Detail | Image loads correctly | ☐ |
| Detection Detail | Confidence score shown | ☐ |

---

## 9. Observed Issues Log

Record every issue encountered during the test, no matter how small.

| # | Time | Component | Description | Severity | Reproducible? |
|---|------|-----------|-------------|:--------:|:-------------:|
| 1 | | | | | ☐ |
| 2 | | | | | ☐ |
| 3 | | | | | ☐ |
| 4 | | | | | ☐ |
| 5 | | | | | ☐ |

**Severity:** 🔴 Critical (pipeline broken) · 🟠 High (data loss) · 🟡 Medium (degraded accuracy) · 🟢 Low (cosmetic)

---

## 10. Test Summary

### 10.1 Detection Accuracy

| Scenario | Passes | Detected | Detection Rate | OCR Correct | OCR Accuracy |
|----------|--------|----------|:--------------:|-------------|:------------:|
| A — Low speed | 5 | | | | |
| B — Med speed | 5 | | | | |
| C — High speed | 3 | | | | |
| D — Plate types | 6 | | | | |
| E — Night | 3 | | | | |
| **TOTAL** | **22** | | | | |

### 10.2 Pipeline Reliability

| Component | Status | Notes |
|-----------|:------:|-------|
| Camera stream (30 fps stable) | ☐ | |
| Vehicle detection | ☐ | |
| Plate detection | ☐ | |
| Hailo OCR | ☐ | |
| Tesseract Thai OCR | ☐ | |
| Async OCR queue (no drops) | ☐ | |
| WebSocket connection stable | ☐ | |
| MQTT health publish | ☐ | |
| DB storage (no missing records) | ☐ | |
| Image storage | ☐ | |
| UI real-time update | ☐ | |

### 10.3 Overall Result

| Area | Score | Target |
|------|:-----:|:------:|
| Detection rate | ___% | ≥ 80% |
| OCR accuracy (detected) | ___% | ≥ 70% |
| End-to-end latency avg | ___ s | ≤ 5 s |
| System stability (no crash) | ☐ | ✅ |

---

## 11. Improvement Plan

> Fill in after reviewing results.

### 11.1 Priority Issues

| Priority | Issue | Root Cause (hypothesis) | Proposed Fix | Target |
|:--------:|-------|------------------------|-------------|--------|
| P1 | | | | |
| P2 | | | | |
| P3 | | | | |

### 11.2 OCR Improvement Ideas

- [ ] Tune confidence threshold (current: _____)
- [ ] Adjust plate crop ROI zone
- [ ] Try different PSM mode for Tesseract (current: PSM 11)
- [ ] Increase `_ocr_min_plate_frames` buffer (current: 3)
- [ ] Evaluate DualBranchLPRNet accuracy vs Tesseract
- [ ] Collect misread plates for retraining dataset

### 11.3 Pipeline Improvement Ideas

- [ ] Reduce OCR queue drop rate (increase maxsize from 10?)
- [ ] Tune `_ocr_min_frame_score` Laplacian threshold (current: 0.3)
- [ ] Adjust async OCR queue `plate_crop_buffer` maxlen (current: 5)
- [ ] Review FPS stability under load
- [ ] Add deduplication window tuning

### 11.4 Infrastructure Improvement Ideas

- [ ] Add IR illuminator for aicamera2 night performance
- [ ] Adjust camera angle / mounting height
- [ ] Test with different vehicle speeds
- [ ] Add second test vehicle with different plate style

---

## 12. Appendix — Quick Command Reference

```bash
# SSH into devices
ssh camuser@aicamera1          # password: (see CLAUDE.md)
ssh camuser@aicamera2
ssh devuser@lprserver

# Watch live edge logs
journalctl -u aicamera_lpr.service -f

# Watch live backend logs (lprserver)
journalctl -u backend-api -f   # or: pm2 logs backend-api

# Real-time detection count
watch -n 2 'psql -U lpruser -d aicamera_app -t -c \
  "SELECT COUNT(*) FROM detections WHERE timestamp >= NOW() - INTERVAL '"'"'1 hour'"'"';"'

# Check WebSocket connections
ss -tnp | grep 3001

# Restart edge service
sudo systemctl restart aicamera_lpr.service

# Restart all lprserver services
pm2 restart all   # or systemctl restart for each
```

---

*Document created: 2026-06-01 | PWD Vision Works*
