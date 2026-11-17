import pytest
from bias import calculate_bias, calculate_fixed_bias, calculate_emitter_bias


def test_golden_lab_defaults():
    """ค่าเริ่มต้นตาม Lab 02: VCC=12, R1=100k, R2=22k, RC=2.2k, RE=1k, beta=100, VBE=0.7

    แบบจำลอง: ดิวิเดอร์ R1-R2 ถือเป็นอุดมคติ (ไม่คิดกระแสเบสที่โหลดดิวิเดอร์)
    """
    result = calculate_bias(12, 100000, 22000, 2200, 1000, 100, 0.7)
    assert result["region"] == "active"
    assert result["VBB"] == pytest.approx(2.1639344262295084, rel=1e-9)
    assert result["RB"] == pytest.approx(18032.786885245903, rel=1e-9)
    assert result["IB"] == pytest.approx(1.4639344262295085e-05, rel=1e-9)
    assert result["IC"] == pytest.approx(0.0014639344262295086, rel=1e-9)
    assert result["IE"] == pytest.approx(0.0014785737704918036, rel=1e-9)
    assert result["VE"] == pytest.approx(1.4785737704918036, rel=1e-9)
    assert result["VB"] == pytest.approx(2.178573770491804, rel=1e-9)
    assert result["VC"] == pytest.approx(8.779344262295082, rel=1e-9)
    assert result["VCE"] == pytest.approx(7.300770491803278, rel=1e-9)


def test_second_bias_point():
    result = calculate_bias(10, 100000, 20000, 1000, 1000, 100, 0.7)
    assert result["region"] == "active"
    assert result["VBB"] == pytest.approx(1.6666666666666667, rel=1e-9)
    assert result["RB"] == pytest.approx(16666.666666666668, rel=1e-9)
    assert result["IB"] == pytest.approx(9.666666666666668e-06, rel=1e-9)
    assert result["IC"] == pytest.approx(0.0009666666666666669, rel=1e-9)
    assert result["IE"] == pytest.approx(0.0009763333333333335, rel=1e-9)
    assert result["VE"] == pytest.approx(0.9763333333333335, rel=1e-9)
    assert result["VB"] == pytest.approx(1.6763333333333335, rel=1e-9)
    assert result["VC"] == pytest.approx(9.033333333333333, rel=1e-9)
    assert result["VCE"] == pytest.approx(8.057, rel=1e-9)


def test_cutoff_region():
    result = calculate_bias(5, 100000, 10000, 1000, 100, 100, 0.7)
    assert result["region"] == "cutoff"
    assert any("Cutoff" in w for w in result["warnings"])


def test_saturation_region():
    result = calculate_bias(12, 10000, 10000, 10000, 100, 150, 0.7)
    assert result["region"] == "saturation"
    assert any("Saturation" in w for w in result["warnings"])


def test_vbe_unusual_warning():
    result = calculate_bias(12, 47000, 10000, 2200, 470, 150, 0.3)
    assert result["region"] == "active"
    assert any("VBE ผิดปกติ" in w for w in result["warnings"])


def test_approximation_ignores_divider_loading():
    """แบบอุดมคติต้องไม่คิด RTH: IB จึงมากกว่าค่าจากการคำนวณแบบเต็ม"""
    approx = calculate_bias(12, 100000, 22000, 2200, 1000, 100, 0.7)
    # IB ของแบบอุดมคติ = (VBB - VBE) / (beta * RE)
    expected_ib = (approx["VBB"] - 0.7) / (100 * 1000)
    assert approx["IB"] == pytest.approx(expected_ib, rel=1e-12)


def test_fixed_bias_golden():
    """Fixed Bias ค่าอ้างอิงคำนวณด้วยมือ (อิสระจากโปรแกรม):
    VCC=12, RB=1MΩ, RC=2.2k, β=100, VBE=0.7
    IB = (12−0.7)/1e6 = 11.3 µA
    IC = 100 × IB = 1.13 mA
    VE = 0, VB = 0.7, VC = 12 − IC×2.2k = 9.514 V, VCE = VC − VE = 9.514 V
    """
    r = calculate_fixed_bias(12, 1_000_000, 2200, 100, 0.7)
    assert r["region"] == "active"
    assert r["IB"] == pytest.approx(11.3e-6, rel=1e-9)
    assert r["IC"] == pytest.approx(1.13e-3, rel=1e-9)
    assert r["VE"] == pytest.approx(0.0, abs=1e-12)
    assert r["VB"] == pytest.approx(0.7, abs=1e-9)
    assert r["VC"] == pytest.approx(9.514, abs=1e-6)
    assert r["VCE"] == pytest.approx(9.514, abs=1e-6)


def test_emitter_bias_golden():
    """Emitter Bias ค่าอ้างอิงคำนวณด้วยมือ (อิสระจากโปรแกรม):
    VCC=12, RB=1MΩ, RE=1kΩ, RC=2.2k, β=100, VBE=0.7
    IB = 11.3 / (1e6 + 101×1000) = 10.2634 µA
    IC = 100 × IB ≈ 1.0263 mA
    VE = IE×RE ≈ 1.0366 V, VB = VE + 0.7 ≈ 1.7366 V
    VC = 12 − IC×2.2k ≈ 9.7421 V, VCE ≈ 8.7054 V
    """
    r = calculate_emitter_bias(12, 1_000_000, 2200, 1000, 100, 0.7)
    assert r["region"] == "active"
    assert r["IB"] == pytest.approx(1.02633969e-5, rel=1e-6)
    assert r["IC"] == pytest.approx(1.02633969e-3, rel=1e-6)
    assert r["VE"] == pytest.approx(1.03660309, abs=1e-4)
    assert r["VB"] == pytest.approx(1.73660309, abs=1e-4)
    assert r["VC"] == pytest.approx(9.74205268, abs=1e-4)
    assert r["VCE"] == pytest.approx(8.70544959, abs=1e-4)


def test_emitter_bias_re_larger_ic_lower():
    """A4 → A3: เพิ่ม RE จาก 1kΩ เป็น 2kΩ ทำให้ IC ต้องลดลง
    (VCE อาจลดหรือเพิ่มก็ได้ ขึ้นอยู่กับแรงดัน drop ที่ R_E มากกว่าที่ประหยัดจาก R_C)"""
    r_a3 = calculate_emitter_bias(12, 1_000_000, 2200, 1000, 100, 0.7)
    r_a4 = calculate_emitter_bias(12, 1_000_000, 2200, 2000, 100, 0.7)
    assert r_a4["IC"] < r_a3["IC"]


def test_fixed_bias_zero_rb_rejected():
    """RB = 0 ต้องไม่คำนวณ (region cutoff / ค่าผิดปกติ)"""
    r = calculate_fixed_bias(12, 0, 2200, 100, 0.7)
    assert r["region"] == "cutoff"
