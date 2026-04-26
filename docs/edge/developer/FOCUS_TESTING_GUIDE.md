# คู่มือการทดสอบระบบโฟกัส (Focus Testing Guide)
## สำหรับ IMX708 Camera Module 3 - LPR Use Case

## สรุป

สคริปต์ทดสอบระบบโฟกัสสำหรับ **IMX708 (Camera Module 3)** ที่ปรับแต่งสำหรับ **LPR (License Plate Recognition) use case** โดยเฉพาะสำหรับกล้องที่ตั้งประจำที่ที่ **รถวิ่งเข้ามาหากล้อง**

สคริปต์จะ config picamera2 ให้เหมาะสมสำหรับการจับภาพรถที่เคลื่อนที่เข้ามา เพื่อให้ได้ภาพที่มีโฟกัสเสถียรและคุณภาพดีสำหรับทั้ง streaming และ detection

## ข้อดีของการทดสอบแยก

1. **ไม่กระทบ Service หลัก**: ทดสอบได้โดยไม่ต้องหยุด service
2. **Config อัตโนมัติสำหรับ IMX708**: สคริปต์จะ config กล้องให้เหมาะสมสำหรับ LPR อัตโนมัติ
3. **รันได้ทันที**: ไม่ต้อง restart หรือ reconfigure
4. **ทดสอบได้หลายครั้ง**: รันทดสอบซ้ำได้ตามต้องการ
5. **Export Results**: ส่งออกผลลัพธ์เป็น JSON (แก้ปัญหา permission แล้ว)
6. **Optimized for LPR**: ตั้งค่าที่เหมาะสมสำหรับรถที่วิ่งเข้ามาหากล้อง

## วิธีการใช้งาน

### 1. ตรวจสอบว่า Service กำลังทำงาน

```bash
# ตรวจสอบว่า camera service ทำงานอยู่
ps aux | grep camera
# หรือ
systemctl status aicamera
```

### 2. รันทดสอบโหมดเดียว

#### วิธีที่ 1: ใช้ Wrapper Script (แนะนำ)

```bash
cd /home/camuser/aicamera

# ทดสอบ Default Mode (ค่าอัตโนมัติทุกค่าของ IMX708)
./edge/src/tools/run_focus_test.sh --mode default --duration 300

# ทดสอบ Adaptive Mode (ปรับอัตโนมัติจนคมชัด)
./edge/src/tools/run_focus_test.sh --mode adaptive --duration 300

# ทดสอบ Manual Mode (ปรับตามต้องการ)
./edge/src/tools/run_focus_test.sh --mode manual --duration 300 --sharpness 1.5 --contrast 1.1

# ทดสอบ Continuous Mode (แนะนำสำหรับพื้นหลังเคลื่อนไหว)
./edge/src/tools/run_focus_test.sh --mode continuous --duration 300
```

#### วิธีที่ 2: รันโดยตรง (ต้องตั้งค่า PYTHONPATH)

```bash
cd /home/camuser/aicamera

# ตั้งค่า PYTHONPATH
export PYTHONPATH=$PWD:$PYTHONPATH

# Activate virtual environment (ถ้ามี)
source edge/installation/venv_hailo/bin/activate

# รันทดสอบ
./edge/src/tools/run_focus_test.sh --mode continuous --duration 300
```

#### ทดสอบ Auto Mode

```bash
./edge/src/tools/run_focus_test.sh --mode auto --duration 300 --trigger-interval 30
```

#### ทดสอบ Manual Mode

```bash
./edge/src/tools/run_focus_test.sh --mode manual --duration 300 --distance 3.0
```

#### ทดสอบ Hybrid Mode

```bash
./edge/src/tools/run_focus_test.sh --mode hybrid --duration 300 --base-distance 3.0
```

### 3. รันทดสอบทุกโหมดและเปรียบเทียบ

```bash
./edge/src/tools/run_focus_test.sh --compare-all --duration 300
```

