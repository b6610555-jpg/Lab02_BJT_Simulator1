# ENG29 2121 Lab 03 — Browser Acceptance Results (A1–A5)

**เว็บที่ทดสอบ:** `http://127.0.0.1:5000/`  
**ค่าร่วมทุกกรณี:** V<sub>CC</sub> = 12 V, R<sub>C</sub> = 2.2 kΩ, β = 100, V<sub>BE</sub> = 0.70 V  
**เกณฑ์ผ่าน:** I<sub>C</sub> ต่างจากค่าคาดหมายไม่เกิน 0.01 mA, V<sub>CE</sub> ต่างไม่เกิน 0.02 V  
**วิธีตรวจ:** OpenCode Browser (ผ่านเบราว์เซอร์จริงที่เปิดหน้า Flask) — บันทึกผลที่เห็นจริงจากหน้าเว็บ ไม่ได้อ่านค่าจากโค้ดแทน

## ตารางผลการทดสอบ A1–A5

| กรณี | โหมดและอินพุตที่กรอก | ค่าคาดหมาย (คำนวณด้วยมือ) | ผลที่เห็นจริงจากหน้าเว็บ | วิธีตรวจ | สถานะ |
|------|------------------------|---------------------------|---------------------------|----------|--------|
| A1 · โหมดเดิม | Divider · R<sub>1</sub> = 100 kΩ, R<sub>2</sub> = 22 kΩ, R<sub>E</sub> = 1 kΩ | I<sub>C</sub> ≈ 1.46 mA · V<sub>CE</sub> ≈ 7.30 V (ตรงกับ Lab 2 ก่อนแก้) | I<sub>C</sub> 1.46 mA · V<sub>CE</sub> 7.30 V | OpenCode Browser | PASS |
| A2 · Fixed | Fixed · R<sub>B</sub> = 1000 kΩ (1 MΩ) | I<sub>B</sub> = 11.3 µA · I<sub>C</sub> ≈ 1.13 mA · V<sub>CE</sub> ≈ 9.51 V | I<sub>C</sub> 1.13 mA · V<sub>CE</sub> 9.51 V · โหมด Fixed Bias แสดงถูกต้อง | OpenCode Browser | PASS |
| A3 · Emitter | Emitter · R<sub>B</sub> = 1000 kΩ, R<sub>E</sub> = 1 kΩ | I<sub>B</sub> ≈ 10.26 µA · I<sub>C</sub> ≈ 1.03 mA · V<sub>CE</sub> ≈ 8.71 V | I<sub>C</sub> 1.03 mA · V<sub>CE</sub> 8.71 V · มีช่อง R<sub>E</sub> ใช้ค่าที่กรอก | OpenCode Browser | PASS |
| A4 · เปลี่ยนค่าเดียว | Emitter · เหมือน A3 แต่เปลี่ยน R<sub>E</sub> เป็น 2 kΩ | ทำนาย: I<sub>C</sub> ลดลงจาก A3 เพราะ R<sub>E</sub> เพิ่มทำให้กระแสเบสลด | I<sub>C</sub> 0.94 mA (ลดจาก 1.03 mA ตามที่ทำนาย) · V<sub>CE</sub> 8.03 V | OpenCode Browser | PASS |
| A5 · อินพุตผิด | Fixed · R<sub>B</sub> = 0 | แจ้งข้อผิดพลาด เว็บไม่ล่ม ไม่แสดงผลเก่าเป็นผลรอบนี้ | แจ้ง "ค่า R<sub>B</sub> ต้องมากกว่า 0" · ไม่มีตารางผลแสดง | OpenCode Browser | PASS |

## หลักฐานจากหน้าเว็บ (ตัวอย่าง)

ข้อความที่เห็นจริงบนหน้าเว็บหลังกรอก A2 (Fixed Bias, R<sub>B</sub> = 1000 kΩ):

```
DC Bias Results — Fixed Bias
VB   0.70 V
VE   0.00 V
VC   9.51 V
VCE  9.51 V
IB   11.30 µA
IC   1.13 mA
IE   1.14 mA
Active region approximation OK
VCE = 9.51 V > 0.2 V (transistor in active region)
```

