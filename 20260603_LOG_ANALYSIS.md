# Field Test Log Analysis — 2026-06-03
**Tester:** PWD Vision Works  
**Source:** `aicamera.log` pulled from aicamera1 & aicamera2 post roadside test

---

## Executive Summary

| Item | aicamera1 | aicamera2 |
|------|-----------|-----------|
| Service uptime | ✅ Stable ~1.5 days | ❌ Restarting ~every 1.5h (11 restarts) |
| Disk status | ❌ **100% FULL at 17:06** → cleared | ✅ 66% used, 20GB free |
| WebSocket | ❌ Namespace errors recurring | ❌ Namespace errors recurring |
| MQTT | ❌ Timeout failures recurring | ❌ Timeout failures recurring |
| OCR pipeline | ⚠️ 2 skips (blur/contrast) | ⚠️ 3 skips (too small/AR invalid) |
| DB errors | ❌ Full disk → insert failed | ⚠️ SQLite transaction errors |

**Immediate actions taken during analysis:**
- ✅ Cleared `/tmp/chromium-kiosk` on aicamera1 (freed 25GB, 100% → 55%)
- ✅ Restarted aicamera2 service (port 80 fix now active)

---

## 1. CRITICAL: Disk Full — aicamera1

### Timeline
```
10:15  Storage Alert: 2.84 GB free
...    (disk draining ~10MB/min from image saves)
16:59  Storage Alert: 0.04 GB free
17:05  cv2.imwrite failed — image save failed
17:06  database or disk is full — DB insert failed
17:06  Storage Alert: 0.00 GB free  ← SYSTEM FAILURE
```

### Root Cause
```
/tmp/chromium-kiosk/   25 GB   ← CULPRIT (Chromium kiosk BrowserMetrics)
/home/camuser/aicamera  5.4 GB
/var                    9.2 GB
/usr                    8.0 GB
Total used: 55GB / 58GB (100%)
```

### Why the cron job failed
The existing cron (`/etc/cron.d/aicamera-cleanup`) deletes files older than 1 day. But Chromium updates file timestamps as it writes, keeping files "fresh" and bypassing the age filter.

### Fix Required
Change the cron to delete **all** chromium BrowserMetrics unconditionally at startup and daily:
```bash
# /etc/cron.d/aicamera-cleanup  (replace existing chromium line)
0 3 * * * camuser find /tmp/chromium-kiosk/BrowserMetrics -mindepth 1 -delete 2>/dev/null; true
@reboot   camuser find /tmp/chromium-kiosk/BrowserMetrics -mindepth 1 -delete 2>/dev/null; true
```

Also add a disk-space guard in the detection pipeline: **pause image saving when disk < 500MB**.

---

## 2. CRITICAL: aicamera2 Restart Loop (~Every 1.5 Hours)

### Pattern
```
00:46  Service start → WebSocketSender started
01:23  health_monitor SQLite error
...    (1.5h window)
04:29  "Could not access detection service API: port=80 Read timed out"
04:29  camera_handler.py: Stopping camera → restart
```

### Observed Restart Times
| Time | Duration since last restart |
|------|-----------------------------|
| 00:46 | — (initial boot) |
| 02:39 | 1h 53m |
| 04:29 | 1h 50m |
| 06:21 | 1h 52m |
| 08:14 | 1h 53m |
| 10:04 | 1h 50m |
| 11:52 | 1h 48m |
| 13:42 | 1h 50m |
| 15:32 | 1h 50m |
| 17:25 | 1h 53m |
| 19:16 | 1h 51m |

**Pattern:** Restart every **~1h 50min** very consistently → triggered by health monitor timeout.

### Root Cause
`health_monitor.py:439 - Could not access detection service API: HTTPConnectionPool(host='localhost', port=80): Read timed out`

health_monitor was calling `http://localhost:80/detection/status` — port 80 (Nginx) doesn't exist on edge cameras. This fix was committed but Gunicorn on aicamera2 was using Unix socket, so port 5000 endpoint may need verification.

**Fix deployed:** `git pull + restart` done at analysis time. Monitor to confirm no more 1.5h restarts.