คำสั่งนี้จะ:
- ทดสอบทุกโหมด (default, adaptive, continuous, auto, hybrid, manual)
- เปรียบเทียบผลลัพธ์
- แสดงสรุปผล
- Export ผลลัพธ์เป็น JSON

**ลำดับการทดสอบ:**
1. **Default** - ค่าเริ่มต้นของ IMX708 (all auto)
2. **Adaptive** - ปรับอัตโนมัติจนคมชัด
3. **Continuous** - Continuous autofocus
4. **Auto** - Auto mode
5. **Hybrid** - Hybrid mode
6. **Manual** - Manual mode

### 4. Export ผลลัพธ์

```bash
# Export ไปยังไฟล์ที่กำหนด (แก้ปัญหา permission แล้ว - ใช้ project directory)
./edge/src/tools/run_focus_test.sh --mode continuous --duration 300 --output edge/tests/results/focus_test.json

# หรือปล่อยให้ใช้ default location (edge/tests/results/)
./edge/src/tools/run_focus_test.sh --mode continuous --duration 300
```

**หมายเหตุ**: ผลลัพธ์จะถูกบันทึกใน `edge/tests/results/` แทน `/tmp/` เพื่อแก้ปัญหา permission denied

## โหมดการทดสอบ 3 แบบใหม่

### 1. Default Mode (โหมดค่าเริ่มต้น)

**ลักษณะการทำงาน:**
- ใช้ค่าอัตโนมัติทุกค่าของ Camera Module 3 IMX708
- Auto Exposure, Auto White Balance, Continuous Autofocus
- ไม่มีการปรับแต่งใดๆ - ใช้ค่า default ของกล้อง

**การใช้งาน:**
```bash
./edge/src/tools/run_focus_test.sh --mode default --duration 300
```

**เหมาะสำหรับ:**
- Baseline testing - เปรียบเทียบกับโหมดอื่น
- สภาพแวดล้อมปกติที่กล้องทำงานได้ดีอยู่แล้ว

### 2. Manual Mode (โหมดแมนนวล)

**ลักษณะการทำงาน:**
- ปรับค่าต่างๆ ตามต้องการ
- สามารถกำหนด Brightness, Contrast, Saturation, Sharpness
- สามารถกำหนด Exposure Time และ Analogue Gain
- สามารถเลือก Autofocus Mode

**การใช้งาน:**
```bash
# ตัวอย่าง: ปรับ Sharpness และ Contrast
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --sharpness 1.5 \
    --contrast 1.1 \
    --brightness 0.0

# ตัวอย่าง: ปรับ Exposure Time แมนนวล
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --exposure-time 33333 \
    --analogue-gain 2.0
```

**Parameters ที่ใช้ได้:**
- `--af-mode`: 0=Manual, 1=Auto, 2=Continuous
- `--brightness`: -1.0 ถึง 1.0
- `--contrast`: 0.0 ถึง 2.0
- `--saturation`: 0.0 ถึง 2.0
- `--sharpness`: 0.0 ถึง 4.0
- `--exposure-time`: microseconds (ปิด auto exposure)
- `--analogue-gain`: gain value (ปิด auto exposure)

### 3. Adaptive Mode (โหมดปรับอัตโนมัติ)

**ลักษณะการทำงาน:**
- ปรับค่าอัตโนมัติด้วย code เพื่อให้ได้ภาพคมชัดที่สุด
- ทดสอบผลและปรับปรุงจนกว่าจะคมชัด
- เมื่อคมชัดแล้วจะหยุดการปรับปรุงค่า เป็นเวลา 1 นาที
- หากภาพแย่ลงจะปรับใหม่

**Algorithm:**
1. **Searching Phase**: ค้นหาค่าที่ดีเริ่มต้น
2. **Optimizing Phase**: ปรับแต่งค่าจนได้คุณภาพดี
3. **Stable Phase**: Lock ค่าและ monitor เป็นเวลา 1 นาที
4. **Degraded Phase**: หากคุณภาพแย่ลง จะ re-optimize

