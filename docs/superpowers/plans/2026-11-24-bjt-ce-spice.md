# BJT Common-Emitter Amplifier Simulator v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่มการจำลอง ngspice จริง (`.op`, `.ac`, `.tran`) สำหรับวงจร CE Voltage Divider หนึ่งวงจรลงใน Flask app จาก Lab 03 โดยไม่ทำลาย analytical DC bias 3 โหมดและ test เดิม

**Architecture:** เพิ่ม `/simulate` แยกจาก `/` และ `/calculate` เดิม; `spice_engine.py` ทำ netlist/subprocess/parser แบบ pure Python; `plots.py` แปลง array จริงเป็น SVG; template แสดงผล SPICE พร้อม provenance และ analytical comparison แยกป้ายชัดเจน

**Tech Stack:** Python 3.12, Flask 3.x, pytest 8.x, ngspice 47 (portable, external process), server-side SVG (ไม่มี chart library)

**Spec:** `docs/superpowers/specs/2026-11-24-bjt-ce-spice-design.md`

## Global Constraints

- ห้ามแก้ behavior ของ `/` และ `/calculate` เดิม; test เดิม 24 ตัวต้องผ่าน
- `spice_engine.py` และ `plots.py` ต้องไม่ import Flask
- เรียก ngspice ด้วย `subprocess.run([...], shell=False, cwd=run_dir, timeout=20)`
- Analysis ที่รองรับ: `dc`, `ac`, `tran`
- AC sweep: `.ac dec 20 1 1meg`
- Tran: 5 รอบความถี่, max step = period/200, `.tran ... UIC` และ precharge Cin/Cout จาก `.op`
- Model: `QEDU` = `NPN(IS=1e-14 BF=100 VAF=100 RB=10 RC=1 CJE=10p CJC=5p TF=0.3n TR=10n)`
- Analytical reference: `bias.calculate_bias(..., beta=100, VBE=0.70)`; SPICE model BF=100
- `Vin` คือโหนด `vin` ก่อน `CIN`; `Vout` คือโหนด `out` หลัง `COUT`
- AC phase จาก ngspice เป็นเรเดียน ต้องแปลงเป็นองศาและ unwrap
- ทุก error ต้องไม่มี `sim` object ส่งไป template และต้องไม่แสดงผลเก่า
- Run artifacts อยู่ใต้ `instance/sim_runs/<run_id>/` และ ignore จาก Git
- ห้าม hard-code trace/กราฟ/ค่าสำเร็จ; ค่าทั้งหมดต้องมาจาก parser ของ output จริง

## Review Focus

1. ngspice ไม่มีใน PATH/`NGSPICE_BIN` → หน้าเว็บแจ้งวิธีติดตั้งและไม่แสดงผลใด ๆ
2. ngspice exit 0 แต่ log มี error/ไม่มีข้อมูล → parser ต้อง raise `ParseError` ไม่คืนกราฟว่างพร้อม Success
3. ผู้ใช้ใส่ RE=0, ค่าติดลบ, frequency นอกช่วง, หรือข้อความ → validation ต้องปฏิเสธก่อนสร้าง netlist
4. เปลี่ยน amplitude/frequency แล้วกราฟต้องเปลี่ยนตามจริง → integration test ต้องยืนยันว่า array เปลี่ยน
5. Request ใหม่ที่ error หลังเคยมีผลสำเร็จ → ต้องไม่มีกราฟ/ตัวเลขเก่าค้างใน response

---

### Task 1: Engine discovery, validation, netlist builder

**Files:**
- Create: `spice_engine.py`
- Create: `tests/test_spice_engine.py`

**Interfaces:**
- Consumes: (none)
- Produces:
  - `find_ngspice() -> pathlib.Path` (raise `NgspiceNotFound`)
  - `ngspice_available() -> bool`
  - `validate_simulation_input(params: dict) -> dict`
  - `build_netlist(params: dict, analysis: str, op_result: dict | None = None) -> str`
  - exceptions: `SimulationError`, `NgspiceNotFound`, `ValidationError`, `ParseError`
  - constants: `DEFAULT_MODEL_NAME`, `BJT_MODEL_CARD`, `AC_FMIN_HZ`, `AC_FMAX_HZ`, `SIM_TIMEOUT_S`