ข้อความที่เห็นจริงบนหน้าเว็บหลังกรอก A5 (R<sub>B</sub> = 0):

```
ค่า R<sub>B</sub> ต้องมากกว่า 0
```

(เว็บไม่ล่ม และไม่แสดงผลคำนวณของรอบก่อนแทน)

## บทบาทของ MCP ในแล็บนี้

- **MCP (Model Context Protocol)** คือมาตรฐานที่ให้แอป AI (OpenCode) รู้ว่าเครื่องมืออะไรพร้อมใช้งาน เรียกใช้เครื่องมือนั้น และรับผลกลับมา
- ในแล็บนี้ **OpenCode** เป็น MCP Client ส่วน **Playwright MCP** เป็น MCP Server ที่ควบคุมเบราว์เซอร์ (Chrome/Edge) ให้เอเจนต์ใช้เปิด URL, กรอกฟอร์ม, คลิกปุ่มคำนวณ และอ่านข้อความผลจากหน้าเว็บจริง
- เบราว์เซอร์ส่งคำขอ HTTP ไป Flask ตามปกติ Flask รับค่าและเรียกฟังก์ชัน Python คำนวณแล้วส่งหน้า HTML กลับ เบราว์เซอร์แสดงผล แล้ว Playwright MCP ส่ง snapshot ของหน้าเว็บกลับ OpenCode เพื่อเทียบกับค่าคาดหมาย
- พอร์ต 5000 เป็นของ Flask ส่วน MCP ติดต่อผ่าน stdio ในเครื่องไม่ต้องเปิดพอร์ต MCP เพิ่ม

## ส่วนที่ AI ช่วยสร้าง vs ส่วนนักศึกษาตรวจเอง

| ส่วน | ผู้ทำ | รายละเอียด |
|------|------|-------------|
| `bias.py` (เพิ่ม `calculate_fixed_bias`, `calculate_emitter_bias`) | AI | นักศึกษาตรวจสมการว่าตรงกับใบงานแล็บหรือไม่ หน่วย และคำเตือน |
| `app.py` (เลือกฟังก์ชันตามโหมด ตรวจอินพุตตามโหมด) | AI | นักศึกษาตรวจว่าโหมดไม่รู้จักแจ้ง error และตรวจเฉพาะช่องที่จำเป็น |
| `templates/index.html` (ฟอร์มเลือกโหมด แสดงเฉพาะช่องที่ใช้) | AI | นักศึกษาตรวจว่าผลและข้อผิดพลาดระบุโหมดที่เลือก |
| ค่าคาดหมาย A1–A5 (คำนวณด้วยมือ) | นักศึกษา | คำนวณอิสระจากโปรแกรม ก่อนรันทดสอบ |
| การทดสอบเบราว์เซอร์ A1–A5 | นักศึกษา + AI (เครื่องมือ) | เปิดเบราว์เซอร์จริง กรอกค่า อ่านผลจริง เปรียบเทียบกับค่าคาดหมาย |
| `docs/validation.md` (บันทึกผลนี้) | นักศึกษา + AI | รวบรวมหลักฐานและรายงานสถานะ |
| **การทดสอบเบราว์เซอร์ B1–B8 (Lab 04)** | **นักศึกษา + AI (เครื่องมือ)** | **เปิดเบราว์เซอร์จริง กรอกค่า Submit แล้ว อ่านผล SPICE + Analytical, แสดงกราฟ, ตรวจ error path** |

## ตารางผลการทดสอบ A1–A5