**การใช้งาน:**
```bash
./edge/src/tools/run_focus_test.sh --mode adaptive --duration 300
```

**เหมาะสำหรับ:**
- สภาพแวดล้อมที่เปลี่ยนแปลงบ่อย
- ต้องการภาพคมชัดที่สุดโดยอัตโนมัติ
- ทดสอบประสิทธิภาพของ adaptive algorithm

**Metrics ที่ Adaptive Mode จะปรับ:**
- Focus Speed (Normal/Fast)
- Sharpness (0.5-2.0)
- Contrast (0.8-1.2)
- Brightness (-0.2-0.2)
- Saturation (0.8-1.2)

## IMX708 Configuration สำหรับ LPR Use Case

### การ Config อัตโนมัติ

สคริปต์จะ config picamera2 สำหรับ IMX708 อัตโนมัติเมื่อเริ่มต้น (สำหรับ default mode):

**Camera Configuration:**
- **Model**: IMX708 (Camera Module 3)
- **Main Stream**: 1280x720 RGB888 (สำหรับ Detection)
- **Lores Stream**: 640x640 RGB888 (สำหรับ Web Preview/Streaming)

**Autofocus Configuration (LPR Optimized):**
- **Mode**: Continuous (Mode 2) - เหมาะสำหรับวัตถุที่เคลื่อนที่
- **Speed**: Normal (0) - ความเร็วปกติเพื่อความเสถียร
- **Metering**: Center-weighted (1) - เหมาะสำหรับ LPR ที่วัตถุอยู่ตรงกลาง
- **Range**: Full range (0) - รองรับระยะโฟกัสเต็มช่วง

**Quality Controls:**
- **Brightness**: 0.0 (default)
- **Contrast**: 1.0 (normal)
- **Saturation**: 1.0 (normal)
- **Sharpness**: 1.0 (normal)
- **Auto Exposure**: Enabled
- **Auto White Balance**: Enabled (Auto mode)

### เหตุผลที่ใช้ Continuous Autofocus สำหรับ LPR

1. **รถเคลื่อนที่เข้ามา**: Continuous mode จะติดตามและปรับโฟกัสอย่างต่อเนื่อง
2. **Center-weighted metering**: เน้นที่กลางภาพซึ่งเป็นตำแหน่งที่รถและป้ายทะเบียนจะอยู่
3. **Normal speed**: ไม่เร็วเกินไปเพื่อลดการ hunting และให้ภาพเสถียร
4. **Full range**: รองรับรถที่อยู่ไกลและใกล้กล้อง

## พารามิเตอร์ที่ใช้ได้

### Default Mode Parameters

**ไม่มีพารามิเตอร์** - ใช้ค่าอัตโนมัติทุกค่าของ IMX708

```bash
./edge/src/tools/run_focus_test.sh --mode default --duration 300
```

### Adaptive Mode Parameters

**ไม่มีพารามิเตอร์** - ระบบจะปรับอัตโนมัติ

```bash
./edge/src/tools/run_focus_test.sh --mode adaptive --duration 300
```

**Algorithm States:**
- `searching`: กำลังค้นหาค่าที่ดี
- `optimizing`: กำลังปรับแต่งค่า
- `stable`: ค่าล็อคแล้ว (monitor 1 นาที)
- `degraded`: คุณภาพแย่ลง กำลัง re-optimize

### Manual Mode Parameters

```bash
--af-mode <0|1|2>              # Autofocus mode (0=Manual, 1=Auto, 2=Continuous, default: 2)
--brightness <float>           # Brightness (-1.0 to 1.0, default: 0.0)
--contrast <float>             # Contrast (0.0 to 2.0, default: 1.0)
--saturation <float>           # Saturation (0.0 to 2.0, default: 1.0)
--sharpness <float>            # Sharpness (0.0 to 4.0, default: 1.0)
--exposure-time <int>          # Exposure time in microseconds (disables auto exposure)
--analogue-gain <float>        # Analogue gain (disables auto exposure)
```

