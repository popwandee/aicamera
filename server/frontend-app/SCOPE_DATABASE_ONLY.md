# Scope: /server Frontend – แสดงผลจากฐานข้อมูลเท่านั้น

## หลักการ

แอปที่ให้บริการที่ **/server/** จะใช้สำหรับ **แสดงผลข้อมูลจากฐานข้อมูล** โดยดึงข้อมูลผ่าน Backend API (`/server/api/`).

- **รวมอยู่ในการทำงานของ /server:**
  - แสดงรายการ/รายงานที่อ่านจาก Backend API (ซึ่งอ่านจาก DB) หากยังไม่มีข้อมูล ให้แสดงตารางเปล่าพร้อมชื่อคอลัมน์ เพื่อง่ายในการนำข้อมูลไปพัฒนาต่อไป
  - ฟอร์มหรือหน้าจอที่ใช้สร้าง/แก้ไข/ลบข้อมูลผ่าน API 

- **รวมอยู่ในการทำงานของ /server/network :**
  - การสื่อสารโดยตรงกับลูกข่าย (Edge) เช่น WebSocket client, MQTT client
  - ข้อมูล คำแนะนำในการรับ/ส่ง real-time กับอุปกรณ์โดยตรง 
- **รวมอยู่ในการทำงานของ /server/edge_control:**
  - การแสดงสถานะลูกข่าย (Edge) แต่ละตัว หากยังไม่มีข้อมูลให้แสดง Dummy บางส่วนไว้ก่อน
  - ประวัติการเชื่อมต่อกับอุปกรณ์ History


การรับข้อมูลจากลูกข่าย (ข้อความ, ภาพ, events) ให้เป็นหน้าที่ของ **Microservices** เท่านั้น:

- **ws-service** – รับผ่าน WebSocket (Socket.IO) ที่ path `/ws/` แล้วบันทึกข้อมูลลงในฐานข้อมูล และเก็บภาพไว้ที่ /storage เพื่อให้ backend api ดึงไปใช้ต่อในการแสดงผลบน /server/
- **mqtt-service** – รับผ่าน MQTT broker (topics `camera/+/health`, `camera/+/status`) แล้วบันทึกลงฐานข้อมูลผ่าน backend-api เพื่อให้แสดงผลบน /server/edge_control/

จากนั้น Microservices จะบันทึกลง DB หรือส่งต่อให้ Backend API ตามที่ออกแบบ. ฝั่ง /server (frontend-app) แค่แสดงผลหรือจัดการข้อมูลที่มาจาก API/DB.

## อ้างอิง

- แผนและสถาปัตยกรรม: [PLAN_MICROSERVICES_AND_LANDING.md](../../docs/server/PLAN_MICROSERVICES_AND_LANDING.md)
- Landing page มีเมนูลิงก์ไปยัง /server/ (ข้อมูลจาก DB) , /edge_control/ (Edge Status) และ /network/ (สถานะ Services)
