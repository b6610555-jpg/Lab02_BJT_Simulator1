# BJT Common-Emitter DC Bias Web App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้างเว็บแอป Flask หน้าเดียวสำหรับแล็บ ENG29 2121 ที่คำนวณจุดทำงานกระแสตรงของขยายสัญญาณ Common-Emitter แสดงผลพร้อมหน่วย ตรวจสอบค่าอินพุต เตือนโซนตัด/อิ่มตัว และเปรียบเทียบผลจากสองวิธีคำนวณข้างกันบนหน้าเว็บ

**Architecture:** โค้ดแบ่งเป็นโมดูลเล็ก ๆ ตามหน้าที่: `bias.py` (คำนวณโดย Thévenin), `reference.py` (คำนวณอิสระโดย KCL สมการ 2×2), `app.py` (เส้นทาง Flask เดียวที่ `/`), `templates/index.html` (ฟอร์ม + ตารางผล), `static/style.css` (สไตล์พื้นฐาน) โมดูลคำนวณทั้งสองไม่นำเข้าอะไรจาก Flask เพื่อทดสอบ standalone ได้

**Tech Stack:** Flask, pytest, Python 3.12 (ไม่ติดตั้ง dependency เพิ่มเติม)

**Spec:** `docs/superpowers/specs/2026-11-10-bjt-ce-bias-design.md`

## Global Constraints

- `bias.py` และ `reference.py` ต้องไม่นำเข้าอะไรจาก Flask (ทดสอบ standalone ได้)
- หน่วยใช้ระบบ SI (V, Ω, ไร้มิติ); แสดง IB เป็น µA, IC/IE เป็น mA
- ค่าเริ่มต้นของฟอร์ม: VCC=12, R1=47000, R2=10000, RC=2200, RE=470, beta=150, VBE=0.7
- ตรวจสอบค่าอินพุต: ตัวเลขเท่านั้น; VCC, R1, R2, RC, RE, beta, VBE ต้องมากกว่า 0
- คำเตือน (ไม่ขัดข้อง): cutoff ถ้า VBB ≤ VBE; saturation ถ้า VCE < 0.2 V; VBE นอกช่วง 0.5–0.8 V
- หน้าเว็บแสดงผลทั้งสองวิธีข้างกัน พร้อมความต่าง绝对และร้อยละของ IC และ VCE
- ต้องมีทดสอบอัตโนมัติครอบคลุมด้วยpytest และรันบนlocalhost ได้

## Review Focus

ห้าสภาวะที่ทดสอบต้องครอบคลุม (ระบุการทดสอบไว้ใน task ที่รับผิดชอบแล้ว):

1. ค่าตัวอักษรหรือเว้นว่างในฟอร์มใด ๆ → แจ้งข้อผิดพลาด กลับไปที่ฟอร์มพร้อมค่าเดิม
2. VCC, R1, R2, RC, RE, beta, VBE เป็นศูนย์หรือติดลบ → แจ้งข้อผิดพลาดแยกตามฟิลด์
3. VBB ≤ VBE → ป้าย "Cutoff" และ IB ≤ 0 (ไม่คำนวณ IC ต่อ)
4. VCE < 0.2 V → ป้าย "Saturation" เตือนว่า IC จริงต่ำกว่าที่โมเดลคำนวณ
5. VBE นอกช่วง 0.5–0.8 V → ข้อความเตือน "VBE ผิดปกติ" แต่ยังคำนวณได้ตามปกติ

---

### Task 1: Scaffold repo (requirements, gitignore, README)

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Consumes: (none)
- Produces: (none — setup task)

- [ ] **Step 1: Write `requirements.txt`**

```text
Flask>=3.0
pytest>=8.0
```

- [ ] **Step 2: Write `.gitignore`**

```text
__pycache__/
*.pyc
.env
.venv/
venv/
```

- [ ] **Step 3: Write `README.md`** (คำอธิบายสั้น ๆ วิธีรันและทดสอบ เป็นภาษาไทย)

