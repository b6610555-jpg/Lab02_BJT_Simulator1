"""DC bias calculation for a Common-Emitter BJT amplifier (three bias circuits).

Pure engineering logic — no Flask imports — so it can be tested standalone.

รองรับวงจรไบอัสสามแบบ:
  1. Voltage-Divider Bias (เดิมจาก Lab 02): ดิวิเดอร์ R1–R2 ถือเป็นอุดมคติ
  2. Fixed Bias: R_B ต่อจาก VCC ไป Base, Emitter ต่อกราวด์โดยตรง
  3. Emitter Bias (แหล่งจ่ายเดียว): R_B ต่อจาก VCC ไป Base, R_E ต่อจาก Emitter ลงกราวด์

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
    """คำนวณจุดทำงานกระแสตรงแบบดิวิเดอร์อุดมคติ (Voltage-Divider Bias).

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


def calculate_fixed_bias(VCC, RB, RC, beta, VBE):
    """คำนวณจุดทำงานกระแสตรงแบบ Fixed Bias (แหล่งจ่ายเดียว).

    สมการ (ตรงกับใบงาน Lab 03):
        IB = (VCC − VBE) / RB
        IC = β × IB
        IE = (β + 1) × IB
        VE = 0 V (Emitter ต่อกราวด์โดยตรง)
        VB = VE + VBE
        VC = VCC − IC × RC
        VCE = VC − VE

    คืนค่าดict พร้อมคีย์เดียวกับ calculate_bias:
    VBB, RB, IB, IC, IE, VE, VB, VC, VCE, region, warnings
    หน่วยดิบ: V, Ω, A
    """
    warnings = []

    # แรงดันที่ขั้วเบส (สำหรับ Fixed Bias VBB = VB = VBE เพราะ VE = 0)
    VBB = VBE

    # Base current (กันค่า RB = 0 เพื่อไม่ให้เกิด ZeroDivisionError)
    region = "active"
    if RB <= 0:
        region = "cutoff"
        warnings.append("Cutoff: RB ≤ 0, โมเดล Forward-Active ใช้ไม่ได้")
        IB = 0.0
    elif VCC <= VBE:
        region = "cutoff"
        warnings.append("Cutoff: VCC ≤ VBE, โมเดล Forward-Active ใช้ไม่ได้")
        IB = (VCC - VBE) / RB
    else:
        IB = (VCC - VBE) / RB

    IC = beta * IB
    IE = (beta + 1) * IB
    VE = 0.0
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


def calculate_emitter_bias(VCC, RB, RC, RE, beta, VBE):
    """คำนวณจุดทำงานกระแสตรงแบบ Emitter Bias (แหล่งจ่ายเดียว).

    สมการ (ตรงกับใบงาน Lab 03):
        IB = (VCC − VBE) / [RB + (β + 1) × RE]
        IC = β × IB
        IE = (β + 1) × IB
        VE = IE × RE
        VB = VE + VBE
        VC = VCC − IC × RC
        VCE = VC − VE

    คืนค่าดict พร้อมคีย์เดียวกับ calculate_bias:
    VBB, RB, IB, IC, IE, VE, VB, VC, VCE, region, warnings
    หน่วยดิบ: V, Ω, A
    """
    warnings = []

    # แรงดันที่ขั้วเบส (คำนวณทีหลังเมื่อรู้ VE แล้ว)
    VBB = None  # จะกำหนดค่าจริงหลังคำนวณ VB

    # Base current — คำนึงถึง R_E ด้วยตัวคูณ (β + 1) (กันค่า RB = 0)
    region = "active"
    if RB <= 0:
        region = "cutoff"
        warnings.append("Cutoff: RB ≤ 0, โมเดล Forward-Active ใช้ไม่ได้")
        IB = 0.0
    elif VCC <= VBE:
        region = "cutoff"
        warnings.append("Cutoff: VCC ≤ VBE, โมเดล Forward-Active ใช้ไม่ได้")
        IB = (VCC - VBE) / (RB + (beta + 1) * RE)
    else:
        IB = (VCC - VBE) / (RB + (beta + 1) * RE)

    IC = beta * IB
    IE = (beta + 1) * IB
    VE = IE * RE
    VB = VE + VBE
    VBB = VB
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
