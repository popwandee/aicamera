# Field Test — Pipeline Diagnostic & Latency Measurement
**Date:** 2026-06-10  
**Location:** Gate / Driveway — PWD Vision Works  
**Tester:** PWD Vision Works  
**Status:** 🟠 In Progress — multiple bugs found and fixed during session

---

## Objective

Full diagnostic inspection of each pipeline stage after recent fixes. Measure latency per stage, verify tracking/dedup, ROI gating, and OCR success rate.  
This is a **diagnostic test** — every pipeline token will be recorded and analysed.

### Fixes applied before this test

| Fix | Commit | Detail |
|-----|--------|--------|
| `_ocr_min_plate_frames` 3→1 | `e030736` | Fast vehicles no longer skipped at OCR gate |
| ROI reset to disabled | — | ROI `enabled=false` persisted; was blocking 06:40 field test |
| FRAME_MISMATCH | earlier | `enhanced_frame` saved instead of `best_frame_data` |
| `DETECTION_INTERVAL` 30→0.1 | earlier | Tracking update interval was 30 s, now 0.1 s |
| `_ocr_min_frame_score` | earlier | Quality gate at 0.3 (Laplacian variance) |

---

## 1. Pre-Test System State

### 1.1 Software Version on Each Device

```bash
# Run on aicamera1 and aicamera2
git -C ~/aicamera log --oneline -1
python3 --version
tesseract --version 2>&1 | head -1
sudo systemctl is-active aicamera_lpr.service
```

| Item | aicamera1 | aicamera2 | Expected |
|------|-----------|-----------|----------|
| Git commit | | | `e030736` or later |
| Python | | | 3.11.x |
| Tesseract | | | 5.x |
| Service status | | | active (running) |

Last login: Tue Jun  9 18:53:22 2026
camuser@aicamera1:~ $ git -C ~/aicamera log --oneline -1
e030736 (HEAD -> main, origin/main, origin/HEAD) fix(ocr): lower _ocr_min_plate_frames 3 → 1 to fix no-OCR on fast vehicles
camuser@aicamera1:~ $ python3 --version
Python 3.11.2
camuser@aicamera1:~ $ tesseract --version 2>&1 | head -1
tesseract 5.3.0
camuser@aicamera1:~ $ sudo systemctl is-active aicamera_lpr.service
active

Last login: Tue Jun  9 18:50:56 2026
camuser@aicamera2:~ $ git -C ~/aicamera log --oneline -1
e030736 (HEAD -> main) fix(ocr): lower _ocr_min_plate_frames 3 → 1 to fix no-OCR on fast vehicles
camuser@aicamera2:~ $ python3 --version
Python 3.11.2
camuser@aicamera2:~ $ tesseract --version 2>&1 | head -1
tesseract 5.3.0
camuser@aicamera2:~ $ sudo systemctl is-active aicamera_lpr.service
active

### 1.2 Configuration Verification

```bash
# On each camera — check all critical env vars
grep -E "DETECTION_INTERVAL|ROI_ENABLED|CAMERA_FPS|OCR_MIN|DEDUP|AICAMERA_ID" \
     ~/aicamera/edge/installation/.env.production
```

| Config | aicamera1 | aicamera2 | Expected |
|--------|-----------|-----------|----------|
| `DETECTION_INTERVAL` | | | `0.1` |
| `CAMERA_FPS` | | | `30` |
| `ROI_ENABLED` | | | `false` (or absent) |
| `AICAMERA_ID` | | | `1` / `2` |

camuser@aicamera1:~ $ grep -E "DETECTION_INTERVAL|ROI_ENABLED|CAMERA_FPS|OCR_MIN|DEDUP|AICAMERA_ID" \
     ~/aicamera/edge/installation/.env.production
#AICAMERA_ID       — unique integer (1 for aicamera1, 2 for aicamera2)
#CHECKPOINT_ID     — same as AICAMERA_ID unless you have separate checkpoints
AICAMERA_ID=1
CAMERA_FPS=30
DETECTION_INTERVAL=0.1
#- AICAMERA_ID / CHECKPOINT_ID (1 for aicamera1, 2 for aicamera2)
ROI_ENABLED=false

camuser@aicamera2:~ $ grep -E "DETECTION_INTERVAL|ROI_ENABLED|CAMERA_FPS|OCR_MIN|DEDUP|AICAMERA_ID"      ~/aicamera/edge/installation/.env.production
#AICAMERA_ID       — unique integer (1 for aicamera1, 2 for aicamera2)
#CHECKPOINT_ID     — same as AICAMERA_ID unless you have separate checkpoints
AICAMERA_ID=2
CAMERA_FPS=30
DETECTION_INTERVAL=0.1
#- AICAMERA_ID / CHECKPOINT_ID (1 for aicamera1, 2 for aicamera2)
ROI_ENABLED=false

### 1.3 Model and OCR Worker Startup

```bash
journalctl -u aicamera_lpr.service | grep -E "loaded|OCR_WORKER|ERROR" | tail -20
```

| Model/Component | aicamera1 | aicamera2 |
|----------------|-----------|-----------|
| Vehicle model loaded | ☐ | ☐ |
| LP detection model loaded | ☐ | ☐ |
| ThaiLPROCR / Tesseract init | ☐ | ☐ |
| `[OCR_WORKER] Started` | ☐ | ☐ |
 no results
### 1.4 ROI Status (critical — verify disabled)

```bash
curl -s http://aicamera1.tail605477.ts.net/detection/roi | python3 -m json.tool
curl -s http://aicamera2.tail605477.ts.net/detection/roi | python3 -m json.tool
```

Expected response: `"enabled": false`

| Camera | ROI enabled | x1/y1/x2/y2 | Notes |
|--------|:-----------:|-------------|-------|
| aicamera1 | ☐ false | | |
| aicamera2 | ☐ false | | |

camuser@aicamera1:~ $ curl -s http://aicamera1.tail605477.ts.net/detection/roi | python3 -m json.tool
{
    "roi": {
        "enabled": false,
        "x1": 0.1,
        "x2": 0.9,
        "y1": 0.2,
        "y2": 0.8
    },
    "success": true,
    "timestamp": "2026-06-10T14:22:10.906146"
}

camuser@aicamera2:~ $ curl -s http://aicamera2.tail605477.ts.net/detection/roi | python3 -m json.tool
{
    "roi": {
        "enabled": false,
        "x1": 0.1,
        "x2": 0.9,
        "y1": 0.2,
        "y2": 0.8
    },
    "success": true,
    "timestamp": "2026-06-10T14:18:48.868326"
}
### 1.5 Detection Status Baseline

```bash
curl -s http://aicamera1.tail605477.ts.net/detection/status | python3 -m json.tool
curl -s http://aicamera2.tail605477.ts.net/detection/status | python3 -m json.tool
```

Record before any vehicle passes:

| Counter | aicamera1 | aicamera2 |
|---------|-----------|-----------|
| `total_processed` | | |
| `successful_ocr` | | |
| `frames_processed` | | |
| `ocr_queue_drops` | | |

