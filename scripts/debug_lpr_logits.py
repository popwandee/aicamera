#!/usr/bin/env python3
"""
debug_lpr_logits.py — Inspect raw DualBranch logits to diagnose chars='' issue
===============================================================================
Run on aicamera1 INSIDE venv_hailo:

    cd /home/camuser/aicamera
    source edge/venv_hailo/bin/activate
    python3 scripts/debug_lpr_logits.py [--crop test_output/plate_crop_0.jpg]

Reports:
  - Per-timestep top-3 class probabilities
  - How many timesteps predict BLANK vs characters
  - Province top-5 probabilities
  - Raw logit min/max (to detect quantization issues)
  - Also tries float32 [-1,1] input to compare outputs
"""
from __future__ import annotations
import argparse, sys, os
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

LPR_CHARS = [
    '0','1','2','3','4','5','6','7','8','9',
    'ก','ข','ค','ฆ','ง','จ','ฉ','ช',
    'ซ','ญ','ฎ','ฐ','ณ','ด','ต','ถ',
    'ท','ธ','น','บ','ป','ผ','ฝ','พ',
    'ฟ','ภ','ม','ย','ร','ล','ว','ศ',
    'ษ','ส','ห','ฬ','อ','ฮ',
]
PROVINCES = [
    'กระบี่','กรุงเทพ','กาญจนบุรี','กาฬสินธุ์','กำแพงเพชร',
    'ขอนแก่น','จันทบุรี','ฉะเชิงเทรา','ชลบุรี','ชัยนาท',
    'ชัยภูมิ','ชุมพร','เชียงราย','เชียงใหม่','ตรัง',
    'ตราด','ตาก','นครนายก','นครปฐม','นครพนม',
    'นครราชสีมา','นครศรีธรรมราช','นครสวรรค์','นนทบุรี','นราธิวาส',
    'น่าน','บึงกาฬ','บุรีรัมย์','ปทุมธานี','ประจวบคีรีขันธ์',
    'ปราจีนบุรี','ปัตตานี','พระนครศรีอยุธยา','พะเยา','พังงา',
    'พัทลุง','พิจิตร','พิษณุโลก','เพชรบุรี','เพชรบูรณ์',
    'แพร่','ภูเก็ต','มหาสารคาม','มุกดาหาร','แม่ฮ่องสอน',
    'ยโสธร','ยะลา','ร้อยเอ็ด','ระนอง','ระยอง',
    'ราชบุรี','ลพบุรี','ลำปาง','ลำพูน','เลย',
    'ศรีสะเกษ','สกลนคร','สงขลา','สตูล','สมุทรปราการ',
    'สมุทรสงคราม','สมุทรสาคร','สระแก้ว','สระบุรี','สิงห์บุรี',
    'สุโขทัย','สุพรรณบุรี','สุราษฎร์ธานี','สุรินทร์','หนองคาย',
    'หนองบัวลำภู','อ่างทอง','อำนาจเจริญ','อุดรธานี','อุตรดิตถ์',
    'อุทัยธานี','อุบลราชธานี',
]
CTC_BLANK = 48
CLASSES = LPR_CHARS + ['<BLANK>']  # 49 total

RESOURCES = str(PROJECT / 'resources')
MODEL_NAME = 'DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503'


def safe_softmax(logits: np.ndarray) -> np.ndarray:
    logits = np.where(np.isfinite(logits), logits, 0.0)
    s = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(np.clip(s, -100, 0))
    return e / (e.sum(axis=-1, keepdims=True) + 1e-9)


