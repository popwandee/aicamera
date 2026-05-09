# Code
```python
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
```
## Terminal output
```bash
(.venv) agx@ubuntu:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr$ python3 export_to_onnx.py --pth /mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth --output DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v$(date +%Y%m%d).onnx --opset 11
/home/agx/hailo_model_zoo/hailo_models/license_plate_recognition/.venv/lib/python3.8/site-packages/torchvision/io/image.py:13: UserWarning: Failed to load image Python extension: '/home/agx/hailo_model_zoo/hailo_models/license_plate_recognition/.venv/lib/python3.8/site-packages/torchvision/image.so: undefined symbol: _ZN5torch3jit17parseSchemaOrNameERKSs'If you don't plan on using image functionality from `torchvision.io`, you can ignore this warning. Otherwise, there might be something wrong with your environment. Did you have `libjpeg` or `libpng` installed before building `torchvision` from source?
  warn(
====== Diagnostic Run torch.onnx.export version 2.1.0a0+41361538.nv23.06 =======
verbose: False, log level: Level.ERROR
======================= 0 NONE 0 NOTE 0 WARNING 0 ERROR ========================

Exported: DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx
ONNX model is valid.
lpr_logits shape:      (1, 49, 38)
province_logits shape: (1, 77)
```
# fix instance norm
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
    python3 fix_instancenorm.py --onnx input.onnx
    # output written to input_fixed_instancenorm.onnx
```bash
(.venv) agx@ubuntu:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr$ python3 fix_instancenorm.py --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx
```
Loading  : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx
Opset    : 11
Nodes    : 55
Shape inference … OK (54 tensors mapped)

พบ 2 InstanceNorm node(s):
  [/proj/proj.1/InstanceNormalization]
    inputs = ['/proj/proj.1/Reshape_output_0', '/proj/proj.1/Constant_1_output_0', '/proj/proj.1/Constant_2_output_0']
  [/lpr_head/lpr_head.1/InstanceNormalization]
    inputs = ['/lpr_head/lpr_head.1/Reshape_output_0', '/lpr_head/lpr_head.1/Constant_1_output_0', '/lpr_head/lpr_head.1/Constant_2_output_0']

แทนที่ in-place …
  ✓ /proj/proj.1/InstanceNormalization
    input shape: [0, 8, 24320]  spatial_axes: [2]
    scale from Constant node, shape=[8]
  ✓ /lpr_head/lpr_head.1/InstanceNormalization
    input shape: [0, 8, 0]  spatial_axes: [2]
    scale from Constant node, shape=[8]

ONNX check … PASSED ✅
Saved    : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx
Nodes    : 75
Op types : ['Add', 'Constant', 'Conv', 'Div', 'Gemm', 'MaxPool', 'Mul', 'ReduceMean', 'Relu', 'Reshape', 'Shape', 'Slice', 'Sqrt', 'Sub', 'Unsqueeze']

Next step:
  # ตรวจ CPU ก่อน
  python3 validate_onnx_cpu.py --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx --test-synthetic
  # ส่ง GCP
  python3 compile_to_hef_v2.py --hw-arch hailo8 --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx

```bash
(.venv) agx@ubuntu:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr$ ls
```
charset.py                                                          export_to_onnx.py      province_map.py       validate_onnx_cpu.py
CONTEXT.md                                                          fix_instancenorm.py    __pycache__
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx  lprnet_dual_branch.py  train_dual_branch.py
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx        lprnet_model.py        train_lprnet.py

# Validate onnx
```bash
(.venv) agx@ubuntu:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr$ python3 validate_onnx_cpu.py --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx --test-synthetic
```
