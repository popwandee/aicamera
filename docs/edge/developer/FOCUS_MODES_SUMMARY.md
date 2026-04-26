# สรุปโหมดการทดสอบระบบโฟกัส 3 แบบใหม่

## ภาพรวม

เพิ่ม 3 โหมดการทดสอบใหม่สำหรับเปรียบเทียบความคมชัดของภาพ:

1. **Default Mode** - ใช้ค่าอัตโนมัติทุกค่าของ Camera Module 3 IMX708
2. **Manual Mode** - ปรับค่าตามต้องการ
3. **Adaptive Mode** - ปรับอัตโนมัติด้วย code จนคมชัด

## 1. Default Mode (โหมดค่าเริ่มต้น)

### ลักษณะการทำงาน
- ใช้ค่าอัตโนมัติทุกค่าของ IMX708
- Auto Exposure, Auto White Balance, Continuous Autofocus
- ไม่มีการปรับแต่งใดๆ

### Configuration
```python
{
    "AeEnable": True,      # Auto exposure
    "AwbEnable": True,     # Auto white balance
    "AfMode": 2,           # Continuous autofocus
    "AfRange": 0,          # Full range
    "AfSpeed": 0,          # Normal speed
    "AfMetering": 1,       # Center-weighted
    "Brightness": 0.0,     # Default
    "Contrast": 1.0,       # Default
    "Saturation": 1.0,     # Default
    "Sharpness": 1.0       # Default
}
```

### การใช้งาน
```bash
./edge/src/tools/run_focus_test.sh --mode default --duration 300
```

### เหมาะสำหรับ
- Baseline testing - เปรียบเทียบกับโหมดอื่น
- สภาพแวดล้อมปกติที่กล้องทำงานได้ดีอยู่แล้ว

## 2. Manual Mode (โหมดแมนนวล)

### ลักษณะการทำงาน
- ปรับค่าต่างๆ ตามต้องการ
- ควบคุมได้ทุกอย่าง: Brightness, Contrast, Saturation, Sharpness
- สามารถกำหนด Exposure Time และ Analogue Gain
- สามารถเลือก Autofocus Mode

### Parameters
```bash
--af-mode <0|1|2>              # 0=Manual, 1=Auto, 2=Continuous
--brightness <float>           # -1.0 ถึง 1.0
--contrast <float>             # 0.0 ถึง 2.0
--saturation <float>           # 0.0 ถึง 2.0
--sharpness <float>            # 0.0 ถึง 4.0
--exposure-time <int>          # microseconds (ปิด auto exposure)
--analogue-gain <float>        # gain value (ปิด auto exposure)
```

### การใช้งาน
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

### เหมาะสำหรับ
- ทดสอบค่าที่เฉพาะเจาะจง
- Fine-tuning สำหรับสภาพแวดล้อมเฉพาะ
- เปรียบเทียบผลของแต่ละพารามิเตอร์

## 3. Adaptive Mode (โหมดปรับอัตโนมัติ)

### ลักษณะการทำงาน
- ปรับค่าอัตโนมัติด้วย code เพื่อให้ได้ภาพคมชัดที่สุด
- ทดสอบผลและปรับปรุงจนกว่าจะคมชัด
- เมื่อคมชัดแล้วจะหยุดการปรับปรุงค่า เป็นเวลา 1 นาที
- หากภาพแย่ลงจะปรับใหม่

### Algorithm States

1. **Searching Phase**
   - ค้นหาค่าที่ดีเริ่มต้น
   - ทดสอบ focus speed, sharpness ต่างๆ
   - เมื่อ FocusFoM >= 700 และ quality score >= 0.7 → ไป Optimizing

2. **Optimizing Phase**
   - ปรับแต่งค่าจนได้คุณภาพดี
   - Fine-tune sharpness, contrast
   - เมื่อ quality stable และ FocusFoM >= 900 → ไป Stable

3. **Stable Phase**
   - Lock ค่าและ monitor เป็นเวลา 1 นาที
   - ไม่มีการปรับค่า
   - หาก quality < 85% ของ best → ไป Degraded

4. **Degraded Phase**
   - คุณภาพแย่ลง
   - Reset ไป best settings
   - หากไม่ recover → ไป Searching ใหม่

