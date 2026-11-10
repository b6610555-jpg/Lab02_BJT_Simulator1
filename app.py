"""Flask web app: BJT Common-Emitter DC Bias calculator (ENG29 2121).

เส้นทางหลักที่ "/" (GET/POST) รับฟอร์ม ตรวจสอบค่าอินพุต
แล้วคำนวณโดย bias.py (Thévenin) และ reference.py (KCL อิสระ)
แสดงผลข้างกันบนเทมเพลต index.html

หน่วยในฟอร์ม: VCC/VBE เป็น V, R1/R2/RC/RE เป็น kΩ (แปลงเป็น Ω ก่อนคำนวณ)
เส้นทาง "/calculate" (POST) รับ JSON สำหรับเรียกผ่าน HTTP client ทั่วไป
"""

from flask import Flask, render_template, request, jsonify

from bias import calculate_bias
from reference import calculate_reference

app = Flask(__name__)

# ค่าเริ่มต้นของฟอร์ม (ตรงกับเอกสาร Lab 02 ของ ENG29 2121) — ตัวต้านทานหน่วย kΩ
DEFAULTS = {
    "VCC": "12.0",
    "R1": "100",
    "R2": "22",
    "RC": "2.2",
    "RE": "1.0",
    "beta": "100",
    "VBE": "0.70",
}

FIELDS = ["VCC", "R1", "R2", "RC", "RE", "beta", "VBE"]

# ฟิลด์ที่ผู้ใช้กรอกเป็น kΩ แต่โมเดลคำนวณใช้ Ω
RESISTOR_FIELDS = ["R1", "R2", "RC", "RE"]


def validate(form):
    """ตรวจสอบค่าอินพุตจากฟอร์ม คืน (values_dict, error_message_or_None)

    ค่าที่คืนมายังเป็นหน่วยที่ผู้ใช้กรอก (kΩ สำหรับตัวต้านทาน)
    """
    values = {}
    for field in FIELDS:
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
        omega[field] = omega[field] * 1000.0
    return omega


def format_results(bias_result, ref_result):
    """แปลงผลคำนวณเป็น dict สำหรับส่งให้เทมเพลต แยกคอลัมน์ Thévenin / อิสระ / ความต่าง"""
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
    }


def _compute(omega):
    """คำนวณจากค่าในหน่วย SI (Ω) คืนผลลัพธ์สำหรับส่งให้เทมเพลต"""
    b = calculate_bias(
        omega["VCC"], omega["R1"], omega["R2"],
        omega["RC"], omega["RE"], omega["beta"], omega["VBE"],
    )
    r = calculate_reference(
        omega["VCC"], omega["R1"], omega["R2"],
        omega["RC"], omega["RE"], omega["beta"], omega["VBE"],
    )
    return format_results(b, r)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        values, error = validate(request.form)
        if error:
            return render_template(
                "index.html",
                error=error,
                values=request.form,
                results=None,
            )

        results = _compute(to_ohms(values))
        return render_template(
            "index.html",
            error=None,
            values=values,
            results=results,
        )

    # GET: แสดงฟอร์มพร้อมค่าเริ่มต้นและผลคำนวณเริ่มต้น
    # ส่ง DEFAULTS (สตริง) ไปแสดงผล เพื่อให้ช่องกรอกแสดงตรงกับเอกสารเป๊ะ
    results = _compute(to_ohms({k: float(v) for k, v in DEFAULTS.items()}))

    return render_template(
        "index.html",
        error=None,
        values=DEFAULTS,
        results=results,
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    """เส้นทางสำหรับเรียกผ่าน JSON (รองรับ HTTP client ทั่วไป)

    รับตัวต้านทานหน่วย kΩ เหมือนกับหน้าเว็บ
    """
    data = request.get_json(silent=True) or {}
    values = {}
    for field in FIELDS:
        try:
            val = float(data.get(field, ""))
        except (TypeError, ValueError):
            return jsonify({"error": f"ค่า {field} ต้องเป็นตัวเลข"}), 400
        if val <= 0:
            return jsonify({"error": f"ค่า {field} ต้องมากกว่า 0"}), 400
        values[field] = val

    results = _compute(to_ohms(values))
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