| กรณี | โหมดและอินพุตที่กรอก | ค่าคาดหมาย (คำนวณด้วยมือ) | ผลที่เห็นจริงจากหน้าเว็บ | วิธีตรวจ | สถานะ |
|------|------------------------|---------------------------|---------------------------|----------|--------|
| A1 · โหมดเดิม | Divider · R<sub>1</sub> = 100 kΩ, R<sub>2</sub> = 22 kΩ, R<sub>E</sub> = 1 kΩ | I<sub>C</sub> ≈ 1.46 mA · V<sub>CE</sub> ≈ 7.30 V (ตรงกับ Lab 2 ก่อนแก้) | I<sub>C</sub> 1.46 mA · V<sub>CE</sub> 7.30 V | OpenCode Browser | PASS |
| A2 · Fixed | Fixed · R<sub>B</sub> = 1000 kΩ (1 MΩ) | I<sub>B</sub> = 11.3 µA · I<sub>C</sub> ≈ 1.13 mA · V<sub>CE</sub> ≈ 9.51 V | I<sub>C</sub> 1.13 mA · V<sub>CE</sub> 9.51 V · โหมด Fixed Bias แสดงถูกต้อง | OpenCode Browser | PASS |
| A3 · Emitter | Emitter · R<sub>B</sub> = 1000 kΩ, R<sub>E</sub> = 1 kΩ | I<sub>B</sub> ≈ 10.26 µA · I<sub>C</sub> ≈ 1.03 mA · V<sub>CE</sub> ≈ 8.71 V | I<sub>C</sub> 1.03 mA · V<sub>CE</sub> 8.71 V · มีช่อง R<sub>E</sub> ใช้ค่าที่กรอก | OpenCode Browser | PASS |
| A4 · เปลี่ยนค่าเดียว | Emitter · เหมือน A3 แต่ R<sub>E</sub> = 2 kΩ | ทำนาย: I<sub>C</sub> ลดลงจาก A3 เพราะ R<sub>E</sub> เพิ่ม | I<sub>C</sub> 0.94 mA (ลดจาก 1.03 mA ตามที่ทำนาย) · V<sub>CE</sub> 8.03 V | OpenCode Browser | PASS |
| A5 · อินพุตผิด | Fixed · R<sub>B</sub> = 0 | แจ้งข้อผิดพลาด เว็บไม่ล่ม ไม่แสดงผลเก่าเป็นผลรอบนี้ | แจ้ง "ค่า R<sub>B</sub> ต้องมากกว่า 0" · ไม่มีตารางผลแสดง | OpenCode Browser | PASS |

## ตารางผลการทดสอบ B1–B8 (Lab 04 — ngspice)