**ตัวอย่าง:**
```bash
# ปรับ Sharpness และ Contrast สำหรับภาพคมชัดขึ้น
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --sharpness 1.5 \
    --contrast 1.1 \
    --brightness 0.0

# ปรับ Exposure Time แมนนวล
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --exposure-time 33333 \
    --analogue-gain 2.0
```

### Continuous Mode Parameters (แนะนำสำหรับ LPR)

```bash
--speed <0|1>                   # 0=Normal (แนะนำ), 1=Fast (default: 0)
--metering <0|1>                # 0=Auto, 1=Center (แนะนำสำหรับ LPR, default: 1)
```

**แนะนำสำหรับ LPR:**
```bash
./edge/src/tools/run_focus_test.sh \
    --mode continuous \
    --duration 300 \
    --speed 0 \
    --metering 1
```

### Auto Mode Parameters

```bash
--trigger-interval <seconds>    # ช่วงเวลาที่จะ trigger autofocus (default: 30.0)
--poor-threshold <value>        # FocusFoM threshold สำหรับ poor quality (default: 400)
```

**ตัวอย่าง:**
```bash
./edge/src/tools/run_focus_test.sh \
    --mode auto \
    --duration 300 \
    --trigger-interval 20 \
    --poor-threshold 350
```

### Continuous Mode Parameters

```bash
--speed <0|1>                   # 0=Normal, 1=Fast (default: 0)
--metering <0|1>                # 0=Auto, 1=Center (default: 1)
```

**ตัวอย่าง:**
```bash
./edge/src/tools/run_focus_test.sh \
    --mode continuous \
    --duration 300 \
    --speed 0 \
    --metering 1
```

### Manual Mode Parameters

```bash
--distance <meters>             # ระยะโฟกัสเป็นเมตร (default: 3.0)
--unlock-interval <seconds>     # ช่วงเวลาที่จะ unlock และ re-focus (default: 60.0)
```

**ตัวอย่าง:**
```bash
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --distance 4.0 \
    --unlock-interval 90
```

### Hybrid Mode Parameters

```bash
--base-distance <meters>        # ระยะโฟกัสพื้นฐาน (default: 3.0)
--continuous-range <meters>     # ช่วงการโฟกัสต่อเนื่อง (default: 2.0)
```

**ตัวอย่าง:**
```bash
./edge/src/tools/run_focus_test.sh \
    --mode hybrid \
    --duration 300 \
    --base-distance 3.5 \
    --continuous-range 2.5
```

## ตัวอย่างการใช้งานจริง

### Scenario 1: ทดสอบโหมด Continuous สำหรับ LPR (แนะนำ)

```bash
# ทดสอบ 5 นาที - เหมาะสำหรับ LPR ที่รถวิ่งเข้ามาหากล้อง
./edge/src/tools/run_focus_test.sh \
    --mode continuous \
    --duration 300 \
    --speed 0 \
    --metering 1 \
    --output edge/tests/results/lpr_continuous_test.json
```

**เหตุผล:**
- Continuous mode จะติดตามและปรับโฟกัสเมื่อรถเคลื่อนที่เข้ามา
- Center-weighted metering จะเน้นที่กลางภาพ (ตำแหน่งรถและป้ายทะเบียน)
- Normal speed ให้ภาพเสถียรและลดการ hunting

### Scenario 2: เปรียบเทียบทุกโหมด (LPR Use Case)

```bash
# ทดสอบทุกโหมด 5 นาทีต่อโหมด (รวม 30 นาที)
# โหมดจะถูกทดสอบตามลำดับ:
# 1. Default (baseline - all auto)
# 2. Adaptive (auto-optimize)
# 3. Continuous (continuous tracking)
# 4. Auto (single-shot)
# 5. Hybrid (adaptive)
# 6. Manual (fixed)
./edge/src/tools/run_focus_test.sh \
    --compare-all \
    --duration 300 \
    --output edge/tests/results/lpr_comparison_test.json
```

