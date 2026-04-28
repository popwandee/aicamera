#!/usr/bin/env python3
"""
AI Camera LPR — Field Test Accuracy Evaluation
Phase 9: Evaluation & Improvement

Usage:
  python3 scripts/evaluate_accuracy.py <detections.json>
  python3 scripts/evaluate_accuracy.py <detections.json> --top 30
  python3 scripts/evaluate_accuracy.py <detections.json> --csv     # export plate list as CSV

Detections JSON is the file produced by export_field_test.sh
(GET /server/api/detections — API returns camelCase field names).
"""

import json
import sys
import csv
import io
import argparse
from datetime import datetime, timedelta
from collections import Counter, defaultdict


def load_detections(filepath):
    with open(filepath, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("data", raw.get("detections", []))
    return []


def _str(val):
    return str(val).strip() if val is not None else ""


def _float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def analyze(detections, top_n=20, csv_out=False):
    total = len(detections)
    if total == 0:
        print("No detections found in file.")
        return

    # ── Field name normalisation (API: camelCase; DB export: snake_case) ──────

    def get(d, *keys):
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return None

    # ── Confidence buckets ─────────────────────────────────────────────────────

    confs = [_float(get(d, "confidence")) for d in detections]
    c90 = sum(1 for c in confs if c >= 0.90)
    c80 = sum(1 for c in confs if 0.80 <= c < 0.90)
    c70 = sum(1 for c in confs if 0.70 <= c < 0.80)
    c_lo = sum(1 for c in confs if c < 0.70)
    avg_conf = sum(confs) / total if total else 0

    # ── Plate text stats ───────────────────────────────────────────────────────

    plates_raw = [
        _str(get(d, "licensePlate", "license_plate")) for d in detections
    ]
    with_plate = sum(1 for p in plates_raw if p)
    without_plate = total - with_plate

    # Plate frequency
    plate_counts = Counter(p for p in plates_raw if p)

    # Unique plate count (non-empty)
    unique_plates = len(plate_counts)

    # Potential duplicates: same plate within 60-second windows
    # Group by plate, count consecutive timestamps < 60s apart as one event
    def count_unique_events(records_for_plate, gap_secs=60):
        tss = sorted(records_for_plate)
        if not tss:
            return 0
        events = 1
        for i in range(1, len(tss)):
            if (tss[i] - tss[i - 1]).total_seconds() > gap_secs:
                events += 1
        return events

    plate_timestamps = defaultdict(list)
    parse_errors = 0
    for d in detections:
        p = _str(get(d, "licensePlate", "license_plate"))
        if not p:
            continue
        ts_str = _str(get(d, "createdAt", "created_at", "timestamp"))
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            parse_errors += 1
            continue
        plate_timestamps[p].append(ts)

    unique_events = {
        p: count_unique_events(ts_list)
        for p, ts_list in plate_timestamps.items()
    }
    total_events = sum(unique_events.values())
    duplicate_readings = with_plate - total_events  # readings beyond first per event

    # ── Time range ────────────────────────────────────────────────────────────

    all_ts_strs = [
        _str(get(d, "createdAt", "created_at", "timestamp")) for d in detections
    ]
    all_ts_strs = [s for s in all_ts_strs if s]
    first_ts = min(all_ts_strs)[:19].replace("T", " ") if all_ts_strs else "N/A"
    last_ts  = max(all_ts_strs)[:19].replace("T", " ") if all_ts_strs else "N/A"

    # Duration
    try:
        t0 = datetime.fromisoformat(min(all_ts_strs).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(max(all_ts_strs).replace("Z", "+00:00"))
        duration = t1 - t0
        mins = int(duration.total_seconds() // 60)
        dur_str = f"{mins // 60}h {mins % 60}m"
        det_per_min = total / max(duration.total_seconds() / 60, 1)
    except Exception:
        dur_str = "N/A"
        det_per_min = 0

    # ── Hourly distribution ───────────────────────────────────────────────────

    hour_counts: Counter = Counter()
    for ts_str in all_ts_strs:
        try:
            h = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).hour
            hour_counts[h] += 1
        except ValueError:
            pass

    # ── Output ────────────────────────────────────────────────────────────────

    sep = "=" * 60

    print(sep)
    print("AI Camera LPR — Field Test Detection Analysis")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep)

    print(f"\n[Summary]")
    print(f"  Total detection records : {total}")
    print(f"  Time range              : {first_ts}  →  {last_ts}")
    print(f"  Session duration        : {dur_str}")
    print(f"  Detection rate          : {det_per_min:.1f} per minute")

    print(f"\n[Confidence Distribution]")
    print(f"  ≥ 90%  (high):   {c90:5d}  ({c90/total*100:.1f}%)")
    print(f"  80–90% (good):   {c80:5d}  ({c80/total*100:.1f}%)")
    print(f"  70–80% (ok):     {c70:5d}  ({c70/total*100:.1f}%)")
    print(f"  < 70%  (low):    {c_lo:5d}  ({c_lo/total*100:.1f}%)")
    print(f"  Average:         {avg_conf*100:.2f}%")

    print(f"\n[License Plate OCR]")
    print(f"  With plate text    : {with_plate:5d}  ({with_plate/total*100:.1f}%)")
    print(f"  Without plate text : {without_plate:5d}  ({without_plate/total*100:.1f}%)")
    print(f"  Unique plate texts : {unique_plates}")
    print(f"  Unique events (60s gap): {total_events}")
    print(f"  Duplicate readings : {max(duplicate_readings, 0)}")

    print(f"\n[Hourly Distribution]")
    for h in sorted(hour_counts):
        bar = "█" * (hour_counts[h] * 30 // max(hour_counts.values(), default=1))
        print(f"  {h:02d}:00  {hour_counts[h]:4d}  {bar}")

    print(f"\n[Top {top_n} License Plates by Frequency]")
    print(f"  {'Plate':<20}  {'Reads':>5}  {'Events':>6}  {'% of total':>10}")
    print(f"  {'-'*20}  {'-'*5}  {'-'*6}  {'-'*10}")
    for plate, count in plate_counts.most_common(top_n):
        events = unique_events.get(plate, count)
        pct = count / total * 100
        print(f"  {plate:<20}  {count:5d}  {events:6d}  {pct:10.2f}%")

    if parse_errors:
        print(f"\n  [Note] {parse_errors} records had unparseable timestamps")

    print(f"\n[Manual Verification Checklist]")
    print("  □ Vehicle Detection Rate = (DB detections) / (manual vehicle count during session)")
    print("  □ OCR Accuracy = (correctly read plates) / (total plate readings)")
    print("  □ False Positives = low-confidence images without actual vehicles")
    print("  □ Missed detections = vehicles not detected (requires manual review)")
    print("  □ Duplicate suppression: same plate appearing many times = check dedup logic")
    print()
    print(f"  Dashboard image review: http://100.95.46.128/server/detections")
    print(sep)

    if csv_out:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["plate", "reads", "unique_events", "pct_of_total"])
        for plate, count in plate_counts.most_common():
            events = unique_events.get(plate, count)
            writer.writerow([plate, count, events, f"{count/total*100:.2f}"])
        print("\n[CSV — plate frequency]")
        print(out.getvalue())


def main():
    parser = argparse.ArgumentParser(
        description="Analyze field test detections JSON",
    )
    parser.add_argument("detections_file", help="Path to detections JSON (from export_field_test.sh)")
    parser.add_argument("--top", type=int, default=20, help="Number of top plates to show (default 20)")
    parser.add_argument("--csv", action="store_true", help="Also output plate frequency as CSV")
    args = parser.parse_args()

    detections = load_detections(args.detections_file)
    analyze(detections, top_n=args.top, csv_out=args.csv)


if __name__ == "__main__":
    main()
