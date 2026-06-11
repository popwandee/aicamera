# Field Test Analysis — 2026-06-11
**Session:** 09:17 – 09:20 | Vehicle: งน 2912 เชียงใหม่  
**Firmware:** commit `6926872` (feat: DEDUP_UPGRADE deployed 09:15-09:16)

---

## A. Test Overview

| Item | Value |
|------|-------|
| Vehicle | งน 2912 เชียงใหม่ |
| Passes | 2 (Pass 1: 09:17:42, Pass 2: 09:19:05) |
| Cameras | aicamera1 (cam1, IMX708 colour) + aicamera2 (cam2, IMX708 NoIR) |
| Commit | `6926872` — first test after DEDUP_UPGRADE feature deployed |

---

## B. Per-Camera Results

| Camera | Record ID | Time | Plate (conf) | Notes |
|--------|-----------|------|--------------|-------|
| cam1 | 1838 | 09:17:54 | No OCR | First plate: PLATE_CROP_SKIP |
| cam1 | 1839 | 09:19:05 | งน 12 (53.0%) | OCR partial — digits "29" missing |
| cam2 | 1863 | 09:17:54 | No OCR | First plate: PLATE_CROP_SKIP |
| cam2 | 1864 | 09:19:05 | AM 2912 \| เลยโหม (56.5%) | OCR: digits correct, consonants wrong, province wrong |

**Target: งน 2912 เชียงใหม่**  
Neither camera got a complete correct reading.

---

## C. Full Timeline (both cameras)

### Pass 1 — track=1 (09:17:42 – 09:17:55, ~13 seconds)

```
09:17:42  [TRACK_NEW] track=1  — vehicle first detected (conf=0.898)
          52 consecutive frames: SAVE_DEFER (no plate visible in any frame)

09:17:54  FRAME 54 — first plate detected (SAVE FRAME)
          cam1: [PLATE] conf=0.672 size=~108×~72px ar≈1.5 (borderline)
          cam2: [PLATE] conf=0.732 size=107×~72px ar<1.5
          [PLATE_CROP_SKIP] both cameras → crop rejected (ar or size bad)
          [OCR_GATE] SKIP track=1: best_crop_lap=0 (buffer empty)
          [DB_SAVE] cam1=ID1838, cam2=ID1863 (no OCR, pending)
          [TRACK_SAVED] track=1 — saved_plate_conf≈0.67, saved_plate_ar≈1.0
          [OCR_PENDING] record=1838/1863 tracks=[1]

09:17:55  FRAMES 55–58 — plate improves (DEDUP window, elapsed 0.9-1.6s)
          [DEDUP_BLOCK] track=1 each frame (elapsed < 30s)
          [DEDUP_UPGRADE_SKIP] at DEBUG level — criteria NOT met (see Section E)
          cam1 plates: conf=0.672-0.760, ar=1.52-1.95, lap=706-799 → [PLATE_CROP] ✓
          cam2 plates: conf=0.672-0.732, ar<1.5 → [PLATE_CROP_SKIP]
          plate_crop_buffer fills: cam1 buf_depth=1→4 (good crops accumulated)
                                   cam2 buf_depth=1→4 (but crops skipped — bad AR)

09:17:55  Vehicle leaves frame ("Vehicles detected: 0 filtered from 1")
          ≈ 1 second after first plate detection → OCR never submitted
```

### Gap: 09:17:55 – 09:19:05 (70 seconds)
Vehicle drove away. No detections.

### Pass 2 — track=2 (09:19:05, DEDUP_REENTRY)

