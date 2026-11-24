"""Flask web app: BJT Common-Emitter DC Bias calculator (ENG29 2121).

เส้นทางหลักที่ "/" (GET/POST) รับฟอร์ม ตรวจสอบค่าอินพุต
แล้วคำนวณโดย bias.py (Thévenin / Fixed Bias / Emitter Bias)
แสดงผลข้างกันบนเทมเพลต index.html

หน่วยในฟอร์ม: VCC/VBE เป็น V, R1/R2/RC/RE/RB เป็น kΩ (แปลงเป็น Ω ก่อนคำนวณ)
เส้นทาง "/calculate" (POST) รับ JSON สำหรับเรียกผ่าน HTTP client ทั่วไป
"""

import math

from flask import Flask, render_template, request, jsonify

from bias import calculate_bias, calculate_fixed_bias, calculate_emitter_bias
from reference import calculate_reference
import spice_engine as se
from spice_engine import run_simulation
from plots import bode_svg, tran_svg, bode_placeholder_svg, tran_placeholder_svg, format_eng

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


UNIT_MULTIPLIERS = {"k": 1.0, "M": 1000.0}

# ค่าเริ่มต้นของฟอร์มจำลอง ngspice (Lab 04)
SIM_DEFAULTS = {
    "analysis": "dc",
    "s_vcc": "12.0",
    "s_r1": "100",
    "s_r2": "22",
    "s_rc": "2.2",
    "s_re": "1.0",
    "s_rl": "10",
    "s_cin": "10",
    "s_cout": "10",
    "s_amp": "10",
    "s_freq": "1.0",
    "s_r1_unit": "k",
    "s_r2_unit": "k",
    "s_rc_unit": "k",
    "s_re_unit": "k",
    "s_rl_unit": "k",
    "s_cin_unit": "u",
    "s_cout_unit": "u",
    "s_amp_unit": "m",
    "s_freq_unit": "kHz",
}

SIM_RESISTOR_UNITS = {"k": 1.0e3, "M": 1.0e6, "Ω": 1.0}
SIM_CAP_UNITS = {"u": 1.0e-6, "µ": 1.0e-6, "n": 1.0e-9, "p": 1.0e-12}
SIM_AMP_UNITS = {"m": 1.0e-3, "V": 1.0}
SIM_FREQ_UNITS = {"Hz": 1.0, "kHz": 1.0e3}
SIM_ANALYSES = {"dc": "DC operating point", "ac": "AC sweep", "tran": "Transient"}


def parse_resistor(raw):
    """แปลงค่าตัวต้านทานที่อาจมีตัวต่อ k/K หรือ M/M คืนค่าเป็น kΩ

    รองรับเช่น "1k" → 1 kΩ, "2.2K" → 2.2 kΩ, "1M" → 1000 kΩ, "100" → 100 kΩ
    """
    raw = raw.strip()
    if raw == "":
        return None, "กรุณากรอกค่า"
    multiplier = 1.0
    if raw[-1] in ("k", "K"):
        raw = raw[:-1]
    elif raw[-1] in ("M",):
        multiplier = 1000.0
        raw = raw[:-1]
    try:
        val = float(raw)
    except ValueError:
        return None, "ต้องเป็นตัวเลข"
    if val <= 0:
        return None, "ต้องมากกว่า 0"
    return val * multiplier, None


