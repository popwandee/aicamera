# RECOMPILE_GUIDE.md — Recompile DualBranchLPRNet HEF for degirum compatibility

## Why recompile?

The original HEF (`*_fixed.hef`) was compiled with a **calibration range mismatch**:

| | Training | Original compile | Correct |
|---|---|---|---|
| Input float range | **[-1, +1]** | calibrated [0, 1] ← **WRONG** | [-1, +1] |
| Effect | model trained correctly | wrong quantization scale/offset | correct |

Result: the HEF's input dequantization maps uint8[128] → float[+0.5] instead of 0.0.
Every first-layer activation is shifted by +0.5 and compressed by 2×. OCR output = garbage.

## What `compile_to_hef_v2.py` now does (fixed)

Two changes vs. the original:

### 1. Normalization baked into HEF (model script)
```alls
normalization([127.5, 127.5, 127.5], [127.5, 127.5, 127.5])
```
- Hailo applies `(x − 127.5) / 127.5` on-chip before the first layer
- Equivalent to PyTorch's `transforms.Normalize([0.5,0.5,0.5],[0.5,0.5,0.5])` after ToTensor()
- **HEF now accepts raw uint8 RGB [0-255] — no Python normalisation needed**

### 2. Calibration data range corrected: [0, 255] not [0, 1]
```python
calib = rng.uniform(0.0, 255.0, ...)   # matches inference input range
```

## Runtime contract after recompile

| | degirum JSON | Python preprocessing |
|---|---|---|
| `InputQuantEn` | `true` | — |
| `InputType` | omitted | — |
| What to pass | `(75, 300, 3) uint8 RGB` | BGR→RGB + resize to 300×75 |

No float normalisation in Python. The `preprocess_for_lprnet()` in
`edge/src/components/dual_branch_degirum_ocr.py` already does this correctly.

## How to recompile (on GCP / Hailo DFC machine)

### Step 1 — copy files to GCP
```bash
# From Mac, project root:
gcloud compute scp \
  scripts/train_dualbranch_model/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx \
  scripts/train_dualbranch_model/fix_instancenorm.py \
  scripts/train_dualbranch_model/compile_to_hef_v2.py \
  <GCP_INSTANCE>:~/dualbranch/
```
```bash
(venv_simulation) sqh@SqHs-MacBook-Pro train_dualbranch_model % gcloud compute scp \
> DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx \
> fix_instancenorm.py \
> compile_to_hef_v2.py \
> hailo-compiler:~/dualbranch/

```
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx     100% 3655KB   1.4MB/s   00:02    
fix_instancenorm.py                                              100% 6261    18.4KB/s   00:00    
compile_to_hef_v2.py                                             100% 5683    21.6KB/s   00:00  