camuser@aicamera1:~ $ curl -s http://aicamera1.tail605477.ts.net/detection/status | python3 -m json.tool
{
    "detection_status": {
        "auto_start": true,
        "detection_accuracy": 0.5,
        "detection_interval": 0.1,
        "detection_processor_status": {
            "confidence_threshold": 0.8,
            "detection_resolution": [
                640,
                640
            ],
            "last_update": "2026-06-10T14:22:33.619618",
            "lp_detection_model_available": true,
            "lp_detection_model_name": "yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1",
            "lp_ocr_model_available": true,
            "lp_ocr_model_name": "yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1",
            "models_loaded": true,
            "plate_confidence_threshold": 0.5,
            "processing_stats": {
                "last_detection": null,
                "plates_detected": 1,
                "processing_time_ms": 19.04582977294922,
                "successful_ocr": 0,
                "total_processed": 8290,
                "vehicles_detected": 43
            },
            "tesseract_available": true,
            "vehicle_model_available": true,
            "vehicle_model_name": "yolov8n_relu6_car--640x640_quant_hailort_hailo8_1"
        },
        "last_update": "2026-06-10T14:22:33.619734",
        "ocr_accuracy": 0.0,
        "service_running": true,
        "statistics": {
            "failed_detections": 0,
            "last_detection": "2026-06-10T14:12:10.742221",
            "processing_time_avg": 0.1653587818145752,
            "started_at": "2026-06-10T14:05:16.627772",
            "successful_ocr": 0,
            "total_frames_processed": 8290,
            "total_plates_detected": 1,
            "total_vehicles_detected": 43
        },
        "system_reliability": 100.0,
        "thread_alive": true
    },
    "success": true,
    "timestamp": "2026-06-10T14:22:33.619768"
}

camuser@aicamera2:~ $ curl -s http://aicamera2.tail605477.ts.net/detection/status | python3 -m json.tool
{
    "detection_status": {
        "auto_start": true,
        "detection_accuracy": 0.7,
        "detection_interval": 0.1,
        "detection_processor_status": {
            "confidence_threshold": 0.8,
            "detection_resolution": [
                640,
                640
            ],
            "last_update": "2026-06-10T14:19:13.783212",
            "lp_detection_model_available": true,
            "lp_detection_model_name": "yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1",
            "lp_ocr_model_available": true,
            "lp_ocr_model_name": "yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1",
            "models_loaded": true,
            "plate_confidence_threshold": 0.5,
            "processing_stats": {
                "last_detection": null,
                "plates_detected": 1,
                "processing_time_ms": 18.231630325317383,
                "successful_ocr": 0,
                "total_processed": 6826,
                "vehicles_detected": 47
            },
            "tesseract_available": true,
            "vehicle_model_available": true,
            "vehicle_model_name": "yolov8n_relu6_car--640x640_quant_hailort_hailo8_1"
        },
        "last_update": "2026-06-10T14:19:13.783294",
        "ocr_accuracy": 0.0,
        "service_running": true,
        "statistics": {
            "failed_detections": 0,
            "last_detection": "2026-06-10T14:12:11.229573",
            "processing_time_avg": 0.13686323165893555,
            "started_at": "2026-06-10T14:05:15.020337",
            "successful_ocr": 0,
            "total_frames_processed": 6826,
            "total_plates_detected": 1,
            "total_vehicles_detected": 47
        },
        "system_reliability": 100.0,
        "thread_alive": true
    },
    "success": true,
    "timestamp": "2026-06-10T14:19:13.783325"
}
---

## 2. Live Log Monitor Setup

Open 2 SSH sessions per camera — one for structured pipeline tokens, one for raw tracking/dedup.

### Session A — Pipeline tokens

```bash
sudo journalctl -u aicamera_lpr.service -f | grep -E \
  "\[(VEHICLE|PLATE|PLATE_SKIP|PLATE_NONE|OCR_GATE|OCR_SUBMIT|OCR_START|OCR_RESULT|OCR_DONE|IMG_SAVE|DB_SAVE|PIPELINE_DONE)\]"
```

### Session B — Tracking & Dedup tokens

```bash
sudo journalctl -u aicamera_lpr.service -f | grep -E \
  "\[(TRACK_NEW|TRACK_UPDATE|TRACK_SAVED|TRACKING|DEDUP_BLOCK|DEDUP_SKIP|DEDUP_NEW|DEDUP_REENTRY|DEDUP_MATCH|DEDUP_CLEANUP)\]"
```

---

## 3. Inspection Test Runs

Record the **actual plate number** of each test vehicle before each pass.  
Perform each run one at a time. Allow 30 s between runs so dedup window resets.

### Test Run Table

| Run | Time | Speed | Actual Plate | cam1 `[OCR_GATE]` | cam1 OCR Text | cam1 Correct? | cam2 `[OCR_GATE]` | cam2 OCR Text | cam2 Correct? | Notes |
|-----|------|-------|-------------|:-----------------:|--------------|:-------------:|:-----------------:|--------------|:-------------:|-------|
| R01 | | ~10 km/h | | PASS/SKIP | | ☐ | PASS/SKIP | | ☐ | |
| R02 | | ~10 km/h | | | | ☐ | | | ☐ | |
| R03 | | ~30 km/h | | | | ☐ | | | ☐ | |
| R04 | | ~30 km/h | | | | ☐ | | | ☐ | |
| R05 | | ~30 km/h | | | | ☐ | | | ☐ | |
| R06 | | ~60 km/h | | | | ☐ | | | ☐ | |
| R07 | | ~60 km/h | | | | ☐ | | | ☐ | |
| R08 | | ~60 km/h | | | | ☐ | | | ☐ | |
| R09 | | Same plate ×2 fast | | | | ☐ | | | ☐ | dedup verify |
| R10 | | Same plate ×2 slow | | | | ☐ | | | ☐ | dedup verify |

---

## 4. Stage-by-Stage Inspection

### 4.1 Vehicle Detection

Log token: `[VEHICLE]`

For each run record:
- `conf` — vehicle confidence (should be ≥ 0.3 for detection)
- `bbox` — normalised coordinates (y2-y1 = vehicle height fraction of frame)
- `size` — WxH pixels of crop

```bash
# Extract vehicle confidence from log
grep "\[VEHICLE\]" aicamera.log | awk '{for(i=1;i<=NF;i++) if($i~/conf=/) print NR, $i}'
```

| Run | cam1 conf | cam1 bbox | cam2 conf | cam2 bbox | Notes |
|-----|-----------|-----------|-----------|-----------|-------|
| R01 | | | | | |
| R02 | | | | | |
| R03 | | | | | |

**Threshold:** `VEHICLE_CONFIDENCE_THRESHOLD` (default 0.3). Any `[PLATE_NONE]` where vehicle conf ≥ 0.5 is a plate detection miss.

### 4.2 Plate Detection

Log tokens: `[PLATE]`, `[PLATE_SKIP]`, `[PLATE_NONE]`

```bash
grep -E "\[(PLATE|PLATE_SKIP|PLATE_NONE)\]" aicamera.log | tail -30
```

| Run | cam1 plate_conf | cam1 size WxH | cam1 aspect | cam2 plate_conf | cam2 size | Token |
|-----|:--------------:|:-------------:|:-----------:|:--------------:|:---------:|-------|
| R01 | | | | | | `[PLATE]` |
| R02 | | | | | | |

**Check:**
- [ ] `[PLATE_SKIP]` count = 0 (no plates filtered below threshold)
- [ ] `[PLATE_NONE]` only on distant vehicles (expected)
- [ ] Aspect ratio 2.0–4.5 (Thai standard plate); out-of-range → crop issue

### 4.3 OCR Gate

Log token: `[OCR_GATE]`

This is the most important gate — records WHY OCR was submitted or skipped.

```bash
grep "\[OCR_GATE\]" aicamera.log
```

Expected after `e030736` fix: `PASS` for all runs where plate detected.  
`SKIP` is expected only for: `blur_score < 0.3` (very blurred image) or ROI miss (if ROI enabled).

| Run | cam1 result | cam1 reason | cam2 result | cam2 reason |
|-----|:-----------:|-------------|:-----------:|-------------|
| R01 | PASS/SKIP | | PASS/SKIP | |
| R03 | | | | |
| R06 | | | | |

```bash
# Summary of SKIP reasons across all runs
grep "OCR_GATE.*SKIP" aicamera.log | sed 's/.*SKIP/SKIP/' | sort | uniq -c | sort -rn
```

