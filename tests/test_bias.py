import pytest
from bias import calculate_bias


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
