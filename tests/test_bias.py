import pytest
from bias import calculate_bias


def test_golden_defaults():
    result = calculate_bias(12, 47000, 10000, 2200, 470, 150, 0.7)
    assert result["region"] == "active"
    assert result["VBB"] == pytest.approx(2.1052631578947367, rel=1e-9)
    assert result["RB"] == pytest.approx(8245.61403508772, rel=1e-9)
    assert result["IB"] == pytest.approx(1.77397243587898e-05, rel=1e-9)
    assert result["IC"] == pytest.approx(0.0026609586538184696, rel=1e-9)
    assert result["IE"] == pytest.approx(0.0026786983781772597, rel=1e-9)
    assert result["VE"] == pytest.approx(1.2589882377433121, rel=1e-9)
    assert result["VB"] == pytest.approx(1.9589882377433122, rel=1e-9)
    assert result["VC"] == pytest.approx(6.145890961599367, rel=1e-9)
    assert result["VCE"] == pytest.approx(4.886902723856055, rel=1e-9)


def test_second_bias_point():
    result = calculate_bias(10, 100000, 20000, 1000, 100, 100, 0.7)
    assert result["region"] == "active"
    assert result["VBB"] == pytest.approx(1.6666666666666667, rel=1e-9)
    assert result["RB"] == pytest.approx(16666.666666666668, rel=1e-9)
    assert result["IB"] == pytest.approx(3.61145703611457e-05, rel=1e-9)
    assert result["IC"] == pytest.approx(0.0036114570361145703, rel=1e-9)
    assert result["VE"] == pytest.approx(0.36475716064757163, rel=1e-9)
    assert result["VB"] == pytest.approx(1.0647571606475716, rel=1e-9)
    assert result["VC"] == pytest.approx(6.38854296388543, rel=1e-9)
    assert result["VCE"] == pytest.approx(6.023785803237858, rel=1e-9)


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
