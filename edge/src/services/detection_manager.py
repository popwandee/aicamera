#!/usr/bin/env python3
"""
Detection Manager — AI Camera edge module.

Orchestrates the full LPR pipeline per frame:
  enhance → detect vehicles → track (pass 1) → detect plates
  → track (pass 2, wire plate context) → OCR → save JPEG → DB

Async OCR path  (preferred):
  Plate crops are submitted to OcrQueueWorker (non-blocking).
  Results are polled each frame and patched back into the DB record.

Sync OCR fallback:
  Used when no OcrQueueWorker is attached to the DetectionProcessor.

Deduplication — two layers:
  1. IoU + reentry_time_threshold  per track_id
  2. Plate-text window             per normalised plate string (default 60 s)
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import numpy as np

from edge.src.core.config import (
    DETECTION_INTERVAL, AUTO_START_DETECTION, STARTUP_DELAY,
    TRACKING_ENABLED, REENTRY_TIME_THRESHOLD, IOU_THRESHOLD, AICAMERA_ID,
)
from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger

logger = get_logger(__name__)


class DetectionManager:
    """Orchestrates the AI detection pipeline for one edge camera."""

    # ──────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────

    def __init__(self, detection_processor=None, database_manager=None, logger=None):
        self.detection_processor = detection_processor
        self.database_manager    = database_manager
        self.logger              = logger or get_logger(__name__)

        self.is_running         = False
        self.detection_thread: Optional[threading.Thread] = None
        self.detection_interval = DETECTION_INTERVAL
        self.auto_start_enabled = AUTO_START_DETECTION

        self.detection_stats: Dict[str, Any] = {
            'started_at':              None,
            'total_frames_processed':  0,
            'total_vehicles_detected': 0,
            'total_plates_detected':   0,
            'successful_ocr':          0,
            'failed_detections':       0,
            'last_detection':          None,
            'processing_time_avg':     0.0,
        }

        # Tracking / dedup config
        self.tracking_enabled       = TRACKING_ENABLED
        self.reentry_time_threshold = REENTRY_TIME_THRESHOLD
        self.iou_threshold          = IOU_THRESHOLD

        # Layer-1 dedup: IoU + time per track_id
        self.recent_tracks: Dict[int, Dict] = {}
        self.track_cleanup_interval         = 300.0   # s
        self.last_track_cleanup             = time.time()

        # Layer-2 dedup: same normalised plate text within window
        self.recent_plate_texts: Dict[str, float] = {}
        self.plate_text_dedup_window              = 60.0   # s

        # Async OCR: track_id → pending DB record id
        self._pending_ocr_updates: Dict[int, int] = {}

        # Tracks that were DEDUP_BLOCK'd but may qualify for plate upgrade this frame
        self._potential_upgrade_tracks: list = []

        self.logger.info(f"DetectionManager initialised (tracking={self.tracking_enabled})")

    # ── init / start / stop ───────────────────────────────────────────

    def initialize(self) -> bool:
        if not self.detection_processor:
            self.logger.error("Detection processor not available")
            return False
        try:
            if not self.detection_processor.load_models():
                self.logger.error("Failed to load detection models")
                return False
            self.logger.info("Detection models loaded")
            if self.database_manager and not self.database_manager.initialize():
                self.logger.warning("Database initialisation failed")
            return self._auto_start_detection() if self.auto_start_enabled else True
        except Exception as e:
            self.logger.error(f"initialize: {e}")
            return False

    def _auto_start_detection(self) -> bool:
        try:
            self.logger.info(f"Auto-start: waiting {STARTUP_DELAY}s for camera …")
            time.sleep(STARTUP_DELAY)
            cam = get_service('camera_manager')
            if cam and cam.get_status().get('streaming', False):
                if self.start_detection():
                    self.logger.info("Detection auto-started ✓")
                    return True
            self.logger.warning("Camera not streaming — auto-start deferred")
            return False
        except Exception as e:
            self.logger.error(f"_auto_start_detection: {e}")
            return False

    def start_detection(self) -> bool:
        if self.is_running:
            return True
        if not self.detection_processor or not self.detection_processor.models_loaded:
            self.logger.error("Models not loaded — cannot start detection")
            return False
        self.is_running = True
        self.detection_thread = threading.Thread(
            target=self._detection_loop, name="DetectionThread", daemon=True)
        self.detection_thread.start()
        self.detection_stats['started_at'] = datetime.now().isoformat()
        self.logger.info("Detection started")
        return True

    def stop_detection(self) -> bool:
        if not self.is_running:
            return True
        self.is_running = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=5.0)
        self.detection_thread = None
        self.logger.info("Detection stopped")
        return True

    def cleanup(self):
        self.stop_detection()
        if self.detection_processor:
            try:
                self.detection_processor.cleanup()
            except Exception as e:
                self.logger.warning(f"cleanup: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Detection loop
    # ──────────────────────────────────────────────────────────────────

    def _detection_loop(self):
        self.logger.info("Detection loop started")
        while self.is_running:
            try:
                cam = get_service('camera_manager')
                if cam and self._is_camera_ready(cam):
                    self.process_frame_from_camera(cam)
                else:
                    self.logger.debug("Camera not ready — waiting")
                time.sleep(self.detection_interval)
            except Exception as e:
                self.logger.error(f"Detection loop error: {e}")
                time.sleep(1.0)
        self.logger.info("Detection loop stopped")

    def _is_camera_ready(self, cam) -> bool:
        try:
            s = cam.get_status()
            return s.get('initialized', False) and s.get('streaming', False)
        except Exception:
            return False

    def process_frame_from_camera(self, camera_manager) -> Optional[Dict[str, Any]]:
        try:
            frame = camera_manager.camera_handler.capture_frame(
                source="buffer", stream_type="main", include_metadata=False)
            if frame is None or not isinstance(frame, np.ndarray):
                return None
            return self.process_frame(frame)
        except Exception as e:
            self.logger.error(f"process_frame_from_camera: {e}")
            self.detection_stats['failed_detections'] += 1
            return None

    # ──────────────────────────────────────────────────────────────────
    # Core pipeline
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # Async OCR flush — must run every frame regardless of detection gate
    # ──────────────────────────────────────────────────────────────────

    def _flush_pending_ocr(self, detect_fid: int):
        """
        Drain completed async OCR results and patch their DB records.

        Called unconditionally at the TOP of every process_frame() invocation —
        before any early-return gate.  This guarantees Tesseract results are
        written to the DB even when:
          • the vehicle has already left the frame, OR
          • all subsequent frames are suppressed by DEDUP_BLOCK.

        Without this, poll_ocr_results() would only run when a NEW vehicle is
        detected, stranding every OCR result from a single-vehicle drive-by.
        """
        async_worker = getattr(self.detection_processor, 'ocr_queue_worker', None)
        if not async_worker or not self._pending_ocr_updates:
            return
        polled = self.detection_processor.poll_ocr_results()
        if not polled:
            return
        for res in polled:
            tid = res.get('track_id')
            rid = self._pending_ocr_updates.pop(tid, None)
            if rid and self.database_manager:
                self._update_db_ocr(rid, [res])
            if tid and tid in self.recent_tracks:
                ocr_text = res.get('text', '')
                if ocr_text:
                    self.recent_tracks[tid]['saved_has_ocr'] = True
                else:
                    # Empty OCR result: keep saved_has_ocr=False so that
                    # DEDUP_UPGRADE Path C can fire again when the plate
                    # reaches a more perpendicular angle (side-pass scenario).
                    self.logger.debug(
                        f"[OCR_FLUSH] track={tid} OCR empty — "
                        f"saved_has_ocr stays False (upgrade retry allowed)")
        self.detection_stats['successful_ocr'] += len(polled)
        self.logger.info(
            f"[OCR_FLUSH] fid={detect_fid} {len(polled)} result(s) flushed "
            f"pending_remaining={len(self._pending_ocr_updates)}")

    # ──────────────────────────────────────────────────────────────────
    # Core pipeline
    # ──────────────────────────────────────────────────────────────────

    def process_frame(self, frame) -> Optional[Dict[str, Any]]:
        """
        Run one LPR frame through the full pipeline.
        Returns a detection-record dict on success, None otherwise.
        None may mean "nothing to save this frame" — not necessarily an error.
        """
        t0         = time.time()
        detect_fid = id(frame) % 1_000_000
        self.detection_stats['total_frames_processed'] += 1

        try:
            # Flush completed async OCR before any early-return gate.
            # Must run every frame so results aren't stranded when the vehicle
            # leaves frame and no new detections trigger _handle_ocr.
            self._flush_pending_ocr(detect_fid)

            # 1. Validate & enhance
            enhanced = self.detection_processor.validate_and_enhance_frame(frame)
            if enhanced is None:
                return None

            # 2. Vehicle detection
            vehicle_boxes, mapping_info = self.detection_processor.detect_vehicles(enhanced)
            if not vehicle_boxes:
                return None
            self.detection_stats['total_vehicles_detected'] += len(vehicle_boxes)
            for vb in vehicle_boxes:
                x1, y1, x2, y2 = vb['bbox']
                self.logger.info(
                    f"[VEHICLE] fid={detect_fid} conf={vb.get('score',0):.3f} "
                    f"size={int(x2-x1)}×{int(y2-y1)}px")

            # 3. Tracking pass 1 — vehicle level (no plate info yet)
            tracks_to_save = self._tracking_pass1(vehicle_boxes, frame, detect_fid)
            # Capture upgrade candidates populated by _should_save_detection()
            upgrade_tracks = list(self._potential_upgrade_tracks)
            self._potential_upgrade_tracks.clear()
            if tracks_to_save is not None and not tracks_to_save and not upgrade_tracks:
                return None   # all vehicles are duplicates, none upgradeable

            # 4. Plate detection
            plate_boxes = self.detection_processor.detect_license_plates(
                enhanced, vehicle_boxes, mapping_info)
            if plate_boxes:
                self.detection_stats['total_plates_detected'] += len(plate_boxes)
                for pb in plate_boxes:
                    x1, y1, x2, y2 = pb['bbox']
                    pw, ph = int(x2-x1), int(y2-y1)
                    ar_str = f" ar={pw/ph:.2f}" if ph > 0 else ""
                    self.logger.info(
                        f"[PLATE] fid={detect_fid} conf={pb.get('score',0):.3f} "
                        f"size={pw}×{ph}px{ar_str}")

            # 5. Tracking pass 2 — wire plate context so best_frame_data
            #    is only updated on frames where a plate is visible
            if tracks_to_save and plate_boxes:
                self._tracking_pass2(tracks_to_save, vehicle_boxes, plate_boxes, frame)

            # 5b. Upgrade check — re-submit OCR on existing records if better plate seen
            if upgrade_tracks and plate_boxes:
                self._tracking_pass2(upgrade_tracks, vehicle_boxes, plate_boxes, frame)
                qualified = self._filter_upgrade_tracks(upgrade_tracks, plate_boxes, detect_fid)
                if qualified:
                    self._submit_ocr_for_tracks(qualified, detect_fid)

            # Gate: skip save if no plate visible this frame
            if not plate_boxes:
                self.logger.info(
                    f"[SAVE_DEFER] fid={detect_fid} "
                    "no plate visible — keeping tracks eligible for next frame")
                return None

            # Gate: if only upgrade tracks were processed (no new record needed)
            if tracks_to_save is not None and not tracks_to_save:
                return None

            # 6. OCR (async poll + submit, or sync fallback)
            ocr_results = self._handle_ocr(
                detect_fid, plate_boxes, enhanced, tracks_to_save or [])

            # 7. Save JPEG — always use current frame so bbox alignment is guaranteed
            self.logger.info(f"[FRAME_SAME] fid={detect_fid} — saving current frame ✓")
            original_path, _, _, _ = self.detection_processor.save_detection_results(
                frame, vehicle_boxes, plate_boxes, ocr_results)

            # 8. Build record and persist to DB
            processing_time = time.time() - t0
            record    = self._build_record(vehicle_boxes, plate_boxes, ocr_results,
                                           original_path, mapping_info, processing_time)
            record_id = self._persist_record(detect_fid, record, ocr_results, original_path)

            # 9. Mark tracks saved; register pending async OCR update
            if self.tracking_enabled and tracks_to_save:
                for track in tracks_to_save:
                    self._mark_track_saved(track)
                    # Store record_id so a later upgrade can patch the same record
                    if record_id and track.track_id in self.recent_tracks:
                        self.recent_tracks[track.track_id]['record_id'] = record_id

            async_worker = getattr(self.detection_processor, 'ocr_queue_worker', None)
            if async_worker and plate_boxes and not ocr_results and record_id and tracks_to_save:
                for track in tracks_to_save:
                    self._pending_ocr_updates[track.track_id] = record_id
                self.logger.info(
                    f"[OCR_PENDING] record={record_id} "
                    f"tracks={[t.track_id for t in tracks_to_save]}")

            self._update_processing_stats(processing_time)
            self.detection_stats['last_detection'] = datetime.now().isoformat()
            self.logger.info(
                f"[PIPELINE_DONE] fid={detect_fid} "
                f"vehicles={len(vehicle_boxes)} plates={len(plate_boxes)} "
                f"ocr={len(ocr_results)} total={processing_time*1000:.0f}ms")
            return record

        except Exception as e:
            self.logger.error(f"[PROCESS_FRAME_ERROR] fid={detect_fid} {e}")
            self.detection_stats['failed_detections'] += 1
            return None

    # ──────────────────────────────────────────────────────────────────
    # Pipeline helpers
    # ──────────────────────────────────────────────────────────────────

    def _tracking_pass1(self, vehicle_boxes, frame, detect_fid) -> Optional[List]:
        """
        IoU tracking + dedup on vehicle detections.
        Returns:
          - List of eligible tracks  (may be empty → all duplicates → skip frame)
          - None                     → tracking disabled or error → fall through
        """
        if not self.tracking_enabled or \
                not hasattr(self.detection_processor, 'update_vehicle_tracks'):
            return None
        try:
            dets     = [{'bbox': vb['bbox'], 'score': vb.get('score', 0.0)}
                        for vb in vehicle_boxes]
            tracks   = self.detection_processor.update_vehicle_tracks(dets, frame)
            filtered = self.detection_processor.apply_deduplication_rules(tracks)
            eligible = [t for t in filtered if self._should_save_detection(t)]
            self.logger.info(
                f"[TRACKING] fid={detect_fid} active={len(tracks)} "
                f"filtered={len(filtered)} eligible={len(eligible)}")
            if not eligible:
                self.logger.info(
                    f"[DEDUP_SKIP] fid={detect_fid} "
                    f"all {len(tracks)} vehicle(s) are duplicates — skip save")
            return eligible
        except Exception as e:
            self.logger.warning(f"[TRACKING_PASS1] {e} — falling back to no-tracking mode")
            return None

    def _tracking_pass2(self, tracks_to_save, vehicle_boxes, plate_boxes, frame):
        """
        Wire plate_bbox into _update_track so best_frame_data is only replaced
        when the plate is actually visible.  Also populates plate_candidates
        so the OCR gating condition (min plate frames) is satisfied.
        """
        if not hasattr(self.detection_processor, '_update_track'):
            return
        try:
            # Build vehicle_idx → best plate box lookup
            vidx_to_pb: Dict[int, Dict] = {}
            for pb in plate_boxes:
                vidx = pb.get('vehicle_idx', -1)
                if vidx >= 0 and vidx not in vidx_to_pb:
                    vidx_to_pb[vidx] = pb

            now = time.time()
            for track in tracks_to_save:
                best_pb  = None
                best_iou = 0.0
                for vidx, pb in vidx_to_pb.items():
                    if vidx < len(vehicle_boxes):
                        iou = self.detection_processor._calculate_iou(
                            track.bbox, vehicle_boxes[vidx]['bbox'])
                        if iou > best_iou:
                            best_iou = iou
                            best_pb  = pb

                plate_bbox = best_pb['bbox'] if best_pb else None
                self.detection_processor._update_track(
                    track, {'bbox': track.bbox, 'score': track.confidence},
                    frame, now, plate_bbox=plate_bbox)

                # Populate plate_candidates (needed by submit_for_ocr gating)
                if best_pb and best_pb not in track.plate_candidates:
                    track.plate_candidates.append(best_pb)

                if plate_bbox:
                    self.logger.debug(
                        f"[TRACK_PLATE_WIRE] track={track.track_id} "
                        f"iou={best_iou:.3f} "
                        f"plate_candidates={len(track.plate_candidates)}")
        except Exception as e:
            self.logger.warning(f"[TRACKING_PASS2] {e}")

    def _handle_ocr(self, detect_fid, plate_boxes, enhanced_frame, tracks) -> List[Dict]:
        """
        Submit plate crops to the async OCR queue; fall back to sync OCR.

        NOTE: polling of completed async results is handled exclusively by
        _flush_pending_ocr(), which runs unconditionally at the top of every
        process_frame() before any early-return gate.  Do NOT add a poll here —
        it would double-count results and miss flushes on deduped frames.
        """
        async_worker = getattr(self.detection_processor, 'ocr_queue_worker', None)
        ocr_results: List[Dict] = []

        # Submit this frame's plates
        if plate_boxes:
            if async_worker:
                n = self._submit_ocr_for_tracks(tracks, detect_fid)
                if n:
                    self.logger.info(
                        f"[OCR_ASYNC_SUBMIT] fid={detect_fid} "
                        f"{n} task(s) queued for background Tesseract")
            else:
                # Sync fallback — blocks ~1.3 s per plate
                ocr_results = self.detection_processor.perform_ocr(
                    enhanced_frame, plate_boxes)
                self.logger.info(
                    f"[OCR_SYNC] fid={detect_fid} "
                    f"{len(ocr_results)} result(s) (no async worker)")

        if ocr_results:
            self.detection_stats['successful_ocr'] += len(ocr_results)
        return ocr_results

    def _submit_ocr_for_tracks(self, tracks, detect_fid: int) -> int:
        """
        Submit OCR tasks via detection_processor.submit_for_ocr (gated).
        Gating: plate_candidates, best_frame_score, ROI zone, ocr_submitted flag.
        """
        submitted = 0
        for track in tracks:
            if not track.plate_candidates:
                continue
            best_plate = max(track.plate_candidates, key=lambda p: p.get('score', 0.0))
            frame_shape = (
                track.best_frame_data.shape
                if track.best_frame_data is not None else (0, 0, 3))
            ok = self.detection_processor.submit_for_ocr(
                track          = track,
                plate_bbox     = best_plate['bbox'],
                det_confidence = best_plate.get('score', 0.0),
                frame_timestamp= time.time(),
                camera_id      = str(AICAMERA_ID),
                frame_shape    = frame_shape,
            )
            if ok:
                submitted += 1
        return submitted

    def _build_record(self, vehicle_boxes, plate_boxes, ocr_results,
                      original_path, mapping_info, processing_time) -> Dict[str, Any]:
        """Assemble the dict for database insertion."""
        record: Dict[str, Any] = {
            'timestamp':           datetime.now().isoformat(),
            'vehicles_count':      len(vehicle_boxes),
            'plates_count':        len(plate_boxes),
            'ocr_results':         ocr_results,
            'original_image_path': original_path or '',
            'vehicle_detections':  vehicle_boxes,
            'plate_detections':    plate_boxes,
            'processing_time_ms':  processing_time * 1000.0,
            'coordinate_mapping':  mapping_info,
        }
        if ocr_results:
            best = max(ocr_results, key=lambda r: r.get('confidence', 0))
            record.update({
                'best_ocr_text':   best.get('text', ''),
                'best_ocr_conf':   best.get('confidence', 0.0),
                'best_ocr_method': best.get('ocr_method', 'none'),
            })
        return record

    def _persist_record(self, detect_fid, record, ocr_results, original_path) -> Optional[int]:
        """Write record to DB; return its id."""
        if not original_path:
            self.logger.warning("[DB_SAVE] no image path — inserting without image")
        elif not os.path.exists(original_path):
            self.logger.warning(f"[DB_SAVE] image missing after write: {original_path}")
            record['original_image_path'] = ''

        if not self.database_manager:
            self.logger.warning("[DB_SAVE] no database_manager — record NOT stored")
            return None

        plate_text = ocr_results[0].get('text', '?')    if ocr_results else '—'
        ocr_conf   = ocr_results[0].get('confidence', 0) if ocr_results else 0
        ocr_meth   = ocr_results[0].get('ocr_method', '?') if ocr_results else '—'

        t_db = time.time()
        record_id = self.database_manager.insert_detection_result(record)
        db_ms = (time.time() - t_db) * 1000
        self.logger.info(
            f"[DB_SAVE] fid={detect_fid} id={record_id} "
            f"plate='{plate_text}' conf={ocr_conf:.3f} method={ocr_meth} "
            f"v={record['vehicles_count']} p={record['plates_count']} "
            f"img={'✓' if original_path else '✗'} db={db_ms:.0f}ms")
        return record_id

    # ──────────────────────────────────────────────────────────────────
    # Deduplication
    # ──────────────────────────────────────────────────────────────────

    def _should_save_detection(self, track) -> bool:
        """
        Two-layer duplicate guard.

        Layer 1 — IoU + time per track_id:
          Blocks if track_id was saved within reentry_time_threshold *and*
          current bbox overlaps the saved bbox by more than iou_threshold.

        Layer 2 — Plate-text window:
          Blocks if the same normalised plate text was saved within
          plate_text_dedup_window seconds, regardless of track_id.
          Handles track_id resets caused by fast IoU drops on the same vehicle.
        """
        if not self.tracking_enabled:
            return True
        try:
            now = time.time()
            # Periodic cleanup
            if now - self.last_track_cleanup > self.track_cleanup_interval:
                self._cleanup_old_tracks(now)
                self.last_track_cleanup = now

            # Layer 1 — track_id + time window + continuous-presence check
            #
            # Two distinct situations after elapsed > reentry_time_threshold:
            #
            #   A. Long stop (inspection, traffic jam): same physical vehicle is
            #      still continuously present.  track.first_seen <= info['last_saved']
            #      because the track was already alive when we last saved it.
            #      → DEDUP_BLOCK_CONTINUOUS — never record the same stop twice.
            #
            #   B. Genuine re-entry: vehicle left the frame, track expired, then
            #      came back and got a NEW track_id.  The new track has
            #      first_seen > info['last_saved'] (created AFTER the prior save).
            #      → DEDUP_REENTRY — allow (different visit).
            #
            # This replaces the old plain time-only DEDUP_REENTRY which caused
            # duplicate records for any vehicle stopped > 30 s.
            track_id = track.track_id
            info = self.recent_tracks.get(track_id)
            if info:
                elapsed = now - info['last_saved']
                if elapsed < self.reentry_time_threshold:
                    self.logger.info(
                        f"[DEDUP_BLOCK] track={track_id} "
                        f"elapsed={elapsed:.1f}s < {self.reentry_time_threshold}s "
                        f"prev='{info.get('plate_text','?')}' — skip")
                    if not info.get('saved_has_ocr', True):
                        self._potential_upgrade_tracks.append(track)
                    return False
                # Beyond the time window — distinguish long stop from re-entry
                track_first_seen = getattr(track, 'first_seen', 0.0)
                if track_first_seen <= info['last_saved']:
                    # Track was alive at (or before) last save → vehicle still present
                    self.logger.info(
                        f"[DEDUP_BLOCK_CONTINUOUS] track={track_id} "
                        f"elapsed={elapsed:.1f}s first_seen={track_first_seen:.1f} "
                        f"<= last_saved={info['last_saved']:.1f} — long stop, skip")
                    if not info.get('saved_has_ocr', True):
                        self._potential_upgrade_tracks.append(track)
                    return False
                self.logger.info(
                    f"[DEDUP_REENTRY] track={track_id} "
                    f"elapsed={elapsed:.1f}s first_seen={track_first_seen:.1f} "
                    f"> last_saved={info['last_saved']:.1f} — genuine re-entry, allow")
            else:
                self.logger.info(f"[DEDUP_NEW] track={track_id} first seen — allow")

            # Layer 2
            plate_text = ''
            if track.ocr_results:
                plate_text = track.ocr_results[-1].get('text', '').strip()
            norm = plate_text.upper().replace(' ', '')
            if len(norm) >= 3:
                last = self.recent_plate_texts.get(norm)
                if last and (now - last) < self.plate_text_dedup_window:
                    self.logger.info(
                        f"[DEDUP_PLATE_TEXT] track={track_id} "
                        f"plate='{plate_text}' seen {now-last:.1f}s ago "
                        f"(window={self.plate_text_dedup_window}s) — skip")
                    return False

            return True
        except Exception as e:
            self.logger.warning(f"_should_save_detection: {e}")
            return True

    def _get_best_plate_metrics(self, track) -> tuple:
        """Return (conf, area, ar) of track's best plate candidate."""
        if not track.plate_candidates:
            return 0.0, 0.0, 0.0
        best = max(track.plate_candidates, key=lambda p: p.get('score', 0.0))
        conf = best.get('score', 0.0)
        x1, y1, x2, y2 = best.get('bbox', [0, 0, 0, 0])
        w, h = max(0, x2 - x1), max(0, y2 - y1)
        area = float(w * h)
        ar   = (w / h) if h > 0 else 0.0
        return conf, area, ar

    def _mark_track_saved(self, track):
        """Record save; register plate text for Layer-2 dedup."""
        try:
            now        = time.time()
            track_id   = track.track_id
            plate_text = ''
            if track.ocr_results:
                plate_text = track.ocr_results[-1].get('text', '')

            saved_conf, saved_area, saved_ar = self._get_best_plate_metrics(track)
            self.recent_tracks[track_id] = {
                'last_saved':       now,
                'bbox':             list(track.bbox) if isinstance(track.bbox, list) else track.bbox,
                'plate_text':       plate_text,
                'saved_plate_conf': saved_conf,
                'saved_plate_area': saved_area,
                'saved_plate_ar':   saved_ar,
                'saved_has_ocr':    False,
                'record_id':        None,   # filled in by process_frame() after DB insert
            }
            self.logger.info(
                f"[TRACK_SAVED] track={track_id} plate='{plate_text or '?'}' "
                f"frames={track.frame_count} score={track.best_frame_score:.3f} "
                f"— dedup active {self.reentry_time_threshold}s")

            norm = plate_text.upper().replace(' ', '') if plate_text else ''
            if len(norm) >= 3:
                self.recent_plate_texts[norm] = now
                self.logger.info(
                    f"[PLATE_TEXT_REGISTERED] '{plate_text}' "
                    f"— dedup active {self.plate_text_dedup_window}s")
        except Exception as e:
            self.logger.warning(f"_mark_track_saved: {e}")

    def _cleanup_old_tracks(self, now: float):
        """Remove stale entries from both dedup caches."""
        cutoff = self.reentry_time_threshold * 2
        for tid in [k for k, v in self.recent_tracks.items()
                    if now - v['last_saved'] > cutoff]:
            del self.recent_tracks[tid]
        for k in [k for k, ts in self.recent_plate_texts.items()
                  if now - ts > self.plate_text_dedup_window * 2]:
            del self.recent_plate_texts[k]

    def _filter_upgrade_tracks(self, candidates: list, plate_boxes: list, detect_fid: int) -> list:
        """
        From the DEDUP_BLOCK'd candidates, return those whose current-frame plate
        is substantially better than what was saved.  Three upgrade paths:

          Path A — area×2:  plate area more than doubled (vehicle moved closer)
          Path B — AR cross: AR improved from < 1.5 to ≥ 1.5 (side-pass first good crop)
          Path C — AR peak:  AR improved from 1.4–1.9 to ≥ 2.0; only fires when the
                             previous OCR returned empty (saved_has_ocr=False).
                             Captures the more-perpendicular phase of a side-pass after
                             the first upgrade OCR failed at a shallow angle.

        Qualifying tracks have their ocr_submitted flag reset and their
        _pending_ocr_updates entry restored so _flush_pending_ocr() will
        patch the existing DB record when OCR completes.
        """
        if not plate_boxes:
            return []
        best_pb = max(plate_boxes, key=lambda p: p.get('score', 0.0))
        new_conf = best_pb.get('score', 0.0)
        x1, y1, x2, y2 = best_pb.get('bbox', [0, 0, 0, 0])
        w, h = max(0, x2 - x1), max(0, y2 - y1)
        new_area = float(w * h)
        new_ar   = (w / h) if h > 0 else 0.0

        result = []
        for track in candidates:
            info = self.recent_tracks.get(track.track_id)
            if not info:
                continue
            saved_area = info.get('saved_plate_area', 0.0)
            saved_conf = info.get('saved_plate_conf', 0.0)
            saved_ar   = info.get('saved_plate_ar',   0.0)

            has_ocr = info.get('saved_has_ocr', True)

            # Path A: substantially larger plate (vehicle moved closer)
            area_ok = new_area > saved_area * 2.0 and new_conf > saved_conf * 1.2
            # Path B: AR crossed 1.5 threshold (partial → full plate, first good crop)
            ar_ok   = new_ar >= 1.5 and saved_ar < 1.5 and new_conf >= saved_conf * 0.9
            # Path C: AR improved to ≥ 2.0 (plate more perpendicular = side-pass peak),
            # but only when previous OCR returned empty — avoids re-patching good results.
            ar_ok2  = (new_ar >= 2.0 and 1.4 <= saved_ar < 2.0
                       and not has_ocr and new_conf >= saved_conf * 0.85)

            if area_ok or ar_ok or ar_ok2:
                record_id = info.get('record_id')
                reason = ('area×2' if area_ok
                          else f'ar {saved_ar:.2f}→{new_ar:.2f}' if ar_ok
                          else f'ar2 {saved_ar:.2f}→{new_ar:.2f}')
                # Restore pending patch entry if OCR result was already consumed
                if record_id and track.track_id not in self._pending_ocr_updates:
                    self._pending_ocr_updates[track.track_id] = record_id
                # Reset submission flag so _submit_ocr_for_tracks re-queues this track
                track.ocr_submitted = False
                track.ocr_submitted_lap = 0.0
                # Update saved metrics to prevent repeated upgrades next frame
                info['saved_plate_area'] = new_area
                info['saved_plate_conf'] = new_conf
                info['saved_plate_ar']   = new_ar
                self.logger.info(
                    f"[DEDUP_UPGRADE] fid={detect_fid} track={track.track_id} "
                    f"reason={reason} area={new_area:.0f} "
                    f"conf {saved_conf:.3f}→{new_conf:.3f} "
                    f"record_id={record_id} — re-submit OCR")
                result.append(track)
            else:
                self.logger.debug(
                    f"[DEDUP_UPGRADE_SKIP] track={track.track_id} "
                    f"area={new_area:.0f}/{saved_area:.0f} ar={new_ar:.2f}/{saved_ar:.2f} "
                    f"conf={new_conf:.3f}/{saved_conf:.3f}")
        return result

    # ──────────────────────────────────────────────────────────────────
    # Async OCR DB patch
    # ──────────────────────────────────────────────────────────────────

    def _update_db_ocr(self, record_id: int, ocr_results: list):
        """Patch an existing DB record with completed async OCR text."""
        if not self.database_manager or not ocr_results:
            return
        try:
            best  = max(ocr_results, key=lambda r: r.get('confidence', 0))
            text  = best.get('text', '')
            conf  = best.get('confidence', 0)
            meth  = best.get('ocr_method', 'async_tesseract')
            conn  = self.database_manager.connection
            if conn:
                conn.execute(
                    "UPDATE detection_results "
                    "SET ocr_results=?, plates_count=MAX(plates_count,1) WHERE id=?",
                    (json.dumps(ocr_results), record_id))
                conn.commit()
                self.logger.info(
                    f"[OCR_UPDATE] record={record_id} "
                    f"plate='{text}' conf={conf:.3f} method={meth}")
        except Exception as e:
            self.logger.warning(f"[OCR_UPDATE] record={record_id}: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Stats / status
    # ──────────────────────────────────────────────────────────────────

    def _update_processing_stats(self, t: float):
        avg = self.detection_stats['processing_time_avg']
        self.detection_stats['processing_time_avg'] = (
            t if avg == 0.0 else 0.1 * t + 0.9 * avg)

    def _quality_metrics(self) -> Dict[str, float]:
        s      = self.detection_stats
        frames = s['total_frames_processed']
        plates = s['total_plates_detected']
        return {
            'detection_accuracy': round(
                s['total_vehicles_detected'] / frames * 100, 1) if frames else 0.0,
            'ocr_accuracy': round(
                s['successful_ocr'] / plates * 100, 1) if plates else 0.0,
            'system_reliability': round(
                max(0, 100 - s['failed_detections'] / frames * 100), 1) if frames else 100.0,
        }

    def get_status(self) -> Dict[str, Any]:
        proc: Dict = {}
        if self.detection_processor:
            proc = self.detection_processor.get_status()
            try:
                ocr = self.detection_processor.get_ocr_status()
                proc.update({
                    'vehicle_model_name':      ocr.get('vehicle_model_name'),
                    'lp_detection_model_name': ocr.get('lp_detection_model_name'),
                    'lp_ocr_model_name':       ocr.get('lp_ocr_model_name'),
                })
            except Exception:
                pass

        qm = self._quality_metrics()
        return {
            'service_running':            self.is_running,
            'detection_processor_status': proc,
            'detection_interval':         self.detection_interval,
            'auto_start':                 self.auto_start_enabled,
            'statistics':                 self.detection_stats.copy(),
            'thread_alive': (
                self.detection_thread.is_alive() if self.detection_thread else False),
            'last_update':                datetime.now().isoformat(),
            'detection_accuracy':         qm['detection_accuracy'],
            'ocr_accuracy':               qm['ocr_accuracy'],
            'system_reliability':         qm['system_reliability'],
        }


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────

def create_detection_manager(detection_processor=None,
                             database_manager=None,
                             logger=None) -> DetectionManager:
    """Return a new DetectionManager (does not call initialize())."""
    return DetectionManager(
        detection_processor=detection_processor,
        database_manager=database_manager,
        logger=logger,
    )