def validate(form, mode):
    """ตรวจสอบค่าอินพุตจากฟอร์ม คืน (values_dict, error_message_or_None)

    ตรวจเฉพาะฟิลด์ที่โหมดนั้นต้องการเท่านั้น
    ตัวต้านทานรับทั้งการพิมพ์ตัวต่อ k/M ท้ายค่า (เช่น 1k, 1M) และการเลือกหน่วยจาก dropdown
    ค่าที่คืนมายังเป็นหน่วยที่ผู้ใช้กรอก (kΩ สำหรับตัวต้านทาน)
    """
    if mode not in MODES:
        return None, f"โหมดวงจร '{mode}' ไม่รู้จัก กรุณาเลือก Voltage Divider, Fixed Bias หรือ Emitter Bias"

    values = {}
    for field in MODE_FIELDS[mode]:
        raw = form.get(field, "").strip()
        if field in RESISTOR_FIELDS:
            # อ่านหน่วยจาก dropdown (ค่าเริ่มต้น k = kΩ)
            unit_raw = form.get(field + "_unit", "k")
            multiplier = UNIT_MULTIPLIERS.get(unit_raw, 1.0)
            # ยังรองรับการพิมพ์ตัวต่อ k/K/M ท้ายค่าได้ด้วย (จะ override dropdown)
            effective_raw = raw
            if raw and raw[-1] in ("k", "K"):
                effective_raw = raw[:-1]
                multiplier = 1.0
            elif raw and raw[-1] in ("M",):
                effective_raw = raw[:-1]
                multiplier = 1000.0
            if effective_raw == "":
                return None, f"กรุณากรอกค่า {field}"
            try:
                val = float(effective_raw)
            except ValueError:
                return None, f"ค่า {field} ต้องเป็นตัวเลข"
            if val <= 0:
                return None, f"ค่า {field} ต้องมากกว่า 0"
            values[field] = val * multiplier
        else:
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
        "critical": b.get("critical", False),
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


def _parse_positive(form, name, label):
    """Read one positive finite number from the simulator form."""
    raw = form.get(name, "").strip()
    if raw == "":
        raise se.ValidationError(f"กรุณากรอกค่า {label}")
    try:
        value = float(raw)
    except ValueError:
        raise se.ValidationError(f"ค่า {label} ต้องเป็นตัวเลข") from None
    if not math.isfinite(value):
        raise se.ValidationError(f"ค่า {label} ต้องเป็นจำนวนจำกัด")
    if value <= 0:
        raise se.ValidationError(f"ค่า {label} ต้องมากกว่า 0")
    return value


def _parse_unit(form, name, choices, default):
    unit = form.get(name, default)
    if unit not in choices:
        raise se.ValidationError(f"หน่วยของ {name} ไม่ถูกต้อง")
    return choices[unit]


def parse_simulation_form(form):
    """Convert the Lab 04 simulation form into validated SI parameters."""
    analysis = form.get("analysis", "dc")
    if analysis not in SIM_ANALYSES:
        raise se.ValidationError(
            f"analysis ต้องเป็นหนึ่งใน {', '.join(SIM_ANALYSES)}"
        )

    def resistor(field, label):
        return _parse_positive(form, field, label) * _parse_unit(
            form, field + "_unit", SIM_RESISTOR_UNITS, "k"
        )

    def capacitor(field, label):
        return _parse_positive(form, field, label) * _parse_unit(
            form, field + "_unit", SIM_CAP_UNITS, "u"
        )

    params = {
        "vcc_v": _parse_positive(form, "s_vcc", "V_CC"),
        "r1_ohm": resistor("s_r1", "R_1"),
        "r2_ohm": resistor("s_r2", "R_2"),
        "rc_ohm": resistor("s_rc", "R_C"),
        "re_ohm": resistor("s_re", "R_E"),
        "rl_ohm": resistor("s_rl", "R_L"),
        "cin_f": capacitor("s_cin", "C_IN"),
        "cout_f": capacitor("s_cout", "C_OUT"),
        "amplitude_v": _parse_positive(form, "s_amp", "amplitude")
        * _parse_unit(form, "s_amp_unit", SIM_AMP_UNITS, "m"),
        "frequency_hz": _parse_positive(form, "s_freq", "frequency")
        * _parse_unit(form, "s_freq_unit", SIM_FREQ_UNITS, "kHz"),
        "beta": 100.0,
        "vbe": 0.70,
    }

    try:
        return se.validate_simulation_input(params, analysis)
    except se.ValidationError as exc:
        raise se.ValidationError(f"ค่าอินพุตไม่ถูกต้อง: {exc}") from None