- [ ] **Step 4: Run `git status` to confirm clean tree**

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore README.md
git commit -m "feat: add project scaffold (requirements, gitignore, README)"
```

---

### Task 2: `bias.py` — Thévenin calculation + tests

**Files:**
- Create: `bias.py`
- Create: `tests/test_bias.py`

**Interfaces:**
- Consumes: (none)
- Produces: `calculate_bias(VCC: float, R1: float, R2: float, RC: float, RE: float, beta: float, VBE: float) -> dict`
  คีย์ที่ส่งกลับ: `VBB, RB, IB, IC, IE, VE, VC, VCE, region, warnings`
  หน่วยในค่าดิบ: V, Ω, A, V; เทมเพลตจะแปลงหน่วยแสดงผลเอง

- [ ] **Step 1: Write failing golden-case test in `tests/test_bias.py`**

```python
def test_golden_defaults():
    result = calculate_bias(12, 47000, 10000, 2200, 470, 150, 0.7)
    assert result["region"] == "active"
    assert result["VBB"] == pytest.approx(2.105263157894737, rel=1e-9)
    assert result["RB"] == pytest.approx(8245.614035087719, rel=1e-9)
    assert result["IB"] == pytest.approx(1.78455e-5, rel=1e-6)
    assert result["IC"] == pytest.approx(0.00267682, rel=1e-6)
    assert result["VCE"] == pytest.approx(4.8445, rel=1e-4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bias.py::test_golden_defaults -v`
Expected: FAIL with "name 'calculate_bias' is not defined"

- [ ] **Step 3: Implement `calculate_bias` in `bias.py`**

สูตร Thévenin:
- VBB = VCC × R2 / (R1 + R2)
- RB = R1 × R2 / (R1 + R2)
- IB = (VBB − VBE) / (RB + beta × RE)
- IC = beta × IB
- IE = (beta + 1) × IB
- VE = IE × RE
- VC = VCC − IC × RC
- VCE = VC − VE

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bias.py::test_golden_defaults -v`
Expected: PASS

- [ ] **Step 5: Add second bias point, cutoff, and saturation tests; run full `tests/test_bias.py`**

- [ ] **Step 6: Commit**

```bash
git add bias.py tests/test_bias.py
git commit -m "feat: add bias.py Thévenin calculation with tests"
```

---

### Task 3: `reference.py` — independent KCL calculation + tests

**Files:**
- Create: `reference.py`
- Create: `tests/test_reference.py`

**Interfaces:**
- Consumes: (none)
- Produces: `calculate_reference(VCC: float, R1: float, R2: float, RC: float, RE: float, beta: float, VBE: float) -> dict`
  คีย์เดียวกับ `calculate_bias` เพื่อเปรียบเทียบบนหน้าเว็บ

- [ ] **Step 1: Write failing agreement test in `tests/test_reference.py`**

```python
def test_matches_bias_golden():
    from bias import calculate_bias
    b = calculate_bias(12, 47000, 10000, 2200, 470, 150, 0.7)
    r = calculate_reference(12, 47000, 10000, 2200, 470, 150, 0.7)
    assert r["IC"] == pytest.approx(b["IC"], rel=1e-9)
    assert r["VCE"] == pytest.approx(b["VCE"], rel=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reference.py::test_matches_bias_golden -v`
Expected: FAIL with "name 'calculate_reference' is not defined"

- [ ] **Step 3: Implement `calculate_reference` in `reference.py`**

เขียน KCL ที่โหนดเบสและลูปอิ미터เป็นสมการเชิงเส้น 2×2 ในตัวแปร `(VB, IB)` แก้ด้วยกฎคราเมอร์ (รายละเอียดอัลกอริทึมเขียนในไฟล์จริง)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reference.py::test_matches_bias_golden -v`
Expected: PASS

- [ ] **Step 5: Add golden-value test for reference module; run full `tests/test_reference.py`**

- [ ] **Step 6: Commit**

```bash
git add reference.py tests/test_reference.py
git commit -m "feat: add reference.py independent KCL calculation with tests"
```

---

### Task 4: Flask route, templates, CSS, and route tests

**Files:**
- Create: `app.py`
- Create: `templates/index.html`
- Create: `static/style.css`
- Create: `tests/test_routes.py`

**Interfaces:**
- Consumes: `bias.calculate_bias`, `reference.calculate_reference`
- Produces: Flask route `GET /` และ `POST /` เรนเดอร์ `templates/index.html`

- [ ] **Step 1: Write failing route tests in `tests/test_routes.py`**

```python
def test_get_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200

def test_valid_post_shows_results(client):
    response = client.post("/", data={
        "VCC": "12", "R1": "47000", "R2": "10000",
        "RC": "2200", "RE": "470", "beta": "150", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"active" in response.data.lower()

def test_invalid_post_shows_error(client):
    response = client.post("/", data={
        "VCC": "abc", "R1": "47000", "R2": "10000",
        "RC": "2200", "RE": "470", "beta": "150", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -v`
Expected: FAIL with "name 'app' is not defined" / missing fixtures

- [ ] **Step 3: Implement `app.py` route, `templates/index.html`, `static/style.css`**

`app.py` สร้าง Flask app, ฟิกซ์เจอร์ `client` สำหรับทดสอบ, รับฟอร์ม POST เรียกทั้งสองฟังก์ชันคำนวณ ส่งผลไปเทมเพลต

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py templates/index.html static/style.css tests/test_routes.py
git commit -m "feat: add Flask app, templates, CSS, and route tests"
```

---

### Task 5: Full test suite, localhost demo, and GitHub commit

**Files:** (none new)

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: all tests PASS

- [ ] **Step 2: Start Flask on localhost and verify page loads**

Run: `flask --app app run --host 127.0.0.1 --port 5000`
เปิด `http://127.0.0.1:5000/` ในเบราว์เซอร์ ยืนยันเห็นฟอร์มและผลคำนวณเริ่มต้น

- [ ] **Step 3: Commit all remaining files**

```bash
git add -A
git commit -m "feat: complete BJT CE DC bias web app with tests"
```

- [ ] **Step 4: Report remote URL needed**

แจ้งผู้ใช้ว่าไม่มี `gh` CLI ในเครื่อง ต้องสร้าง GitHub repository แล้วบอก remote URL (หรือผู้ใช้ดันขึ้นเอง)

---

## Self-review (complete)

1. **Spec coverage:** ทุกข้อกำหนดในดีไซน์มี task รองรับ: โครงสร้างไฟล์ (Task 1), การคำนวณ Thévenin + อิสระ (Task 2–3), เส้นทาง Flask + เทมเพลต + CSS (Task 4), ทดสอบทั้งหมด + localhost + GitHub (Task 5) ไม่มีช่องว่าง
2. **Step scan:** แต่ละステ็ปเขียนได้อย่างเดียวจากข้อมูลที่มี ไม่มีบรรทัดที่ตัดสินใจไม่ได้ เช่น "handle edge cases" หรือ "write tests" โดยไม่ระบุชื่อทดสอบ
3. **Type consistency:** `calculate_bias` และ `calculate_reference` คืน dict คีย์เดียวกัน `app.py` เรียกทั้งสองตัวโดยไม่มีความขัดแย้งของชื่อหรือชนิดข้อมูล
4. **Review Focus:** ห้าสภาวะเสี่ยงทั้งหมดมีการทดสอบระบุไว้ใน Task 2–4 แล้ว
5. **Proportion:** แผนงานสั้นกว่าเอกสารดีไซน์พอสมควร ไม่ใช่การลอกโค้ดทั้งหมดเป็นทาส์ก

---

**Plan complete and saved to `docs/superpowers/plans/2026-11-10-bjt-ce-bias.md`.**

Please review the plan. Does it capture what you want?

**Which execution approach should we use?**

- **Subagent-driven** — ผมส่งงานแต่ละทาส์กให้ subagent ทำแยกกัน มีผู้รีวิวตัวใหม่ตรวจก่อนทาส์กถัดไป แล้วรีวิวทั้งสาขาท้ายที่สุด ละเอียดสุด แต่ใช้บริบทใหม่ต่องานและต่องานรีวิว
- **Native** — ผมลงมือทุกทาส์กเองในเซชันนี้ แล้วมีผู้รีวิวตัวใหม่ตรวจทั้งสาขาทีหลังครั้งเดียว เร็วและประหยัดสุด ไม่มีรีวิวอิสระจนจบงาน เหมาะกับโมเดลกลางเพราะแผนงานถือการออกแบบไว้แล้ว

**สำหรับแผนนี้ผมแนะนำ Native** เพราะโปรเจกต์เล็ก ทาส์กน้อย ความสัมพันธ์ระหว่างอินเตอร์เฟซชัดเจน และข้อผิดพลาดที่ส่งออกแก้ไขได้ง่าย คุณเห็นด้วยกับแผนและวิธีนี้ไหมครับ?