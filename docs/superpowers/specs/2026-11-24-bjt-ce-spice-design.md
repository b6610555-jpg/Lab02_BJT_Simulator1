# Design Doc: BJT Common-Emitter Amplifier Simulator v1 (Lab 04)

## Intent and Why

ต่อยอดเว็บแอป Flask จาก Lab 03 (ENG29 2121) ให้เป็นเครื่องมือจำลองขยายสัญญาณ
Common-Emitter แบบ Voltage Divider หนึ่งวงจรอ้างอิง ที่รัน ngspice จริงสำหรับ
DC operating point (`.op`), AC frequency response (`.ac`) และ transient (`.tran`)
โดยไม่ทำให้เส้นทาง Analytical DC Bias ทั้งสามโหมดของ Lab 03 เสียหาย

เป้าหมายไม่ใช่การแทนที่แอปเดิม แต่เป็นการเพิ่มชั้น Simulation ที่แยก provenance
ชัดเจน: ค่าจากสมการ Lab 03 ต้องมีป้าย Analytical และค่าจาก ngspice ต้องมีป้าย SPICE
พร้อม netlist, engine status, run id และ log ที่ตรวจย้อนกลับได้

## Goals

- คง `/` และ `/calculate` รวมถึงผล DC Bias 3 โหมดเดิมทั้งหมด
- เพิ่ม route `/simulate` สำหรับ CE Voltage Divider reference circuit
- รัน ngspice จริง 3 analysis: `.op`, `.ac`, `.tran`
- รับ amplitude และ frequency จากผู้ใช้ พร้อมหน่วยวิศวกรรม
- แสดง DC comparison ระหว่าง SPICE กับ analytical reference
- แสดง Bode magnitude/phase และ Vin/Vout waveform จากข้อมูลที่ parse จริง
- แสดง netlist, run id, engine version, model, elapsed time และ log excerpt
- แจ้ง error ทุกกรณีโดยไม่แสดงผลเก่าหรือค่าประมาณว่าเป็น SPICE
- รักษา test เดิม 24 ตัว และเพิ่ม test สำหรับ engine/parser/route

## Non-Goals

- ไม่จำลอง AC/Transient ของ Fixed Bias หรือ Emitter Bias
- ไม่มี drag-and-drop circuit editor, emitter bypass, FET หรือ SPICE solver ของตัวเอง
- ไม่ deploy สู่ผู้ใช้ภายนอก
- ไม่ติดตั้ง chart library ฝั่ง browser; ใช้ server-side SVG จากข้อมูลจริง
- ไม่ commit binary ngspice หรือ run artifacts ขนาดใหญ่

## Anti-Goals (ถือว่าล้มเหลวแม้หน้าจอสวย)

- มีกราฟหรือตัวเลข SPICE ที่ hard-code หรือสร้างขึ้นแทนการ parse output จริง
- ngspice ล้มเหลวแต่หน้าเว็บยังแสดง Success หรือกราฟเดิม
- รวมค่าจาก `bias.py` กับค่าจาก ngspice เป็นค่าเดียวกันโดยไม่มีป้าย provenance
- ใช้ `shell=True` หรือส่งข้อความจากฟอร์มเข้า command โดยไม่ผ่าน validation
- ทำให้ test หรือพฤติกรรมของ Lab 03 เสีย

## Constraints

- Python 3.12, Flask 3.x, pytest 8.x; ไม่เพิ่ม Python dependency ใหม่
- ngspice 47 portable ติดตั้งนอก repo ที่
  `C:\Users\b6610555\AppData\Local\ngspice-47\Spice64\bin\ngspice_con.exe`
  และค้นหาผ่าน `NGSPICE_BIN`, PATH หรือตำแหน่งมาตรฐาน
- เรียก ngspice ด้วย `subprocess.run([...], shell=False, cwd=run_dir, timeout=20)`
- Analysis mode: `dc`, `ac`, `tran`
- AC sweep คงที่ 1 Hz–1 MHz, 20 points/decade
- Transient ใช้ 5 รอบของความถี่, max step = period/200, และ precharge
  coupling capacitors จาก `.op` ด้วย `UIC`
- ค่า default: VCC=12 V, R1=100 kΩ, R2=22 kΩ, RC=2.2 kΩ, RE=1 kΩ, RL=10 kΩ,
  Cin=Cout=10 µF, amplitude=10 mV peak, frequency=1 kHz
- BJT model: `QEDU` generic educational NPN
  `NPN(IS=1e-14 BF=100 VAF=100 RB=10 RC=1 CJE=10p CJC=5p TF=0.3n TR=10n)`
  เนื่องจากไม่พบ instructor starter model ในเครื่อง
- Analytical reference ใช้ `bias.calculate_bias(..., beta=100, VBE=0.70)` และ
  `reference.calculate_reference(...)` ตามสมมติฐาน Lab 03

## Approaches Considered

### A. แยก `/simulate` + `spice_engine.py` + `plots.py` (เลือกแล้ว)

