#!/usr/bin/env python3
"""
OCR Queue Worker — Async Producer-Consumer OCR for edge LPR pipeline.

Runs Tesseract (ThaiLPROCR) in a background thread so the main detection
loop is never blocked waiting for OCR.

Usage
-----
    worker = OcrQueueWorker(thai_lp_ocr=thai_ocr, logger=logger)
    worker.start()

    # Producer (main thread) — non-blocking:
    submitted = worker.submit(task)   # returns False if queue full

    # Consumer poll (main thread, each frame):
    for result in worker.drain_results():
        # handle OcrResult

    worker.cleanup()   # graceful shutdown
"""

import queue
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OcrTask:
    """One plate crop submitted to the OCR worker."""
    track_id: int
    plate_crop: np.ndarray          # BGR uint8 — best crop for this track
    bbox: List[float]               # [x1, y1, x2, y2] in original frame coords
    det_confidence: float
    frame_timestamp: float          # time.time() when frame was captured
    camera_id: str
    submitted_at: float = field(default_factory=time.time)


@dataclass
class OcrResult:
    """OCR result returned to the main thread."""
    track_id: int
    text: str
    confidence: float
    method: str                     # "tesseract", "hailo", "fallback"
    valid_thai: bool
    bbox: List[float]
    det_confidence: float
    frame_timestamp: float
    camera_id: str
    completed_at: float = field(default_factory=time.time)
    error: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────────────────────────────────────

_SENTINEL = None   # signals worker thread to exit