- [ ] **Step 1: Write failing tests in `tests/test_spice_engine.py`**

```python
import math
from pathlib import Path
import pytest
import spice_engine as se

BASE = {
    "vcc_v": 12.0,
    "r1_ohm": 100_000.0,
    "r2_ohm": 22_000.0,
    "rc_ohm": 2_200.0,
    "re_ohm": 1_000.0,
    "rl_ohm": 10_000.0,
    "cin_f": 10e-6,
    "cout_f": 10e-6,
    "amplitude_v": 0.010,
    "frequency_hz": 1_000.0,
    "beta": 100.0,
    "vbe": 0.70,
}

def test_find_ngspice_from_env(monkeypatch, tmp_path):
    fake = tmp_path / "ngspice_con.exe"
    fake.write_text("")
    monkeypatch.setenv("NGSPICE_BIN", str(fake))
    assert se.find_ngspice() == fake

def test_validate_baseline_converts_to_si():
    p = se.validate_simulation_input(BASE)
    assert p["vcc_v"] == pytest.approx(12.0)
    assert p["r1_ohm"] == pytest.approx(100_000.0)
    assert p["cin_f"] == pytest.approx(10e-6)
    assert p["amplitude_v"] == pytest.approx(0.010)
    assert p["frequency_hz"] == pytest.approx(1_000.0)

@pytest.mark.parametrize("field,value", [
    ("vcc_v", 0), ("r1_ohm", 0), ("re_ohm", -1),
    ("amplitude_v", 0), ("frequency_hz", 0), ("frequency_hz", 2e6),
    ("cin_f", 0), ("beta", 0), ("vbe", 2),
])
def test_validate_rejects_bad_values(field, value):
    with pytest.raises(se.ValidationError):
        se.validate_simulation_input({**BASE, field: value})

def test_validate_rejects_unknown_analysis():
    with pytest.raises(se.ValidationError):
        se.validate_simulation_input(BASE, analysis="fft")

def test_build_netlist_contains_required_elements():
    net = se.build_netlist(BASE, "dc")
    assert "Q1 coll base emit QEDU" in net
    assert ".model QEDU NPN(" in net
    assert ".op" in net
    assert "VIN vin 0 DC 0 AC 1 SIN(0 0.01 1000)" in net
    assert "R1 vcc base 100000" in net
    assert "CIN vin base 1e-05" in net

def test_build_netlist_ac_and_tran_directives():
    assert ".ac dec 20 1 1meg" in se.build_netlist(BASE, "ac")
    tran = se.build_netlist(BASE, "tran", op_result={
        "vb": 1.949127, "ve": 1.289352, "vc": 9.189633,
        "vout": 0.0, "vin": 0.0, "vcc": 12.0,
    })
    assert ".tran" in tran and "UIC" in tran
    assert "CIN vin base 1e-05 IC=-1.949127" in tran
    assert "COUT coll out 1e-05 IC=9.189633" in tran
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_spice_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spice_engine'`

- [ ] **Step 3: Implement constants, exceptions, discovery, validation, and netlist builder in `spice_engine.py`**

`find_ngspice()` checks in order:
1. `NGSPICE_BIN` env if it points to an existing file
2. `shutil.which("ngspice_con")`, then `shutil.which("ngspice")`
3. `Path.home()/"AppData/Local/ngspice-47/Spice64/bin/ngspice_con.exe"`
4. `Path("C:/Spice64/bin/ngspice_con.exe")`
5. `Path("C:/Program Files/ngspice/Spice64/bin/ngspice_con.exe")`

`validate_simulation_input(params, analysis="dc")` returns a normalized copy with float values and a `warnings` list. Ranges:
- `vcc_v` 1–60; `r1_ohm`, `r2_ohm` 100–10e6
- `rc_ohm`, `re_ohm`, `rl_ohm` 1–1e6
- `cin_f`, `cout_f` 1e-9–1e-2
- `amplitude_v` 1e-6–2.0 (warning if > 0.2 that small-signal/clipping may apply)
- `frequency_hz` 1–1e6
- `beta` 1–1000; `vbe` 0.1–1.0
- reject `NaN`, infinity, non-numeric, and `analysis not in {"dc","ac","tran"}`

