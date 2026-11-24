import pytest

from app import app

import spice_engine as se


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def sim_form(**overrides):
    data = {
        "analysis": "dc",
        "s_vcc": "12",
        "s_r1": "100",
        "s_r2": "22",
        "s_rc": "2.2",
        "s_re": "1",
        "s_rl": "10",
        "s_cin": "10",
        "s_cout": "10",
        "s_amp": "10",
        "s_freq": "1",
        "s_r1_unit": "k",
        "s_r2_unit": "k",
        "s_rc_unit": "k",
        "s_re_unit": "k",
        "s_rl_unit": "k",
        "s_cin_unit": "u",
        "s_cout_unit": "u",
        "s_amp_unit": "m",
        "s_freq_unit": "kHz",
    }
    data.update(overrides)
    return data


def test_get_page_has_simulation_section(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"SPICE Simulation" in response.data
    assert b"Run ngspice" in response.data


def test_simulate_rejects_zero_re(client):
    response = client.post("/simulate", data=sim_form(s_re="0"))
    assert response.status_code == 200
    assert "ต้องมากกว่า 0".encode() in response.data
    assert b"SPICE RESULT" not in response.data


def test_simulate_shows_engine_error_without_stale_result(client, monkeypatch):
    def boom(params, analysis):
        raise se.SimulationError("ngspice exploded")

    monkeypatch.setattr("app.run_simulation", boom)
    response = client.post("/simulate", data=sim_form())
    assert response.status_code == 200
    assert b"ngspice exploded" in response.data
    assert b"SPICE RESULT" not in response.data


@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_simulate_dc_real(client):
    response = client.post("/simulate", data=sim_form(analysis="dc"))
    assert response.status_code == 200
    assert b"SPICE RESULT" in response.data
    assert b"1.278" in response.data


@pytest.mark.skipif(not se.ngspice_available(), reason="ngspice not installed")
def test_simulate_ac_real_has_chart(client):
    response = client.post("/simulate", data=sim_form(analysis="ac"))
    assert response.status_code == 200
    assert b"<svg" in response.data
    assert b"Gain (dB)" in response.data
