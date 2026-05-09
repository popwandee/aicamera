#!/usr/bin/env python3
"""
Compile DualBranchLPRNet ONNX -> HEF using Hailo DFC 3.33.x

Recommended workflow:
  1. python3 fix_instancenorm.py          # removes InstanceNorm subgraphs
  2. python3 compile_to_hef_v2.py \\
       --hw-arch hailo8 \\
       --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx

Usage:
  python compile_to_hef_v2.py [--hw-arch hailo8l|hailo8]
                               [--onnx path.onnx]
                               [--calib-npy path.npy]
"""

import argparse
import os
import textwrap
import numpy as np

DEFAULT_ONNX = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx"
MODEL_NAME   = "DualBranchLPRNet_ThaiLP"
INPUT_SHAPE  = [1, 3, 75, 300]   # NCHW — matches ONNX graph
CALIB_N      = 64                 # calibration samples when no .npy supplied
MODEL_SCRIPT = "model_script.alls"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--hw-arch", default="hailo8",
                   choices=["hailo8", "hailo8l"],
                   help="Target Hailo hardware (default: hailo8)")
    p.add_argument("--onnx", default=DEFAULT_ONNX,
                   help=f"Path to (pre-processed) ONNX file "
                        f"(default: {DEFAULT_ONNX})")
    p.add_argument("--calib-npy",
                   help="Calibration data .npy, shape [N,3,75,300] float32 0-1. "
                        "If omitted, random data is used (good enough for first-pass; "
                        "use real licence-plate crops for production accuracy).")
    return p.parse_args()


def write_model_script():
    """
    Minimal model script — only calibration config and optimization flavor.
    The broken post_quantization_optimization line has been removed because
    DFC 3.33.x uses a different syntax (policy= is required, algorithm= is
    not a valid field at the top level).
    """
    script = textwrap.dedent("""\
        model_optimization_config(calibration, batch_size=1, calibset_size=64)
        model_optimization_flavor(optimization_level=0, compression_level=0)
    """)
    with open(MODEL_SCRIPT, "w") as f:
        f.write(script)
    print(f"[hailo] model script written → {MODEL_SCRIPT}")


def main():
    args = parse_args()
    onnx_path  = args.onnx
    output_hef = onnx_path.replace(".onnx", ".hef")

    print(f"[hailo] target arch : {args.hw_arch}")
    print(f"[hailo] onnx        : {onnx_path}")

    if not os.path.exists(onnx_path):
        print(f"[hailo] ERROR: {onnx_path} not found.")
        print("        Run first:  python3 fix_instancenorm.py")
        raise SystemExit(1)

    from hailo_sdk_client import ClientRunner

    runner = ClientRunner(hw_arch=args.hw_arch)

    # ── 1. Translate ONNX ────────────────────────────────────────────────────
    print("[hailo] translating ONNX model …")
    hn, npz = runner.translate_onnx_model(
        onnx_path,
        MODEL_NAME,
        start_node_names=None,
        end_node_names=None,
        net_input_shapes=None,   # shapes come from the ONNX graph
    )

    # ── 2. Load model script (must be done before optimize) ─────────────────
    write_model_script()
    runner.load_model_script(MODEL_SCRIPT)

    # ── 3. Calibration data ──────────────────────────────────────────────────
    if args.calib_npy and os.path.exists(args.calib_npy):
        print(f"[hailo] calibration ← {args.calib_npy}")
        calib = np.load(args.calib_npy).astype(np.float32)
        assert calib.ndim == 4 and calib.shape[1:] == (3, 75, 300), \
            f"Expected [N,3,75,300], got {calib.shape}"
    else:
        print(f"[hailo] using {CALIB_N} random calibration samples "
              "(replace with real licence-plate images for production)")
        rng = np.random.default_rng(42)
        calib = rng.uniform(0.0, 1.0,
                            (CALIB_N, *INPUT_SHAPE[1:])).astype(np.float32)

    # ── 4. Optimize (quantize) — no fallback to full_precision ───────────────
    # Hailo uses NHWC internally; calibration data must be (N, H, W, C).
    # Our array is NCHW (N, C, H, W) so we transpose before passing.
    calib_nhwc = calib.transpose(0, 2, 3, 1)   # (N,3,75,300) → (N,75,300,3)
    print(f"[hailo] calib shape (NHWC): {calib_nhwc.shape}")
    print("[hailo] optimizing (quantizing) …")
    runner.optimize(calib_nhwc)

    # ── 5. Compile to HEF ───────────────────────────────────────────────────
    print("[hailo] compiling to HEF …")
    hef_bytes = runner.compile()

    with open(output_hef, "wb") as f:
        f.write(hef_bytes)

    size_mb = os.path.getsize(output_hef) / 1024 / 1024
    print(f"[hailo] done → {output_hef}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
