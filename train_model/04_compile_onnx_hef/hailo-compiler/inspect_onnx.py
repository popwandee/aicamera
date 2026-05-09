#!/usr/bin/env python3
"""
Inspect ONNX graph: list all ops and find manual LayerNorm patterns.
Hailo DFC can detect LayerNorm built from primitive ops even without
a formal LayerNormalization node.

Usage:
    python3 inspect_onnx.py [model.onnx]
"""

import sys
import onnx
from collections import defaultdict

DEFAULT = "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    model = onnx.load(path)
    graph = model.graph

    # ── Build lookup tables ──────────────────────────────────────────────────
    # output_name → node
    out2node = {}
    for node in graph.node:
        for o in node.output:
            out2node[o] = node

    # input_name → list of nodes that consume it
    inp2nodes = defaultdict(list)
    for node in graph.node:
        for i in node.input:
            inp2nodes[i].append(node)

    # ── 1. Op-type frequency ─────────────────────────────────────────────────
    from collections import Counter
    counts = Counter(n.op_type for n in graph.node)
    print("=== Op-type counts ===")
    for op, cnt in sorted(counts.items()):
        print(f"  {op:30s} x{cnt}")

    # ── 2. Dump all nodes ────────────────────────────────────────────────────
    print("\n=== All nodes (index | op_type | name | inputs → outputs) ===")
    for i, node in enumerate(graph.node):
        inputs  = ", ".join(node.input)
        outputs = ", ".join(node.output)
        print(f"  [{i:03d}] {node.op_type:25s} | {node.name!r:40s} | {inputs} → {outputs}")

    # ── 3. Find ReduceMean nodes (key op in manual LayerNorm) ────────────────
    print("\n=== ReduceMean nodes (manual LayerNorm fingerprint) ===")
    for i, node in enumerate(graph.node):
        if node.op_type == "ReduceMean":
            # Get axes attribute
            axes = []
            for attr in node.attribute:
                if attr.name == "axes":
                    axes = list(attr.ints)
            keepdims = 1
            for attr in node.attribute:
                if attr.name == "keepdims":
                    keepdims = attr.i
            # Who produces the input?
            inp = node.input[0]
            producer = out2node.get(inp, None)
            producer_op = producer.op_type if producer else "GRAPH_INPUT"
            # Who consumes the output?
            consumers = inp2nodes.get(node.output[0], [])
            consumer_ops = [c.op_type for c in consumers]
            print(f"  [{i:03d}] name={node.name!r}")
            print(f"         axes={axes}, keepdims={keepdims}")
            print(f"         input={inp!r}  (from {producer_op})")
            print(f"         output={node.output[0]!r}  (to {consumer_ops})")

    # ── 4. Detect manual LayerNorm pattern heuristically ────────────────────
    # Pattern:  input → ReduceMean(axis=-1) → [Sub] → [Pow/Mul] → ReduceMean → [Add,Sqrt,Div]
    print("\n=== Potential manual LayerNorm subgraphs ===")
    found_any = False
    for i, node in enumerate(graph.node):
        if node.op_type != "ReduceMean":
            continue
        axes = []
        for attr in node.attribute:
            if attr.name == "axes":
                axes = list(attr.ints)
        # First ReduceMean in LayerNorm computes the mean along last axis
        if not axes or axes[-1] not in (-1, 3):  # -1 or last spatial dim
            continue
        # Check if there's a second ReduceMean downstream within ~8 hops
        queue = [(node.output[0], 0)]
        visited = set()
        second_rm = None
        while queue:
            cur_name, depth = queue.pop(0)
            if depth > 8 or cur_name in visited:
                continue
            visited.add(cur_name)
            for consumer in inp2nodes.get(cur_name, []):
                if consumer.op_type == "ReduceMean" and consumer is not node:
                    second_rm = consumer
                    break
                queue.append((consumer.output[0] if consumer.output else "", depth + 1))
            if second_rm:
                break
        if second_rm is None:
            continue
        # Check that after 2nd ReduceMean there's an Add(eps) then Sqrt then Div
        cur = second_rm.output[0]
        ops_after = []
        for _ in range(6):
            consumers = inp2nodes.get(cur, [])
            if not consumers:
                break
            c = consumers[0]
            ops_after.append(c.op_type)
            cur = c.output[0] if c.output else ""
        found_any = True
        print(f"  Candidate LayerNorm starting at node [{i:03d}] {node.name!r}")
        print(f"    input op: {(out2node.get(node.input[0], None) or type('X', (), {'op_type': 'INPUT'})).op_type}")
        print(f"    mean node: {node.name!r} (axes={axes})")
        print(f"    2nd ReduceMean: {second_rm.name!r}")
        print(f"    ops after 2nd ReduceMean: {ops_after}")
    if not found_any:
        print("  No obvious manual LayerNorm patterns found via heuristic.")

    # ── 5. Show Reshape nodes (context for shape mismatch) ──────────────────
    print("\n=== Reshape / Squeeze / Unsqueeze nodes ===")
    for i, node in enumerate(graph.node):
        if node.op_type in ("Reshape", "Squeeze", "Unsqueeze", "Flatten"):
            inputs  = ", ".join(node.input)
            outputs = ", ".join(node.output)
            print(f"  [{i:03d}] {node.op_type:12s} | {node.name!r:40s} | {inputs} → {outputs}")

    # ── 6. Shape info for key tensors (if available) ─────────────────────────
    model_si = onnx.shape_inference.infer_shapes(model)
    shape_map = {}
    for vi in list(model_si.graph.value_info) + list(model_si.graph.input) + list(model_si.graph.output):
        shape = [d.dim_value if d.dim_value > 0 else -1
                 for d in vi.type.tensor_type.shape.dim]
        shape_map[vi.name] = shape
    print("\n=== Tensor shapes around Reshape nodes ===")
    for i, node in enumerate(graph.node):
        if node.op_type in ("Reshape", "Squeeze", "Unsqueeze", "Flatten"):
            for t in list(node.input) + list(node.output):
                s = shape_map.get(t, "?")
                print(f"  {t!r:50s}  shape={s}")


if __name__ == "__main__":
    main()