`build_netlist` emits exactly:

```text
* ENG29 2121 Lab 04 - CE voltage divider reference
.options noacct
VCC vcc 0 {vcc}
VIN vin 0 DC 0 AC 1 SIN(0 {amp} {freq})
R1 vcc base {r1}
R2 base 0 {r2}
RC vcc coll {rc}
RE emit 0 {re}
Q1 coll base emit QEDU
CIN vin base {cin}{ic_cin}
COUT coll out {cout}{ic_cout}
RL out 0 {rl}
.model QEDU NPN(IS=1e-14 BF=100 VAF=100 RB=10 RC=1 CJE=10p CJC=5p TF=0.3n TR=10n)
<analysis directives>
.end
```

Use `_spice_num(value)` formatting `f"{value:.12g}"`. For `tran`, require `op_result`; add `.ic V(vin)=... V(base)=vb ...` and capacitor `IC=` values. Tran directives:
`_tran_step = 1/(frequency*200)`, `_tran_stop = 5/frequency`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_spice_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add spice_engine.py tests/test_spice_engine.py
git commit -m "feat: add ngspice discovery, validation, and netlist builder"
```

---

### Task 2: Parse DC operating point (`.op`)

**Files:**
- Create: `tests/fixtures/op_baseline.log` (copy from the real probe run)
- Modify: `tests/test_spice_engine.py`
- Modify: `spice_engine.py`

**Interfaces:**
- Consumes: `spice_engine` constants from Task 1
- Produces: `parse_op(log: str) -> dict` with keys `nodes`, `vb`, `ve`, `vc`, `vce`, `ic`, `ib`, `ie`, `region`, `warnings`, `source`

- [ ] **Step 1: Copy the real `.op` log into fixtures**

```powershell
New-Item -ItemType Directory -Force -Path tests/fixtures | Out-Null
Copy-Item 'C:\Users\b6610555\AppData\Local\Temp\opencode\spice-probe2\op.log' 'tests/fixtures/op_baseline.log'
```

- [ ] **Step 2: Add failing parser tests**

```python
FIXTURES = Path(__file__).parent / "fixtures"

def test_parse_op_fixture():
    data = se.parse_op((FIXTURES / "op_baseline.log").read_text())
    assert data["vb"] == pytest.approx(1.949127, abs=1e-5)
    assert data["ve"] == pytest.approx(1.289352, abs=1e-5)
    assert data["vc"] == pytest.approx(9.189633, abs=1e-5)
    assert data["vce"] == pytest.approx(7.900281, abs=1e-5)
    assert data["ic"] == pytest.approx(1.278092e-3, rel=1e-4)
    assert data["ib"] == pytest.approx(1.191812e-5, rel=1e-4)
    assert data["ie"] == pytest.approx(1.29001e-3, rel=1e-4)
    assert data["region"] == "active"

def test_parse_op_rejects_empty_log():
    with pytest.raises(se.ParseError):
        se.parse_op("")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_spice_engine.py -k "parse_op" -v`
Expected: FAIL with `AttributeError: module 'spice_engine' has no attribute 'parse_op'`

- [ ] **Step 4: Implement `parse_op` in `spice_engine.py`**

Parse the default `.op` node table (`Node / Voltage` header, then `name value` rows) into `nodes`. Parse `@q1[ic]`, `@q1[ib]`, `@q1[ie]` from the source-current table; use absolute value for `ie`. If `@q1` values are absent, derive:
`ic=(vcc-vc)/rc`, `ie=ve/re`, `ib=ie-ic` and append a warning that values were derived from SPICE node voltages.

`region`:
- `cutoff` if `ic < 1e-9` or `vb < 0.4`
- `saturation` if `vce < 0.2`
- else `active`

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_spice_engine.py -k "parse_op" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add spice_engine.py tests/test_spice_engine.py tests/fixtures/op_baseline.log
git commit -m "feat: parse ngspice DC operating point"
```

