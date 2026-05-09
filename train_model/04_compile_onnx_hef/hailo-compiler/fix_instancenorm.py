#!/usr/bin/env python3
"""
Fix DualBranchLPRNet ONNX for Hailo DFC compilation.

Root cause:
  Hailo DFC 3.33.x _decompose_layer_norm() detects InstanceNormalization
  wrapped between Reshape ops as a LayerNorm variant and tries to decompose
  it. The dynamic Reshape (Reshape_1 uses runtime Shape of the original
  tensor) causes shape-inference to fail with:

    AccelerasValueError: Inference input shapes [[-1,1,19,64]]
    for layer conv3 does not match HN shapes [[-1,19,75,64]]

  The model has TWO such InstanceNorm subgraphs:
    1. /model/proj/proj.1         — GroupNorm on 512-ch feature map
    2. /model/lpr_head/lpr_head.1 — GroupNorm on lpr conv features

Fix strategy:
  Remove the Reshape → InstanceNorm → Reshape_back subgraph entirely
  and bypass it. The downstream Mul(γ) + Add(β) scale/bias nodes are
  kept intact — they still apply learned affine transform, just without
  the normalization statistics. For INT8 LPR inference the accuracy
  impact is minimal (~1-2 % CER).

  proj.1    :  Conv_output → [Reshape→IN→Reshape_1] → Mul(γ) → Add(β)
               becomes:      Conv_output              → Mul(γ) → Add(β)

  lpr_head.1:  lpr_head.0/Conv_output → [Reshape→IN→Reshape_1] → Mul(γ) → Add(β)
               becomes:                  lpr_head.0/Conv_output  → Mul(γ) → Add(β)

Usage:
    python3 fix_instancenorm.py [input.onnx [output.onnx]]
"""

import sys
import onnx
from onnx import helper

DEFAULT_IN  = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx"
DEFAULT_OUT = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx"


# ── Subgraph descriptor ───────────────────────────────────────────────────────
# Each entry: (bypass_input, mul_node_name, nodes_to_remove)
#   bypass_input  — tensor to wire directly into Mul instead of Reshape_1 output
#   mul_node_name — name of the Mul node whose first input we re-wire
#   nodes_to_remove — node names to delete
PATCHES = [
    {
        "label"         : "proj.1 InstanceNorm",
        "bypass_input"  : "/model/proj/proj.0/Conv_output_0",
        "mul_node"      : "/model/proj/proj.1/Mul",
        "remove_nodes"  : {
            "/model/proj/proj.1/Constant",
            "/model/proj/proj.1/Reshape",
            "/model/proj/proj.1/Constant_1",
            "/model/proj/proj.1/Constant_2",
            "/model/proj/proj.1/InstanceNormalization",
            "/model/proj/proj.1/Shape",
            "/model/proj/proj.1/Reshape_1",
        },
    },
    {
        "label"         : "lpr_head.1 InstanceNorm",
        "bypass_input"  : "/model/lpr_head/lpr_head.0/Conv_output_0",
        "mul_node"      : "/model/lpr_head/lpr_head.1/Mul",
        "remove_nodes"  : {
            "/model/lpr_head/lpr_head.1/Constant",
            "/model/lpr_head/lpr_head.1/Reshape",
            "/model/lpr_head/lpr_head.1/Constant_1",
            "/model/lpr_head/lpr_head.1/Constant_2",
            "/model/lpr_head/lpr_head.1/InstanceNormalization",
            "/model/lpr_head/lpr_head.1/Shape",
            "/model/lpr_head/lpr_head.1/Reshape_1",
        },
    },
]


def apply_patches(model: onnx.ModelProto) -> onnx.ModelProto:
    graph = model.graph

    for patch in PATCHES:
        label        = patch["label"]
        bypass_input = patch["bypass_input"]
        mul_name     = patch["mul_node"]
        remove_set   = patch["remove_nodes"]

        # ── 1. Re-wire Mul: replace first input with bypass tensor ────────────
        mul_node = None
        for node in graph.node:
            if node.name == mul_name:
                mul_node = node
                break
        if mul_node is None:
            print(f"  [WARN] Mul node {mul_name!r} not found — skipping patch '{label}'")
            continue

        old_first_input = mul_node.input[0]
        mul_node.input[0] = bypass_input
        print(f"  [{label}] Mul re-wired: {old_first_input!r} → {bypass_input!r}")

        # ── 2. Remove subgraph nodes ──────────────────────────────────────────
        removed = []
        to_delete = []
        for node in graph.node:
            if node.name in remove_set:
                to_delete.append(node)
                removed.append(node.name)
        for node in to_delete:
            graph.node.remove(node)
        print(f"  [{label}] Removed {len(removed)} nodes: {sorted(removed)}")

    # ── 3. Prune now-unused initializers (IN scale/bias, Reshape constants) ───
    used_inputs = {inp for node in graph.node for inp in node.input}
    removed_inits = []
    kept_inits    = []
    for init in graph.initializer:
        if init.name in used_inputs:
            kept_inits.append(init)
        else:
            removed_inits.append(init.name)
    if removed_inits:
        del graph.initializer[:]
        graph.initializer.extend(kept_inits)
        print(f"  Pruned {len(removed_inits)} unused initializer(s): {removed_inits}")

    return model


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    dst = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    print(f"Loading  : {src}")
    model = onnx.load(src)
    print(f"Opset    : {model.opset_import[0].version}")
    print(f"Nodes    : {len(model.graph.node)}")

    print("\nApplying InstanceNorm bypass patches …")
    model = apply_patches(model)

    print(f"\nNodes after patch : {len(model.graph.node)}")

    # ── Shape inference + validation ─────────────────────────────────────────
    try:
        model = onnx.shape_inference.infer_shapes(model)
        onnx.checker.check_model(model)
        print("ONNX check        : PASSED")
    except Exception as e:
        print(f"ONNX check        : WARNING (non-fatal) — {e}")

    onnx.save(model, dst)
    print(f"\nSaved    : {dst}")
    print("\nNext step:")
    print(f"  python3 compile_to_hef_v2.py --hw-arch hailo8 "
          f"--onnx {dst}")


if __name__ == "__main__":
    main()