### Parameters ที่ Adaptive Mode จะปรับ

- **Focus Speed**: Normal (0) หรือ Fast (1)
- **Sharpness**: 0.5 ถึง 2.0 (step: 0.25)
- **Contrast**: 0.8 ถึง 1.2 (step: 0.1)
- **Brightness**: -0.2 ถึง 0.2 (step: 0.05)
- **Saturation**: 0.8 ถึง 1.2 (step: 0.1)

### Quality Score Calculation

```python
quality_score = (
    focus_score * 0.7 +      # FocusFoM normalized (0-1)
    exposure_score * 0.2 +   # Exposure quality (0-1)
    gain_score * 0.1          # Gain quality (0-1)
)
```

### การใช้งาน
```bash
./edge/src/tools/run_focus_modes.py --mode adaptive --duration 300
```

### เหมาะสำหรับ
- สภาพแวดล้อมที่เปลี่ยนแปลงบ่อย
- ต้องการภาพคมชัดที่สุดโดยอัตโนมัติ
- ทดสอบประสิทธิภาพของ adaptive algorithm

## การเปรียบเทียบโหมด

### ลำดับการทดสอบ (เมื่อใช้ --compare-all)

1. **Default** - Baseline: ค่าเริ่มต้นของ IMX708
2. **Adaptive** - Auto-optimize: ปรับอัตโนมัติจนคมชัด
3. **Continuous** - Continuous autofocus
4. **Auto** - Auto mode
5. **Hybrid** - Hybrid mode
6. **Manual** - Manual mode

### Metrics สำหรับเปรียบเทียบ

1. **Focus Quality Metrics:**
   - Mean FocusFoM
   - Standard deviation
   - Excellent/Good/Fair/Poor distribution

2. **Detection Metrics:**
   - Detection rate
   - Total vehicles detected
   - Total license plates detected

3. **Overall Score:**
   - Focus Quality (60%) + Detection Rate (40%)

## ตัวอย่างการใช้งาน

### ทดสอบ Default Mode (Baseline)
```bash
./edge/src/tools/run_focus_test.sh --mode default --duration 300
```

### ทดสอบ Adaptive Mode (Auto-Optimize)
```bash
./edge/src/tools/run_focus_test.sh --mode adaptive --duration 300
```

### ทดสอบ Manual Mode (Custom Settings)
```bash
./edge/src/tools/run_focus_test.sh \
    --mode manual \
    --duration 300 \
    --sharpness 1.5 \
    --contrast 1.1
```

### เปรียบเทียบทุกโหมด
```bash
./edge/src/tools/run_focus_test.sh --compare-all --duration 300
```

## ผลลัพธ์ที่ได้

### Adaptive Mode Results

```json
{
  "mode": "adaptive",
  "adaptive_stats": {
    "state": "stable",
    "best_quality": 0.856,
    "current_quality": 0.852,
    "optimization_cycles": 15,
    "settings_tested": 8,
    "stable_periods": 1,
    "re_optimizations": 0,
    "best_settings": {
      "focus_mode": 2,
      "focus_speed": 0,
      "sharpness": 1.5,
      "contrast": 1.1
    }
  },
  "focus_quality": {
    "mean": 856.3,
    "std": 45.2,
    "min": 750,
    "max": 1200
  }
}
```

## สรุป

### Default Mode
- ✅ ง่าย - ไม่ต้องตั้งค่า
- ✅ Baseline สำหรับเปรียบเทียบ
- ❌ อาจไม่เหมาะกับสภาพแวดล้อมเฉพาะ

### Manual Mode
- ✅ ควบคุมได้ทุกอย่าง
- ✅ เหมาะสำหรับ fine-tuning
- ❌ ต้องทดสอบหลายครั้งเพื่อหาค่าที่ดี

### Adaptive Mode
- ✅ ปรับอัตโนมัติ
- ✅ หาค่าที่ดีที่สุดโดยอัตโนมัติ
- ✅ Monitor และ re-optimize เมื่อคุณภาพแย่ลง
- ❌ ใช้เวลานานกว่าในการ optimize

---

**เอกสารนี้สรุปโหมดการทดสอบระบบโฟกัส 3 แบบใหม่**

