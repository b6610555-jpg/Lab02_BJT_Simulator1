"""Flask web app: BJT Common-Emitter DC Bias calculator (ENG29 2121).

เส้นทางหลักที่ "/" (GET/POST) รับฟอร์ม ตรวจสอบค่าอินพุต
แล้วคำนวณโดย bias.py (Thévenin / Fixed Bias / Emitter Bias)
แสดงผลข้างกันบนเทมเพลต index.html

หน่วยในฟอร์ม: VCC/VBE เป็น V, R1/R2/RC/RE/RB เป็น kΩ (แปลงเป็น Ω ก่อนคำนวณ)
เส้นทาง "/calculate" (POST) รับ JSON สำหรับเรียกผ่าน HTTP client ทั่วไป
"""

from flask import Flask, render_template, request, jsonify

from bias import calculate_bias, calculate_fixed_bias, calculate_emitter_bias
from reference import calculate_reference

app = Flask(__name__)

# โหมดวงจรที่รองรับ
MODES = {
    "divider": "Voltage Divider Bias",
    "fixed": "Fixed Bias",
    "emitter": "Emitter Bias",
}

# ค่าเริ่มต้นของฟอร์ม (ตรงกับเอกสาร Lab 02 ของ ENG29 2121) — ตัวต้านทานหน่วย kΩ
DEFAULTS = {
    "VCC": "12.0",
    "R1": "100",
    "R2": "22",
    "RC": "2.2",
    "RE": "1.0",
    "RB": "1000",
    "beta": "100",
    "VBE": "0.70",
    "mode": "divider",
}

# ฟิลด์ร่วมทุกโหมด (กรอกเสมอ)
COMMON_FIELDS = ["VCC", "RC", "beta", "VBE"]

# ฟิลด์เฉพาะแต่ละโหมด (หน่วย kΩ)
MODE_EXTRA_FIELDS = {
    "divider": ["R1", "R2", "RE"],
    "fixed": ["RB"],
    "emitter": ["RB", "RE"],
}

# ฟิลด์ทั้งหมดของแต่ละโหมด
MODE_FIELDS = {
    mode: COMMON_FIELDS + fields
    for mode, fields in MODE_EXTRA_FIELDS.items()
}

# ฟิลด์ที่ผู้ใช้กรอกเป็น kΩ แต่โมเดลคำนวณใช้ Ω
RESISTOR_FIELDS = ["R1", "R2", "RC", "RE", "RB"]


def validate(form, mode):
    """ตรวจสอบค่าอินพุตจากฟอร์ม คืน (values_dict, error_message_or_None)

    ตรวจเฉพาะฟิลด์ที่โหมดนั้นต้องการเท่านั้น
    ค่าที่คืนมายังเป็นหน่วยที่ผู้ใช้กรอก (kΩ สำหรับตัวต้านทาน)
    """
    if mode not in MODES:
        return None, f"โหมดวงจร '{mode}' ไม่รู้จัก กรุณาเลือก Voltage Divider, Fixed Bias หรือ Emitter Bias"

    values = {}
    for field in MODE_FIELDS[mode]:
        raw = form.get(field, "").strip()
        if raw == "":
            return None, f"กรุณากรอกค่า {field}"
        try:
            val = float(raw)
        except ValueError:
            return None, f"ค่า {field} ต้องเป็นตัวเลข"
        if val <= 0:
            return None, f"ค่า {field} ต้องมากกว่า 0"
        values[field] = val
    return values, None


def to_ohms(values):
    """แปลงค่าตัวต้านทานจาก kΩ เป็น Ω ก่อนนำไปคำนวณ"""
    omega = dict(values)
    for field in RESISTOR_FIELDS:
        if field in omega:
            omega[field] = omega[field] * 1000.0
    return omega


def format_divider_results(bias_result, ref_result):
    """แปลงผลคำนวณ Voltage Divider เป็น dict สำหรับส่งให้เทมเพลต

    bias_result = แบบดิวิเดอร์อุดมคติ (ค่าที่แสดงหลัก)
    ref_result  = แบบเต็มที่คิดผลการโหลดดิวิเดอร์ (ใช้ตรวจสอบอิสระ)
    """
    b = bias_result
    r = ref_result

    def ma(a):
        return a * 1000  # A -> mA

    def ua(a):
        return a * 1e6  # A -> µA

    diff_ic = abs(b["IC"] - r["IC"])
    diff_vce = abs(b["VCE"] - r["VCE"])
    diff_ic_pct = (diff_ic / b["IC"] * 100) if b["IC"] != 0 else 0.0
    diff_vce_pct = (diff_vce / b["VCE"] * 100) if b["VCE"] != 0 else 0.0

    return {
        "VBB": (b["VBB"], r["VBB"], abs(b["VBB"] - r["VBB"]), "V"),
        "VB": (b["VB"], r["VB"], abs(b["VB"] - r["VB"]), "V"),
        "RB": (b["RB"], r["RB"], abs(b["RB"] - r["RB"]), "Ω"),
        "IB": (ua(b["IB"]), ua(r["IB"]), ua(abs(b["IB"] - r["IB"])), "µA"),
        "IC": (ma(b["IC"]), ma(r["IC"]), ma(diff_ic), "mA"),
        "IE": (ma(b["IE"]), ma(r["IE"]), ma(abs(b["IE"] - r["IE"])), "mA"),
        "VE": (b["VE"], r["VE"], abs(b["VE"] - r["VE"]), "V"),
        "VC": (b["VC"], r["VC"], abs(b["VC"] - r["VC"]), "V"),
        "VCE": (b["VCE"], r["VCE"], abs(b["VCE"] - r["VCE"]), "V"),
        "region": b["region"],
        "warnings": list(set(b["warnings"] + r["warnings"])),
        "diff_ic_pct": diff_ic_pct,
        "diff_vce_pct": diff_vce_pct,
        # โมเดลหลักที่ใช้แสดงผล และค่าจากการตรวจสอบอิสระ
        "model_note": "ดิวิเดอร์ R₁–R₂ ถือเป็นอุดมคติ (ไม่คิดผลกระแสเบสที่โหลดดิวิเดอร์)",
        "ref_ic_ma": ma(r["IC"]),
        "ref_vce_v": r["VCE"],
        "mode": "divider",
    }