class OcrQueueWorker:
    """
    Background OCR worker using threading (not multiprocessing).

    Tesseract is a subprocess — its CPU work is fork()-ed outside GIL, so
    threading is sufficient and avoids pickling / IPC overhead.

    Parameters
    ----------
    thai_lp_ocr
        ThaiLPROCR instance (must already be loaded before passing here).
    ocr_queue_maxsize
        Max pending tasks.  put_nowait() drops new tasks when full.
    result_queue_maxsize
        Max unconsumed results before oldest are dropped.
    num_workers
        Number of parallel worker threads.  RPi5 has 4 cores; 1-2 is safe.
    logger
        Standard Python logger.
    """

    def __init__(
        self,
        thai_lp_ocr,
        ocr_queue_maxsize: int = 10,
        result_queue_maxsize: int = 50,
        num_workers: int = 1,
        logger: Optional[logging.Logger] = None,
    ):
        self.thai_lp_ocr = thai_lp_ocr
        self.logger = logger or logging.getLogger(__name__)
        self.num_workers = max(1, num_workers)

        self._ocr_queue: queue.Queue = queue.Queue(maxsize=ocr_queue_maxsize)
        self._result_queue: queue.Queue = queue.Queue(maxsize=result_queue_maxsize)

        self._workers: List[threading.Thread] = []
        self._running = False

        # Stats (thread-safe via GIL for simple int counters)
        self._stats = {
            'submitted': 0,
            'dropped_full': 0,
            'processed': 0,
            'errors': 0,
        }

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        """Start background worker thread(s)."""
        if self._running:
            return
        self._running = True
        for i in range(self.num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"ocr-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        self.logger.info(
            f"[OCR_WORKER] Started {self.num_workers} worker thread(s)"
        )

    def cleanup(self):
        """Graceful shutdown — drain queue then join threads."""
        if not self._running:
            return
        self._running = False

        # Send one sentinel per worker
        for _ in self._workers:
            try:
                self._ocr_queue.put(_SENTINEL, timeout=1.0)
            except queue.Full:
                pass

        for t in self._workers:
            t.join(timeout=5.0)

        self._workers.clear()
        self.logger.info(
            f"[OCR_WORKER] Shutdown complete — "
            f"submitted={self._stats['submitted']} "
            f"dropped={self._stats['dropped_full']} "
            f"processed={self._stats['processed']} "
            f"errors={self._stats['errors']}"
        )

    # ── producer API ───────────────────────────────────────────────────────────

    def submit(self, task: OcrTask) -> bool:
        """
        Non-blocking submit.  Returns True if queued, False if dropped.
        Never blocks the calling thread.
        """
        try:
            self._ocr_queue.put_nowait(task)
            self._stats['submitted'] += 1
            self.logger.debug(
                f"[OCR_WORKER] Queued track_id={task.track_id} "
                f"queue_size={self._ocr_queue.qsize()}"
            )
            return True
        except queue.Full:
            self._stats['dropped_full'] += 1
            self.logger.warning(
                f"[OCR_QUEUE_DROP] queue full — dropping track_id={task.track_id} "
                f"(total_dropped={self._stats['dropped_full']})"
            )
            return False

    # ── consumer API ──────────────────────────────────────────────────────────

    def drain_results(self) -> List[OcrResult]:
        """
        Non-blocking poll of completed OCR results.
        Call once per frame iteration in the main thread.
        """
        results = []
        while True:
            try:
                results.append(self._result_queue.get_nowait())
            except queue.Empty:
                break
        return results

    # ── stats ─────────────────────────────────────────────────────────────────

    @property
    def queue_size(self) -> int:
        return self._ocr_queue.qsize()

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    # ── worker loop ───────────────────────────────────────────────────────────

    def _worker_loop(self):
        """Run in background thread — pull tasks, run OCR, push results."""
        self.logger.info(
            f"[OCR_WORKER] {threading.current_thread().name} started"
        )
        while True:
            try:
                task = self._ocr_queue.get(timeout=1.0)
            except queue.Empty:
                if not self._running:
                    break
                continue

            # Sentinel — time to exit
            if task is _SENTINEL:
                break

            result = self._run_ocr(task)
            self._stats['processed'] += 1

            # Push result; if result queue is full drop oldest
            try:
                self._result_queue.put_nowait(result)
            except queue.Full:
                try:
                    self._result_queue.get_nowait()   # drop oldest
                except queue.Empty:
                    pass
                self._result_queue.put_nowait(result)

        self.logger.info(
            f"[OCR_WORKER] {threading.current_thread().name} exited"
        )

    def _run_ocr(self, task: OcrTask) -> OcrResult:
        """Execute OCR for one task.  Runs in worker thread."""
        t0 = time.perf_counter()
        try:
            from edge.src.components.thai_lp_ocr import (
                preprocess_plate_crop,
                validate_thai_plate,
            )

            preprocessed = preprocess_plate_crop(task.plate_crop.copy())
            thai_result = self.thai_lp_ocr.read_plate(preprocessed)

            text = thai_result.get('text', '') if thai_result else ''
            confidence = thai_result.get('confidence', 0.0) if thai_result else 0.0
            valid = False
            if text:
                validation = validate_thai_plate(text)
                valid = validation.get('valid', False)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.logger.debug(
                f"[OCR_WORKER] track_id={task.track_id} "
                f"text='{text}' valid={valid} "
                f"elapsed={elapsed_ms:.0f}ms"
            )
            return OcrResult(
                track_id=task.track_id,
                text=text,
                confidence=confidence,
                method='tesseract',
                valid_thai=valid,
                bbox=task.bbox,
                det_confidence=task.det_confidence,
                frame_timestamp=task.frame_timestamp,
                camera_id=task.camera_id,
            )

        except Exception as e:
            self._stats['errors'] += 1
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.logger.error(
                f"[OCR_WORKER] OCR error track_id={task.track_id} "
                f"elapsed={elapsed_ms:.0f}ms: {e}"
            )
            return OcrResult(
                track_id=task.track_id,
                text='',
                confidence=0.0,
                method='tesseract',
                valid_thai=False,
                bbox=task.bbox,
                det_confidence=task.det_confidence,
                frame_timestamp=task.frame_timestamp,
                camera_id=task.camera_id,
                error=str(e),
            )