**Also check:** Does aicamera2 Gunicorn actually expose port 5000? Verify:
```bash
ss -tlnp | grep 5000
curl http://localhost:5000/detection/status
```

### Autofocus Issue on aicamera2 (IMX708 NoIR)
```
camera_handler.py:1058 - Autofocus timeout after 3.0s (may still be acceptable)
camera_handler.py:1161 - Focus health verification failed after 2 attempts. FoM range 3-4, variation=1.0
```
Every restart cycle, camera takes 3 seconds to try autofocus and fails. IMX708 NoIR may need **manual focus** lock for roadside mounting.

---

## 3. WebSocket Namespace Error (Both Cameras)

### Error
```
websocket_sender.py:743 - health_status send failed: / is not a connected namespace.
```

### Frequency
- aicamera1: ~every 30-60 minutes
- aicamera2: ~every 1-2 hours (between restarts)

### Pattern
Occurs even when PING/PONG shows the connection is active. The Socket.IO client connects to `lprserver` at path `/ws/` but sends health_status to namespace `/` which is not registered.

### Root Cause
`websocket_sender.py` sends `health_status` to `namespace='/'` but the ws-service on lprserver registers the namespace as `/ws` (or the client is not in the correct namespace after reconnect).

### Fix Required
In `websocket_sender.py`, verify namespace after reconnect:
```python
# Before: self.sio.emit('health_status', payload)
# After: self.sio.emit('health_status', payload, namespace='/')  # or correct ns
```
Or: check the `socketio_path` vs `namespace` distinction — path `/ws/` is the transport path, namespace `/` is the application namespace. Confirm lprserver ws-service accepts namespace `/`.

---

## 4. MQTT Broker Connection Failures (Both Cameras)

### Error
```
mqtt_client.py:52 - Failed to connect to MQTT broker: timed out
```

### Frequency
- aicamera1: ~every 5-30 minutes
- aicamera2: ~every 1-2 hours

### Analysis
MQTT connects to `lprserver.tail605477.ts.net:1883`. The failures coincide with Tailscale reconnect periods or lprserver MQTT broker overload.

The `client.py:573 - packet queue is empty, aborting` messages are from Socket.IO (not MQTT), indicating the Socket.IO packet queue drains and the connection is cut.

### Fix Required
1. Verify Mosquitto broker on lprserver is running with appropriate keepalive settings
2. Add exponential backoff MQTT reconnect (if not already implemented)
3. Verify Tailscale MTU and keepalive: `tailscale set --accept-dns=false`

---

## 5. OCR Pipeline Quality Filters

### aicamera1 (2 skips during test)
| Time | Reason |
|------|--------|
| 14:33 | `Low contrast (std=12.9)` — blank/overexposed region |
| 17:04 | `Too blurry (laplacian=34.8 < 60.0)` — motion blur or OOF |

Also: **Thai OCR timeout** at 15:05 and 16:50:
```
parallel_ocr_processor.py:86 - Thai OCR timed out for plate 0
```
Tesseract hung for >timeout seconds. Likely caused by low disk I/O contention when disk was nearly full.

### aicamera2 (3 skips during test)
| Time | Reason | Detail |
|------|--------|--------|
| 05:51 | `Width too small (65px < 80px)` | Plate at 65px wide — 3.9× upscale needed |
| 06:25 | `Width too small (66px < 80px)` | Same — vehicle too far or wrong angle |
| 09:02 | `Aspect ratio 1.45 invalid` | `81×56px` — nearly square, not a license plate |

### Analysis
The `80px minimum width` threshold is critical. At the current mounting distance/angle:
- Plates appear at 65-66px → **below threshold → OCR never triggered**
- This means no plate reading at all for those vehicle passes

**Possible causes:**
1. Camera mounted too far from the road
2. Camera angle too steep (plate appears foreshortened → aspect ratio invalid)
3. MAIN_RESOLUTION too low for the detection distance → plate too small in pixels

### Fix Required
1. Move camera closer to detection zone OR increase MAIN_RESOLUTION
2. Adjust mounting angle (more horizontal → better plate aspect ratio)
3. Consider reducing `width_min_px` threshold from 80 to 60px (with risk assessment)
4. Log plate pixel size more prominently to calibrate optimal mounting distance

---

