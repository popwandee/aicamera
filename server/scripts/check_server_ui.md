# ตรวจสอบ /server/ แสดงหน้าว่าง

## บนเครื่อง server (lprserver)

1. **เทียบ config กับ repo**
   ```bash
   diff /home/devuser/aicamera/server/nginx-lprserver.conf /etc/nginx/sites-available/lprserver
   ```
   ถ้าไม่ตรง ให้ copy แล้ว reload:
   ```bash
   sudo cp /home/devuser/aicamera/server/nginx-lprserver.conf /etc/nginx/sites-available/lprserver
   sudo nginx -t && sudo systemctl reload nginx
   ```

2. **ทดสอบจาก local**
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/server/        # ต้อง 200
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/server/js/chunk-vendors.*.js  # ใช้ชื่อไฟล์จริงจาก dist/js/
   ```

3. **เปิดใน Browser แล้วดู DevTools**
   - แท็บ Network: ตรวจว่า /server/, /server/js/*.js, /server/css/*.css ได้ 200 (ไม่มี 404)
   - แท็บ Console: ดูว่ามี error สีแดงหรือไม่