### Step 2 — pre-process ONNX (remove InstanceNorm subgraphs if not already done)
# SSH Gcloud 
```bash
(venv_simulation) sqh@SqHs-MacBook-Pro AICAMERA % gcloud compute ssh hailo-compiler
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
```
Welcome to Ubuntu 22.04.5 LTS (GNU/Linux 6.8.0-1053-gcp x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

 System information as of Fri May  8 01:09:49 UTC 2026

  System load:  0.0                Processes:             126
  Usage of /:   22.2% of 48.27GB   Users logged in:       0
  Memory usage: 4%                 IPv4 address for ens4: 10.128.0.2
  Swap usage:   0%

 * Strictly confined Kubernetes makes edge and IoT secure. Learn how MicroK8s
   just raised the bar for easy, resilient and secure K8s cluster deployment.

   https://ubuntu.com/engage/secure-kubernetes-at-the-edge

Expanded Security Maintenance for Applications is not enabled.

10 updates can be applied immediately.
7 of these updates are standard security updates.
To see these additional updates run: apt list --upgradable

21 additional security updates can be applied with ESM Apps.
Learn more about enabling ESM Apps service at https://ubuntu.com/esm

New release '24.04.4 LTS' available.
Run 'do-release-upgrade' to upgrade to it.


*** System restart required ***
Last login: Thu May  7 15:23:22 2026 from 49.228.241.221
```bash
admin_pwdvisionworks_com@hailo-compiler:~$ ls
#dualbranch  hailo-compiler  snap
admin_pwdvisionworks_com@hailo-compiler:~$ cd dualbranch
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ ls
#DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx  
#fix_instancenorm.py  
#compile_to_hef_v2.py    
#lp_crops                                      
#lp_calib.npy

#============
# Install onnx (if not already)
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ pip install onnx

# Run the fix 
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ python3 fix_instancenorm.py \
    DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx 

# → produces DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx
```
### Expected output:
[proj.1 InstanceNorm] Mul re-wired: ...
[proj.1 InstanceNorm] Removed 7 nodes: [...]
[lpr_head.1 InstanceNorm] Mul re-wired: ...
[lpr_head.1 InstanceNorm] Removed 7 nodes: [...]
Pruned N unused initializer(s): [...]
ONNX check : PASSED
Saved : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_
### Actual Output:
Loading  : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx
Opset    : 13
Nodes    : 55

Applying InstanceNorm bypass patches …
  [proj.1 InstanceNorm] Mul re-wired: '/model/proj/proj.1/Reshape_1_output_0' → '/model/proj/proj.0/Conv_output_0'
  [proj.1 InstanceNorm] Removed 7 nodes: ['/model/proj/proj.1/Constant', '/model/proj/proj.1/Constant_1', '/model/proj/proj.1/Constant_2', '/model/proj/proj.1/InstanceNormalization', '/model/proj/proj.1/Reshape', '/model/proj/proj.1/Reshape_1', '/model/proj/proj.1/Shape']
  [lpr_head.1 InstanceNorm] Mul re-wired: '/model/lpr_head/lpr_head.1/Reshape_1_output_0' → '/model/lpr_head/lpr_head.0/Conv_output_0'
  [lpr_head.1 InstanceNorm] Removed 7 nodes: ['/model/lpr_head/lpr_head.1/Constant', '/model/lpr_head/lpr_head.1/Constant_1', '/model/lpr_head/lpr_head.1/Constant_2', '/model/lpr_head/lpr_head.1/InstanceNormalization', '/model/lpr_head/lpr_head.1/Reshape', '/model/lpr_head/lpr_head.1/Reshape_1', '/model/lpr_head/lpr_head.1/Shape']

Nodes after patch : 41
ONNX check        : PASSED

Saved    : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx

Next step:
  python3 compile_to_hef_v2.py --hw-arch hailo8 --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx

### Step 3 — compile (random calibration data — fast, OK for testing)
```bash
python3 compile_to_hef_v2.py \
  --hw-arch hailo8 \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx
# → produces DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef
```

### Step 3 (better) — compile with real LP crop calibration data
```bash
# First build a calibration .npy: real Thai LP crops resized to 300×75, uint8 NCHW [0-255]
# Shape: (N, 3, 75, 300) float32, values 0-255
python3 compile_to_hef_v2.py \
  --hw-arch hailo8 \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx \
  --calib-npy /path/to/lp_crops_calib.npy
```
```bash
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ source ~/hailo-compiler/hailo_env/bin/activate
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ python3 compile_to_hef_v2.py \
> --hw-arch hailo8 \
> --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx \
> --calib-npy lp_calib.npy

# ผลลัพธ์เกิดความผิดพลาด เราแก้ไข

[hailo] target arch : hailo8
[hailo] onnx        : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx
[info] No GPU chosen and no suitable GPU found, falling back to CPU.
[hailo] translating ONNX model …
[info] Translation started on ONNX model DualBranchLPRNet_ThaiLP
[info] Restored ONNX model DualBranchLPRNet_ThaiLP (completion time: 00:00:00.07)
[info] Extracted ONNXRuntime meta-data for Hailo model (completion time: 00:00:00.25)
[info] Simplified ONNX model for a parsing retry attempt (completion time: 00:00:00.43)
[info] Start nodes mapped from original model: 'input_image': 'DualBranchLPRNet_ThaiLP/input_layer1'.
[info] End nodes mapped from original model: '/model/lpr_head/lpr_head.4/Conv', '/model/province_head/province_head.1/Gemm'.
[info] Translation completed on ONNX model DualBranchLPRNet_ThaiLP (completion time: 00:00:00.61)
[hailo] model script written → model_script.alls
[info] Loading model script commands to DualBranchLPRNet_ThaiLP from model_script.alls
Traceback (most recent call last):
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/hailo_sdk_client/sdk_backend/script_parser/model_script_parser.py", line 381, in parse_script
    script_grammar.parseString(input_script, parseAll=True)
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/pyparsing.py", line 1955, in parseString
    raise exc
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/pyparsing.py", line 3814, in parseImpl
    raise ParseException(instring, loc, self.errmsg, self)
pyparsing.ParseException: Expected end of text, found 'n'  (at char 0), (line:1, col:1)

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/admin_pwdvisionworks_com/dualbranch/compile_to_hef_v2.py", line 132, in <module>
    main()
  File "/home/admin_pwdvisionworks_com/dualbranch/compile_to_hef_v2.py", line 94, in main
    runner.load_model_script(MODEL_SCRIPT)
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/hailo_sdk_common/states/states.py", line 16, in wrapped_func
    return func(self, *args, **kwargs)
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/hailo_sdk_client/runner/client_runner.py", line 502, in load_model_script
    self._sdk_backend.load_model_script_from_file(model_script, append)
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/hailo_sdk_client/sdk_backend/sdk_backend.py", line 492, in load_model_script_from_file
    self._script_parser.parse_script_from_file(model_script_path, nms_config, append)
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/hailo_sdk_client/sdk_backend/script_parser/model_script_parser.py", line 312, in parse_script_from_file
    return self.parse_script(f.read(), append, nms_config_file)
  File "/home/admin_pwdvisionworks_com/hailo-compiler/hailo_env/lib/python3.10/site-packages/hailo_sdk_client/sdk_backend/script_parser/model_script_parser.py", line 389, in parse_script
    raise BackendScriptParserException(f"Parsing failed at:\n{e.markInputline()}")
hailo_sdk_client.sdk_backend.sdk_backend_exceptions.BackendScriptParserException: Parsing failed at:
>!<normalization([127.5,127.5,127.5],[127.5,127.5,127.5])
(hailo_env) admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ python3 - << 'PATCH'
with open('compile_to_hef_v2.py', 'r') as f:
    src = f.read()

# 1. Remove normalization() from model script (not supported in this DFC version)
src = src.replace(
    '        normalization([127.5, 127.5, 127.5], [127.5, 127.5, 127.5])\n',
    ''
)

# 2. Normalize calib to [-1,1] before optimize()
#    Hailo DFC sees [-1,1] → sets input quant: scale=2/255, zp=128
#    → uint8[0]=-1, uint8[128]=0, uint8[255]=+1  ✅
src = src.replace(
    '    calib_nhwc = calib.transpose(0, 2, 3, 1)',
    '    calib_nhwc = calib.transpose(0, 2, 3, 1)  # (N,75,300,3)\n'
    '    calib_nhwc = (calib_nhwc / 127.5) - 1.0   # [0,255] → [-1,1] to match training'
)

with open('compile_to_hef_v2.py', 'w') as f:
    f.write(src)
print("Patched ✅")
PATCH
Patched ✅
```
#### Try Again
```bash
(hailo_env) admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ python3 compile_to_hef_v2.py \
  --hw-arch hailo8 \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx \
  --calib-npy lp_calib.npy
[hailo] target arch : hailo8
[hailo] onnx        : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx
[info] No GPU chosen and no suitable GPU found, falling back to CPU.
....
....
[info] Iterations: 4
Reverts on cluster mapping: 0
Reverts on inter-cluster connectivity: 0
Reverts on pre-mapping validation: 0
Reverts on split failed: 0
[info] +-----------+---------------------+---------------------+--------------------+
[info] | Cluster   | Control Utilization | Compute Utilization | Memory Utilization |
[info] +-----------+---------------------+---------------------+--------------------+
[info] | cluster_0 | 50%                 | 29.7%               | 18.8%              |
[info] | cluster_1 | 100%                | 68.8%               | 46.1%              |
[info] | cluster_2 | 81.3%               | 60.9%               | 32.8%              |
[info] | cluster_3 | 68.8%               | 67.2%               | 21.1%              |
[info] | cluster_4 | 81.3%               | 84.4%               | 29.7%              |
[info] | cluster_5 | 68.8%               | 93.8%               | 25%                |
[info] | cluster_6 | 56.3%               | 84.4%               | 17.2%              |
[info] | cluster_7 | 100%                | 90.6%               | 45.3%              |
[info] +-----------+---------------------+---------------------+--------------------+
[info] | Total     | 75.8%               | 72.5%               | 29.5%              |
[info] +-----------+---------------------+---------------------+--------------------+
[info] Successful Mapping (allocation time: 2m 49s)
[info] Compiling kernels of DualBranchLPRNet_ThaiLP_context_0...
[info] Bandwidth of model inputs: 0.514984 Mbps, outputs: 0.0147934 Mbps (for a single frame)
[info] Bandwidth of DDR buffers: 0.0 Mbps (for a single frame)
[info] Bandwidth of inter context tensors: 0.0 Mbps (for a single frame)
[info] Building HEF...
[info] Successful Compilation (compilation time: 5s)
[hailo] done → DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef  (3.6 MB)
```

### Step 4 — copy new HEF back to Mac + camera
```bash
# GCP → Mac
gcloud compute scp \
  <GCP_INSTANCE>:~/dualbranch/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef \
  scripts/train_dualbranch_model/

(venv_simulation) sqh@SqHs-MacBook-Pro AICAMERA % gcloud compute scp \
> hailo-compiler:~/dualbranch/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef \
> scripts/train_dualbranch_model/
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef                                                       55% 2040KB 3   DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef                                    100% 3664KB 263.0KB/s   00:13    
(venv_simulation) sqh@SqHs-MacBook-Pro AICAMERA % gcloud compute scp \
hailo-compiler:~/dualbranch/compile_to_hef_v2.py \                                             
scripts/train_dualbranch_model/
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
compile_to_hef_v2.py                                                                                                             100% 5716    10.0KB/s   00:00    
(venv_simulation) sqh@SqHs-MacBook-Pro AICAMERA % 

# Mac → aicamera1 (via deploy script)
cp scripts/train_dualbranch_model/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef \
   resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503/

bash scripts/deploy_dualbranch_degirum.sh
```


## Calibration .npy format (for Step 3 better)
```python
import cv2, numpy as np, glob

crops = []
for path in glob.glob("lp_crops/*.jpg"):
    img = cv2.imread(path)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (300, 75))             # (75, 300, 3) uint8
    nchw = resized.transpose(2, 0, 1).astype(np.float32)  # (3, 75, 300)
    crops.append(nchw)

calib = np.stack(crops)           # (N, 3, 75, 300) float32, values 0-255
np.save("lp_calib.npy", calib)
```

## Summary of what changed between original and v2 (fixed)

| Parameter | Original (broken) | Fixed |
|---|---|---|
| model script | no normalization | `normalization([127.5,127.5,127.5],[127.5,127.5,127.5])` |
| calib range | `uniform(0.0, 1.0)` | `uniform(0.0, 255.0)` |
| HEF input contract | wrong: uint8 maps to [0,1] | correct: uint8 maps to [-1,1] |
| Python preprocessing | had to normalise to float | just pass uint8 RGB |

# Annotation and crop license plate 
(venv_simulation) sqh@SqHs-MacBook-Pro AICAMERA % python3 scripts/train_dualbranch_model/crop_lp.py \
~/Downloads/train/multiple \ 
~/Downloads/lp_crops
Found 8 images in /Users/sqh/Downloads/train/multiple
Resuming from ID 000169  (168 crops already saved)

[1/8] 07-kn30v1.jpg  (800×600)
Select a ROI and then press SPACE or ENTER button!
Cancel the selection process by pressing c button!

[2/8] 555000003593201.jpg  (450×338)
Select a ROI and then press SPACE or ENTER button!
Cancel the selection process by pressing c button!
  Plate text [consonants digits+province] e.g. 'กข 1234ชลบุรี'  > พธ 755กรุงเทพมหานคร
  ✅  พธ_755กรุงเทพมหานคร_000169.jpg  (83×40 → saved)
  Another LP in this image? [y/N] > y
Select a ROI and then press SPACE or ENTER button!
Cancel the selection process by pressing c button!
  Plate text [consonants digits+province] e.g. 'กข 1234ชลบุรี'  > 70 1885กรุงเทพมหานคร
  ✅  70_1885กรุงเทพมหานคร_000170.jpg  (101×46 → saved)
  Another LP in this image? [y/N] > y
Select a ROI and then press SPACE or ENTER button!
Cancel the selection process by pressing c button!
  Plate text [consonants digits+province] e.g. 'กข 1234ชลบุรี'  > ทม 4558กรุงเทพมหานคร
  ✅  ทม_4558กรุงเทพมหานคร_000171.jpg  (86×36 → saved)
  Another LP in this image? [y/N] > y
Select a ROI and then press SPACE or ENTER button!
Cancel the selection process by pressing c button!
  Plate text [consonants digits+province] e.g. 'กข 1234ชลบุรี'  >   บย 2895สกลนคร
  ✅  บย_2895สกลนคร_000197.jpg  (235×99 → saved)
  Another LP in this image? [y/N] > n

==================================================
Done. 29 new crops saved to /Users/sqh/Downloads/lp_crops
Total in folder: 197 files

# Upload folder to GCloud
(venv_simulation) sqh@SqHs-MacBook-Pro train_dualbranch_model % gcloud compute scp --recurse ./lp_crops hailo-compiler:~/dualbranch/lp_crops

Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
1กย_889กรุงเทพมหานคร_000108.jpg                                100%  124KB 144.6KB/s   00:00    
1กช_2499กรุงเทพมหานคร_000126.jpg                               100% 6171    14.5KB/s   00:00    
ฒถ_4741กรุงเทพมหานคร_000073.jpg                                100% 8051    30.6KB/s   00:00    
ฆญ_9703กรุงเทพมหานคร_000076.jpg                                100%   11KB  42.9KB/s   00:00    
พษ_9614กรุงเทพมหานคร_000181.jpg                                100% 2819    10.7KB/s   00:00 

# SSH Gcloud เพื่อเข้าไปตรวจสอบ
(venv_simulation) sqh@SqHs-MacBook-Pro AICAMERA % gcloud compute ssh hailo-compiler
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
Welcome to Ubuntu 22.04.5 LTS (GNU/Linux 6.8.0-1053-gcp x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

 System information as of Fri May  8 01:09:49 UTC 2026

  System load:  0.0                Processes:             126
  Usage of /:   22.2% of 48.27GB   Users logged in:       0
  Memory usage: 4%                 IPv4 address for ens4: 10.128.0.2
  Swap usage:   0%

 * Strictly confined Kubernetes makes edge and IoT secure. Learn how MicroK8s
   just raised the bar for easy, resilient and secure K8s cluster deployment.

   https://ubuntu.com/engage/secure-kubernetes-at-the-edge

Expanded Security Maintenance for Applications is not enabled.

10 updates can be applied immediately.
7 of these updates are standard security updates.
To see these additional updates run: apt list --upgradable

21 additional security updates can be applied with ESM Apps.
Learn more about enabling ESM Apps service at https://ubuntu.com/esm

New release '24.04.4 LTS' available.
Run 'do-release-upgrade' to upgrade to it.


*** System restart required ***
Last login: Thu May  7 15:23:22 2026 from 49.228.241.221
admin_pwdvisionworks_com@hailo-compiler:~$ ls
dualbranch  hailo-compiler  snap
admin_pwdvisionworks_com@hailo-compiler:~$ cd dualbranch
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ ls
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx  compile_to_hef_v2.py  lp_crops
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ sudo rm -rf lp_crops
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ ls
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503.onnx  compile_to_hef_v2.py
admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ ls lp_crops -la
total 3596
drwxr-xr-x 2 admin_pwdvisionworks_com admin_pwdvisionworks_com   20480 May  8 01:14  .
drwxr--r-- 3 admin_pwdvisionworks_com admin_pwdvisionworks_com    4096 May  8 01:10  ..
-rw-r--r-- 1 admin_pwdvisionworks_com admin_pwdvisionworks_com    6148 May  8 01:11  .DS_Store
-rw-r--r-- 1 admin_pwdvisionworks_com admin_pwdvisionworks_com   17444 May  8 01:11  15_7410กรุงเทพมหานคร_000122.jpg
-rw-r--r-- 1 admin_pwdvisionworks_com admin_pwdvisionworks_com    3608 May  8 01:13  1กก_5367กรุงเทพมหานคร_000102.jpg
-rw-r--r-- 1 admin_pwdvisionworks_com admin_pwdvisionworks_com   21042 May  8 01:13  1กข_929กรุงเทพมหานคร_000115.jpg
-rw-r--r-- 1 admin_pwdvisionworks_com admin_pwdvisionworks_com    6171 May  8 01:10  1กช_2499กรุงเทพมหานคร_000126.jpg
-rw-r--r-- 1 admin_pwdvisionworks_com admin_pwdvisionworks_com    6837 May  8 01:12  1กช_2499กรุงเทพมหานคร_000195.jpg

# Build The Calibration .npy on GCP
```bash
# On GCP
cd ~/dualbranch
pip install opencv-python
python3 - <<'EOF'
import cv2, numpy as np, glob

crops = []
for path in sorted(glob.glob("lp_crops/*.jpg") + glob.glob("lp_crops/*.png")):
    img = cv2.imread(path)
    if img is None:
        continue
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (300, 75))
    crops.append(resized.transpose(2, 0, 1).astype(np.float32))

calib = np.stack(crops)
np.save("lp_calib.npy", calib)
print(f"Saved lp_calib.npy — shape {calib.shape}, range [{calib.min():.0f}, {calib.max():.0f}]")
EOF

```
# compile 
```bash
python3 compile_to_hef_v2.py \
  --hw-arch hailo8 \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx \
  --calib-npy lp_calib.npy
```

# output on Compile log
(hailo_env) admin_pwdvisionworks_com@hailo-compiler:~/dualbranch$ python3 compile_to_hef_v2.py \
  --hw-arch hailo8 \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx \
  --calib-npy lp_calib.npy
[hailo] target arch : hailo8
[hailo] onnx        : DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.onnx
[info] No GPU chosen and no suitable GPU found, falling back to CPU.
[hailo] translating ONNX model …
[info] Translation started on ONNX model DualBranchLPRNet_ThaiLP
[info] Restored ONNX model DualBranchLPRNet_ThaiLP (completion time: 00:00:00.04)
[info] Extracted ONNXRuntime meta-data for Hailo model (completion time: 00:00:00.13)
[info] Simplified ONNX model for a parsing retry attempt (completion time: 00:00:00.27)
[info] Start nodes mapped from original model: 'input_image': 'DualBranchLPRNet_ThaiLP/input_layer1'.
[info] End nodes mapped from original model: '/model/lpr_head/lpr_head.4/Conv', '/model/province_head/province_head.1/Gemm'.
[info] Translation completed on ONNX model DualBranchLPRNet_ThaiLP (completion time: 00:00:00.51)
[hailo] model script written → model_script.alls
[info] Loading model script commands to DualBranchLPRNet_ThaiLP from model_script.alls
[hailo] calibration ← lp_calib.npy
[hailo] calib shape (NHWC): (194, 75, 300, 3)
[hailo] optimizing (quantizing) …
[info] Found model with 3 input channels, using real RGB images for calibration instead of sampling random data.
[info] Starting Model Optimization
[warning] Running model optimization with zero level of optimization is not recommended for production use and might lead to suboptimal accuracy results
[info] Model received quantization params from the hn
[info] MatmulDecompose skipped
[info] Starting Mixed Precision
[info] Model Optimization Algorithm Mixed Precision is done (completion time is 00:00:00.28)
[info] LayerNorm Decomposition skipped
[info] Starting Statistics Collector
[info] Using dataset with 64 entries for calibration
Calibration: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 64/64 [00:11<00:00,  5.60entries/s]
[info] Model Optimization Algorithm Statistics Collector is done (completion time is 00:00:12.16)
[info] Starting Fix zp_comp Encoding
[info] Model Optimization Algorithm Fix zp_comp Encoding is done (completion time is 00:00:00.00)
[info] Matmul Equalization skipped
[info] Starting MatmulDecomposeFix
[info] Model Optimization Algorithm MatmulDecomposeFix is done (completion time is 00:00:00.00)
[info] Finetune encoding skipped
[info] Bias Correction skipped
[info] Adaround skipped
[info] Quantization-Aware Fine-Tuning skipped
[info] Layer Noise Analysis skipped
[info] The calibration set seems to not be normalized, because the values range is [(-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0)].
Since the neural core works in 8-bit (between 0 to 255), a quantization will occur on the CPU of the runtime platform.
Add a normalization layer to the model to offload the normalization to the neural core.
Refer to the user guide Hailo Dataflow Compiler user guide / Model Optimization / Optimization Related Model Script Commands / model_modification_commands / normalization for details.
[info] Model Optimization is done
[hailo] compiling to HEF …
[info] To achieve optimal performance, set the compiler_optimization_level to "max" by adding performance_param(compiler_optimization_level=max) to the model script. Note that this may increase compilation time.
[info] Loading network parameters
[info] Starting Hailo allocation and compilation flow
[info] Building optimization options for network layers...
[info] Successfully built optimization options - 1s 954ms
[info] Trying to compile the network in a single context
[info] Using Single-context flow
[info] Resources optimization params: max_control_utilization=75%, max_compute_utilization=75%, max_compute_16bit_utilization=75%, max_memory_utilization (weights)=75%, max_input_aligner_utilization=75%, max_apu_utilization=75%
[info] Validating layers feasibility

Validating DualBranchLPRNet_ThaiLP_context_0 layer by layer (100%)

 +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  + 
 +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  + 
 +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  + 
 +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  + 
 +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  +  + 

● Finished                                                                             

[info] Layers feasibility validated successfully
[info] Running resources allocation (mapping) flow, time per context: 59m 59s
Context:0/0 Iteration 4: Trying parallel mapping...  
          cluster_0  cluster_1  cluster_2  cluster_3  cluster_4  cluster_5  cluster_6  cluster_7  prepost 
 worker0  V          V          V          V          V          V          V          V          V       
 worker1  V          V          V          V          X          V          V          V          V       
 worker2  V          V          V          V          V          V          X          V          V       
 worker3                                                                                                  

  00:58
Reverts on cluster mapping: 0
Reverts on inter-cluster connectivity: 0
Reverts on pre-mapping validation: 0
Reverts on split failed: 0

[info] Iterations: 4
Reverts on cluster mapping: 0
Reverts on inter-cluster connectivity: 0
Reverts on pre-mapping validation: 0
Reverts on split failed: 0
[info] +-----------+---------------------+---------------------+--------------------+
[info] | Cluster   | Control Utilization | Compute Utilization | Memory Utilization |
[info] +-----------+---------------------+---------------------+--------------------+
[info] | cluster_0 | 50%                 | 29.7%               | 18.8%              |
[info] | cluster_1 | 100%                | 68.8%               | 46.1%              |
[info] | cluster_2 | 81.3%               | 60.9%               | 32.8%              |
[info] | cluster_3 | 68.8%               | 67.2%               | 21.1%              |
[info] | cluster_4 | 81.3%               | 84.4%               | 29.7%              |
[info] | cluster_5 | 68.8%               | 93.8%               | 25%                |
[info] | cluster_6 | 56.3%               | 84.4%               | 17.2%              |
[info] | cluster_7 | 100%                | 90.6%               | 45.3%              |
[info] +-----------+---------------------+---------------------+--------------------+
[info] | Total     | 75.8%               | 72.5%               | 29.5%              |
[info] +-----------+---------------------+---------------------+--------------------+
[info] Successful Mapping (allocation time: 2m 49s)
[info] Compiling kernels of DualBranchLPRNet_ThaiLP_context_0...
[info] Bandwidth of model inputs: 0.514984 Mbps, outputs: 0.0147934 Mbps (for a single frame)
[info] Bandwidth of DDR buffers: 0.0 Mbps (for a single frame)
[info] Bandwidth of inter context tensors: 0.0 Mbps (for a single frame)
[info] Building HEF...
[info] Successful Compilation (compilation time: 5s)
[hailo] done → DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503_fixed.hef  (3.6 MB)
