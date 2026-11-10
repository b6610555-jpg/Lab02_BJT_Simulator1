import pytest
from bias import calculate_bias
from reference import calculate_reference


def test_matches_bias_golden():
    b = calculate_bias(12, 47000, 10000, 2200, 470, 150, 0.7)
    r = calculate_reference(12, 47000, 10000, 2200, 470, 150, 0.7)
    assert r["IC"] == pytest.approx(b["IC"], rel=1e-9)
    assert r["VCE"] == pytest.approx(b["VCE"], rel=1e-9)
    assert r["region"] == b["region"]


def test_golden_defaults_values():
    r = calculate_reference(12, 47000, 10000, 2200, 470, 150, 0.7)
    assert r["region"] == "active"
    assert r["VBB"] == pytest.approx(2.1052631578947367, rel=1e-9)
    assert r["RB"] == pytest.approx(8245.61403508772, rel=1e-9)
    assert r["IB"] == pytest.approx(1.77397243587898e-05, rel=1e-9)
    assert r["IC"] == pytest.approx(0.0026609586538184696, rel=1e-9)
    assert r["VCE"] == pytest.approx(4.886902723856055, rel=1e-9)


def test_second_bias_point_values():
    r = calculate_reference(10, 100000, 20000, 1000, 100, 100, 0.7)
    assert r["region"] == "active"
    assert r["VBB"] == pytest.approx(1.6666666666666667, rel=1e-9)
    assert r["RB"] == pytest.approx(16666.666666666668, rel=1e-9)
    assert r["IB"] == pytest.approx(3.61145703611457e-05, rel=1e-9)
    assert r["IC"] == pytest.approx(0.0036114570361145703, rel=1e-9)
    assert r["VCE"] == pytest.approx(6.023785803237858, rel=1e-9)


def test_cutoff_region():
    r = calculate_reference(5, 100000, 10000, 1000, 100, 100, 0.7)
    assert r["region"] == "cutoff"
    assert any("Cutoff" in w for w in r["warnings"])


def test_saturation_region():
    r = calculate_reference(12, 10000, 10000, 10000, 100, 150, 0.7)
    assert r["region"] == "saturation"
    assert any("Saturation" in w for w in r["warnings"])