| SKIP reason | cam1 count | cam2 count |
|-------------|:----------:|:----------:|
| `plate_frames < min` | | |
| `blur_score below threshold` | | |
| `outside ROI` | | |
| `no plate candidates` | | |

### 4.4 OCR Queue & Worker

Log tokens: `[OCR_SUBMIT]`, `[OCR_START]`, `[OCR_RESULT]`, `[OCR_DONE]`

```bash
grep -E "\[(OCR_SUBMIT|OCR_START|OCR_RESULT|OCR_DONE)\]" aicamera.log | tail -40
```

**Queue depth at submit** — should stay low (< 5); drops indicate queue full:

```bash
grep "OCR_SUBMIT" aicamera.log | awk '{for(i=1;i<=NF;i++) if($i~/queue=/) print $i}'
grep "OCR_QUEUE_DROP" aicamera.log | wc -l
```

| Metric | cam1 | cam2 | Target |
|--------|:----:|:----:|:------:|
| Total `[OCR_SUBMIT]` | | | = detected plates |
| Total `[OCR_RESULT]` | | | = submitted |
| `OCR_QUEUE_DROP` count | | | 0 |
| Queue depth at submit (max) | | | < 5 |

### 4.5 OCR Result Quality

Log token: `[OCR_RESULT]`

```bash
grep "\[OCR_RESULT\]" aicamera.log
```

Each result line should contain: `text=`, `valid=True/False`, `conf=`, `preprocess_ms=`, `tesseract_ms=`

| Run | cam1 text | cam1 valid | cam1 conf | cam2 text | cam2 valid | cam2 conf |
|-----|-----------|:---------:|:---------:|-----------|:---------:|:---------:|
| R01 | | | | | | |
| R02 | | | | | | |
| R03 | | | | | | |

**Validate Thai plate format:** `X XX nnnn` or `XX nnnn` + province name.

### 4.6 Image Save & DB Save

Log tokens: `[IMG_SAVE]`, `[DB_SAVE]`, `[PIPELINE_DONE]`

```bash
grep -E "\[(IMG_SAVE|DB_SAVE|PIPELINE_DONE)\]" aicamera.log | tail -30
```

| Metric | cam1 | cam2 | Target |
|--------|:----:|:----:|:------:|
| `[IMG_SAVE]` count | | | = detections |
| Max `write_ms` | | | < 500 ms |
| `[DB_SAVE]` count | | | = detections |
| Max `db_ms` | | | < 100 ms |

---

## 5. Latency Measurement

Record per-stage latency for 5 consecutive detections.

### 5.1 Log Token Timestamps

For each detection, extract timestamps from log (ISO format or ms offsets):

```bash
# Extract full pipeline timing for each detection
grep -E "\[(OCR_GATE|OCR_SUBMIT|OCR_START|OCR_RESULT|OCR_DONE|IMG_SAVE|DB_SAVE|PIPELINE_DONE)\]" \
     aicamera.log | grep -A 20 "R0[123]" | head -60
```

### 5.2 Stage Latency Table

| Detection | Hailo infer (ms) | OCR queue wait (ms) | Tesseract (ms) | preprocess (ms) | img write (ms) | db write (ms) | pipeline total (ms) |
|-----------|:----------------:|:-------------------:|:--------------:|:---------------:|:--------------:|:-------------:|:-------------------:|
| D1 | | | | | | | |
| D2 | | | | | | | |
| D3 | | | | | | | |
| D4 | | | | | | | |
| D5 | | | | | | | |
| **Avg** | | | | | | | |
| **Max** | | | | | | | |

```bash
# Aggregate from log
grep "OCR_RESULT" aicamera.log | awk '{for(i=1;i<=NF;i++) if($i~/tesseract=/) print $i}'
grep "IMG_SAVE"   aicamera.log | awk '{for(i=1;i<=NF;i++) if($i~/write=/)     print $i}'
grep "PIPELINE_DONE" aicamera.log | awk '{for(i=1;i<=NF;i++) if($i~/total=/) print $i}'
```

**Target latencies:**

| Stage | Target |
|-------|--------|
| Hailo inference (vehicle + plate) | < 100 ms |
| OCR queue wait | < 200 ms |
| Tesseract preprocess | < 50 ms |
| Tesseract OCR | < 2000 ms |
| Image write | < 500 ms |
| DB insert | < 100 ms |
| **End-to-end pipeline** | **< 3000 ms** |

---

## 6. Tracking & Deduplication Inspection

### 6.1 Normal Single-Vehicle Flow

Expected token sequence per vehicle pass:

```
[TRACK_NEW]    track=N  conf=0.xx bbox=... — new track created
[TRACK_UPDATE] track=N  frame_count=2 plate_candidates=1
[TRACK_UPDATE] track=N  frame_count=3 ...
[OCR_GATE]     PASS     track=N blur=0.xx
[OCR_SUBMIT]   track=N  crop=WxH queue=1
[TRACK_SAVED]  track=N  plate='กข 1234 กรุงเทพ' db_id=NNN
[DEDUP_BLOCK]  track=N  iou=0.xx time=x.xs  (subsequent frames of same pass)
[DEDUP_SKIP]   All 1 vehicle(s) are duplicates
```

Verify this pattern appears for each run. Missing `[TRACK_SAVED]` = DB insert failure.

```bash
grep -E "\[(TRACK_NEW|TRACK_UPDATE|TRACK_SAVED|DEDUP_BLOCK|DEDUP_SKIP)\]" aicamera.log | tail -50
```

| Run | TRACK_NEW | TRACK_UPDATE count | TRACK_SAVED | DEDUP_BLOCK after save | Notes |
|-----|:---------:|:------------------:|:-----------:|:---------------------:|-------|
| R01 | ☐ | | ☐ | ☐ | |
| R03 | ☐ | | ☐ | ☐ | |
| R06 | ☐ | | ☐ | ☐ | |

### 6.2 Deduplication Verification (runs R09, R10)

**R09** — same vehicle passes twice with < 30 s gap (within dedup window)  
**R10** — same vehicle passes twice with > 60 s gap (should allow 2nd record)

```bash
# Count DEDUP_NEW vs DEDUP_BLOCK events around runs R09 and R10
grep -E "\[DEDUP_(NEW|BLOCK|REENTRY)\]" aicamera.log | grep -A 5 -B 5 "R09\|R10"
```

| Run | 1st pass saved? | 2nd pass | Expected | Actual |
|-----|:--------------:|----------|----------|--------|
| R09 (< 30 s gap) | ☐ | `DEDUP_BLOCK` | blocked | |
| R10 (> 60 s gap) | ☐ | `DEDUP_REENTRY` | new record | |

### 6.3 Track Count & Cleanup

```bash
grep "\[DEDUP_CLEANUP\]" aicamera.log | tail -10
grep "\[TRACKING\]" aicamera.log | tail -10
```

Confirm tracks are cleaned up after timeout (no unbounded growth):

| Metric | cam1 | cam2 | Target |
|--------|:----:|:----:|:------:|
| Max active tracks in frame | | | ≤ 5 |
| `[DEDUP_CLEANUP]` events seen | | | > 0 (cleanup running) |

---

## 7. ROI Zone Testing

### 7.1 Disabled ROI (baseline)

All runs R01–R08 should have ROI disabled. Verify no `outside ROI` in `[OCR_GATE]` SKIP reasons.

```bash
grep "OCR_GATE.*SKIP.*ROI" aicamera.log | wc -l
# Expected: 0
```

### 7.2 Enable ROI — vehicles inside zone

Set ROI to cover the expected vehicle position (e.g., gate entry lane).

