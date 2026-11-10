"""Flask web app: BJT Common-Emitter DC Bias calculator (ENG29 2121).

เส้นทางเดียวที่ "/" รับฟอร์ม GET/POST ตรวจสอบค่าอินพุต
แล้วคำนวณโดย bias.py (Thévenin) และ reference.py (KCL อิสระ)
แสดงผลข้างกันบนเทมเพลต index.html
"""

from flask import Flask, render_template, request

from bias import calculate_bias
from reference import calculate_reference

app = Flask(__name__)

# ค่าเริ่มต้นของฟอร์ม (เปิดแอปแล้วคำนวณได้เลย)
DEFAULTS = {
    "VCC": "12",
    "R1": "47000",
    "R2": "10000",
    "RC": "2200",
    "RE": "470",
    "beta": "150",
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
        "RB": (b["RB"], r["RB"], abs(b["RB"] - r["RB"]), "Ω"),
        "IB": (ua(b["IB"]), ua(r["IB"]), ua(diff_ic) * 0 + ua(abs(b["IB"] - r["IB"])), "µA"),
        "IC": (ma(b["IC"]), ma(r["IC"]), ma(diff_ic), "mA"),
        "IE": (ma(b["IE"]), ma(r["IE"]), ma(abs(b["IE"] - r["IE"])), "mA"),
        "VE": (b["VE"], r["VE"], abs(b["VE"] - r["VE"]), "V"),
        "VC": (b["VC"], r["VC"], abs(b["VC"] - r["VC"]), "V"),
        "VCE": (b["VCE"], r["VCE"], ma(diff_vce) * 0 + abs(b["VCE"] - r["VCE"]), "V"),
        "region": b["region"],
        "warnings": list(set(b["warnings"] + r["warnings"])),
        "diff_ic_pct": diff_ic_pct,
        "diff_vce_pct": diff_vce_pct,
    }


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

        b = calculate_bias(
            values["VCC"], values["R1"], values["R2"],
            values["RC"], values["RE"], values["beta"], values["VBE"],
        )
        r = calculate_reference(
            values["VCC"], values["R1"], values["R2"],
            values["RC"], values["RE"], values["beta"], values["VBE"],
        )
        results = format_results(b, r)

        return render_template(
            "index.html",
            error=None,
            values=values,
            defaults=DEFAULTS,
            results=results,
        )

    # GET: แสดงฟอร์มพร้อมค่าเริ่มต้นและผลคำนวณเริ่มต้น
    b = calculate_bias(
        float(DEFAULTS["VCC"]), float(DEFAULTS["R1"]), float(DEFAULTS["R2"]),
        float(DEFAULTS["RC"]), float(DEFAULTS["RE"]), float(DEFAULTS["beta"]), float(DEFAULTS["VBE"]),
    )
    r = calculate_reference(
        float(DEFAULTS["VCC"]), float(DEFAULTS["R1"]), float(DEFAULTS["R2"]),
        float(DEFAULTS["RC"]), float(DEFAULTS["RE"]), float(DEFAULTS["beta"]), float(DEFAULTS["VBE"]),
    )
    results = format_results(b, r)

    return render_template(
        "index.html",
        error=None,
        values=DEFAULTS,
        defaults=DEFAULTS,
        results=results,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
