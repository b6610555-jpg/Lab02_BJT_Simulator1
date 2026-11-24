# แอปพลิเคชันวิศวกรรม BJT Common-Emitter DC Bias (ENG29 2121) — Lab 03

เว็บแอป Flask หน้าเดียวสำหรับคำนวณจุดทำงานกระแสตรง (DC operating point) ของขยายสัญญาณแบบ Common-Emitter จากค่าองค์ประกอบที่ป้อนเข้ามา แสดงผลพร้อมหน่วย ตรวจสอบความถูกต้องของค่าอินพุต และเตือนเมื่อทรานซิสเตอร์อยู่ในโซนตัด (cutoff) หรืออิ่มตัว (saturation) นอกจากนี้ต้องเปรียบเทียบผลลัพธ์กับการคำนวณอิสระอีกหนึ่งทางบนหน้าเว็บเดียวกัน เพื่อให้อาจารย์ตรวจสอบความสอดคล้องได้ทันที

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

ทดสอบได้ 58 รายการ (38 รายการเดิมจาก Lab 03 + 20 รายการใหม่สำหรับ Lab 04)

## โครงสร้าง

- `app.py` — เส้นทาง Flask (`GET /`, `POST /`, `POST /simulate`) เลือกฟังก์ชันคำนวณตามโหมดวงจร และตรวจอินพุตเฉพาะช่องที่โหมดนั้นต้องการ
- `bias.py` — คำนวณ DC bias (Thévenin สำหรับ Divider, Fixed Bias, Emitter Bias) ไม่พึ่ง Flask ทดสอบ standalone ได้
- `reference.py` — คำนวณอิสระโดย KCL สมการ 2×2 (สำหรับ Divider) ไม่พึ่ง Flask
- `templates/index.html` — ฟอร์ม + ตารางผล เลือกโหมดได้สามแบบ (Lab 03) + แสดงผล Simulation (Lab 04)
- `static/style.css` — สไตล์พื้นฐาน
- `tests/` — ทดสอบอัตโนมัติด้วย pytest

## หมายเหตุการพัฒนา

โค้ดส่วนที่ AI ช่วยสร้าง: ฟังก์ชัน `calculate_fixed_bias` และ `calculate_emitter_bias` ใน `bias.py`, การเลือกฟังก์ชันตามโหมดและตรวจอินพุตใน `app.py`, และปรับฟอร์มใน `templates/index.html`
นักศึกษาตรวจสมการ หน่วย และผลลัพธ์จากเบราว์เซอร์ (กรณี A1–A5) ด้วยตนเอง

## Lab 04: BJT Amplifier Simulator (ngspice)

### ภาพรวม
ต่อยอดเว็บแอป Flask จาก Lab 03 ให้รัน ngspice จริงสำหรับวงจร Common-Emitter แบบ Voltage Divider reference circuit
- เพิ่มเส้นทาง `/simulate` ให้เลือก Analyse Mode: DC (`.op`), AC (`.ac`), Transient (`.tran`)
- ค่าที่แสดงมาจาก ngspice output จริง (parse แล้ว) มีป้าย SPICE ในหน้าเว็บ
- ค่าอ้างอิงเชิงวิศวกรรม (Lab 03 bias calculation) มีป้าย ANALYTICAL REFERENCE แยกชัดเจน

### การติดตั้ง ngspice 47 แบบ Portable
- ติดตั้งไว้ที่ `C:\Users\{user}\AppData\Local\ngspice-47\Spice64\bin\ngspice_con.exe`
- หรือตั้ง environment variable `NGSPICE_BIN` ชี้ไปที่ executable เหมือนกัน
- เแอปจะค้นหา ngspice ผ่านลำดับ: `NGSPICE_BIN` → `PATH` → `~/AppData/Local/ngspice-47/...` → `C:/Spice64/...` → `C:/Program Files/ngspice/...`

### รันแอป
```bash
py -m pip install -r requirements.txt
set FLASK_APP=app.py
py -m flask run --host 127.0.0.1 --port 5000
```
เปิด `http://127.0.0.1:5000/` แล้วเลือก **Lab 04 · SPICE Simulation** เพื่อรัน ngspice

### คำสั่งทดสอบ
```bash
py -m pytest -v
```
ทดสอบได้ 58 รายการ (38 รายการเดิมจาก Lab 03 + 20 รายการใหม่สำหรับ Lab 04)

### ข้อจำกัด
- วงจรเดียว: CE Voltage Divider reference circuit เท่านั้น
- ไม่มี: Fixed Bias / Emitter Bias การจำลอง AC/Transient
- แบบจำลอง BJT: `QEDU` = `NPN(IS=1e-14 BF=100 VAF=100 RB=10 RC=1 CJE=10p CJC=5p TF=0.3n TR=10n)`
- ค่ากำลังรับ AC sweep: 1 Hz – 1 MHz เพียง 20 จุด/ทศนิยม
- ไม่มี emitter bypass, FET, หรือ drag-and-drop editor
- ไม่มี deployment สู่ผู้ใช้ภายนอก

### โครงสร้างไฟล์ที่เพิ่มเข้ามา
- `spice_engine.py` — discovery, validation, netlist builder, parser
- `plots.py` — SVG Bode/transient plots, engineering units
- `tests/fixtures/` — `.log` fixture จาก ngspice จริง (op.log, ac.log, tran.log)
- `tests/test_spice_engine.py` — test suite สำหรับ engine/parser/real runs
- `tests/test_simulation_routes.py` — test suite สำหรับ `/simulate` route
- `instance/sim_runs/` — run directory (gitignored)
- `docs/superpowers/specs/2026-11-24-bjt-ce-spice-design.md` — design spec
- `docs/superpowers/plans/2026-11-24-bjt-ce-spice.md` — implementation plan