---

### Task 3: Parse AC response and calculate Bode metrics

**Files:**
- Create: `tests/fixtures/ac_baseline.log`
- Modify: `tests/test_spice_engine.py`
- Modify: `spice_engine.py`

**Interfaces:**
- Consumes: `parse` helpers from Task 2
- Produces:
  - `parse_ac(log: str) -> dict` with `frequency_hz`, `vout_mag`, `vin_mag`, `gain_db`, `phase_deg`
  - `interpolate_at(freqs: list[float], values: list[float], target: float) -> float | None`
  - `find_cutoff(freqs: list[float], gain_db: list[float], side: str) -> float | None`
  - `ac_metrics(data: dict, frequency_hz: float) -> dict`

- [ ] **Step 1: Copy the real `.ac` log**

```powershell
Copy-Item 'C:\Users\b6610555\AppData\Local\Temp\opencode\spice-probe2\ac.log' 'tests/fixtures/ac_baseline.log'
```

- [ ] **Step 2: Add failing AC tests**

```python
def test_parse_ac_fixture():
    data = se.parse_ac((FIXTURES / "ac_baseline.log").read_text())
    assert len(data["frequency_hz"]) == 121
    assert data["frequency_hz"][0] == pytest.approx(1.0)
    assert data["frequency_hz"][-1] == pytest.approx(1e6)
    assert data["gain_db"][60] == pytest.approx(4.858954, abs=1e-4)
    assert data["phase_deg"][60] == pytest.approx(-179.8686, abs=1e-3)

def test_find_low_cutoff_and_no_high_cutoff():
    data = se.parse_ac((FIXTURES / "ac_baseline.log").read_text())
    assert se.find_cutoff(data["frequency_hz"], data["gain_db"], "low") == pytest.approx(1.82658, rel=1e-3)
    assert se.find_cutoff(data["frequency_hz"], data["gain_db"], "high") is None

def test_interpolate_at_uses_log_frequency():
    data = se.parse_ac((FIXTURES / "ac_baseline.log").read_text())
    assert se.interpolate_at(data["frequency_hz"], data["gain_db"], 1000) == pytest.approx(4.858954, abs=1e-4)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_spice_engine.py -k "ac or cutoff or interpolate" -v`
Expected: FAIL with missing `parse_ac`

- [ ] **Step 4: Implement AC parsing and metrics**

The log contains repeated `Index frequency vm(...) vp(...)` headers and page breaks. Parse every table, collect `vm(out)`, `vp(out)`, `vm(vin)`, `vp(vin)` by row index, merge by index, then:
- `phase_deg = degrees(vp_out - vp_in)` with unwrap (adjust by ±360 when jump > 180)
- `gain_db = 20*log10(vout_mag/vin_mag)`

`find_cutoff`:
- `target = max(gain_db) - 3`
- `side="low"`: first upward crossing; `side="high"`: first downward crossing
- interpolate linearly in `log10(f)`; return `None` if no crossing

`ac_metrics` returns `gain_db_at_frequency`, `gain_vv_at_frequency`, `phase_deg_at_frequency`, `midband_gain_db`, `cutoff_low_hz`, `cutoff_high_hz`, `sweep_hz`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_spice_engine.py -k "ac or cutoff or interpolate" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add spice_engine.py tests/test_spice_engine.py tests/fixtures/ac_baseline.log
git commit -m "feat: parse ngspice AC response and Bode metrics"
```

---

### Task 4: Run ngspice, parse transient, and precharge from `.op`

**Files:**
- Create: `tests/fixtures/tran_baseline.log`
- Modify: `tests/test_spice_engine.py`
- Modify: `spice_engine.py`

**Interfaces:**
- Consumes: `build_netlist`, `parse_op`, `parse_ac`, `parse_tran`, `find_ngspice`
- Produces:
  - `parse_tran(log: str) -> dict` with `time_s`, `vin_v`, `vout_v`
  - `tran_metrics(data: dict) -> dict`
  - `run_simulation(params: dict, analysis: str) -> dict`

- [ ] **Step 1: Copy the real `.tran` log created with `.op` IC precharge**

```powershell
Copy-Item 'C:\Users\b6610555\AppData\Local\Temp\opencode\spice-probe3\tran_ic.log' 'tests/fixtures/tran_baseline.log'
```

- [ ] **Step 2: Add failing transient + runner tests**

```python
def test_parse_tran_fixture():
    data = se.parse_tran((FIXTURES / "tran_baseline.log").read_text())
    assert len(data["time_s"]) == 5011
    assert data["time_s"][0] == pytest.approx(1e-8)
    assert data["time_s"][-1] == pytest.approx(5e-3)
    assert min(data["vin_v"]) == pytest.approx(-0.01, abs=1e-6)
    assert max(data["vout_v"]) == pytest.approx(0.0175129, abs=1e-6)

