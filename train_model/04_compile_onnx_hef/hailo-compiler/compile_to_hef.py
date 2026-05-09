#!/usr/bin/env python3
"""
Compile DualBranchLPRNet ONNX -> HEF using Hailo DFC 3.33.x
Expects the pre-processed ONNX (LayerNorm stripped by preprocess_onnx.py).

Usage:
  python compile_to_hef.py [--hw-arch hailo8|hailo8l] [--calib-npy path.npy]
"""

import argparse
import os
import numpy as np

ONNX_PATH   = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_nolayernorm.onnx"
MODEL_NAME  = "DualBranchLPRNet_ThaiLP"
INPUT_SHAPE = [1, 3, 75, 300]   # NCHW
CALIB_N     = 64
OUTPUT_HEF  = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.hef"
MODEL_SCRIPT = "model_script.alls"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--hw-arch", default="hailo8",
                   choices=["hailo8", "hailo8l"])
    p.add_argument("--calib-npy",
                   help="Calibration data .npy [N,3,75,300] float32 0-1. "
                        "Use real LP crops for production accuracy.")
    return p.parse_args()


def write_model_script():
    # DFC 3.33.x model script — correct syntax
    script = (
        "model_optimization_config(calibration, batch_size=1, calibset_size=64)\n"
        "model_optimization_flavor(optimization_level=0, compression_level=0)\n"
        "post_quantization_optimization(finetune, policy=disabled)\n"
    )
    with open(MODEL_SCRIPT, "w") as f:
        f.write(script)
    print(f"[hailo] model script → {MODEL_SCRIPT}")


def main():
    args = parse_args()
    print(f"[hailo] arch  : {args.hw_arch}")
    print(f"[hailo] onnx  : {ONNX_PATH}")

    if not os.path.exists(ONNX_PATH):
        print(f"[hailo] ERROR: {ONNX_PATH} not found.")
        print("        Run first:  python preprocess_onnx.py")
        raise SystemExit(1)

    from hailo_sdk_client import ClientRunner

    runner = ClientRunner(hw_arch=args.hw_arch)

    # ── 1. Translate ─────────────────────────────────────────────────────────
    print("[hailo] translating …")
    runner.translate_onnx_model(
        ONNX_PATH,
        MODEL_NAME,
        start_node_names=None,
        end_node_names=None,
        net_input_shapes=None,
    )

    # ── 2. Model script ──────────────────────────────────────────────────────
    write_model_script()
    runner.load_model_script(MODEL_SCRIPT)

    # ── 3. Calibration data ──────────────────────────────────────────────────
    if args.calib_npy and os.path.exists(args.calib_npy):
        print(f"[hailo] calibration ← {args.calib_npy}")
        calib = np.load(args.calib_npy).astype(np.float32)
        assert calib.ndim == 4 and calib.shape[1:] == (3, 75, 300), \
            f"Expected [N,3,75,300], got {calib.shape}"
    else:
        print(f"[hailo] using {CALIB_N} random samples "
              "(use real LP crops for production)")
        rng = np.random.default_rng(42)
        calib = rng.uniform(0.0, 1.0,
                            (CALIB_N, *INPUT_SHAPE[1:])).astype(np.float32)

    # ── 4. Quantize ──────────────────────────────────────────────────────────
    print("[hailo] optimizing (quantizing) …")
    runner.optimize(calib)

    # ── 5. Compile to HEF ───────────────────────────────────────────────────
    print("[hailo] compiling to HEF …")
    hef_bytes = runner.compile()

    with open(OUTPUT_HEF, "wb") as f:
        f.write(hef_bytes)

    size_mb = os.path.getsize(OUTPUT_HEF) / 1024 / 1024
    print(f"[hailo] done → {OUTPUT_HEF}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
