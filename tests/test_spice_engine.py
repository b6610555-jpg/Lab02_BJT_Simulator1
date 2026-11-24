import math
from pathlib import Path

import pytest

import spice_engine as se

BASE = {
    "vcc_v": 12.0,
    "r1_ohm": 100_000.0,
    "r2_ohm": 22_000.0,
    "rc_ohm": 2_200.0,
    "re_ohm": 1_000.0,
    "rl_ohm": 10_000.0,
    "cin_f": 10e-6,
    "cout_f": 10e-6,
    "amplitude_v": 0.010,
    "frequency_hz": 1_000.0,
    "beta": 100.0,
    "vbe": 0.70,
}


def test_find_ngspice_from_env(monkeypatch, tmp_path):
    fake = tmp_path / "ngspice_con.exe"
    fake.write_text("")
    monkeypatch.setenv("NGSPICE_BIN", str(fake))
    assert se.find_ngspice() == fake


def test_validate_baseline_converts_to_si():
    p = se.validate_simulation_input(BASE)
    assert p["vcc_v"] == pytest.approx(12.0)
    assert p["r1_ohm"] == pytest.approx(100_000.0)
    assert p["cin_f"] == pytest.approx(10e-6)
    assert p["amplitude_v"] == pytest.approx(0.010)
    assert p["frequency_hz"] == pytest.approx(1_000.0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("vcc_v", 0),
        ("r1_ohm", 0),
        ("re_ohm", -1),
        ("amplitude_v", 0),
        ("frequency_hz", 0),
        ("frequency_hz", 2e6),
        ("cin_f", 0),
        ("beta", 0),
        ("vbe", 2),
    ],
)
def test_validate_rejects_bad_values(field, value):
    with pytest.raises(se.ValidationError):
        se.validate_simulation_input({**BASE, field: value})


def test_validate_rejects_unknown_analysis():
    with pytest.raises(se.ValidationError):
        se.validate_simulation_input(BASE, analysis="fft")


def test_build_netlist_contains_required_elements():
    net = se.build_netlist(BASE, "dc")
    assert "Q1 coll base emit QEDU" in net
    assert ".model QEDU NPN(" in net
    assert ".op" in net
    assert "VIN vin 0 DC 0 AC 1 SIN(0 0.01 1000)" in net
    assert "R1 vcc base 100000" in net
    assert "CIN vin base 1e-05" in net


def test_build_netlist_ac_and_tran_directives():
    assert ".ac dec 20 1 1meg" in se.build_netlist(BASE, "ac")
    tran = se.build_netlist(
        BASE,
        "tran",
        op_result={
            "vb": 1.949127,
            "ve": 1.289352,
            "vc": 9.189633,
            "vout": 0.0,
            "vin": 0.0,
            "vcc": 12.0,
        },
    )
    assert ".tran" in tran and "UIC" in tran
    assert "CIN vin base 1e-05 IC=-1.949127" in tran
    assert "COUT coll out 1e-05 IC=9.189633" in tran
