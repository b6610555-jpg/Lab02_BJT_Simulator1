# BJT Common-Emitter DC Bias (ENG29 2121)

เว็บแอป Flask หน้าเดียวสำหรับคำนวณจุดทำงานกระแสตรงของขยายสัญญาณแบบ Common-Emitter

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

- `app.py` — เส้นทาง Flask (`GET /`, `POST /`)
- `bias.py` — คำนวณโดยวิธี Thévenin (ไม่พึ่ง Flask)
- `reference.py` — คำนวณอิสระโดย KCL สมการ 2×2 (ไม่พึ่ง Flask)
- `templates/index.html` — ฟอร์ม + ตารางผลลัพธ์
- `static/style.css` — สไตล์พื้นฐาน
- `tests/` — ทดสอบอัตโนมัติด้วย pytest
