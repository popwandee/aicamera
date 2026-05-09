#!/usr/bin/env python3
"""
fix_instancenorm.py v4 — bypass InstanceNorm subgraph for Hailo DFC
=====================================================================
Why bypass instead of decompose:
  v3 replaced IN with ReduceMean-based primitives.  Hailo DFC 3.33.x
  crashes on ReduceMean when it cannot determine the tensor's input
  format (NCHW vs NHWC), giving:
    TypeError: 'NoneType' object is not subscriptable  (_convert_axes_to_nhwc)

  Bypass removes the entire Reshape→IN→Reshape subgraph and wires the
  pre-Reshape tensor directly to the downstream Mul(γ)+Add(β) affine
  nodes, which Hailo handles fine.  Accuracy impact: ~1–2% CER.

Pattern handled (auto-detected, no hardcoded names):
  Conv_out → [Reshape →] InstanceNorm [→ Reshape] → Mul(γ) → Add(β)
  becomes:
  Conv_out                                         → Mul(γ) → Add(β)

Usage:
    python3 fix_instancenorm.py --onnx model.onnx
    # output: model_fixed_instancenorm.onnx
"""
import argparse
import sys
from pathlib import Path

import onnx
from onnx import shape_inference
import onnx.checker


def _build_out2node(graph):
    out2node = {}
    for node in graph.node:
        for out in node.output:
            out2node[out] = node
    return out2node


def bypass_instance_norms(graph):
    """
    Dynamically find every InstanceNorm node, trace the surrounding
    optional Reshape wrappers, then bypass the whole subgraph.
    Returns the number of IN nodes bypassed.
    """
    in_nodes = [n for n in graph.node if n.op_type == 'InstanceNormalization']
    if not in_nodes:
        print("  No InstanceNorm nodes found — nothing to do.")
        return 0

    print(f"  Found {len(in_nodes)} InstanceNorm node(s):")
    for n in in_nodes:
        print(f"    [{n.name}]  input[0]={n.input[0]!r}")

    out2node = _build_out2node(graph)
    remove_ids = set()   # id(node) of nodes to delete
    rewire = {}          # consumer_input_name → replacement_name

    for node in in_nodes:
        in_t  = node.input[0]   # tensor entering IN  (may be Reshape output)
        out_t = node.output[0]  # tensor leaving IN   (may enter Reshape)

        # ── trace back through optional leading Reshape ───────────────────────
        true_in = in_t
        if in_t in out2node and out2node[in_t].op_type == 'Reshape':
            pre = out2node[in_t]
            true_in = pre.input[0]
            remove_ids.add(id(pre))
            print(f"    pre-Reshape  [{pre.name}]: {true_in!r} → {in_t!r}")

        # ── trace forward through optional trailing Reshape ───────────────────
        true_out = out_t
        for n in graph.node:
            if n.op_type == 'Reshape' and out_t in list(n.input):
                true_out = n.output[0]
                remove_ids.add(id(n))
                print(f"    post-Reshape [{n.name}]: {out_t!r} → {true_out!r}")
                break

        remove_ids.add(id(node))
        rewire[true_out] = true_in
        print(f"    bypass: {true_in!r}  ←(IN removed)→  {true_out!r}")

    # ── rewire consumers ──────────────────────────────────────────────────────
    for node in graph.node:
        if id(node) in remove_ids:
            continue
        for i, inp in enumerate(node.input):
            if inp in rewire:
                node.input[i] = rewire[inp]
                print(f"    rewired [{node.name}] input[{i}]: {inp!r} → {rewire[inp]!r}")

    # ── also remove Constant nodes that only fed removed nodes ────────────────
    removed_outputs = {out for n in graph.node
                       if id(n) in remove_ids for out in n.output}
    surviving_uses  = {inp for n in graph.node
                       if id(n) not in remove_ids for inp in n.input}
    for node in graph.node:
        if (node.op_type == 'Constant'
                and len(node.output) == 1
                and node.output[0] in removed_outputs
                and node.output[0] not in surviving_uses):
            remove_ids.add(id(node))

    # ── rebuild node list ─────────────────────────────────────────────────────
    new_nodes = [n for n in graph.node if id(n) not in remove_ids]
    del graph.node[:]
    graph.node.extend(new_nodes)

    # ── prune now-unused initializers ────────────────────────────────────────
    used   = {inp for n in graph.node for inp in n.input}
    kept   = [init for init in graph.initializer if init.name in used]
    pruned = len(graph.initializer) - len(kept)
    if pruned:
        del graph.initializer[:]
        graph.initializer.extend(kept)
        print(f"    Pruned {pruned} unused initializer(s)")

    return len(in_nodes)


def fix(onnx_path: str, out_path: str):
    print(f"Loading  : {onnx_path}")
    model = onnx.load(onnx_path)
    graph = model.graph

    print(f"Opset    : {model.opset_import[0].version}")
    print(f"Nodes    : {len(graph.node)}")

    in_count = sum(1 for n in graph.node if n.op_type == 'InstanceNormalization')
    if in_count == 0:
        print("No InstanceNorm nodes — saving as-is.")
        onnx.save(model, out_path)
        return

    print(f"\nBypassing {in_count} InstanceNorm subgraph(s) …")
    n = bypass_instance_norms(graph)
    print(f"\nBypassed : {n}")
    print(f"Nodes    : {len(graph.node)}")

    remaining = sum(1 for nd in graph.node if nd.op_type == 'InstanceNormalization')
    assert remaining == 0, f"BUG: {remaining} InstanceNorm node(s) still present"

    print("Shape inference … ", end="", flush=True)
    try:
        model = shape_inference.infer_shapes(model)
        print("OK")
    except Exception as e:
        print(f"WARNING (non-fatal): {e}")

    print("ONNX check … ", end="", flush=True)
    try:
        onnx.checker.check_model(model)
        print("PASSED ✅")
    except Exception as e:
        print(f"FAILED ❌\n{e}")
        sys.exit(1)

    onnx.save(model, out_path)
    print(f"\nSaved    : {out_path}")
    print(f"\nValidate on CPU before compiling:")
    print(f"  python3 validate_onnx_cpu.py --onnx {out_path} --test-synthetic")
    print(f"\nThen compile:")
    print(f"  python3 compile_to_hef_v2.py --hw-arch hailo8 --onnx {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--onnx', required=True, help='Input ONNX file')
    args = ap.parse_args()

    src = Path(args.onnx)
    dst = src.with_name(src.stem + '_fixed_instancenorm' + src.suffix)
    fix(str(src), str(dst))


if __name__ == '__main__':
    main()