def run_and_report(model, inp_uint8: np.ndarray, label: str):
    print(f"\n{'='*60}")
    print(f"  INPUT MODE: {label}")
    print(f"  input dtype={inp_uint8.dtype}  shape={inp_uint8.shape}")
    print(f"  pixel range: [{inp_uint8.min():.4f}, {inp_uint8.max():.4f}]")
    print(f"{'='*60}")

    result = model(inp_uint8)

    # --- extract raw tensors ---
    lpr = None
    prov = None
    try:
        for item in result.results:
            arr = None
            if isinstance(item, np.ndarray):
                arr = item
            elif isinstance(item, dict):
                for v in item.values():
                    if isinstance(v, np.ndarray):
                        arr = v; break
            if arr is None: continue
            sq = np.squeeze(arr)
            if sq.ndim == 2 and sq.shape[1] == 49:
                lpr = sq
            elif sq.ndim == 3 and sq.shape[2] == 49:
                lpr = sq[0]
            elif sq.ndim == 1 and sq.shape[0] == 77:
                prov = sq
    except Exception as e:
        print(f"  Extraction error: {e}")
        return

    if lpr is None:
        print("  ❌ LPR tensor NOT FOUND in result.results")
        print(f"  result.results type: {type(result.results)}")
        if hasattr(result, 'results'):
            for i, item in enumerate(result.results):
                print(f"    [{i}] type={type(item).__name__}", end='')
                if isinstance(item, dict):
                    for k,v in item.items():
                        print(f"  key='{k}' type={type(v).__name__}", end='')
                        if isinstance(v, np.ndarray):
                            print(f" shape={v.shape}", end='')
                print()
        return

    print(f"\n  LPR tensor: shape={lpr.shape}  min={lpr.min():.3f}  max={lpr.max():.3f}")
    if prov is not None:
        print(f"  Prov tensor: shape={prov.shape}  min={prov.min():.3f}  max={prov.max():.3f}")

    # --- Per-timestep analysis ---
    sm = safe_softmax(lpr)          # (T, 49)
    argmax = np.argmax(sm, axis=1)  # (T,)
    n_blank = (argmax == CTC_BLANK).sum()
    n_char  = (argmax != CTC_BLANK).sum()

    print(f"\n  CTC timestep summary: {n_char}/38 predict CHAR, {n_blank}/38 predict BLANK")
    print(f"  Mean softmax-max: {sm.max(axis=1).mean():.4f}  (high=confident, ~0.02=random)")

    # Show all 38 timesteps compactly
    print(f"\n  Timestep predictions (top-1):")
    row = ''
    for t in range(len(argmax)):
        cls = argmax[t]
        sym = CLASSES[cls] if cls < len(CLASSES) else '?'
        conf = sm[t, cls]
        row += f"  t{t:02d}: {sym:6s} {conf:.3f}\n"
    print(row)

    # Show timesteps where a CHARACTER wins (not blank)
    char_steps = [(t, argmax[t], sm[t, argmax[t]]) for t in range(len(argmax)) if argmax[t] != CTC_BLANK]
    if char_steps:
        print(f"  ✅ Character predictions at {len(char_steps)} timesteps:")
        for t, cls, conf in char_steps:
            sym = CLASSES[cls]
            # show top-3
            top3 = np.argsort(sm[t])[::-1][:3]
            detail = '  '.join(f"{CLASSES[c]}:{sm[t,c]:.3f}" for c in top3)
            print(f"    t{t:02d}: {detail}")
    else:
        print(f"  ❌ No character predictions — all {n_blank} timesteps predict BLANK")
        print("  Top-3 at t=0:")
        top3 = np.argsort(sm[0])[::-1][:5]
        for c in top3:
            print(f"    {CLASSES[c]}: {sm[0,c]:.4f}")

    # Province
    if prov is not None:
        prov_sm = safe_softmax(prov.flatten())
        top5_prov = np.argsort(prov_sm)[::-1][:5]
        print(f"\n  Province top-5:")
        for idx in top5_prov:
            print(f"    [{idx:02d}] {PROVINCES[idx]:20s}: {prov_sm[idx]:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--crop', default='test_output/plate_crop_0.jpg',
                    help='Path to plate crop image (default: test_output/plate_crop_0.jpg)')
    args = ap.parse_args()

    crop_path = PROJECT / args.crop
    if not crop_path.exists():
        print(f"ERROR: {crop_path} not found")
        print("Run test_dual_branch_lpr.py --save-crops first, or specify --crop /path/to/plate.jpg")
        sys.exit(1)

    bgr = cv2.imread(str(crop_path))
    print(f"Loaded crop: {crop_path}  size={bgr.shape[1]}x{bgr.shape[0]}")

    # Preprocess
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    resized_uint8 = cv2.resize(rgb, (300, 75), interpolation=cv2.INTER_LINEAR)
    resized_float = (resized_uint8.astype(np.float32) / 127.5) - 1.0  # [-1,1]

    import degirum as dg
    print(f"\nLoading {MODEL_NAME} ...")
    model = dg.load_model(model_name=MODEL_NAME, inference_host_address='@local', zoo_url=RESOURCES)
    print("Loaded OK\n")

    # Test A: current approach — uint8
    run_and_report(model, resized_uint8, "UINT8 [0-255] — current approach (InputQuantEn=true)")

    # Test B: float32 [-1,1]
    run_and_report(model, resized_float, "FLOAT32 [-1,1] — training normalization")

    print(f"\n{'='*60}")
    print("  DONE — compare outputs above to identify which input mode works")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
