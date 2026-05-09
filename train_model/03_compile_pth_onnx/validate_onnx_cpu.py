#!/usr/bin/env python3
"""
validate_onnx_cpu.py — Run DualBranchLPRNet ONNX directly on CPU (no Hailo)
===========================================================================
Validates model weights independently of HEF quantization.

Run on AGX / Mac / aicamera (no display needed):
    pip install onnxruntime pillow
    python3 validate_onnx_cpu.py --onnx model_fixed.onnx --test-synthetic
    python3 validate_onnx_cpu.py --onnx model_fixed.onnx --crop plate_crop.jpg
"""
from __future__ import annotations
import argparse, sys, os
from pathlib import Path

from PIL import Image
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
# PROVINCES ต้องตรงกับ province_map.py (ใช้ long form 'กรุงเทพมหานคร' ไม่ใช่ 'กรุงเทพ')
PROVINCES = [
    'กระบี่','กรุงเทพมหานคร','กาญจนบุรี','กาฬสินธุ์','กำแพงเพชร',
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
CLASSES = LPR_CHARS + ['<BLANK>']


def safe_softmax(logits: np.ndarray) -> np.ndarray:
    logits = np.where(np.isfinite(logits), logits, 0.0)
    s = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(np.clip(s, -100, 0))
    return e / (e.sum(axis=-1, keepdims=True) + 1e-9)


def ctc_greedy(logits: np.ndarray) -> str:
    if logits.ndim == 3:
        logits = logits[0]
    best = np.argmax(logits, axis=-1).tolist()
    decoded, prev = [], -1
    for idx in best:
        if idx != prev:
            if idx != CTC_BLANK and 0 <= idx < len(LPR_CHARS):
                decoded.append(LPR_CHARS[idx])
            prev = idx
    return ''.join(decoded)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--onnx', required=True,
                    help='Path to ONNX model (.onnx)')
    ap.add_argument('--crop', default=None,
                    help='Path to a real plate crop image')
    ap.add_argument('--test-synthetic', action='store_true',
                    help='Run on a synthetic (random noise) crop — no image file needed')
    args = ap.parse_args()

    onnx_path = Path(args.onnx)
    if not onnx_path.exists():
        print(f"ERROR: ONNX model not found: {onnx_path}")
        sys.exit(1)
    print(f"ONNX model: {onnx_path}")

    try:
        import onnxruntime as ort
    except ImportError:
        print("ERROR: onnxruntime not installed.")
        print("pip install onnxruntime --break-system-packages")
        sys.exit(1)

    # Load model
    sess = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
    inputs  = sess.get_inputs()
    outputs = sess.get_outputs()
    print(f"\nONNX inputs:  {[(i.name, i.shape, i.type) for i in inputs]}")
    print(f"ONNX outputs: {[(o.name, o.shape, o.type) for o in outputs]}")

    # Build input: synthetic noise or real crop
    if args.test_synthetic:
        print("Input: synthetic random-noise crop (75×300 RGB)")
        rng = np.random.default_rng(42)
        res = rng.integers(0, 256, (75, 300, 3), dtype=np.uint8)
    else:
        crop_path = Path(args.crop) if args.crop else None
        if crop_path is None or not crop_path.exists():
            print(f"ERROR: no --crop file given (or not found). Use --test-synthetic to skip.")
            sys.exit(1)
        img = Image.open(crop_path).convert('RGB').resize((300, 75), Image.BILINEAR)
        res = np.array(img, dtype=np.uint8)
        print(f"Input: {crop_path}")

    # Training normalisation: [0,255] → [-1,1]
    inp_f32  = (res.astype(np.float32) / 127.5) - 1.0        # (75,300,3)
    inp_nchw = np.transpose(inp_f32, (2, 0, 1))[np.newaxis]  # (1,3,75,300)

    print(f"\nInput: shape={inp_nchw.shape}  dtype={inp_nchw.dtype}")
    print(f"  pixel range: [{inp_nchw.min():.4f}, {inp_nchw.max():.4f}]")

    # Run
    feed = {inputs[0].name: inp_nchw}
    raw_outs = sess.run(None, feed)

    print(f"\n{'='*60}")
    print("  ONNX CPU INFERENCE RESULTS (ground truth / no quantization)")
    print(f"{'='*60}")

    lpr_out  = None
    prov_out = None

    for i, (out, info) in enumerate(zip(raw_outs, outputs)):
        sq = np.squeeze(out)
        print(f"\n  Output[{i}] name='{info.name}'  raw_shape={out.shape}  "
              f"squeezed={sq.shape}  dtype={out.dtype}")
        print(f"    min={sq.min():.4f}  max={sq.max():.4f}  mean={sq.mean():.4f}")

        if sq.ndim == 2 and sq.shape[1] == 49:
            # (T, C) format — ใช้ตรงได้เลย
            lpr_out = sq
            print(f"    → LPR tensor (T,C) = {sq.shape}")
        elif sq.ndim == 2 and sq.shape[0] == 49:
            # (C, T) format — ONNX export ส่งออกรูปแบบนี้ → transpose เป็น (T,C)
            lpr_out = sq.T
            print(f"    → LPR tensor (C,T)={sq.shape} → transposed to (T,C)={lpr_out.shape}")
        elif sq.ndim == 3 and sq.shape[2] == 49:
            lpr_out = sq[0]
            print(f"    → LPR tensor (1,T,C) = {sq.shape}")
        elif sq.ndim == 3 and sq.shape[1] == 49:
            # (1, C, T) format → transpose
            lpr_out = sq[0].T
            print(f"    → LPR tensor (1,C,T)={sq.shape} → transposed to (T,C)={lpr_out.shape}")
        elif sq.ndim == 1 and sq.shape[0] == 77:
            prov_out = sq
            print(f"    → Province tensor (77,)")

    # CTC decode
    if lpr_out is not None:
        sm = safe_softmax(lpr_out)
        argmax = np.argmax(sm, axis=1)
        n_blank = (argmax == CTC_BLANK).sum()
        n_char  = (argmax != CTC_BLANK).sum()
        chars   = ctc_greedy(lpr_out)

        print(f"\n{'='*60}")
        print(f"  CTC DECODE: '{chars}'")
        print(f"  Timesteps: {n_char}/38 CHAR,  {n_blank}/38 BLANK")
        print(f"  Mean softmax-max: {sm.max(axis=1).mean():.4f}")

        char_steps = [(t, argmax[t], sm[t, argmax[t]]) for t in range(len(argmax)) if argmax[t] != CTC_BLANK]
        if char_steps:
            print(f"\n  Character predictions at {len(char_steps)} timesteps:")
            for t, cls, conf in char_steps:
                top3 = np.argsort(sm[t])[::-1][:3]
                detail = '  '.join(f"{CLASSES[c]}:{sm[t,c]:.3f}" for c in top3)
                print(f"    t{t:02d}: {detail}")
        else:
            print("  ❌ All timesteps predict BLANK — model issue (weights/training)")
            print("  Top-5 at t=16 (usually highest activation):")
            t = min(16, lpr_out.shape[0]-1)
            top5 = np.argsort(sm[t])[::-1][:5]
            for c in top5:
                print(f"    {CLASSES[c]:8s}: {sm[t,c]:.4f}")
    else:
        print("ERROR: Could not identify LPR tensor in ONNX output")

    if prov_out is not None:
        prov_sm = safe_softmax(prov_out)
        top5    = np.argsort(prov_sm)[::-1][:5]
        pred    = np.argmax(prov_sm)
        print(f"\n  Province: '{PROVINCES[pred]}' (conf={prov_sm[pred]:.4f})")
        print(f"  Top-5:")
        for idx in top5:
            print(f"    [{idx:02d}] {PROVINCES[idx]:20s}: {prov_sm[idx]:.4f}")

    print(f"\n{'='*60}")
    print("  INTERPRETATION:")
    if lpr_out is not None:
        chars = ctc_greedy(lpr_out)
        if chars:
            print(f"  ✅ ONNX pipeline OK — non-empty output: chars='{chars}'")
            print("")
            print("  NEXT STEPS:")
            print("    1. ทดสอบด้วยภาพจาก val set (/mnt/pwd-data/lpr_dataset/val/)")
            print("       ถ้า chars ตรงกับชื่อไฟล์ → model OK → ส่ง GCP compile HEF")
            print("    2. ถ้า chars ผิดบน val image → normalization หรือ model issue")
            print("    3. ถ้า chars ผิดเฉพาะ synthetic image ใหม่ → domain shift (ปกติ)")
        else:
            print("  ❌ ALL BLANK → model weights problem (ไม่ใช่ ONNX export bug)")
            print("     → ต้อง retrain หรือตรวจสอบ training dataset")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