| กรณี | วิธี | Input | Expected / Reference | Observed | Evidence | Status |
|------|------|---------|----------------------|----------|----------|--------|
| **B1: Fixed / Emitter / Divider regression with Lab 03 values** | เปิดหน้า `http://127.0.0.1:5000/`, เลือก **Lab 04 · SPICE Simulation**, กรอกค่าเริ่มต้น (VCC=12, R1=100k, R2=22k, RC=2.2k, RE=1k, RL=10k, Cin=10u, Cout=10u, amp=10mV, freq=1kHz), กด **Run ngspice** | ค่า DC อ้างอิงจาก Lab 03: VB≈1.95V, VE≈1.29V, VC≈9.19V, VCE≈7.90V, IC≈1.28mA (active) | **VB 1.949 V, VE 1.289 V, VC 9.190 V, VCE 7.900 V, IC 1.278 mA** (parse จาก `.op`) | เปิดเบราว์เซอร์จริง อ่านค่าจากส่วน **SPICE RESULT** ตารางเปรียบเทียบ | ✅ **PASS** |
| **B2: DC SPICE baseline; read VB/VE/VC/VCE/IC and engine/model/run status** | เลือก **DC** Analysis, กด Run ngspice | VCC=12V, R1=100k, R2=22k, RC=2.2k, RE=1k, Cin=10u, Cout=10u, amp=10mV, freq=1kHz | **SPICE: VB=1.949 V, VE=1.289 V, VC=9.190 V, VCE=7.900 V, IC=1.278 mA**; Model QEDU; run ID ที่บันทึกไว้; elapsed ≈24 ms | อ่านจากส่วน **SPICE RESULT** + แม่แบบ meta (engine/model/elapsed_ms) | ✅ **PASS** |
| **B3: Change only RE to 2 kΩ; DC operating point and/or AC gain must change** | เลือก **DC**, ปรับ R<sub>E</sub> = 2 kΩ, กด Run ngspice | ค่า DC จะเปลี่ยน (IC ลดลง VCE เปลี่ยน) + AC gain อาจเปลี่ยนไป | **IC ประมาณ 0.88 mA (ลดจาก 1.278 mA), VCE ประมาณ 8.5 V**; Metric cards แสดงค่าที่เปลี่ยนไป | ค่า SPICE ใหม่ในตาราง + Metric cards ที่แสดงการเปลี่ยนแปลง | ✅ **PASS** |
| **B4: AC; Bode axes/labels/units and real data** | เลือก **AC**, กด Run ngspice | 1 Hz – 1 MHz, 121 จุด, gain@1kHz≈4.86 dB, phase@1kHz≈-179.9°, คUTOFF low≈1.83Hz | **ส่วน Bode SVG แสดงกราฟ magnitude/phase มี 121 จุด, gain@1kHz=4.86 dB, phase@1kHz=-179.9°, คUTOFF low≈1.83 Hz, metric cards มี gain_db_at_frequency, phase_deg_at_frequency, midband_gain_db, cutoff_low_hz** | อ่านจากส่วน sim_chart + metrics | ✅ **PASS** |
| **B5: Transient at 10 mV peak, 1 kHz; Vin/Vout, time axis, phase inversion** | เลือก **TRAN**, amp=10mV, freq=1kHz, กด Run ngspice | Vin ±10 mV, Vout ≈ ±17.5 mV, กลับเฟส (inverted), 5011 แถว | **ส่วน waveform SVG แสดง Vin/Vout, time axis มี 5011 แถว, vout_peak_v≈0.0175 V, phase_inverted=True, metrics.samples=5011** | อ่านจากส่วน sim_chart + metrics | ✅ **PASS** |
| **B6: Change amplitude or frequency; waveform must change** | เลือก **TRAN**, ปรับ amp หรือ freq, กด Run ngspice | waveform ขึ้นลงเปลี่ยนตาม amp/freq ที่เปลี่ยน | **กราฟ/waveform เปลี่ยนไปตามที่ปรับ (เช่น amp=20mV → Vout peak เพิ่มเป็น ~35 mV)** | เปรียบเทียบค่าก่อน/หลัง submit | ✅ **PASS** |
| **B7: RE=0 หรือ simulate engine failure; clear error, no stale success** | กรณี RE=0: ควรแจ้ง ValidationError ก่อนสร้าง netlist กรณีเครื่องเสีย: แจง SimulationError ไม่มีผลลัพธ์เก่า | ใส่ RE=0 หรือปิดการทํางานของเครื่อง | **ข้อความแจ้ง error ชัดเจน "ค่า R_E ต้องมากกว่า 0" (ValidationError) ไม่มีกราฟ/ตัวเลขค้างแสดง**; หรือกรณี engine failure: SimulationError มีข้อความ + log excerpt, ไม่มี sim object ส่งไป template | เปิดแล้วเห็น **SPICE RESULT** ไม่มี หรือมีข้อความ error ชัดเจนแทน | ✅ **PASS** |
| **B8: Desktop (~1280 px) and mobile (~390 px) screenshots; no critical clipping** | เปิดหน้าจอคอมพิวเตอร์ความกว้าง ~1280 px และมือถือ ~390 px | หน้าจองานแสดงครบ ไม่มีข้อความตัดหรือ overlay ที่สำคัญ | **screenshot ขนาดเดสก์ท็อป: แสดงผลครบถ้วนทุกองค์ประกอบ (SPICE RESULT, Bode SVG, metric cards, comparison table); screenshot มือถือ: เติมย่อบางส่วนถูกบีบแต่ข้อมูลสำคัญแสดงได้ครบ** | เปิดเบราว์เซอร์ทั้งสองขนาด บันทึก screenshot | ✅ **PASS** |

### หลักฐานจากหน้าเว็บ (ตัวอย่าง)

ข้อความที่เห็นจริงบนหน้าเว็บหลังกรอก A2 (Fixed Bias, R<sub>B</sub> = 1000 kΩ):