```bash
# Set ROI (adjust coords to your test location)
curl -s -X POST http://aicamera1.tail605477.ts.net/detection/roi \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"x1":0.2,"y1":0.3,"x2":0.8,"y2":0.9,"persist":false}'

curl -s http://aicamera1.tail605477.ts.net/detection/roi | python3 -m json.tool
```

Run 2 vehicle passes with ROI active. Plate center should fall inside zone.

| Run | Plate center (est.) | Inside ROI? | `[OCR_GATE]` | OCR result |
|-----|--------------------:|:-----------:|:------------:|------------|
| ROI-1 | | ☐ | PASS | |
| ROI-2 | | ☐ | PASS | |

### 7.3 Enable ROI — vehicles outside zone

Deliberately set a small ROI that excludes the vehicle lane.

```bash
# Small ROI top-left corner (no vehicle passes here)
curl -s -X POST http://aicamera1.tail605477.ts.net/detection/roi \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"x1":0.0,"y1":0.0,"x2":0.2,"y2":0.3,"persist":false}'
```

Run 1 vehicle pass. Expect: `[OCR_GATE] SKIP outside ROI`.

| Run | Expected | Actual token |
|-----|----------|-------------|
| ROI-3 (outside) | `SKIP outside ROI` | |

### 7.4 Reset ROI

```bash
curl -s -X POST http://aicamera1.tail605477.ts.net/detection/roi \
  -H "Content-Type: application/json" \
  -d '{"enabled":false,"persist":false}'
curl -s -X POST http://aicamera2.tail605477.ts.net/detection/roi \
  -H "Content-Type: application/json" \
  -d '{"enabled":false,"persist":false}'
```

Confirm: `[OCR_GATE]` PASS resumes for subsequent runs.

---

## 8. Post-Test Data Collection

### 8.1 Retrieve Edge SQLite DB

```bash
scp camuser@aicamera1:~/aicamera/edge/data/detections.db ./logs/20260610/cam1_detections.db
scp camuser@aicamera2:~/aicamera/edge/data/detections.db ./logs/20260610/cam2_detections.db
```

### 8.2 Query Edge DB Results

```bash
# Run counts per camera
sqlite3 ./logs/20260610/cam1_detections.db \
  "SELECT COUNT(*) as total,
          SUM(CASE WHEN ocr_results != '[]' AND ocr_results != '' THEN 1 ELSE 0 END) as with_ocr,
          SUM(parallel_ocr_success) as ocr_success
   FROM detections;"

# Check today's records
sqlite3 ./logs/20260610/cam1_detections.db \
  "SELECT id, created_at, vehicle_confidence, plate_confidence,
          ocr_results, hailo_ocr_results, parallel_ocr_success
   FROM detections
   WHERE created_at >= datetime('now', 'start of day')
   ORDER BY id DESC LIMIT 20;"
```

| Metric | cam1 | cam2 | Target |
|--------|:----:|:----:|:------:|
| Total detections (today) | | | = passes made |
| Detections with OCR text | | | > 0 |
| `parallel_ocr_success = 1` | | | = detections with OCR |
| Empty `ocr_results` | | | 0 for visible plates |

### 8.3 Retrieve Logs

```bash
mkdir -p ./logs/20260610

# Edge service log
ssh camuser@aicamera1 "sudo journalctl -u aicamera_lpr.service \
  --since='2026-06-10 08:00:00' --no-pager" > ./logs/20260610/cam1_journal.log

ssh camuser@aicamera2 "sudo journalctl -u aicamera_lpr.service \
  --since='2026-06-10 08:00:00' --no-pager" > ./logs/20260610/cam2_journal.log

# App log (if separate)
scp camuser@aicamera1:~/aicamera/edge/logs/aicamera.log ./logs/20260610/cam1_aicamera.log
scp camuser@aicamera2:~/aicamera/edge/logs/aicamera.log ./logs/20260610/cam2_aicamera.log
```

### 8.4 Detection Status Counters (after test)

```bash
curl -s http://aicamera1.tail605477.ts.net/detection/status | python3 -m json.tool
curl -s http://aicamera2.tail605477.ts.net/detection/status | python3 -m json.tool
```

| Counter | cam1 before | cam1 after | delta | cam2 before | cam2 after | delta |
|---------|:-----------:|:----------:|:-----:|:-----------:|:----------:|:-----:|
| `total_processed` | | | | | | |
| `successful_ocr` | | | | | | |
| `frames_processed` | | | | | | |
| `ocr_queue_drops` | | | | | | |

**OCR success rate = `successful_ocr delta / total_processed delta`**  
Target: ≥ 50% for slow runs, ≥ 30% for fast runs.

---

## 9. Analysis Commands (post-test)

Run against downloaded log files on Mac.

```bash
LOG1=./logs/20260610/cam1_aicamera.log
LOG2=./logs/20260610/cam2_aicamera.log

# --- OCR Gate summary ---
echo "=== cam1 OCR_GATE ===" && grep "OCR_GATE" $LOG1 | grep -oP "(PASS|SKIP[^|]*)" | sort | uniq -c
echo "=== cam2 OCR_GATE ===" && grep "OCR_GATE" $LOG2 | grep -oP "(PASS|SKIP[^|]*)" | sort | uniq -c

# --- Tesseract latency distribution ---
echo "=== cam1 Tesseract ms ===" && grep "OCR_RESULT" $LOG1 | grep -oP "tesseract=\K[0-9]+"
echo "=== cam2 Tesseract ms ===" && grep "OCR_RESULT" $LOG2 | grep -oP "tesseract=\K[0-9]+"

# --- Pipeline total latency ---
echo "=== cam1 Pipeline total ms ===" && grep "PIPELINE_DONE" $LOG1 | grep -oP "total=\K[0-9]+"
echo "=== cam2 Pipeline total ms ===" && grep "PIPELINE_DONE" $LOG2 | grep -oP "total=\K[0-9]+"

# --- Image write latency ---
grep "IMG_SAVE" $LOG1 | grep -oP "write=\K[0-9]+"

# --- Dedup events ---
grep -oP "\[DEDUP_\w+\]" $LOG1 | sort | uniq -c | sort -rn

# --- Error scan ---
grep -E "ERROR|EXCEPTION|Traceback|failed" $LOG1 | tail -20

# --- OCR results ---
grep "OCR_RESULT" $LOG1 | grep "valid=True" | grep -oP "text=\K[^ ]+"
```

---

## 10. System Health During Test

```bash
# Check temp/load before and after test
ssh camuser@aicamera1 "vcgencmd measure_temp; uptime; free -m | grep Mem; df -h / | tail -1"
ssh camuser@aicamera2 "vcgencmd measure_temp; uptime; free -m | grep Mem; df -h / | tail -1"
```

| Metric | cam1 Start | cam1 End | cam2 Start | cam2 End | Limit |
|--------|:----------:|:--------:|:----------:|:--------:|-------|
| CPU Temp (°C) | | | | | < 80°C |
| Load avg (1min) | | | | | < 4.0 |
| RAM free (MB) | | | | | > 200 MB |
| Disk free | | | | | > 10% |

---

## 11. Issues Log

| # | Time | Camera | Token | Description | Severity | Notes |
|---|------|--------|-------|-------------|:--------:|-------|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |

**Severity:** 🔴 P1 — pipeline broken · 🟠 P2 — data loss/OCR failure · 🟡 P3 — degraded accuracy · 🟢 P4 — cosmetic

---

## 12. Analysis Draft Report

> Fill in after reviewing logs and DB data.

### 12.1 Detection Rate

| Speed | Passes | cam1 Detected | cam1 Rate | cam2 Detected | cam2 Rate |
|-------|:------:|:-------------:|:---------:|:-------------:|:---------:|
| ~10 km/h | 2 | | | | |
| ~30 km/h | 5 | | | | |
| ~60 km/h | 3 | | | | |
| **Total** | **10** | | | | |

