"""Independent DC bias calculation using KCL at base node + emitter loop.

Solves a 2x2 linear system in (VB, IB) by Cramer's rule — different algebra
from bias.py (Thévenin reduction), same physics. Pure engineering logic,
no Flask imports.
"""


def calculate_reference(VCC, R1, R2, RC, RE, beta, VBE):
    """คำนวณจุดทำงานกระแสตรงด้วย KCL สมการ 2×2 แก้ด้วยกฎคราเมอร์.

    คืนค่าดict พร้อมคีย์เดียวกับ bias.calculate_bias:
    VBB, RB, IB, IC, IE, VE, VC, VCE, region, warnings
    """
    warnings = []

    # KCL at base node:  (VCC - VB)/R1 = VB/R2 + IB
    # Emitter loop:       (VB - VBE)/RE = (beta + 1) * IB
    #
    # Matrix form:
    #   [ R1+R2       R1*R2     ] [VB]   [R2*VCC]
    #   [ 1           -(b+1)*RE ] [IB] = [VBE   ]

    a11 = R1 + R2
    a12 = R1 * R2
    a21 = 1.0
    a22 = -(beta + 1) * RE
    b1 = R2 * VCC
    b2 = VBE

    det = a11 * a22 - a12 * a21  # Cramer's determinant

    det_vb = b1 * a22 - a12 * b2
    det_ib = a11 * b2 - b1 * a21

    VB = det_vb / det
    IB = det_ib / det

    # VBB and RB are Thévenin equivalents at the base (for display only;
    # they are not used to compute IB in this method)
    VBB = VCC * R2 / (R1 + R2)
    RB = R1 * R2 / (R1 + R2)

    # Region detection (same thresholds as bias.py)
    if VBB <= VBE:
        region = "cutoff"
        warnings.append("Cutoff: VBB <= VBE, IB ติดลบ โมเดลใช้ไม่ได้")
    else:
        region = "active"

    IC = beta * IB
    IE = (beta + 1) * IB
    VE = IE * RE
    VC = VCC - IC * RC
    VCE = VC - VE

    if VCE < 0.2:
        region = "saturation"
        warnings.append(
            "Saturation: VCE < 0.2 V, IC จริงต่ำกว่าเพราะจำกัดด้วย β"
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
        "VC": VC,
        "VCE": VCE,
        "region": region,
        "warnings": warnings,
    }