def build_dc_comparison(params, spice_dc):
    """Build SPICE-vs-analytical rows for the DC operating point.

    The analytical side is the Lab 03 ideal-divider model
    (:func:`bias.calculate_bias`) using the same component values with
    beta=100 and VBE=0.70.  It is labelled separately in the template.
    """
    analytical = calculate_bias(
        params["vcc_v"],
        params["r1_ohm"],
        params["r2_ohm"],
        params["rc_ohm"],
        params["re_ohm"],
        params["beta"],
        params["vbe"],
    )

    specs = [
        ("VB", "V<sub>B</sub>", "V", spice_dc["vb"], analytical["VB"], 3),
        ("VE", "V<sub>E</sub>", "V", spice_dc["ve"], analytical["VE"], 3),
        ("VC", "V<sub>C</sub>", "V", spice_dc["vc"], analytical["VC"], 3),
        ("VCE", "V<sub>CE</sub>", "V", spice_dc["vce"], analytical["VCE"], 3),
        ("IC", "I<sub>C</sub>", "mA", spice_dc["ic"] * 1e3, analytical["IC"] * 1e3, 3),
        ("IB", "I<sub>B</sub>", "µA", spice_dc["ib"] * 1e6, analytical["IB"] * 1e6, 3),
        ("IE", "I<sub>E</sub>", "mA", spice_dc["ie"] * 1e3, analytical["IE"] * 1e3, 3),
    ]

    rows = []
    for key, symbol, unit, spice, reference, decimals in specs:
        delta = spice - reference
        delta_pct = (
            abs(delta) / abs(reference) * 100.0 if reference else None
        )
        rows.append(
            {
                "key": key,
                "symbol": symbol,
                "unit": unit,
                "spice": f"{spice:.{decimals}f} {unit}",
                "analytical": f"{reference:.{decimals}f} {unit}",
                "delta": f"{delta:+.{decimals}f} {unit}",
                "delta_pct": (
                    f"{delta_pct:.2f} %" if delta_pct is not None else "—"
                ),
            }
        )
    return rows


def _format_sim_view(sim):
    """Add display-ready metric rows without changing the parsed values."""
    view = dict(sim)
    analysis = sim["analysis"]
    data = sim["data"]

    if analysis == "dc":
        view["dc_rows"] = [
            ("V<sub>B</sub>", format_eng(data["vb"], "V")),
            ("V<sub>E</sub>", format_eng(data["ve"], "V")),
            ("V<sub>C</sub>", format_eng(data["vc"], "V")),
            ("V<sub>CE</sub>", format_eng(data["vce"], "V")),
            ("I<sub>C</sub>", format_eng(data["ic"], "A")),
            ("I<sub>B</sub>", format_eng(data["ib"], "A")),
            ("I<sub>E</sub>", format_eng(data["ie"], "A")),
        ]
        view["dc_region"] = data["region"]
        view["metrics_rows"] = []
    elif analysis == "ac":
        metrics = sim["metrics"]

        def cutoff(value):
            if value is None:
                return "not determined in sweep range"
            return format_eng(value, "Hz")

        view["dc_rows"] = []
        view["metrics_rows"] = [
            {
                "label": "Gain at source frequency",
                "value": format_eng(
                    metrics["gain_db_at_frequency"], "dB"
                ),
            },
            {
                "label": "Gain (V/V)",
                "value": (
                    f'{metrics["gain_vv_at_frequency"]:.3f} V/V'
                    if metrics["gain_vv_at_frequency"] is not None
                    else "—"
                ),
            },
            {
                "label": "Phase at source frequency",
                "value": format_eng(
                    metrics["phase_deg_at_frequency"], "°"
                ),
            },
            {
                "label": "Midband gain",
                "value": format_eng(metrics["midband_gain_db"], "dB"),
            },
            {
                "label": "Low −3 dB cutoff",
                "value": cutoff(metrics["cutoff_low_hz"]),
            },
            {
                "label": "High −3 dB cutoff",
                "value": cutoff(metrics["cutoff_high_hz"]),
            },
            {
                "label": "Sweep range",
                "value": (
                    f'{format_eng(metrics["sweep_hz"]["min"], "Hz")} – '
                    f'{format_eng(metrics["sweep_hz"]["max"], "Hz")}'
                ),
            },
            {
                "label": "Source frequency",
                "value": format_eng(sim["params"]["frequency_hz"], "Hz"),
            },
        ]
    else:
        metrics = sim["metrics"]
        view["dc_rows"] = []
        view["metrics_rows"] = [
            {
                "label": "Vin peak",
                "value": format_eng(metrics["vin_peak_v"], "V"),
            },
            {
                "label": "Vout peak",
                "value": format_eng(metrics["vout_peak_v"], "V"),
            },
            {
                "label": "Vin peak-to-peak",
                "value": format_eng(metrics["vin_pp_v"], "V"),
            },
            {
                "label": "Vout peak-to-peak",
                "value": format_eng(metrics["vout_pp_v"], "V"),
            },
            {
                "label": "Peak gain",
                "value": (
                    f'{metrics["gain_vv_peak"]:.3f} V/V'
                    if metrics["gain_vv_peak"] is not None
                    else "—"
                ),
            },
            {
                "label": "Phase relation",
                "value": (
                    "inverted (≈180°)" if metrics["phase_inverted"]
                    else "in phase"
                ),
            },
            {
                "label": "Samples",
                "value": f'{metrics["samples"]:,}',
            },
            {
                "label": "Duration",
                "value": format_eng(metrics["duration_s"], "s"),
            },
        ]

    view["analysis_label"] = SIM_ANALYSES[analysis]
    return view