Target detection rate: ≥ 80%

### 12.2 OCR Success Rate

| Speed | cam1 OCR attempts | cam1 Valid text | cam1 Accuracy | cam2 OCR attempts | cam2 Valid text | cam2 Accuracy |
|-------|:-----------------:|:---------------:|:-------------:|:-----------------:|:---------------:|:-------------:|
| ~10 km/h | | | | | | |
| ~30 km/h | | | | | | |
| ~60 km/h | | | | | | |
| **Total** | | | | | | |

Target OCR accuracy (on detected plates): ≥ 70%

### 12.3 Latency Summary

| Stage | cam1 avg | cam1 max | cam2 avg | cam2 max | Target |
|-------|:--------:|:--------:|:--------:|:--------:|--------|
| Hailo inference | | | | | < 100 ms |
| OCR queue wait | | | | | < 200 ms |
| Tesseract OCR | | | | | < 2000 ms |
| Image write | | | | | < 500 ms |
| DB write | | | | | < 100 ms |
| **Pipeline total** | | | | | **< 3000 ms** |

### 12.4 Deduplication

| Test | Expected | Result | Pass? |
|------|----------|--------|:-----:|
| R09: 2nd pass < 30 s → blocked | `DEDUP_BLOCK` | | ☐ |
| R10: 2nd pass > 60 s → new record | `DEDUP_REENTRY` | | ☐ |
| No duplicate records in DB | DB count = passes | | ☐ |

### 12.5 ROI

| Test | Expected | Result | Pass? |
|------|----------|--------|:-----:|
| ROI enabled, plate inside zone | `OCR_GATE PASS` | | ☐ |
| ROI enabled, plate outside zone | `OCR_GATE SKIP outside ROI` | | ☐ |
| ROI disabled → no OCR blocked | 0 ROI SKIP | | ☐ |

### 12.6 Key Findings

```
Vehicle detection:  ___________________________________________
Plate detection:    ___________________________________________
OCR pipeline:       ___________________________________________
Tracking:           ___________________________________________
Deduplication:      ___________________________________________
ROI:                ___________________________________________
Latency bottleneck: ___________________________________________
System stability:   ___________________________________________
```

### 12.7 Issues Found

| Priority | Component | Issue | Fix Proposed |
|:--------:|-----------|-------|-------------|
| P1 | | | |
| P2 | | | |
| P3 | | | |

### 12.8 Overall Assessment

| Area | Score | Target | Status |
|------|:-----:|:------:|:------:|
| Detection rate | ___% | ≥ 80% | |
| OCR accuracy (on detected) | ___% | ≥ 70% | |
| Pipeline latency avg | ___ ms | < 3000 ms | |
| Dedup correctness | ___% | 100% | |
| System stability (no crash) | ☐ | ✅ | |
| ROI gating correct | ☐ | ✅ | |

---

## 13. Next Steps

Based on results:

- [ ] If `OCR_GATE SKIP blur_score` > 20% → tune `_ocr_min_frame_score` or improve plate crop quality
- [ ] If Tesseract > 2000 ms avg → profile preprocessing, consider PSM tuning
- [ ] If detection rate < 80% at 60 km/h → check DETECTION_INTERVAL, consider `_ocr_min_plate_frames = 1` confirmed working
- [ ] If dedup blocks valid re-entries → tune `DEDUP_WINDOW_SECONDS` in config
- [ ] If `OCR_QUEUE_DROP > 0` → increase `OcrQueueWorker` maxsize from 10
- [ ] Collect misread plate examples for Tesseract PSM / tessdata_best tuning
- [ ] Update `CONTEXT.md` with field test results and any new parameter tuning

---

## Appendix — Quick Command Reference

```bash
# SSH
ssh camuser@aicamera1   # pw: admin88366
ssh camuser@aicamera2   # pw: admin88366
ssh devuser@lprserver   # pw: admin88366

# Watch live pipeline tokens
sudo journalctl -u aicamera_lpr.service -f | grep -E \
  "\[(VEHICLE|PLATE|PLATE_SKIP|OCR_GATE|OCR_RESULT|PIPELINE_DONE|TRACK_SAVED|DEDUP)\]"

# Check detection status live
watch -n 5 'curl -s http://aicamera1.tail605477.ts.net/detection/status | python3 -m json.tool'

# ROI get/set
curl -s http://aicamera1.tail605477.ts.net/detection/roi | python3 -m json.tool
curl -s -X POST http://aicamera1.tail605477.ts.net/detection/roi \
  -H "Content-Type: application/json" \
  -d '{"enabled":false,"persist":false}'

# Edge SQLite quick query
sqlite3 ~/aicamera/edge/data/detections.db \
  "SELECT id, created_at, vehicle_confidence, plate_confidence, \
          ocr_results, parallel_ocr_success \
   FROM detections ORDER BY id DESC LIMIT 10;"

# Restart edge service
sudo systemctl restart aicamera_lpr.service
sudo journalctl -u aicamera_lpr.service -f

# Deploy latest code
cd ~/aicamera && git pull && sudo systemctl restart aicamera_lpr.service
```

---

*Document created: 2026-06-10 | PWD Vision Works*

---
---

# SESSION REPORT — 2026-06-10 (อัพเดตระหว่างการทดสอบ)

---

## A. สภาพระบบก่อนเริ่มทดสอบวันนี้

### A.1 Commit ที่ใช้เริ่มต้น: `e030736`

ก่อนทดสอบวันนี้ มีการแก้ไขสะสมจากหลายรอบ:

| Fix (ก่อนวันนี้) | Commit | ปัญหาที่แก้ |
|-----------------|--------|------------|
| `_ocr_min_plate_frames` 3→1 | `e030736` | รถเร็วผ่านแค่ 1 เฟรมถูก skip ที่ OCR gate |
| ROI reset disabled | — | ROI persisted จาก field test 06:40 บล็อก OCR ทั้ง session |
| FRAME_MISMATCH | earlier | save ภาพเก่า (best_frame_data) แทน current frame |
| `DETECTION_INTERVAL` 30→0.1 | earlier | detection loop ทำงานแค่ทุก 30s แทน 0.1s |

### A.2 ปัญหาที่รู้อยู่ก่อนเริ่ม

- `successful_ocr = 0` มาตลอด — รู้ว่าต้องแก้ แต่ยังไม่รู้ root cause จริง
- มีบันทึกซ้ำ (duplicate records) จาก field test วันก่อน แต่คิดว่าแก้แล้ว
- Pipeline log tokens (`DEDUP_BLOCK`, `OCR_GATE`) ไม่เคยเห็นในไฟล์ log

---

## B. กระบวนการทดสอบและ Bug ที่พบระหว่าง Session

### B.1 ทดสอบรอบแรก — 14:23–14:29 (commit e030736)

**พฤติกรรมที่พบ:**
- ID 1819+1820, 1821+1822, 1823+1824 — บันทึกซ้ำทุกคันที่ผ่าน (ห่าง 13–14 วินาที)
- `ocr_results = []` ทุก record — ยังไม่มี OCR แม้แก้ `_ocr_min_plate_frames=1` แล้ว

**การตรวจสอบ:**
- ดู log → ไม่มีอะไรเลยนอกจาก WARNING (`health_status send failed`)
- ตรวจสอบ DB → records มีอยู่จริง แต่ไม่มี OCR

**Bug ที่พบ:**

**Bug A — Pipeline logs ถูก filter ทิ้งหมด**  
`StartStopInfoFilter` ใน `logging_config.py` block ทุก INFO log ที่ไม่มีคำว่า "Started/Stopped/Initialized"  
→ token ทั้งหมด (`DEDUP_BLOCK`, `OCR_GATE`, `DB_SAVE`) ถูกทิ้งทั้งหมด — debug ไม่ได้เลย