def test_tran_metrics_detects_inversion():
    data = se.parse_tran((FIXTURES / "tran_baseline.log").read_text())
    m = se.tran_metrics(data)
    assert m["vin_peak_v"] == pytest.approx(0.01, rel=1e-4)
    assert m["vout_peak_v"] == pytest.approx(0.0175, rel=1e-3)
    assert m["phase_inverted"] is True

def test_run_simulation_raises_when_ngspice_missing(monkeypatch):
    def boom():
        raise se.NgspiceNotFound("ngspice not found")
    monkeypatch.setattr(se, "find_ngspice", boom)
    with pytest.raises(se.NgspiceNotFound):
        se.run_simulation(BASE, "dc")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_spice_engine.py -k "tran or run_simulation" -v`
Expected: FAIL with missing `parse_tran`/`run_simulation`

- [ ] **Step 4: Implement runner and transient parser**

`run_simulation`:
1. `params = validate_simulation_input(params, analysis)`
2. create `instance/sim_runs/<run_id>/`
3. if `analysis == "tran"`: run a `.op` netlist first, parse it, then build `.tran` with `op_result`
4. write `circuit.cir` and `ngspice.log`
5. `subprocess.run([ngspice, "-b", "-o", log_path, netlist_path], cwd=run_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, shell=False)`
6. on nonzero exit or `TimeoutExpired`, raise `SimulationError` with log excerpt
7. check log for `Error`, `fatal`, `singular matrix`, `Timestep too small`; raise `SimulationError`
8. parse according to analysis; if data empty, raise `ParseError`
9. return dict with `analysis`, `engine`, `model`, `run_id`, `run_dir`, `netlist`, `log_excerpt`, `elapsed_ms`, `warnings`, `data`, `metrics`

`parse_tran` parses the `Index time v(vin) v(out)` table. `tran_metrics` returns peak/pp values and `phase_inverted` by comparing `vout` at the index of maximum `|vin|`.

- [ ] **Step 5: Add real integration tests (skip when ngspice absent)**

```python
pytestmark_real = pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")

@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_real_dc_run():
    result = se.run_simulation(BASE, "dc")
    assert result["data"]["ic"] == pytest.approx(1.278e-3, rel=0.05)

@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_real_ac_run():
    result = se.run_simulation(BASE, "ac")
    assert len(result["data"]["frequency_hz"]) == 121
    assert result["metrics"]["gain_db_at_frequency"] == pytest.approx(4.86, abs=0.1)

@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_real_tran_run():
    result = se.run_simulation(BASE, "tran")
    assert len(result["data"]["time_s"]) > 100
    assert result["metrics"]["phase_inverted"] is True
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_spice_engine.py -v`
Expected: PASS (integration tests run against the installed ngspice 47)

- [ ] **Step 7: Commit**

```bash
git add spice_engine.py tests/test_spice_engine.py tests/fixtures/tran_baseline.log
git commit -m "feat: run ngspice and parse transient with .op precharge"
```

---

### Task 5: SVG plots and engineering-unit formatting

**Files:**
- Create: `plots.py`
- Create: `tests/test_plots.py`

**Interfaces:**
- Consumes: parsed dicts from `spice_engine`
- Produces:
  - `format_eng(value: float | None, unit: str) -> str`
  - `bode_svg(ac: dict, width: int = 720, height: int = 440) -> str`
  - `tran_svg(tran: dict, width: int = 720, height: int = 360) -> str`

- [ ] **Step 1: Write failing tests**

```python
from plots import format_eng, bode_svg, tran_svg

