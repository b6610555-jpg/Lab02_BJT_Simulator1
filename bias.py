"""DC bias calculation for a Common-Emitter BJT amplifier (Voltage-Divider Bias).

Pure engineering logic — no Flask imports — so it can be tested standalone.

แบบจำลองหลัก (ตรงกับภาพอ้างอิงของ Lab 02):
    ดิวิเดอร์ R1–R2 ถือเป็นอุดมคติ ไม่คิดผลของกระแสเบสที่ไหลกลับมาโหลดดิวิเดอร์

        VBB = VCC × R2 / (R1 + R2)
        IB  = (VBB − VBE) / (β × RE)
        IC  = β × IB
        IE  = (β + 1) × IB
        VE  = IE × RE
        VB  = VE + VBE
        VC  = VCC − IC × RC
        VCE = VC − VE

สำหรับการตรวจสอบอิสระที่คิดผลของการโหลดดิวิเดอร์ (RTH) ดู reference.py
"""


def calculate_bias(VCC, R1, R2, RC, RE, beta, VBE):
    """คำนวณจุดทำงานกระแสตรงแบบดิวิเดอร์อุดมคติ.

    คืนค่าดict พร้อมคีย์: VBB, RB, IB, IC, IE, VE, VB, VC, VCE, region, warnings
    หน่วยดิบ: V, Ω, A (เทมเพลตจะแปลงหน่วยแสดงผลเอง)
    """
    warnings = []

    # Thévenin voltage at the base (open-circuit divider voltage)
    VBB = VCC * R2 / (R1 + R2)
    RB = R1 * R2 / (R1 + R2)

    # Base current — แบบอุดมคติ: ไม่คิด RTH (กระแสเบสไม่โหลดดิวิเดอร์)
    IB = (VBB - VBE) / (beta * RE)

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