## 6. SQLite Transaction Errors (aicamera2)

### Errors
```
database_manager.py:1151 - Error marking health check as sent: cannot commit - no transaction is active
database_manager.py:1151 - Error marking health check as sent: cannot start a transaction within a transaction
database_manager.py:1151 - Error marking health check as sent: error return without exception set
```

### Analysis
Multiple threads are accessing the SQLite connection concurrently. When health_monitor and detection_manager both try to write simultaneously, transaction state gets corrupted.

SQLite connections with `check_same_thread=False` don't automatically serialize writes — explicit locking is needed.

### Fix Required
Wrap all `connection.commit()` calls in `database_manager.py` with:
```python
try:
    if conn.in_transaction:
        conn.commit()
except Exception:
    pass  # already committed
```
Or use `connection.isolation_level = None` (autocommit) for the health check operations which are independent.

---

## 7. Dual Detection Manager Initialization (Both Cameras)

Every service start shows the `DetectionManager` initializing **twice**:
```
00:46:17 detection_manager.py - Initializing Detection Manager...
00:46:17 detection_processor.py - Starting model loading process...
...
00:46:22 detection_manager.py - Starting detection service...
00:46:22 detection_manager.py - Initializing Detection Manager...  ← SECOND TIME
00:46:22 detection_processor.py - Starting model loading process...  ← loads models twice!
```

This doubles startup time and loads Hailo models into NPU twice unnecessarily.

### Fix Required
Find the duplicate initialization call in `app.py` or `detection_manager.py` and remove it.

---

## Priority Fix List

| Priority | Issue | Component | Fix |
|:--------:|-------|-----------|-----|
| P0 | Disk fills with chromium BrowserMetrics | cron job | Unconditional delete at reboot + daily |
| P0 | aicamera2 restart loop (port 80) | health_monitor | Verify port 5000 working after restart |
| P1 | WebSocket "/ not a connected namespace" | websocket_sender | Check namespace after reconnect |
| P1 | MQTT connection timeout | mqtt_client | Verify broker + reconnect logic |
| P1 | Plate too small → OCR never runs | Camera mounting | Move closer / increase resolution |
| P2 | SQLite concurrent write errors | database_manager | Serialize writes with lock |
| P2 | Thai OCR timeout (Tesseract hung) | parallel_ocr | Add process timeout + kill |
| P2 | Duplicate DetectionManager init | app.py | Remove duplicate call |
| P3 | aicamera2 autofocus failure (NoIR) | camera_handler | Set manual focus for fixed mount |

---

## Immediate Next Steps

### aicamera1 (disk cleared — service still running)
```bash
ssh camuser@aicamera1
# 1. Fix cron to prevent chromium regrowth
sudo crontab -e  # Add: @reboot camuser rm -rf /tmp/chromium-kiosk/BrowserMetrics/
# 2. Restart service to get latest git (if not done)
sudo systemctl restart aicamera_lpr.service
```

### aicamera2 (service restarted with port fix)
```bash
ssh camuser@aicamera2
# Verify port 5000 is accessible
curl http://localhost:5000/detection/status | python3 -m json.tool
# Monitor for restart loop (should stop now)
journalctl -u aicamera_lpr.service -f | grep -E "Stopping camera|Started"
# Check chromium preemptively
du -sh /tmp/chromium-kiosk/ 2>/dev/null
```

### Camera mounting adjustment
- aicamera2: plate width only 65-66px → camera too far or angle too steep
- Target: plate width ≥ 100px at normal vehicle pass distance
- Reduce distance to road OR tilt camera more horizontal

---

## Key Metrics from Test

| Metric | aicamera1 | aicamera2 |
|--------|-----------|-----------|
| Service start time | Jun 02 11:39 | Jun 02 11:42 |
| Service restarts in 24h | 0 ✅ | 11 ❌ |
| OCR quality skips | 2 | 3 |
| Thai OCR timeouts | 2 | 0 |
| WebSocket failures | ~8 | ~8 |
| MQTT failures | ~7 | ~5 |
| Disk at end of test | 0% free → cleared | 66% used |
| Image saves failed | ~4 (disk full) | 0 |

---

*Analysis date: 2026-06-03 | Source: aicamera.log pulled remotely*