**ลำดับการทดสอบ:**
1. **Default** - Baseline: ค่าเริ่มต้นของ IMX708 (all auto)
2. **Adaptive** - Auto-optimize: ปรับอัตโนมัติจนคมชัด
3. **Continuous** - เหมาะที่สุดสำหรับรถที่เคลื่อนที่
4. **Auto** - เหมาะสำหรับสภาพที่เสถียร
5. **Hybrid** - แบบปรับตัว
6. **Manual** - เหมาะสำหรับระยะคงที่

### Scenario 3: ทดสอบ Adaptive Mode (Auto-Optimize)

```bash
# ทดสอบ Adaptive Mode - ระบบจะปรับอัตโนมัติจนคมชัด
./edge/src/tools/run_focus_test.sh \
    --mode adaptive \
    --duration 300 \
    --output edge/tests/results/lpr_adaptive_test.json
```

**สิ่งที่ Adaptive Mode จะทำ:**
- ค้นหาค่าที่ดีเริ่มต้น (Searching)
- ปรับแต่งค่าจนได้คุณภาพดี (Optimizing)
- Lock ค่าและ monitor เป็นเวลา 1 นาที (Stable)
- หากคุณภาพแย่ลงจะปรับใหม่ (Degraded → Re-optimize)

### Scenario 4: ทดสอบ Manual Mode ด้วยพารามิเตอร์ต่างๆ

```bash
# ทดสอบ Manual Mode - ปรับ Sharpness และ Contrast
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --sharpness 1.5 \
    --contrast 1.1 \
    --brightness 0.0 \
    --output edge/tests/results/lpr_manual_test.json
```

### Scenario 5: ทดสอบ Auto Mode ด้วยพารามิเตอร์ต่างๆ (LPR Alternative)

```bash
# ทดสอบ Auto Mode ที่ trigger บ่อยขึ้น (เหมาะสำหรับรถเคลื่อนที่เร็ว)
./edge/src/tools/run_focus_test.sh \
    --mode auto \
    --duration 300 \
    --trigger-interval 15 \
    --poor-threshold 350 \
    --output edge/tests/results/lpr_auto_frequent.json

# ทดสอบ Auto Mode ที่ trigger น้อยลง (เหมาะสำหรับรถเคลื่อนที่ช้า)
./edge/src/tools/run_focus_test.sh \
    --mode auto \
    --duration 300 \
    --trigger-interval 60 \
    --poor-threshold 400 \
    --output edge/tests/results/lpr_auto_infrequent.json
```

## ผลลัพธ์ที่ได้

### 1. Console Output

สคริปต์จะแสดงผลลัพธ์แบบ real-time:

```
Starting test: mode=continuous, duration=300s
Test completed successfully.
  Focus Quality - Mean: 756.3
  Detection Rate: 0.234
  Total Frames: 9000
```

### 2. JSON Export

ผลลัพธ์จะถูก export เป็น JSON ใน `edge/tests/results/` หรือ path ที่กำหนด ประกอบด้วย:

```json
{
  "timestamp": "2025-12-XX...",
  "test_results": [
    {
      "mode": "continuous",
      "focus_quality": {
        "mean": 756.3,
        "std": 123.4,
        "min": 450,
        "max": 1200
      },
      "detection_metrics": {
        "detection_rate": 0.234,
        "total_vehicles_detected": 210
      },
      "focus_quality_distribution": {
        "excellent": 1200,
        "good": 3500,
        "fair": 3000,
        "poor": 1300
      }
    }
  ],
  "comparison": {
    "best_mode": {
      "mode": "continuous",
      "score": 0.756
    }
  }
}
```

## การวิเคราะห์ผลลัพธ์

### Metrics สำคัญ

1. **Focus Quality Metrics:**
   - `mean`: FocusFoM เฉลี่ย (ควร > 700)
   - `std`: ความแปรปรวน (ควรต่ำ)
   - `excellent_percent`: เปอร์เซ็นต์ frames ที่มีคุณภาพดี (ควร > 30%)