def test_format_eng():
    assert format_eng(0.00146, "A") == "1.46 mA"
    assert format_eng(0.010, "V") == "10.0 mV"
    assert format_eng(1000, "Hz") == "1.00 kHz"
    assert format_eng(2200, "Ω") == "2.20 kΩ"
    assert format_eng(-179.87, "°") == "-179.9 °"
    assert format_eng(None, "V") == "—"

def test_bode_svg_contains_axes_and_changes_with_data():
    a = {"frequency_hz": [1, 10, 100], "gain_db": [-10, 0, 5],
         "phase_deg": [-90, -120, -150], "vout_mag": [0.1, 1, 2], "vin_mag": [1, 1, 1]}
    b = {**a, "gain_db": [-20, -10, -5]}
    svg = bode_svg(a)
    assert "<svg" in svg
    assert "Frequency (Hz)" in svg
    assert "Gain (dB)" in svg
    assert "Phase (°)" in svg
    assert bode_svg(a) != bode_svg(b)

def test_tran_svg_contains_two_series_and_units():
    d = {"time_s": [0, 0.001, 0.002], "vin_v": [0, 0.01, 0],
         "vout_v": [0, -0.017, 0]}
    svg = tran_svg(d)
    assert "<svg" in svg
    assert "Vin" in svg and "Vout" in svg
    assert "Time (ms)" in svg
    assert "mV" in svg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_plots.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'plots'`

- [ ] **Step 3: Implement `plots.py`**

- `format_eng`: 3 significant digits, prefixes `p n µ m k M G`, no prefix for `dB` and `°`, `None -> "—"`.
- `bode_svg`: two stacked panels; x = `log10(f)`; magnitude y = dB; phase y = degrees; decade grid; axis labels; legend; path `d` built from actual arrays.
- `tran_svg`: x = time auto-scaled to ms or µs; y = mV; two paths with legend Vin/Vout; axis labels.
- Use CSS palette: `#0c8078` (teal), `#c47a1a` (orange), `#123658` (navy), `#d5e2ec` (grid).
- If arrays are empty, return a small SVG with text `No simulation data`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_plots.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plots.py tests/test_plots.py
git commit -m "feat: add SVG Bode/transient plots and engineering units"
```

---

### Task 6: Flask `/simulate` route, template section, and CSS

**Files:**
- Modify: `app.py`
- Modify: `templates/index.html`
- Modify: `static/style.css`
- Create: `tests/test_simulation_routes.py`

**Interfaces:**
- Consumes: `spice_engine.run_simulation`, `spice_engine.*Error`, `plots.bode_svg`, `plots.tran_svg`, `plots.format_eng`, `bias.calculate_bias`, `reference.calculate_reference`
- Produces:
  - `parse_simulation_form(form) -> dict`
  - `build_dc_comparison(params: dict, spice_dc: dict) -> list[dict]`
  - `POST /simulate`

- [ ] **Step 1: Write failing route tests**

```python
import pytest
from app import app
import spice_engine as se

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def sim_form(**overrides):
    data = {
        "analysis": "dc",
        "s_vcc": "12", "s_r1": "100", "s_r2": "22", "s_rc": "2.2",
        "s_re": "1", "s_rl": "10", "s_cin": "10", "s_cout": "10",
        "s_amp": "10", "s_freq": "1",
        "s_r1_unit": "k", "s_r2_unit": "k", "s_rc_unit": "k",
        "s_re_unit": "k", "s_rl_unit": "k", "s_cin_unit": "u",
        "s_cout_unit": "u", "s_amp_unit": "m", "s_freq_unit": "kHz",
    }
    data.update(overrides)
    return data

