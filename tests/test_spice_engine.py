import math
from pathlib import Path

import pytest

import spice_engine as se

FIXTURES = Path(__file__).parent / "fixtures"

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


def test_parse_op_fixture():
    data = se.parse_op((FIXTURES / "op_baseline.log").read_text())
    assert data["vb"] == pytest.approx(1.949127, abs=1e-5)
    assert data["ve"] == pytest.approx(1.289352, abs=1e-5)
    assert data["vc"] == pytest.approx(9.189633, abs=1e-5)
    assert data["vce"] == pytest.approx(7.900281, abs=1e-5)
    assert data["ic"] == pytest.approx(1.278092e-3, rel=1e-4)
    assert data["ib"] == pytest.approx(1.191812e-5, rel=1e-4)
    assert data["ie"] == pytest.approx(1.29001e-3, rel=1e-4)
    assert data["region"] == "active"


def test_parse_op_rejects_empty_log():
    with pytest.raises(se.ParseError):
        se.parse_op("")


def test_parse_ac_fixture():
    data = se.parse_ac((FIXTURES / "ac_baseline.log").read_text())
    assert len(data["frequency_hz"]) == 121
    assert data["frequency_hz"][0] == pytest.approx(1.0)
    assert data["frequency_hz"][-1] == pytest.approx(1e6)
    assert data["gain_db"][60] == pytest.approx(4.858954, abs=1e-4)
    assert data["phase_deg"][60] == pytest.approx(-179.8686, abs=1e-3)


def test_find_low_cutoff_and_no_high_cutoff():
    data = se.parse_ac((FIXTURES / "ac_baseline.log").read_text())
    assert se.find_cutoff(
        data["frequency_hz"], data["gain_db"], "low"
    ) == pytest.approx(1.82658, rel=1e-3)
    assert se.find_cutoff(data["frequency_hz"], data["gain_db"], "high") is None


def test_interpolate_at_uses_log_frequency():
    data = se.parse_ac((FIXTURES / "ac_baseline.log").read_text())
    assert se.interpolate_at(
        data["frequency_hz"], data["gain_db"], 1000
    ) == pytest.approx(4.858954, abs=1e-4)


def test_parse_tran_fixture():
    data = se.parse_tran((FIXTURES / "tran_baseline.log").read_text())
    assert len(data["time_s"]) == 5011
    assert data["time_s"][0] == pytest.approx(1e-8)
    assert data["time_s"][-1] == pytest.approx(5e-3)
    assert min(data["vin_v"]) == pytest.approx(-0.01, abs=1e-6)
    assert max(data["vout_v"]) == pytest.approx(0.0175129, abs=1e-6)


def test_tran_metrics_detects_inversion():
    data = se.parse_tran((FIXTURES / "tran_baseline.log").read_text())
    m = se.tran_metrics(data)
    assert m["vin_peak_v"] == pytest.approx(0.01, rel=1e-4)
    assert m["vout_peak_v"] == pytest.approx(0.0175, rel=1e-3)
    assert m["phase_inverted"] is True


def test_run_simulation_raises_when_ngspice_missing(monkeypatch):
    def boom():
        raise se.NgspiceNotFound("ngspice not found")

    monkeypatch.setattr(se, "find_ngspice", boom)
    with pytest.raises(se.NgspiceNotFound):
        se.run_simulation(BASE, "dc")


@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_real_dc_run():
    result = se.run_simulation(BASE, "dc")
    assert result["data"]["ic"] == pytest.approx(1.278e-3, rel=0.05)


@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_real_ac_run():
    result = se.run_simulation(BASE, "ac")
    assert len(result["data"]["frequency_hz"]) == 121
    assert result["metrics"]["gain_db_at_frequency"] == pytest.approx(
        4.86, abs=0.1
    )


@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_real_tran_run():
    result = se.run_simulation(BASE, "tran")
    assert len(result["data"]["time_s"]) > 100
    assert result["metrics"]["phase_inverted"] is True