2. **Detection Metrics:**
   - `detection_rate`: อัตราการตรวจจับ (ควร > 0.2)
   - `total_vehicles_detected`: จำนวนรถที่ตรวจจับได้

3. **Overall Score:**
   - คะแนนรวม (0-1) ที่คำนวณจาก Focus Quality (60%) + Detection Rate (40%)

### การเลือกโหมดที่ดีที่สุด

1. **ดู Overall Score**: เลือกโหมดที่มีคะแนนสูงสุด
2. **ดู Focus Quality**: ตรวจสอบว่า FocusFoM เฉลี่ยสูงและความแปรปรวนต่ำ
3. **ดู Detection Rate**: ตรวจสอบว่าอัตราการตรวจจับสูง
4. **ดู Focus Quality Distribution**: ตรวจสอบว่าเปอร์เซ็นต์ excellent/good สูง

## ข้อควรระวัง

1. **Service จะถูกหยุดอัตโนมัติ**: Script จะหยุด `aicamera_lpr` service ก่อนทดสอบและเริ่มใหม่หลังเสร็จ
2. **Camera ไม่รองรับ Multi-Access**: กล้องไม่สามารถใช้งานพร้อมกันได้ ต้องหยุด service ก่อน
3. **ระยะเวลาทดสอบ**: ควรทดสอบอย่างน้อย 5 นาที (300 วินาที) เพื่อให้ได้ผลลัพธ์ที่แม่นยำ
4. **สภาพแวดล้อม**: ทดสอบในสภาพแวดล้อมจริงที่ต้องการใช้งาน (LPR - รถวิ่งเข้ามาหากล้อง)
5. **Service จะเริ่มใหม่อัตโนมัติ**: หลังทดสอบเสร็จ script จะเริ่ม service ใหม่อัตโนมัติ
6. **Skip Service Control**: ใช้ `--skip-service-control` ถ้า service ไม่ได้ทำงานอยู่แล้ว
7. **IMX708 Configuration**: Script จะ config กล้องอัตโนมัติให้เหมาะสมสำหรับ LPR
8. **Results Directory**: ผลลัพธ์จะถูกบันทึกใน `edge/tests/results/` แทน `/tmp/` เพื่อแก้ปัญหา permission (แก้ไขแล้ว)

## Troubleshooting

### ปัญหา: Permission Denied เมื่อบันทึกผลลัพธ์

**แก้ไขแล้ว**: ผลลัพธ์จะถูกบันทึกใน `edge/tests/results/` ซึ่ง script จะสร้างและตั้ง permission อัตโนมัติ

```bash
# ตรวจสอบว่า directory มีอยู่และมี permission
ls -la edge/tests/results/

# ถ้ายังมีปัญหา ให้สร้าง directory และตั้ง permission เอง
mkdir -p edge/tests/results
chmod 755 edge/tests/results
```

**Fallback**: ถ้า project directory ไม่สามารถเขียนได้ script จะใช้ `~/aicamera_test_results/` แทน

### ปัญหา: ModuleNotFoundError: No module named 'edge'

```bash
# ใช้ wrapper script แทน (แนะนำ)
./edge/src/tools/run_focus_test.sh --mode continuous --duration 300

# หรือตั้งค่า PYTHONPATH ก่อนรัน
export PYTHONPATH=$PWD:$PYTHONPATH
./edge/src/tools/run_focus_test.sh --mode continuous --duration 300
```

### ปัญหา: Camera handler not available

```bash
# Script จะหยุด service อัตโนมัติ แต่ถ้ายังมีปัญหา:
# ตรวจสอบว่า service ทำงานอยู่
systemctl status aicamera_lpr

# หรือ restart service ก่อนรันทดสอบ
sudo systemctl restart aicamera_lpr
```

### ปัญหา: Service stop failed (Permission denied)

```bash
# ต้องใช้ sudo สำหรับหยุด/เริ่ม service
# Script จะเรียก sudo อัตโนมัติ แต่ถ้ายังมีปัญหา:
# ตรวจสอบ sudo permissions หรือรันด้วย sudo
sudo ./edge/src/tools/run_focus_test.sh --mode continuous --duration 300
```