def test_get_page_has_simulation_section(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"SPICE Simulation" in response.data
    assert b"Run ngspice" in response.data

def test_simulate_rejects_zero_re(client):
    response = client.post("/simulate", data=sim_form(s_re="0"))
    assert response.status_code == 200
    assert "ต้องมากกว่า 0".encode() in response.data
    assert b"SPICE RESULT" not in response.data

def test_simulate_shows_engine_error_without_stale_result(client, monkeypatch):
    def boom(params, analysis):
        raise se.SimulationError("ngspice exploded")
    monkeypatch.setattr("app.run_simulation", boom)
    response = client.post("/simulate", data=sim_form())
    assert response.status_code == 200
    assert b"ngspice exploded" in response.data
    assert b"SPICE RESULT" not in response.data

@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_simulate_dc_real(client):
    response = client.post("/simulate", data=sim_form(analysis="dc"))
    assert response.status_code == 200
    assert b"SPICE RESULT" in response.data
    assert b"1.278" in response.data

@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_simulate_ac_real_has_chart(client):
    response = client.post("/simulate", data=sim_form(analysis="ac"))
    assert response.status_code == 200
    assert b"<svg" in response.data
    assert b"Gain (dB)" in response.data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_simulation_routes.py -v`
Expected: FAIL with 404 for `/simulate` / missing template text

- [ ] **Step 3: Implement form parsing and `/simulate` in `app.py`**

Add:
```python
SIM_DEFAULTS = {
    "analysis": "dc", "s_vcc": "12.0",
    "s_r1": "100", "s_r2": "22", "s_rc": "2.2", "s_re": "1.0", "s_rl": "10",
    "s_cin": "10", "s_cout": "10", "s_amp": "10", "s_freq": "1.0",
    "s_r1_unit": "k", "s_r2_unit": "k", "s_rc_unit": "k",
    "s_re_unit": "k", "s_rl_unit": "k",
    "s_cin_unit": "u", "s_cout_unit": "u",
    "s_amp_unit": "m", "s_freq_unit": "kHz",
}
```

`parse_simulation_form`:
- analysis in `dc/ac/tran`
- resistors: value × unit multiplier (`k`=1e3, `M`=1e6) → Ω
- capacitors: `u`=1e-6, `n`=1e-9 → F
- amplitude: `m`=1e-3, `V`=1 → V
- frequency: `Hz`=1, `kHz`=1e3 → Hz
- raise `se.ValidationError` with Thai field-specific messages

`build_dc_comparison` returns rows for `VB, VE, VC, VCE, IC, IB, IE` with `spice`, `analytical`, `delta`, `delta_pct`, `unit` using `bias.calculate_bias(..., 100, 0.7)`.

Route behavior:
- `POST /simulate`: parse, run, build chart (`bode_svg`/`tran_svg`) and `sim_ref` for dc
- On `se.ValidationError`, `se.NgspiceNotFound`, `se.SimulationError`, `se.ParseError`: render with `sim=None`, `sim_error=str(exc)`, preserve submitted `sim_values`, no chart
- Keep existing `index()` and `calculate()` untouched; add `sim=None` defaults to GET/POST `/`

- [ ] **Step 4: Add the SPICE section to `templates/index.html`**

Place after the existing 3-column `lab-grid` and before the A1–A5 section:
- Heading `Lab 04 · SPICE Simulation — CE Voltage Divider Reference`
- Engine/model badge
- Form posting to `/simulate` with analysis selector, circuit params, source params
- `SPICE RESULT` badge and engine status when `sim` exists
- DC: SPICE table + analytical comparison table with `ANALYTICAL REFERENCE` badge
- AC: metric cards + `sim_chart` (Bode SVG)
- Tran: metric cards + `sim_chart` (waveform SVG)
- `<details>` for netlist and log excerpt
- Error alert when `sim_error`

- [ ] **Step 5: Add CSS classes to `static/style.css`**

Add styles for `.sim-card`, `.sim-form-grid`, `.analysis-tabs`, `.metric-grid`, `.metric`, `.badge-spice`, `.badge-analytical`, `.chart`, `.sim-error`, `.compare-table`, `.data-details`; responsive at `max-width: 900px` to one column.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_simulation_routes.py -v`
Expected: PASS (real tests run with ngspice 47)

- [ ] **Step 7: Run the full suite to prove Lab 03 is intact**

Run: `python -m pytest -q`
Expected: all tests pass, including the original 24

- [ ] **Step 8: Commit**

```bash
git add app.py templates/index.html static/style.css tests/test_simulation_routes.py
git commit -m "feat: add /simulate route, SPICE results UI, and plots"
```

---

### Task 7: README, gitignore, and validation document

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: `docs/validation.md`

- [ ] **Step 1: Update `.gitignore`**

Append:
```text
instance/
```

- [ ] **Step 2: Update `README.md`**

Include:
- Lab 04 title and scope
- ngspice 47 install/run instructions (portable path + `NGSPICE_BIN`)
- `python -m flask --app app run --host 127.0.0.1 --port 5000`
- `python -m pytest -v`
- File structure with `spice_engine.py`, `plots.py`, `tests/fixtures/`
- Model assumptions and measurement definitions (`Vin` before CIN, `Vout` after COUT)
- Limitations: one CE voltage divider, AC sweep 1 Hz–1 MHz, generic QEDU model, no emitter bypass
- Provenance: netlist/log under `instance/sim_runs/`

- [ ] **Step 3: Append Lab 04 Browser Acceptance section to `docs/validation.md`**

Add the B1–B8 table with columns `Case | Method | Input | Expected/Reference | Observed | Evidence | Status`. Leave `Observed`/`Status` to be filled after Task 8; do not claim PASS before the browser run.

- [ ] **Step 4: Commit docs**

```bash
git add README.md .gitignore docs/validation.md
git commit -m "docs: add Lab 04 setup, limitations, and validation template"
```

---

### Task 8: Full verification, browser B1–B8, and GitHub push

**Files:**
- Modify: `docs/validation.md`
- Optional: `docs/captures/*.png`

- [ ] **Step 1: Run the full automated suite**

Run: `python -m pytest -q`
Expected: all tests pass; record the count

- [ ] **Step 2: Start Flask**

Run: `python -m flask --app app run --host 127.0.0.1 --port 5000`
Use a background process; verify `GET /` returns 200

- [ ] **Step 3: Load the browser skill, then run B1–B8 on the real page**

For each case: navigate, snapshot, fill exact values, submit, read observed values, compare to independent reference/real ngspice log, record PASS/FAIL/NOT RUN with evidence.
- B1: Fixed / Emitter / Divider regression with Lab 03 values
- B2: DC SPICE baseline; read VB/VE/VC/VCE/IC and engine/model/run status
- B3: Change only RE to 2 kΩ; DC operating point and/or AC gain must change
- B4: AC; Bode axes/labels/units and real data
- B5: Transient at 10 mV peak, 1 kHz; Vin/Vout, time axis, phase inversion
- B6: Change amplitude or frequency; waveform must change
- B7: RE=0 or simulate engine failure; clear error, no stale success
- B8: Desktop (~1280 px) and mobile (~390 px) screenshots; no critical clipping

Capture screenshots into `docs/captures/` if the browser tool supports file output.

- [ ] **Step 4: Update `docs/validation.md` with actual observations**

Record ngspice version, model, run ids, observed values, method, and PASS/FAIL/NOT RUN. Do not claim Playwright MCP if it was not used; use the actual browser tool name.

- [ ] **Step 5: Re-run the full suite after docs changes**

Run: `python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Review the diff and commit**

```bash
git status --short
git diff --stat
git add -A
git commit -m "test: record Lab 04 browser acceptance and verification evidence"
```

- [ ] **Step 7: Push to the Lab 04 repository**

```bash
git remote add lab4 https://github.com/b6610555-jpg/b6610555Lab-04-BJT-Amplifier-Simulator-v1.git
git push -u lab4 main
git ls-remote https://github.com/b6610555-jpg/b6610555Lab-04-BJT-Amplifier-Simulator-v1.git refs/heads/main
```

Expected: remote `refs/heads/main` points to the final local `HEAD`. Record the commit SHA.