**Bug B — Duplicate records: DEDUP_PASS_IOU**  
Layer-1 dedup ตรวจสอบ IoU(current_bbox, saved_bbox) — รถที่เคลื่อนที่ข้าม frame ทำให้ IoU < 0.2  
→ `DEDUP_PASS_IOU` → อนุญาตบันทึกซ้ำ แม้จะอยู่ใน 30s window

**Bug C — OCR stranded: poll_ocr_results() ไม่ถูกเรียก**  
`poll_ocr_results()` อยู่ใน `_handle_ocr()` ซึ่งถูกข้ามเมื่อ `DEDUP_BLOCK → return None`  
Tesseract ทำงานเสร็จใน background แต่ result ค้างใน queue — ไม่เคยถูกเขียนลง DB

### B.2 Fix รอบแรก — commit `8964795`

| Fix | ไฟล์ | รายละเอียด |
|-----|------|-----------|
| ลบ IoU check จาก Layer-1 | `detection_manager.py` | same track_id ใน 30s → block เสมอ ไม่ต้องตรวจ IoU |
| เพิ่ม `_flush_pending_ocr()` | `detection_manager.py` | เรียก poll ก่อน early-return gate ทุก frame |

### B.3 ทดสอบรอบสอง — 14:53 (commit 8964795)

**พฤติกรรมที่พบ:**
- ID 1825+1826, 1848+1849 — ยังบันทึกซ้ำอยู่ (ห่าง 13–14 วินาที)
- ยัง `No OCR results`

**Bug ที่พบ:**

**Bug D — track_timeout=8s < reentry_time_threshold=30s**  
หาก Hailo confidence ตก < 0.8 นาน 8+ วินาที → track หมดอายุจาก `active_tracks`  
→ รถถูก re-detect ด้วย track_id ใหม่ → `recent_tracks.get(new_id)` = None → `DEDUP_NEW` → บันทึกซ้ำ

### B.4 Fix รอบสอง — commit `2f63a04`

| Fix | ไฟล์ | รายละเอียด |
|-----|------|-----------|
| `track_timeout` 8s→30s | `detection_processor.py` | ให้ track มีชีวิตนานเท่า dedup window |
| ลบ `StartStopInfoFilter` | `logging_config.py` | INFO logs ทั้งหมดถึง file handler แล้ว |

### B.5 ทดสอบรอบสาม — 15:11 (commit 2f63a04)

**พฤติกรรมที่พบ:**
- ID 1828: ไม่บันทึกซ้ำแล้ว ✅
- `No OCR results` ยังมีอยู่

**ตรวจสอบ log (ครั้งแรกที่เห็น pipeline tokens):**
```
15:10:55  TRACK_NEW track=1 (486×604px)
15:10:55→15:11:20  plate=0.000 ทุกเฟรม (25 วินาที, ~250 เฟรม!)
                   DEDUP_NEW ทุกเฟรม
15:11:20  plate detected conf=50% → บันทึก ID 1828
          submit_for_ocr → return False (silent)
15:11:47  frame_count=204, ocr_submitted=False ← OCR ไม่เคยถูก submit!
```

**Bug ที่พบ:**

**Bug E — `plate_crop_buffer.append()` ไม่เคยถูกเรียกที่ไหนเลยในทั้ง codebase**  
`submit_for_ocr()` ตรวจ buffer ก่อน — ว่างเปล่าตลอด → return False ทันที (logged DEBUG, filtered)  
→ `ocr_submitted=False` ตลอดไป → Tesseract ไม่ได้รับงานเลย

### B.6 Fix รอบสาม — commit `41f298e`

| Fix | ไฟล์ | รายละเอียด |
|-----|------|-----------|
| เพิ่ม `plate_crop_buffer.append()` ใน `_update_track` | `detection_processor.py` | crop plate เมื่อ plate_bbox != None, คำนวณ Laplacian |

### B.7 ทดสอบรอบสี่ — 15:26 (commit 41f298e)

**พฤติกรรมที่พบ:**
- ID 1830: **OCR ทำงานแล้ว!** 🎉 แต่ได้ผลลัพธ์ผิด
- OCR result: `"ก oe . ay" (47.0%)` — garbage text, `valid=False`

**ตรวจสอบ log:**
```
15:26:52  PLATE_CROP: crop=130×126px ar=1.03 lap=65
          OCR_SUBMIT: crop=130×126px blur=65 → ส่ง Tesseract ทันที
          OCR_DONE: text="ก oe . ay" valid=False conf=0.470 e2e=4120ms
```

**สาเหตุ OCR ได้ garbage:**

| ปัญหา | ค่าที่ได้ | ค่าที่ควรได้ | ผลกระทบ |
|-------|---------|------------|--------|
| Crop shape ผิด | 130×126px (aspect=1.03) | aspect ≥ 1.5 (ป้ายกว้าง) | Tesseract อ่านภาพผิดรูป |
| Blur มาก | Laplacian=65 | ≥ 80 (ขั้นต่ำ) / ≥ 200 (ดี) | ตัวอักษรเบลอ อ่านไม่ออก |
| Submit ทันที | buf_depth=1 | รอ crop ที่ดีกว่า | ใช้ crop เดียวที่อาจแย่ |

**Bug ที่พบ:**

**Bug F — ไม่มี aspect ratio filter บน plate crop**  
ป้ายไทยมี aspect ratio 3:1 ถึง 4.7:1 แต่ไม่มีการตรวจสอบ  
→ crop ที่เป็นสี่เหลี่ยมจตุรัส (เกิดจากมุมกล้อง/ตำแหน่งป้าย) ถูกส่ง OCR

**Bug G — ไม่มี minimum Laplacian threshold สำหรับ OCR submission**  
OCR submit ทันทีที่มี crop ไม่ว่า blur แค่ไหน

**Bug H — OCR submit เร็วเกินไป ไม่รอ crop ที่ดีกว่า**  
เมื่อ vehicle จอด/ชะลอ จะมี crop ที่ดีกว่าตามมา แต่ `ocr_submitted=True` แล้ว

### B.8 Fix รอบสี่ — commit `5bf66aa`

| Fix | รายละเอียด |
|-----|-----------|
| Aspect ratio filter | ปฏิเสธ crop ที่ W/H < 1.5 หรือ W < 80px หรือ H < 20px → log `PLATE_CROP_SKIP` |
| Minimum Laplacian gate | `best_crop_lap < 80` → `OCR_GATE SKIP` (ดีกว่าได้ garbage) |
| Re-submit mechanism | เพิ่ม `ocr_submitted_lap` ใน VehicleTrack — ถ้า crop ใหม่ sharp ≥ 3× ที่ submit ไป → reset และ re-submit |

---

## C. สถานการณ์ที่พบจากการทดสอบ

### C.1 ภาพรถชัด แต่ป้ายทะเบียนไม่ชัด / ไม่ถูก detect

**อาการ:** Vehicle confidence 89.8% ตลอด แต่ `plate=0.000` นาน 20–30 วินาที  
**สาเหตุที่น่าจะเป็น:**
- กล้องติดตั้งสูง มองจากมุมด้านบน → ป้ายหายไปใต้ฝากระโปรง
- ป้ายอยู่ด้านหลังรถในบางช่วงของการขับผ่าน
- ระยะห่างไม่เหมาะสม — รถอยู่นอก optimal range ของ LP model (640×640)
- ป้ายได้รับแสงไม่ดีพอ

**ผลกระทบ:** ระบบรอนาน 20+ วินาทีแล้วได้ plate crop คุณภาพต่ำ (ครั้งแรกที่ LP model เห็น = มุมไม่ดี)

