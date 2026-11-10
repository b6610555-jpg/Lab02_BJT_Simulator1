"""DC bias calculation for a Common-Emitter BJT amplifier (Voltage-Divider Bias).

Pure engineering logic — no Flask imports — so it can be tested standalone.

สมการอ้างอิง (ตามเอกสาร Lab 02 ของ ENG29 2121):
    VTH  = VCC × R2 / (R1 + R2)
    RTH  = R1 × R2 / (R1 + R2)
    IB   = (VTH − VBE) / (RTH + (β + 1) × RE)
    IC   = β × IB
    IE   = (β + 1) × IB
    VE   = IE × RE
    VB   = VE + VBE        (= VBE + IB × (RTH + (β+1)×RE) − I_B×RTH, เท่ากับ VBE + VE)
    VC   = VCC − IC × RC
    VCE  = VC − VE
"""


def calculate_bias(VCC, R1, R2, RC, RE, beta, VBE):
    """คำนวณจุดทำงานกระแสตรงของขยาย Common-Emitter แบบ Voltage-Divider Bias.

    คืนค่าดict พร้อมคีย์: VBB, RB, IB, IC, IE, VE, VB, VC, VCE, region, warnings
    หน่วยดิบ: V, Ω, A (เทมเพลตจะแปลงหน่วยแสดงผลเอง)
    """
    warnings = []

    # Thévenin equivalent at the base
    VBB = VCC * R2 / (R1 + R2)
    RB = R1 * R2 / (R1 + R2)

    # Base current — ใช้ (beta + 1) × RE ให้สมการเทียบเท่ากับ KCL ทุกประการ
    IB = (VBB - VBE) / (RB + (beta + 1) * RE)

    # Region detection
    if VBB <= VBE:
        region = "cutoff"
        warnings.append("Cutoff: VBB ≤ VBE, โมเดล Forward-Active ใช้ไม่ได้")
    else:
        region = "active"

    IC = beta * IB
    IE = (beta + 1) * IB
    VE = IE * RE
    VB = VE + VBE
    VC = VCC - IC * RC
    VCE = VC - VE

    if VCE < 0.2:
        region = "saturation"
        warnings.append(
            "Saturation: VCE < 0.2 V, ค่า IC จริงต่ำกว่าที่โมเดลคำนวณเพราะจำกัดด้วย β"
        )

    if VBE < 0.5 or VBE > 0.8:
        warnings.append("VBE ผิดปกติ: ควรอยู่ในช่วง 0.5–0.8 V")

    return {
        "VBB": VBB,
        "RB": RB,
        "IB": IB,
        "IC": IC,
        "IE": IE,
        "VE": VE,
        "VB": VB,
        "VC": VC,
        "VCE": VCE,
        "region": region,
        "warnings": warnings,
    }