def format_single_results(result, mode):
    """แปลงผลคำนวณ Fixed/Emitter Bias เป็น dict สำหรับส่งให้เทมเพลต

    result = ค่าจาก calculate_fixed_bias หรือ calculate_emitter_bias
    mode   = "fixed" หรือ "emitter"
    """
    b = result

    def ma(a):
        return a * 1000  # A -> mA

    def ua(a):
        return a * 1e6  # A -> µA

    return {
        "VBB": (b["VBB"], None, None, "V"),
        "VB": (b["VB"], None, None, "V"),
        "RB": (b["RB"], None, None, "Ω"),
        "IB": (ua(b["IB"]), None, None, "µA"),
        "IC": (ma(b["IC"]), None, None, "mA"),
        "IE": (ma(b["IE"]), None, None, "mA"),
        "VE": (b["VE"], None, None, "V"),
        "VC": (b["VC"], None, None, "V"),
        "VCE": (b["VCE"], None, None, "V"),
        "region": b["region"],
        "warnings": list(b["warnings"]),
        "diff_ic_pct": 0.0,
        "diff_vce_pct": 0.0,
        "model_note": "แบบจำลอง Forward-Active ประมาณ (คำนวณจากสูตรตำราโดยตรง)",
        "ref_ic_ma": None,
        "ref_vce_v": None,
        "mode": mode,
    }


def _compute(omega, mode):
    """คำนวณจากค่าในหน่วย SI (Ω) ตามโหมดที่เลือก คืนผลลัพธ์สำหรับส่งให้เทมเพลต"""
    if mode == "divider":
        b = calculate_bias(
            omega["VCC"], omega["R1"], omega["R2"],
            omega["RC"], omega["RE"], omega["beta"], omega["VBE"],
        )
        r = calculate_reference(
            omega["VCC"], omega["R1"], omega["R2"],
            omega["RC"], omega["RE"], omega["beta"], omega["VBE"],
        )
        results = format_divider_results(b, r)
    elif mode == "fixed":
        b = calculate_fixed_bias(
            omega["VCC"], omega["RB"], omega["RC"],
            omega["beta"], omega["VBE"],
        )
        results = format_single_results(b, "fixed")
    elif mode == "emitter":
        b = calculate_emitter_bias(
            omega["VCC"], omega["RB"], omega["RC"], omega["RE"],
            omega["beta"], omega["VBE"],
        )
        results = format_single_results(b, "emitter")
    else:
        results = None
    return results


@app.route("/", methods=["GET", "POST"])
def index():
    mode = request.form.get("mode", DEFAULTS["mode"])
    if mode not in MODES:
        mode = DEFAULTS["mode"]

    mode_fields = MODE_FIELDS[mode]

    if request.method == "POST":
        values, error = validate(request.form, mode)
        if error:
            return render_template(
                "index.html",
                error=error,
                values=request.form,
                results=None,
                modes=MODES,
                mode_fields=mode_fields,
                selected_mode=mode,
            )

        results = _compute(to_ohms(values), mode)
        return render_template(
            "index.html",
            error=None,
            values=values,
            results=results,
            modes=MODES,
            mode_fields=mode_fields,
            selected_mode=mode,
        )

    # GET: แสดงฟอร์มพร้อมค่าเริ่มต้นและผลคำนวณเริ่มต้น
    defaults_omega = {k: float(v) for k, v in DEFAULTS.items() if k != "mode"}
    results = _compute(defaults_omega, DEFAULTS["mode"])

    return render_template(
        "index.html",
        error=None,
        values=DEFAULTS,
        results=results,
        modes=MODES,
        mode_fields=MODE_FIELDS[DEFAULTS["mode"]],
        selected_mode=DEFAULTS["mode"],
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    """เส้นทางสำหรับเรียกผ่าน JSON (รองรับ HTTP client ทั่วไป)

    รับตัวต้านทานหน่วย kΩ เหมือนกับหน้าเว็บ พร้อมฟิลด์ mode
    """
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "divider")
    values = {}
    for field in MODE_FIELDS.get(mode, []):
        try:
            val = float(data.get(field, ""))
        except (TypeError, ValueError):
            return jsonify({"error": f"ค่า {field} ต้องเป็นตัวเลข"}), 400
        if val <= 0:
            return jsonify({"error": f"ค่า {field} ต้องมากกว่า 0"}), 400
        values[field] = val

    results = _compute(to_ohms(values), mode)
    if results is None:
        return jsonify({"error": f"โหมดวงจร '{mode}' ไม่รู้จัก"}), 400
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