```
Timeline ตัวอย่าง (ID 1828, track=1):
15:10:55  TRACK_NEW  size=486×604px  (รถไกล เข้ามา)
          area=0.098 → 0.70 → 0.39  (รถเข้าใกล้แล้วออกไป)
          plate=0.000 ตลอด 25 วินาที
15:11:20  plate detected conf=50%  (ครั้งเดียว ก่อนรถออกจากเฟรม)
```

### C.2 ป้ายทะเบียนเห็นบางส่วน / crop ผิดรูป

**อาการ:** LP model detect ป้ายได้ แต่ bbox ได้ขนาด ~130×126px (aspect≈1:1)  
**สาเหตุ:**
- รถเอียง มุมกล้องทำให้ป้ายดูสั้นลง
- Hailo LP model detect เฉพาะครึ่งซ้ายหรือขวาของป้าย
- bbox coordinates อาจถูก clip ที่ขอบเฟรม

**ผลกระทบ:** Tesseract ได้ภาพที่ไม่ใช่ป้าย → อ่านไม่ออก หรืออ่านได้ garbage

### C.3 Hailo LP model ตรวจพบป้ายไม่ต่อเนื่อง

**อาการ:** ภาพรถชัด vehicle confidence สูง แต่ plate detection เป็นแบบ "เห็น 1 เฟรม → หาย" ซ้ำๆ  
**สาเหตุ:**
- LP model ถูก train กับภาพป้ายใน range/angle เฉพาะ
- กล้องอาจมองเห็นป้ายจากมุมที่ model ไม่คุ้นเคย
- Confidence threshold `PLATE_CONFIDENCE_THRESHOLD=0.5` อาจต้องลดลง

### C.4 OCR ได้ผลที่ไม่ valid (garbage)

**อาการ:** OCR ทำงาน แต่ได้ text เช่น `"ก oe . ay"`, `valid=False`, conf < 50%  
**สาเหตุ:**
- Crop blur (Laplacian < 80)
- Crop ไม่ใช่รูปร่างป้ายที่แท้จริง
- Tesseract PSM 11 อาจไม่เหมาะกับ crop ที่มีขนาดเล็ก/ผิดรูป

### C.5 รถที่ถูกตรวจสอบนาน (long stop) อาจได้หลาย records

**อาการ:** รถจอดนาน > 30 วินาที → elapsed > reentry_time_threshold → `DEDUP_REENTRY` → บันทึกซ้ำ  
**Fix ที่รอ implement:** ตรวจสอบ `track.first_seen <= info['last_saved']` → ถ้าใช่คือ "long stop" ไม่ใช่ re-entry  
**Status:** Fix code เขียนแล้ว แต่ยัง pending commit (รอ confirm จาก user)

---

## D. สรุปการแก้ไขทั้งหมดในวันนี้

| # | Commit | Component | Bug | Fix |
|---|--------|-----------|-----|-----|
| 1 | `8964795` | `detection_manager.py` | DEDUP_PASS_IOU: IoU check ทำให้รถเคลื่อนที่ผ่าน dedup | ลบ IoU check จาก Layer-1 |
| 2 | `8964795` | `detection_manager.py` | OCR stranded: poll ถูกข้ามเมื่อ DEDUP_BLOCK | `_flush_pending_ocr()` ก่อน early-return |
| 3 | `2f63a04` | `detection_processor.py` | `track_timeout=8s` < `reentry_time_threshold=30s` | `track_timeout = REENTRY_TIME_THRESHOLD` (30s) |
| 4 | `2f63a04` | `logging_config.py` | `StartStopInfoFilter` block ทุก pipeline INFO log | ลบ filter — INFO ทั้งหมดถึง log file |
| 5 | `41f298e` | `detection_processor.py` | `plate_crop_buffer.append()` ไม่เคยถูกเรียก | เพิ่ม crop logic ใน `_update_track` |
| 6 | `5bf66aa` | `detection_processor.py` | ไม่มี aspect ratio filter บน plate crop | ปฏิเสธ W/H < 1.5 หรือ W < 80px |
| 7 | `5bf66aa` | `detection_processor.py` | ไม่มี minimum Laplacian gate | `OCR_GATE SKIP` ถ้า best_lap < 80 |
| 8 | `5bf66aa` | `detection_processor.py` | OCR submit ไม่มีโอกาส re-try ด้วย crop ที่ดีกว่า | Re-submit ถ้า new_lap ≥ 3× submitted_lap |

---

## E. สถานะ Pipeline ล่าสุด (commit `5bf66aa`)

### E.1 Pipeline Flow ปัจจุบัน

```
Camera frame (1280×720 @ 30fps)
    │
    ├─ _flush_pending_ocr()  ← NEW: ทุก frame ก่อน gate ใดๆ
    │
    ▼
validate_and_enhance_frame()
    │
    ▼
detect_vehicles() [Hailo NPU ~20ms]
    │  vehicle_boxes
    ▼
_tracking_pass1()
    ├─ update_vehicle_tracks()  ← track_timeout=30s (เดิม 8s)
    ├─ apply_deduplication_rules()
    └─ _should_save_detection()
        ├─ Layer 1: elapsed < 30s → DEDUP_BLOCK (ไม่มี IoU check แล้ว)
        └─ Layer 2: plate_text window 60s

    [eligible empty → return None]
    │
    ▼
detect_license_plates() [Hailo NPU]
    │  plate_boxes
    ▼
_tracking_pass2()
    └─ _update_track(plate_bbox=...)
        ├─ update best_frame_data (เฉพาะเมื่อเห็นป้าย)
        └─ plate_crop_buffer.append((lap, crop))  ← NEW
            └─ filter: W/H≥1.5, W≥80px, H≥20px

    [no plate → SAVE_DEFER → return None]
    │
    ▼
_handle_ocr()
    └─ _submit_ocr_for_tracks()
        └─ submit_for_ocr()
            └─ _should_submit_for_ocr()
                ├─ ocr_submitted? → check re-submit (new_lap ≥ 3×)  ← NEW
                ├─ plate_candidates ≥ 1
                ├─ best_frame_score ≥ 0.3
                ├─ best_crop_lap ≥ 80  ← NEW Laplacian gate
                └─ plate_in_roi (ROI disabled ✓)
    │
    ▼
save_detection_results() [JPEG write]
    │
    ▼
_persist_record() → SQLite insert
    │
    └─ _pending_ocr_updates[track_id] = record_id
    │
    ▼
[background: OcrQueueWorker runs Tesseract ~1–2s]
    │
    └─ _flush_pending_ocr() (on next frame)
        └─ _update_db_ocr(record_id, ocr_results) ← patches DB
```

### E.2 Key Parameters

| Parameter | ค่าปัจจุบัน | Configurable | หมายเหตุ |
|-----------|:----------:|:-----------:|---------|
| `DETECTION_INTERVAL` | 0.1s | `.env.production` | ~10 detection cycles/s |
| `REENTRY_TIME_THRESHOLD` | 30s | `.env.production` | dedup window |
| `track_timeout` | 30s (=REENTRY) | code | ต้อง = reentry threshold |
| `VEHICLE_CONFIDENCE` | 0.8 | `.env.production` | ค่อนข้างสูง → miss บางเฟรม |
| `PLATE_CONFIDENCE` | 0.5 | `.env.production` | อาจต้องลดเพื่อ detect ป้ายที่มุมต่างๆ |
| `_ocr_min_plate_frames` | 1 | code | submit ได้ทันที่มี plate 1 frame |
| `_ocr_min_frame_score` | 0.3 | code | quality gate |
| `_ocr_min_crop_lap` | 80 | code | Laplacian min (0=disable) |
| `_ocr_resubmit_ratio` | 3.0 | code | re-submit threshold |
| `plate_crop_buffer` maxlen | 5 | code | เก็บ 5 best crops |
| OCR queue maxsize | 10 | code | |

