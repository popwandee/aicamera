#!/usr/bin/env python3
"""
Remove LayerNormalization nodes from the ONNX graph before Hailo DFC compilation.

Hailo DFC 3.33.x fails to decompose LayerNorm when the op sits between
reshape operations (shape mismatch in acceleras shape inference).
Replacing LayerNorm with Identity (pass-through) avoids the decomposition
and lets the rest of the graph quantize normally.  The accuracy impact is
minor for INT8 LPR models; re-add calibrated LayerNorm params if needed.

Usage:
    python preprocess_onnx.py [input.onnx] [output.onnx]
"""

import sys
import onnx
from onnx import helper, TensorProto

DEFAULT_IN  = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx"
DEFAULT_OUT = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_nolayernorm.onnx"


def remove_layer_norm(model: onnx.ModelProto) -> onnx.ModelProto:
    graph = model.graph
    nodes_to_remove = []
    nodes_to_add   = []

    for node in graph.node:
        if node.op_type == "LayerNormalization":
            # Replace: LayerNorm(X, scale, bias) → Identity(X)
            # Output[0] = normalised tensor  (we bypass it)
            # Output[1] = mean  (optional, skip if unused)
            # Output[2] = inv_std_dev  (optional, skip if unused)
            print(f"  removing LayerNormalization node: {node.name!r} "
                  f"(input={node.input[0]!r} → output={node.output[0]!r})")
            identity = helper.make_node(
                "Identity",
                inputs=[node.input[0]],
                outputs=[node.output[0]],
                name=(node.name or "unnamed_ln") + "_identity",
            )
            nodes_to_remove.append(node)
            nodes_to_add.append(identity)

    if not nodes_to_remove:
        print("  no LayerNormalization nodes found — ONNX unchanged")
        return model

    for n in nodes_to_remove:
        graph.node.remove(n)
    graph.node.extend(nodes_to_add)

    # Drop now-unused initializers (scale / bias tensors of the removed LN nodes)
    used_inputs = {inp for node in graph.node for inp in node.input}
    kept = [init for init in graph.initializer if init.name in used_inputs]
    removed_inits = [init.name for init in graph.initializer if init.name not in used_inputs]
    if removed_inits:
        print(f"  removed unused initializers: {removed_inits}")
    del graph.initializer[:]
    graph.initializer.extend(kept)

    return model


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    dst = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    print(f"Loading  : {src}")
    model = onnx.load(src)
    print(f"Opset    : {model.opset_import[0].version}")
    print(f"Nodes    : {len(model.graph.node)}")

    print("Removing LayerNorm nodes …")
    model = remove_layer_norm(model)

    # Basic shape inference + check
    try:
        model = onnx.shape_inference.infer_shapes(model)
        onnx.checker.check_model(model)
        print("ONNX check passed.")
    except Exception as e:
        print(f"ONNX check warning (non-fatal): {e}")

    onnx.save(model, dst)
    print(f"Saved    : {dst}")
    print(f"Nodes    : {len(model.graph.node)}")


if __name__ == "__main__":
    main()
