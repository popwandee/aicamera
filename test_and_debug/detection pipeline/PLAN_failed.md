# แผนปรับปรุงประสิทธิภาพจาก EasyOCR ไปใช้ PaddleOCR
## EasyOCR ช้า ไม่สามารถอ่านข้อความบนป้ายได้
## PaddleOCR ไม่สามารถรันบน RPi5 + Hailo-8 ได้
## ข้อสรุป 2026/04/30 คือใช้ Tesseract + Thai+Eng ทำงานได้
1. Plate crop preprocessing 
ก่อนส่งเข้า OCR ต้องทำ preprocessing ของ crop ก่อน เพราะป้ายทะเบียนที่ crop มาจาก detection มักจะเอียง มีแสงไม่สม่ำเสมอ หรือ contrast ต่ำ
```python
import cv2
import numpy as np

def preprocess_plate_crop(crop: np.ndarray) -> np.ndarray:
    # 1. Resize ให้สูงอย่างน้อย 64px รักษา aspect ratio
    h, w = crop.shape[:2]
    if h < 64:
        scale = 64 / h
        crop = cv2.resize(crop, (int(w * scale), 64), 
                          interpolation=cv2.INTER_CUBIC)

    # 2. Deskew ด้วย Hough line transform
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=30)
    if lines is not None:
        angles = [l[0][1] for l in lines[:5]]
        angle_deg = np.degrees(np.median(angles)) - 90
        if abs(angle_deg) < 15:  # แก้เฉพาะที่เอียงน้อย ไม่งั้นจะพัง
            M = cv2.getRotationMatrix2D(
                (crop.shape[1]//2, crop.shape[0]//2), angle_deg, 1.0)
            crop = cv2.warpAffine(crop, M, (crop.shape[1], crop.shape[0]),
                                   borderMode=cv2.BORDER_REPLICATE)

    # 3. CLAHE เพื่อ normalize contrast (สำคัญมากสำหรับแสงจัด/แสงน้อย)
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l = clahe.apply(l)
    crop = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    return crop
```
2. เปลี่ยน OCR engine เป็น PaddleOCR
```python
# ติดตั้ง
# pip install paddlepaddle paddleocr

from paddleocr import PaddleOCR

class ThaiLPROCR:
    def __init__(self):
        # โหลดครั้งเดียวตอน init — ไม่ใช่ async
        # use_angle_cls=True ช่วยจัดการป้ายที่ถ่ายเอียงเล็กน้อย
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang='th',           # Thai + English + digits
            use_gpu=False,       # RPi5 ไม่มี CUDA
            show_log=False,
            det_model_dir='models/paddle/det',   # cache path
            rec_model_dir='models/paddle/rec_th',
            cls_model_dir='models/paddle/cls',
        )
    
    def read_plate(self, crop: np.ndarray) -> dict:
        result = self.ocr.ocr(crop, cls=True)
        
        if not result or not result[0]:
            return {'text': '', 'confidence': 0.0}
        
        # รวม text จากทุก line detection
        texts, scores = [], []
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0]
                score = line[1][1]
                texts.append(text)
                scores.append(score)
        
        combined = ' '.join(texts)
        avg_confidence = float(np.mean(scores)) if scores else 0.0
        
        return {
            'text': combined,
            'confidence': avg_confidence,
            'raw_lines': list(zip(texts, scores))
        }
```

3. Postprocessing ด้วย province dictionary
ป้ายทะเบียนไทยมีโครงสร้างที่แน่นอน ใช้ regex + dictionary เพื่อ validate และ correct ผลลัพธ์
```python
import re

# จังหวัดทั้งหมด 77 จังหวัด (ตัวอย่าง — ใส่ครบทุกจังหวัด)
THAI_PROVINCES = {
    'กรุงเทพมหานคร', 'กระบี่', 'กาญจนบุรี', 'กาฬสินธุ์',
    'กำแพงเพชร', 'ขอนแก่น', 'จันทบุรี', 'ฉะเชิงเทรา',
    'ชลบุรี', 'ชัยนาท', 'ชัยภูมิ', 'ชุมพร', 'เชียงราย',
    'เชียงใหม่', 'ตรัง', 'ตราด', 'ตาก', 'นครนายก',
    'นครปฐม', 'นครพนม', 'นครราชสีมา', 'นครศรีธรรมราช',
    'นครสวรรค์', 'นนทบุรี', 'นราธิวาส', 'น่าน',
    'บึงกาฬ', 'บุรีรัมย์', 'ปทุมธานี', 'ประจวบคีรีขันธ์',
    'ปราจีนบุรี', 'ปัตตานี', 'พระนครศรีอยุธยา', 'พะเยา',
    'พังงา', 'พัทลุง', 'พิจิตร', 'พิษณุโลก', 'เพชรบุรี',
    'เพชรบูรณ์', 'แพร่', 'ภูเก็ต', 'มหาสารคาม', 'มุกดาหาร',
    'แม่ฮ่องสอน', 'ยโสธร', 'ยะลา', 'ร้อยเอ็ด', 'ระนอง',
    'ระยอง', 'ราชบุรี', 'ลพบุรี', 'ลำปาง', 'ลำพูน',
    'เลย', 'ศรีสะเกษ', 'สกลนคร', 'สงขลา', 'สตูล',
    'สมุทรปราการ', 'สมุทรสงคราม', 'สมุทรสาคร', 'สระแก้ว',
    'สระบุรี', 'สิงห์บุรี', 'สุโขทัย', 'สุพรรณบุรี',
    'สุราษฎร์ธานี', 'สุรินทร์', 'หนองคาย', 'หนองบัวลำภู',
    'อ่างทอง', 'อำนาจเจริญ', 'อุดรธานี', 'อุตรดิตถ์',
    'อุทัยธานี', 'อุบลราชธานี',
}

# pattern ป้ายทะเบียนไทย: อักษรไทย 2 ตัว + ตัวเลข 1-4 หลัก + จังหวัด
PLATE_PATTERN = re.compile(
    r'([ก-ฮ]{1,3})\s*(\d{1,4})\s*(.+)?$'
)

def validate_thai_plate(text: str) -> dict:
    text = text.strip()
    m = PLATE_PATTERN.match(text)
    
    if not m:
        return {'valid': False, 'raw': text}
    
    letters = m.group(1)
    numbers = m.group(2)
    province_raw = (m.group(3) or '').strip()
    
    # หาจังหวัดที่ใกล้เคียงที่สุด (fuzzy match อย่างง่าย)
    province_matched = None
    for p in THAI_PROVINCES:
        if province_raw and (p in province_raw or province_raw in p):
            province_matched = p
            break
    
    return {
        'valid': True,
        'letters': letters,
        'numbers': numbers,
        'province': province_matched or province_raw,
        'province_confirmed': province_matched is not None,
        'formatted': f'{letters} {numbers} {province_matched or province_raw}'
    }
```