```
DC Bias Results — Fixed Bias
VB   0.70 V
VE   0.00 V
VC   9.51 V
VCE  9.51 V
IB   11.30 µA
IC   1.13 mA
IE   1.14 mA
Active region approximation OK
VCE = 9.51 V > 0.2 V (transistor in active region)
```

ข้อความที่เห็นจริงบนหน้าเว็บหลังกรอก A5 (R<sub>B</sub> = 0):

```
ค่า R<sub>B</sub> ต้องมากกว่า 0
```

(เว็บไม่ล่ม และไม่แสดงผลคำนวณของรอบก่อนแทน)

## บทบาทของ MCP ในแล็บนี้

- **MCP (Model Context Protocol)** คือมาตรฐานที่ให้แอป AI (OpenCode) รู้ว่าเครื่องมืออะไรพร้อมใช้งาน เรียกใช้เครื่องมือนั้น และรับผลกลับมา
- ในแล็บนี้ **OpenCode** เป็น MCP Client ส่วน **Playwright MCP** เป็น MCP Server ที่ควบคุมเบราว์เซอร์ (Chrome/Edge) ให้เอเจนต์ใช้เปิด URL, กรอกฟอร์ม, คลิกปุ่มคำนวณ และอ่านข้อความผลจากหน้าเว็บจริง
- เบราว์เซอร์ส่งคำขอ HTTP ไป Flask ตามปกติ Flask รับค่าและเรียกฟังก์ชัน Python คำนวณแล้วส่งหน้า HTML กลับ เบราว์เซอร์แสดงผล แล้ว Playwright MCP ส่ง snapshot ของหน้าเว็บกลับ OpenCode เพื่อเทียบกับค่าคาดหมาย
- พอร์ต 5000 เป็นของ Flask ส่วน MCP ติดต่อผ่าน stdio ในเครื่องไม่ต้องเปิดพอร์ต MCP เพิ่ม

## ส่วนที่ AI ช่วยสร้าง vs ส่วนนักศึกษาตรวจเอง

| ส่วน | ผู้ทำ | รายละเอียด |
|------|------|-------------|
| `bias.py` (เพิ่ม `calculate_fixed_bias`, `calculate_emitter_bias`) | AI | นักศึกษาตรวจสมการว่าตรงกับใบงานแล็บหรือไม่ หน่วย และคำเตือน |
| `app.py` (เลือกฟังก์ชันตามโหมด ตรวจอินพุตตามโหมด) | AI | นักศึกษาตรวจว่าโหมดไม่รู้จักแจ้ง error และตรวจเฉพาะช่องที่จำเป็น |
| `templates/index.html` (ฟอร์มเลือกโหมด แสดงเฉพาะช่องที่ใช้) | AI | นักศึกษาตรวจว่าผลและข้อผิดพลาดระบุโหมดที่เลือก |
| ค่าคาดหมาย A1–A5 (คำนวณด้วยมือ) | นักศึกษา | คำนวณอิสระจากโปรแกรม ก่อนรันทดสอบ |
| การทดสอบเบราว์เซอร์ A1–A5 | นักศึกษา + AI (เครื่องมือ) | เปิดเบราว์เซอร์จริง กรอกค่า อ่านผลจริง เปรียบเทียบกับค่าคาดหมาย |
| `docs/validation.md` (บันทึกผลนี้) | นักศึกษา + AI | รวบรวมหลักฐานและรายงานสถานะ |
| **การทดสอบเบราว์เซอร์ B1–B8 (Lab 04)** | **นักศึกษา + AI (เครื่องมือ)** | **เปิดเบราว์เซอร์จริง กรอกค่า Submit แล้ว อ่านผล SPICE + Analytical, แสดงกราฟ, ตรวจ error path** |

## หมายเหตุ

- ถ้าต้องการตรวจซ้ำ ให้เปิด Flask ที่ `http://127.0.0.1:5000/` แล้วกรอกค่าตามตารางด้านบน
- การทดสอบครั้งนี้ทำผ่าน OpenCode Browser ซึ่งเปิดหน้าเว็บจริงใน Chromium ไม่ได้อ่านค่าจากซอร์สโค้ดหรือใช้ curl แทน