### ปัญหา: Service was not running before test

```bash
# ถ้า service ไม่ได้ทำงานอยู่แล้ว ใช้ --skip-service-control
./edge/src/tools/run_focus_test.sh \
    --mode continuous \
    --duration 300 \
    --skip-service-control
```

### ปัญหา: Frame buffer not ready

```bash
# รอให้ service เริ่มต้นเสร็จก่อน (ประมาณ 10-30 วินาที)
# หรือตรวจสอบ log
tail -f /var/log/aicamera/camera.log
```

### ปัญหา: Detection manager not available

```bash
# ไม่เป็นปัญหา - ทดสอบจะรันได้แต่จะไม่มี detection metrics
# หรือตรวจสอบว่า detection service ทำงานอยู่
systemctl status aicamera-detection
```

## สรุป

### Features สำหรับ IMX708 LPR Use Case

- **หยุด/เริ่ม Service อัตโนมัติ**: Script จะหยุด `aicamera_lpr` ก่อนทดสอบและเริ่มใหม่หลังเสร็จ
- **IMX708 Auto Configuration**: Config กล้องอัตโนมัติให้เหมาะสมสำหรับ LPR (Continuous AF, Center-weighted)
- **Camera ไม่รองรับ Multi-Access**: ต้องหยุด service ก่อนใช้งานกล้อง
- **รันแยกได้**: ทดสอบได้โดยไม่ต้องแก้ไข service หลัก
- **Export Results**: ส่งออกผลลัพธ์เป็น JSON ใน `edge/tests/results/` (แก้ปัญหา permission แล้ว)
- **เปรียบเทียบได้**: รันทดสอบหลายโหมดและเปรียบเทียบผล (ลำดับตามความเหมาะสมสำหรับ LPR)
- **Cleanup อัตโนมัติ**: หลังทดสอบเสร็จจะหยุดกล้องและเริ่ม service ใหม่ให้เรียบร้อย
- **Optimized for Moving Objects**: Continuous autofocus เหมาะสำหรับรถที่วิ่งเข้ามาหากล้อง
- **Stable Image Quality**: Center-weighted metering และ normal speed ให้ภาพเสถียรและลด hunting

### Configuration สำหรับ LPR ที่แนะนำ

**Best Practice (3 แบบ):**

1. **Default Mode (Baseline):**
   - ใช้ค่าอัตโนมัติทุกค่าของ IMX708
   - เหมาะสำหรับ baseline testing

2. **Adaptive Mode (Auto-Optimize):**
   - ระบบปรับอัตโนมัติจนคมชัด
   - เหมาะสำหรับสภาพแวดล้อมที่เปลี่ยนแปลง

3. **Continuous Mode (Manual Tuned):**
   - **Mode**: Continuous (Mode 2)
   - **Speed**: Normal (0)
   - **Metering**: Center-weighted (1)
   - **Range**: Full (0)
   - **Resolution**: Main 1280x720, Lores 640x640
   - **Format**: RGB888

**การเลือกโหมด:**
- **Default**: ใช้เป็น baseline เพื่อเปรียบเทียบ
- **Adaptive**: ใช้เมื่อต้องการภาพคมชัดที่สุดโดยอัตโนมัติ
- **Continuous**: ใช้เมื่อรู้ค่าที่เหมาะสมแล้ว
- **Manual**: ใช้เมื่อต้องการควบคุมทุกอย่างเอง

การ config นี้เหมาะสำหรับกล้อง LPR ที่ตั้งประจำที่ที่รถวิ่งเข้ามาหากล้อง เพราะจะติดตามและปรับโฟกัสอย่างต่อเนื่องให้ได้ภาพที่ชัดและเสถียรสำหรับทั้ง streaming และ detection

---

**เอกสารนี้ให้คำแนะนำการใช้งาน Focus Testing Script**