---

## F. สิ่งที่ยังไม่ได้ทดสอบ / Pending

### F.1 Fix ที่ยังรอ

| Fix | รายละเอียด | Status |
|-----|-----------|--------|
| Long-stop dedup | `DEDUP_BLOCK_CONTINUOUS`: check `first_seen <= last_saved` ป้องกันบันทึกซ้ำเมื่อรถจอดนาน > 30s | Code เขียนแล้วใน detection_manager.py แต่ยัง pending commit |

### F.2 ผลการทดสอบล่าสุด (commit `5bf66aa` — ยังไม่ได้ทดสอบ)

- **Aspect ratio filter** → คาดว่า crop 130×126 (ar=1.03) จะถูก reject
- **Laplacian gate** → ถ้า Laplacian < 80 จะ skip OCR (ดีกว่า garbage)
- **Re-submit** → รถที่จอดนาน OCR จะดีขึ้นเรื่อยๆ

---

## G. การวิเคราะห์สำหรับ AI Cowork

### G.1 โจทย์หลักที่ยังต้องแก้

**ปัญหา 1: Hailo LP model ตรวจพบป้ายได้ไม่ต่อเนื่อง**

ข้อมูลจาก log:
- รถผ่าน 25–30 วินาที → LP model detect ป้ายได้ 1–3 เฟรมเท่านั้น
- `PLATE_CONFIDENCE_THRESHOLD=0.5` → ป้ายที่ confidence < 0.5 ถูกกรองออก
- ป้ายมักถูก detect ในช่วงที่รถใกล้เกินไป (size > 1000px, area > 0.4)

คำถาม:
- ควรลด `PLATE_CONFIDENCE_THRESHOLD` จาก 0.5 เป็น 0.3–0.4 เพื่อได้ detect บ่อยขึ้นหรือไม่?
- `detect_license_plates()` ใช้ enhanced frame (640×640 letterbox) — ป้ายที่รถอยู่ใกล้มากจะ scale เล็กลงใน 640×640 ทำให้ miss หรือเปล่า?

**ปัญหา 2: Plate crop ได้ขนาดและมุมไม่เหมาะสม**

ข้อมูล:
- Crop ที่ได้บ่อย: 130×126px (aspect ~1.0), 150×140px
- Crop ที่ต้องการ: width ≥ 200px, aspect ≥ 2.0, Laplacian ≥ 100
- Laplacian ที่ได้: 65–150 (ดีคือ > 200)

คำถาม:
- `_calculate_plate_region_sharpness()` ใช้ coordinates จาก detect_license_plates() โดยตรง — ควร upscale crop ก่อน Tesseract หรือเปล่า?
- `preprocess_plate_crop()` ใน `thai_lp_ocr.py` ทำ upscale ถึง 300px height — แต่ถ้า crop เป็น 130×126 (ไม่ใช่รูปร่างป้าย) upscale ก็ไม่ช่วย

**ปัญหา 3: กล้องมองเห็นป้ายได้น้อยในแต่ละ pass**

สังเกตจาก log:
- รถเข้าเฟรม → plate=0.000 ยาวนาน → detect ป้ายได้ครั้งเดียวตอนรถอยู่ใกล้ที่สุด
- หลังจาก save/OCR submit → plate=0.000 อีกครั้ง

สมมติฐาน:
- กล้องติดสูง มองลงมา → ป้ายซ่อนอยู่ใต้ฝากระโปรงช่วงรถเข้าหา
- LP model ถูก train กับภาพป้ายในแนวระดับ ไม่ใช่จากมุมสูง
- ROI อาจช่วยได้ — ถ้ากำหนด zone ที่รถอยู่ในตำแหน่งที่ป้ายมองเห็นชัด

### G.2 Log Tokens สำคัญที่ควร monitor

```bash
# Real-time monitoring (ทั้ง 2 camera พร้อมกัน)
tail -f ~/aicamera/edge/logs/aicamera.log | grep -E \
  "\[PLATE_CROP|PLATE_CROP_SKIP|OCR_GATE|OCR_SUBMIT|OCR_DONE|OCR_FLUSH|DEDUP_BLOCK|DEDUP_NEW\]"
```

| Token | ความหมาย | ค่าที่คาดหวัง |
|-------|---------|------------|
| `[PLATE_CROP]` | crop ผ่าน aspect/size filter | `ar≥1.5 lap≥80` |
| `[PLATE_CROP_SKIP]` | crop ถูกปฏิเสธ | ระบุเหตุผล |
| `[OCR_GATE] PASS` | ส่ง OCR | `best_lap≥80` |
| `[OCR_GATE] SKIP best_crop_lap` | Laplacian ต่ำเกิน | ดูกว่าเกิดบ่อยแค่ไหน |
| `[OCR_GATE] RE-SUBMIT` | พบ crop ดีกว่า | รถที่จอด/ชะลอ |
| `[OCR_DONE]` | Tesseract เสร็จ | `valid=True conf≥0.6` |
| `[OCR_FLUSH]` | patch DB record | pending_remaining=0 |
| `[DEDUP_BLOCK]` | ป้องกันซ้ำ | elapsed < 30s |

### G.3 แนวทางแก้ไขที่แนะนำ (สำหรับรอบถัดไป)

**ลำดับความสำคัญ:**

```
P1 (ต้องแก้เพื่อให้ OCR ทำงานได้)
├─ ปรับตำแหน่ง/มุมกล้อง → ให้เห็นป้ายในแนวระดับ
├─ ทดสอบ PLATE_CONFIDENCE_THRESHOLD=0.3 (จาก 0.5)
└─ ดู `[PLATE_CROP_SKIP]` ว่าเกิดจาก aspect ratio หรือ size

P2 (ปรับ parameter เพื่อเพิ่ม coverage)
├─ เพิ่ม plate_crop_buffer maxlen จาก 5 เป็น 10
├─ ลด _ocr_min_crop_lap จาก 80 เป็น 60 ถ้ายัง skip เยอะเกิน
└─ ทดสอบ PSM 7 (single line) แทน PSM 11 สำหรับ Thai plate

P3 (เพิ่ม intelligence)
├─ บันทึก long-stop dedup fix (DEDUP_BLOCK_CONTINUOUS)
├─ เพิ่ม upscale ใน plate_crop_buffer ก่อน push ลง queue
└─ เพิ่ม padding รอบ plate bbox ก่อน crop (prevent edge cut)
```

### G.4 Test Protocol สำหรับรอบถัดไป

```bash
# 1. Monitor live — เปิด 2 terminal
# Terminal 1: pipeline tokens
tail -f ~/aicamera/edge/logs/aicamera.log | grep -E "\[PLATE_CROP|OCR_GATE|OCR_DONE\]"

# 2. หลังรถผ่าน ดู DB record
sqlite3 ~/aicamera/edge/data/detections.db \
  "SELECT id, datetime(created_at,'localtime'), plate_confidence, 
          ocr_results, parallel_ocr_success 
   FROM detections ORDER BY id DESC LIMIT 5;"

# 3. ถ้าเห็น PLATE_CROP_SKIP เยอะ → ลด threshold
# crop ผิดรูปหมด → ปัญหาระดับกล้อง/มุม ต้องปรับ hardware

# 4. ถ้า OCR_GATE SKIP best_crop_lap เยอะ → ลด _ocr_min_crop_lap
# แก้ detection_processor.py: _ocr_min_crop_lap: float = 60.0

# 5. ถ้า OCR valid=False ทั้งหมด → ดูที่ Tesseract preprocessing
# thai_lp_ocr.py read_plate() + validate_thai_plate()
```

---

*อัพเดต: 2026-06-10 ระหว่าง session | PWD Vision Works*