```
09:19:05  [DEDUP_REENTRY] track=2 — new track (first_seen > last_saved of track=1)
          elapsed since track=1 save: 71s > 30s threshold

          cam1: [PLATE] conf=0.760 size=161×88px ar=1.83
                [PLATE_CROP] raw=161×88 padded=241×132 ar=1.83 lap=741 buf_depth=1
                [OCR_GATE] PASS track=2: frames=1 score=0.523 best_lap=741
                [OCR_SUBMIT] track=2 crop=241×132px blur=741
                [DB_SAVE] ID=1839 (no OCR yet, pending)
                [OCR_PENDING] record=1839 tracks=[2]

          cam2: [PLATE] conf=0.760 size=160×~87px ar≈1.84
                [PLATE_CROP] ar=1.83 lap=375 buf_depth=1
                [OCR_GATE] PASS track=2: frames=1 score=0.421 best_lap=375
                [OCR_SUBMIT] track=2 crop=240×~130px blur=375
                [DB_SAVE] ID=1864 (pending)
                [OCR_PENDING] record=1864 tracks=[2]

09:19:07  OCR_DONE (both cameras, ~2s after submit)
          cam1: [OCR_UPDATE] record=1839 → "งน 12" (53.0%)
          cam2: [OCR_UPDATE] record=1864 → "AM 2912 | เลยโหม" (56.5%)
          [OCR_FLUSH] both — pending_remaining=1 (track=1 record still pending)
```

---

## D. DEDUP_UPGRADE Analysis

### D.1 Why DEDUP_UPGRADE did NOT fire

Criteria checked in `_filter_upgrade_tracks()`:
- **Path A (area):** `new_area > saved_area × 2.0 AND new_conf > saved_conf × 1.2`
- **Path B (AR):** *(not in this version — added in commit after this test)*

At save time (frame 54):  
`saved_plate_conf ≈ 0.672`, `saved_plate_area ≈ 7776px²`, `saved_plate_ar ≈ 1.0`

Post-save DEDUP frames (cam1):
| Frame | new_conf | new_area | new_ar | area>2× ? | conf>1.2× ? |
|-------|----------|----------|--------|-----------|-------------|
| +0.9s | 0.672 | 9559 | 1.53 | 9559>15552? ❌ | 0.672>0.806? ❌ |
| +1.1s | 0.672 | 9216 | 1.78 | ❌ | ❌ |
| +1.4s | 0.732 | 8509 | 1.90 | ❌ | ❌ |
| +1.6s | 0.760 | 8000 | 1.95 | ❌ | ❌ |

**Root cause:** The plate was not larger — it was the same physical plate at nearly the same distance. The improvement was in **shape** (AR 1.0→1.9) and **sharpness** (lap 0→706-799), NOT in area. The 2× area threshold was designed for "vehicle moves closer" but this is a "partial plate→full plate" scenario.

### D.2 What DID work correctly

| Feature | Status | Evidence |
|---------|--------|---------|
| Plate detection continues despite DEDUP_BLOCK | ✅ | [PLATE] logged after [DEDUP_SKIP] |
| `_tracking_pass2` runs for upgrade tracks | ✅ | [PLATE_CROP] logged for dedup'd track |
| `plate_crop_buffer` fills during dedup window | ✅ | cam1 buf_depth=1→4 with lap=706-799 |
| DEDUP_UPGRADE_SKIP logged (at DEBUG) | ✅ | Not visible in INFO logs, but code ran |
| DEDUP_REENTRY correctly identifies second pass | ✅ | track=2 created at 09:19:05 |
| OCR submits successfully on second pass | ✅ | OCR_DONE at 09:19:07 |

### D.3 Fix deployed (commit after this test)

Added **Path B** to upgrade criteria:
```python
# Path B: aspect ratio improved into valid range (bad crop → good crop)
ar_ok = new_ar >= 1.5 and saved_ar < 1.5 and new_conf >= saved_conf * 0.9
```

With Path B active, the cam1 frames at +0.9s would trigger:
- `new_ar = 1.53 >= 1.5` ✓ AND `saved_ar ≈ 1.0 < 1.5` ✓ AND `0.672 >= 0.672 × 0.9` ✓
- → **[DEDUP_UPGRADE]** fires → OCR_SUBMIT from cam1's buffer (lap=799) → record 1838 patched

---

## E. OCR Accuracy Analysis (Pass 2)

| Camera | Crop | Lap | OCR Result | Target | Accuracy |
|--------|------|-----|-----------|--------|---------|
| cam1 | 241×132px | 741 | งน 12 | งน 2912 | 50% — digits "29" dropped |
| cam2 | 240×130px | 375 | AM 2912 \| เลยโหม | งน 2912 เชียงใหม่ | Digits ✓, consonants ✗, province ✗ |

