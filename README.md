# BJT Common-Emitter DC Bias Web App (ENG29 2121) — Lab 03

เว็บแอป Flask หน้าเดียวสำหรับคำนวณจุดทำงานกระแสตรงของขยายสัญญาณ Common-Emitter
รองรับวงจรไบอัสสามแบบ (Fixed Bias, Emitter Bias แบบแหล่งจ่ายเดียว และ Voltage Divider Bias)
คำนวณด้วย Python แยกสมการไว้ใน `bias.py` แล้วแสดงผลพร้อมหน่วยบนหน้าเว็บ

## วิธีรัน

```bash
py -m pip install -r requirements.txt
set FLASK_APP=app.py
py -m flask run --host 127.0.0.1 --port 5000
```

เปิด `http://127.0.0.1:5000/` ในเบราว์เซอร์

## วิธีทดสอบ

```bash
py -m pytest -v
```

## โครงสร้าง

- `app.py` — เส้นทาง Flask (`GET /`, `POST /`, `POST /calculate`) เลือกฟังก์ชันคำนวณตามโหมดวงจร และตรวจอินพุตเฉพาะช่องที่โหมดนั้นต้องการ
- `bias.py` — คำนวณ DC bias (Thévenin สำหรับ Divider, Fixed Bias, Emitter Bias) ไม่พึ่ง Flask ทดสอบ standalone ได้
- `reference.py` — คำนวณอิสระโดย KCL สมการ 2×2 (สำหรับ Divider) ไม่พึ่ง Flask
- `templates/index.html` — ฟอร์ม + ตารางผล เลือกโหมดได้สามแบบ แสดงเฉพาะช่องที่โหมดนั้นใช้
- `static/style.css` — สไตล์พื้นฐาน
- `tests/` — ทดสอบอัตโนมัติด้วย pytest

## หมายเหตุการพัฒนา

โค้ดส่วนที่ AI ช่วยสร้าง: ฟังก์ชัน `calculate_fixed_bias` และ `calculate_emitter_bias` ใน `bias.py`, การเลือกฟังก์ชันตามโหมดและตรวจอินพุตใน `app.py`, และปรับฟอร์มใน `templates/index.html`
นักศึกษาตรวจสมการ หน่วย และผลลัพธ์จากเบราว์เซอร์ (กรณี A1–A5) ด้วยตนเอง
