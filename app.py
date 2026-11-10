"""Flask web app: BJT Common-Emitter DC Bias calculator (ENG29 2121).

เส้นทางหลักที่ "/" (GET/POST) รับฟอร์ม ตรวจสอบค่าอินพุต
แล้วคำนวณโดย bias.py (Thévenin) และ reference.py (KCL อิสระ)
แสดงผลข้างกันบนเทมเพลต index.html

เส้นทาง "/calculate" (POST) รับ JSON สำหรับเรียกผ่าน HTTP client ทั่วไป
"""

from flask import Flask, render_template, request, jsonify

from bias import calculate_bias
from reference import calculate_reference

app = Flask(__name__)

# ค่าเริ่มต้นของฟอร์ม (ตรงกับเอกสาร Lab 02 ของ ENG29 2121)
DEFAULTS = {
    "VCC": "12",
    "R1": "100000",
    "R2": "22000",
    "RC": "2200",
    "RE": "1000",
    "beta": "100",
    "VBE": "0.7",
}

FIELDS = ["VCC", "R1", "R2", "RC", "RE", "beta", "VBE"]


def validate(form):
    """ตรวจสอบค่าอินพุตจากฟอร์ม คืน (values_dict, error_message_or_None)

    valuesdict มีคีย์เป็นชื่อฟิลด์ ค่าเป็น float แปลงแล้ว
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


def _compute(values):
    """คำนวณจาก dict ค่า (float) คืนผลลัพธ์สำหรับส่งให้เทมเพลต"""
    b = calculate_bias(
        values["VCC"], values["R1"], values["R2"],
        values["RC"], values["RE"], values["beta"], values["VBE"],
    )
    r = calculate_reference(
        values["VCC"], values["R1"], values["R2"],
        values["RC"], values["RE"], values["beta"], values["VBE"],
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
                defaults=DEFAULTS,
                results=None,
            )

        results = _compute(values)
        return render_template(
            "index.html",
            error=None,
            values=values,
            defaults=DEFAULTS,
            results=results,
        )

    # GET: แสดงฟอร์มพร้อมค่าเริ่มต้นและผลคำนวณเริ่มต้น
    values = {k: float(v) for k, v in DEFAULTS.items()}
    results = _compute(values)

    return render_template(
        "index.html",
        error=None,
        values=DEFAULTS,
        defaults=DEFAULTS,
        results=results,
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    """เส้นทางสำหรับเรียกผ่าน JSON (รองรับ HTTP client ทั่วไป)"""
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

    results = _compute(values)
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
