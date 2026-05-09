#!/usr/bin/env python3
"""export_to_onnx.py — Export DualBranchLPRNet PTH to ONNX (opset 11)"""
import sys, argparse, torch
from datetime import datetime
from pathlib import Path

from lprnet_dual_branch import DualBranchLPRNet

parser = argparse.ArgumentParser()
parser.add_argument('--pth',    default='/mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth')
parser.add_argument('--output', default=f'DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v{datetime.now().strftime("%Y%m%d")}.onnx')
parser.add_argument('--opset',  type=int, default=11)
args = parser.parse_args()

PTH_PATH = args.pth
ONNX_OUT = args.output
OPSET    = args.opset

# Use CPU for ONNX export — keeps the graph device-agnostic
device = 'cpu'
model  = DualBranchLPRNet().to(device)
state  = torch.load(PTH_PATH, map_location=device)
# Handle checkpoint dict (train_dual_branch.py saves full checkpoint)
if 'model_state_dict' in state:
    state = state['model_state_dict']
model.load_state_dict(state)
model.eval()

dummy = torch.zeros(1, 3, 75, 300, device=device)  # (B, C, H, W)

with torch.no_grad():
    torch.onnx.export(
        model, dummy, ONNX_OUT,
        opset_version=OPSET,
        input_names=['input'],
        output_names=['lpr_logits', 'province_logits'],
        dynamic_axes={'input': {0: 'batch'}},
        do_constant_folding=True,
    )

print(f"Exported: {ONNX_OUT}")

# Quick sanity check
import onnx
m = onnx.load(ONNX_OUT)
onnx.checker.check_model(m)
print("ONNX model is valid.")

# Print output shapes
import onnxruntime as ort
sess   = ort.InferenceSession(ONNX_OUT, providers=['CPUExecutionProvider'])
inputs = {sess.get_inputs()[0].name: dummy.numpy()}
outs   = sess.run(None, inputs)
print(f"lpr_logits shape:      {outs[0].shape}")   # expect (1, 49, 38)
print(f"province_logits shape: {outs[1].shape}")   # expect (1, 77)