**Combined reading:** cam1 gets "งน" (consonants) ✓, cam2 gets "2912" (digits) ✓ — each camera sees part correctly.

### Root gaps for OCR failure

| Gap | cam1 | cam2 |
|-----|------|------|
| Lap score | 741 (good) | 375 (borderline) |
| Crop size | 241×132 | 240×130 |
| Digit drop | "29" missing in "งน **29**12" | — |
| Consonant error | — | "งน" read as "AM" |
| Province error | — | "เชียงใหม่" → "เลยโหม" |
| Likely cause | PSM 11 sparse text may drop interior characters | Tesseract confused noise as consonants |

---

## F. System Behavior vs Intent

| Intended behavior | Actual behavior | Gap |
|-------------------|-----------------|-----|
| Save first detection (any quality) | ✅ Saved at 09:17:54 | — |
| DEDUP_BLOCK subsequent frames in 30s window | ✅ Correctly blocked | — |
| Continue plate detection for upgrade check | ✅ Plate detected after DEDUP | — |
| Fill plate_crop_buffer during dedup window | ✅ cam1 buf_depth=4 | — |
| Trigger DEDUP_UPGRADE when better plate seen | ❌ Did NOT fire | Area threshold too strict (see D.1) |
| Re-submit OCR on upgraded record | N/A (upgrade didn't trigger) | — |
| DEDUP_REENTRY on second pass (>30s) | ✅ track=2 at +71s | — |
| OCR correct on second pass | ⚠️ Partial only | Digits or consonants missing |

**Score: 5/7 intended behaviors working.** Two gaps: DEDUP_UPGRADE criteria (fixed post-test) and OCR accuracy.

---

## G. Action Items

| # | Item | Priority | Status |
|---|------|----------|--------|
| G.1 | Fix DEDUP_UPGRADE: add AR path (`new_ar≥1.5 AND saved_ar<1.5`) | 🔴 Critical | ✅ Fixed in next commit |
| G.2 | Verify DEDUP_UPGRADE fires on next test (look for `[DEDUP_UPGRADE]` token) | 🔴 Critical | ⏳ Pending test |
| G.3 | OCR: cam2 lap=375 borderline — consider raising OCR_GATE threshold OR improving crop upscale | 🟡 Medium | ⏳ Pending |
| G.4 | OCR: cam1 drops interior digits ("29" in "2912") — test PSM 6 or 7 for digits-only crop | 🟡 Medium | ⏳ Pending |
| G.5 | Hardware: cam1 plate enters left edge → poor AR on first detect → test pointing camera slightly right | 🟡 Medium | ⏳ Pending |
| G.6 | OCR_FLUSH: record 1838/1863 still has `pending_remaining=1` after pass 2 flush → investigate | 🟢 Low | ⏳ Pending |

---

## H. Monitor Commands for Next Test

```bash
# Watch upgrade feature on cam1
ssh camuser@aicamera1
tail -f ~/aicamera/edge/logs/aicamera.log | grep -E '\[(DEDUP_BLOCK|DEDUP_UPGRADE|OCR_SUBMIT|OCR_UPDATE|OCR_FLUSH)\]'

# Key tokens to look for:
# [DEDUP_UPGRADE] reason=ar 1.00→1.53 — upgrade fired (AR path)
# [OCR_SUBMIT] track=1 — re-queued from buffer
# [OCR_UPDATE] record=1838 — existing record patched
# [OCR_FLUSH] pending_remaining=0 — all pending cleared
```

---

## I. Next Test Checklist

- [ ] Deploy fixed code (commit after `6926872`) to both cameras
- [ ] Run same vehicle test: 1 slow pass through frame center
- [ ] Verify `[DEDUP_UPGRADE]` fires within 1-2s of first plate detection
- [ ] Check DB record is patched with OCR result (no new record created)
- [ ] If OCR still partial: try adjusting `PLATE_CONFIDENCE_THRESHOLD=0.3`
