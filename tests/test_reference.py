import pytest
from bias import calculate_bias
from reference import calculate_reference


def test_exact_golden_values():
    """แบบเต็ม: KCL ที่โหนดเบส + ลูปอิเมตเตอร์ แก้ 2×2 ด้วยกฎคราเมอร์ (คิดผลการโหลดดิวิเดอร์)

    ค่าเริ่มต้น Lab 02: VCC=12, R1=100k, R2=22k, RC=2.2k, RE=1k, beta=100, VBE=0.7
    """
    r = calculate_reference(12, 100000, 22000, 2200, 1000, 100, 0.7)
    assert r["region"] == "active"
    assert r["VBB"] == pytest.approx(2.1639344262295084, rel=1e-9)
    assert r["RB"] == pytest.approx(18032.786885245903, rel=1e-9)
    assert r["IB"] == pytest.approx(1.2298581462608456e-05, rel=1e-9)
    assert r["IC"] == pytest.approx(0.0012298581462608456, rel=1e-9)
    assert r["IE"] == pytest.approx(0.001242156727723454, rel=1e-9)
    assert r["VE"] == pytest.approx(1.2421567277234542, rel=1e-9)
    assert r["VB"] == pytest.approx(1.9421567277234542, rel=1e-9)
    assert r["VC"] == pytest.approx(9.29431207822614, rel=1e-9)
    assert r["VCE"] == pytest.approx(8.052155350502685, rel=1e-9)


def test_matches_classic_thevenin_with_rth():
    """KCL 2×2 ต้องตรงกับสูตร Thévenin ที่รวม RTH — ยืนยันว่าสองทางคำนวณถูกต้อง"""
    r = calculate_reference(12, 100000, 22000, 2200, 1000, 100, 0.7)
    VBB = 12 * 22000 / (100000 + 22000)
    RB = 100000 * 22000 / (100000 + 22000)
    assert r["IB"] == pytest.approx((VBB - 0.7) / (RB + 101 * 1000), rel=1e-12)


def test_exact_is_lower_than_approximation():
    """แบบเต็ม (คิดการโหลดดิวิเดอร์) ต้องได้กระแสเบสน้อยกว่าแบบอุดมคติ"""
    approx = calculate_bias(12, 100000, 22000, 2200, 1000, 100, 0.7)
    exact = calculate_reference(12, 100000, 22000, 2200, 1000, 100, 0.7)
    assert exact["IB"] < approx["IB"]
    assert exact["IC"] < approx["IC"]
    assert exact["VCE"] > approx["VCE"]


def test_second_bias_point_values():
    r = calculate_reference(10, 100000, 20000, 1000, 100, 100, 0.7)
    assert r["region"] == "active"
    assert r["VBB"] == pytest.approx(1.6666666666666667, rel=1e-9)
    assert r["RB"] == pytest.approx(16666.666666666668, rel=1e-9)
    assert r["IB"] == pytest.approx(3.61145703611457e-05, rel=1e-9)
    assert r["IC"] == pytest.approx(0.0036114570361145703, rel=1e-9)
    assert r["VE"] == pytest.approx(0.36475716064757163, rel=1e-9)
    assert r["VB"] == pytest.approx(1.0647571606475716, rel=1e-9)
    assert r["VC"] == pytest.approx(6.38854296388543, rel=1e-9)
    assert r["VCE"] == pytest.approx(6.023785803237858, rel=1e-9)


def test_cutoff_region():
    r = calculate_reference(5, 100000, 10000, 1000, 100, 100, 0.7)
    assert r["region"] == "cutoff"
    assert any("Cutoff" in w for w in r["warnings"])


def test_saturation_region():
    r = calculate_reference(12, 10000, 10000, 10000, 100, 150, 0.7)
    assert r["region"] == "saturation"
    assert any("Saturation" in w for w in r["warnings"])