def _default_bias_results():
    defaults_omega = {k: float(v) for k, v in DEFAULTS.items() if k != "mode"}
    return _compute(defaults_omega, DEFAULTS["mode"])


def _sim_template_defaults():
    return {
        "sim": None,
        "sim_error": None,
        "sim_values": SIM_DEFAULTS,
        "sim_chart": bode_placeholder_svg(),
        "sim_ref": None,
    }


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
                **_sim_template_defaults(),
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
            **_sim_template_defaults(),
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
        **_sim_template_defaults(),
    )


@app.route("/simulate", methods=["POST"])
def simulate():
    """Run the real ngspice CE reference simulation and render its output.

    Any validation, engine, or parse failure renders the page with only the
    error message: no ``sim`` object and no stale chart or result is passed.
    """
    submitted = {**SIM_DEFAULTS, **request.form.to_dict()}
    base = {
        "error": None,
        "values": DEFAULTS,
        "results": _default_bias_results(),
        "modes": MODES,
        "mode_fields": MODE_FIELDS[DEFAULTS["mode"]],
        "selected_mode": DEFAULTS["mode"],
        "sim_values": submitted,
    }

    try:
        params = parse_simulation_form(request.form)
        sim = run_simulation(params, params["analysis"])

        chart = None
        if sim["analysis"] == "ac":
            chart = bode_svg(sim["data"])
        elif sim["analysis"] == "tran":
            chart = tran_svg(sim["data"])

        sim_ref = None
        if sim["analysis"] == "dc":
            sim_ref = build_dc_comparison(params, sim["data"])

        view = _format_sim_view(sim)
    except (se.ValidationError, se.NgspiceNotFound, se.SimulationError, se.ParseError) as exc:
        return render_template(
            "index.html",
            sim=None,
            sim_error=str(exc),
            sim_chart=bode_placeholder_svg(),
            sim_ref=None,
            **base,
        )

    return render_template(
        "index.html",
        sim=view,
        sim_error=None,
        sim_chart=chart or bode_placeholder_svg(),
        sim_ref=sim_ref,
        **base,
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
        raw = str(data.get(field, "")).strip()
        if field in RESISTOR_FIELDS:
            unit_raw = str(data.get(field + "_unit", "k"))
            multiplier = UNIT_MULTIPLIERS.get(unit_raw, 1.0)
            if raw and raw[-1] in ("k", "K"):
                raw = raw[:-1]
                multiplier = 1.0
            elif raw and raw[-1] in ("M",):
                raw = raw[:-1]
                multiplier = 1000.0
            if raw == "":
                return jsonify({"error": f"กรุณากรอกค่า {field}"}, 400)
            try:
                val = float(raw)
            except ValueError:
                return jsonify({"error": f"ค่า {field} ต้องเป็นตัวเลข"}, 400)
            if val <= 0:
                return jsonify({"error": f"ค่า {field} ต้องมากกว่า 0"}, 400)
            values[field] = val * multiplier
        else:
            if raw == "":
                return jsonify({"error": f"กรุณากรอกค่า {field}"}, 400)
            try:
                val = float(raw)
            except ValueError:
                return jsonify({"error": f"ค่า {field} ต้องเป็นตัวเลข"}, 400)
            if val <= 0:
                return jsonify({"error": f"ค่า {field} ต้องมากกว่า 0"}, 400)
            values[field] = val
    results = _compute(to_ohms(values), mode)
    if results is None:
        return jsonify({"error": f"โหมดวงจร '{mode}' ไม่รู้จัก"}), 400
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