- `/` และ `/calculate` ไม่ถูกแตะ; เพิ่ม route และ section ใหม่ในหน้าเดียวกัน
- `spice_engine.py` เป็น adapter บริสุทธิ์ ไม่ import Flask
- `plots.py` แปลง array จริงเป็น SVG
- ข้อดี: ความเสี่ยงต่อ regression ต่ำ แยกทดสอบ parser ได้ ตรวจ provenance ง่าย
- ข้อเสีย: มีฟอร์ม SPICE แยกจากฟอร์ม Lab 03 (แต่ทำให้ provenance ชัดขึ้น)

### B. รวม analysis selection เข้า `/` เดียว

- ข้อดี: ฟอร์มเดียว
- ข้อเสีย: ต้องแก้ validation และ behavior เดิมของ 3 bias modes ซึ่งเสี่ยงต่อ test
  และทำให้ error path ซับซ้อนโดยไม่จำเป็น

### C. วาดกราฟฝั่ง browser ด้วย Chart.js จาก CDN

- ข้อดี: interactive
- ข้อเสีย: เพิ่ม dependency/network, เสี่ยงกราฟว่างเมื่อ offline และไม่จำเป็นต่อ v1

**ผู้ใช้เลือก A หลังอนุมัติแผนผสาน**

## How It Works (As Decided)

1. ผู้ใช้กรอกค่าอุปกรณ์, amplitude, frequency และเลือก analysis ใน section SPICE
2. `POST /simulate` แปลงค่าฟอร์มเป็น SI แล้วเรียก `spice_engine.run_simulation`
3. Engine สร้าง run directory ใหม่, เขียน netlist, เรียก ngspice batch
4. Parser อ่าน output จริง:
   - `.op`: node voltage table + `@q1[ic]`, `@q1[ib]`, `@q1[ie]`
   - `.ac`: `vm(out)`, `vp(out)`, `vm(vin)`, `vp(vin)` (phase เป็นเรเดียน)
   - `.tran`: `time`, `v(vin)`, `v(out)`
5. `.tran` รัน `.op` ก่อน แล้วใช้ node voltages สร้าง `.ic` และ capacitor IC
   จากนั้นรัน `.tran ... UIC` เพื่อตัด startup transient ของ Cin/Cout
6. Template แสดงผลตาม analysis พร้อม badge SPICE, netlist และ log excerpt
7. ถ้า analysis เป็น DC จะสร้าง comparison row กับ analytical reference
8. ทุก error แสดง alert และไม่ส่ง `sim` object ใด ๆ ไปยัง template

## Measurement Definitions

- `Vin` = โหนด `vin` ซึ่งเป็น ideal source node ก่อน `CIN`
- `Vout` = โหนด `out` หลัง `COUT` เหนือ `RL`
- AC gain = `20 log10(|V(out)| / |V(vin)|)`; phase = `phase(V(out)) - phase(V(vin))`
- AC phase จาก ngspice เป็นเรเดียน ต้องแปลงเป็นองศาและ unwrap
- -3 dB cutoff คำนวณจาก midband gain (max gain ใน sweep)
  ถ้าไม่พบจุดตัดใน 1 Hz–1 MHz ให้แสดง "not determined in sweep range"
- Transient metrics ใช้ค่าจริงจาก array: peak, peak-to-peak และตรวจการกลับเฟส
  จากจุดที่ `|Vin|` สูงสุด

## Provenance

ทุก run แสดง:
- engine version (`ngspice-47`)
- model name/card (`QEDU`)
- run id และตำแหน่ง run directory
- netlist ที่ใช้จริง
- log excerpt (ท้ายไฟล์ ไม่เกิน 4,000 ตัวอักษร)
- elapsed time
- analysis mode และค่าที่ผู้ใช้ป้อน

Run artifacts เก็บใน `instance/sim_runs/<run_id>/` และ ignore จาก Git

## Error Paths

| กรณี | พฤติกรรม |
|---|---|
| ไม่พบ ngspice | `NgspiceNotFound` + วิธีติดตั้ง/ตั้ง `NGSPICE_BIN`; ไม่มีผลลัพธ์ |
| อินพุตผิด/ติดลบ/เกินช่วง | `ValidationError` ก่อนสร้าง netlist; คงค่าฟอร์ม |
| ngspice exit code ≠ 0 | `SimulationError` + exit code + log excerpt |
| timeout 20 s | `SimulationError` ระบุ timeout; ไม่มีผลลัพธ์ |
| output ว่าง/parse ไม่ได้ | `ParseError` + log excerpt |
| convergence/singular matrix | ตรวจ marker ใน log แล้วแจ้ง error จริง |
| request ใหม่หลัง error | ล้าง `sim` เดิม; ไม่มีกราฟหรือ Success ค้าง |

## What's Left to the Builder

- ถ้อยคำและ layout ของ section SPICE ให้เข้ากับ style เดิม
- ความยาว log excerpt และการจัด `<details>`
- การเลือกสี/legend ของกราฟให้อ่านง่ายบน desktop/mobile
- ถ้ามี instructor model card ภายหลัง ให้แทนที่ `QEDU` และอัปเดต validation
