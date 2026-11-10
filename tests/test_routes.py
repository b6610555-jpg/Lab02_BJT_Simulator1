import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_get_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_defaults_in_form(client):
    response = client.get("/")
    assert response.status_code == 200
    # ค่าเริ่มต้นตามเอกสาร Lab 02: R1=100 kΩ, R2=22 kΩ, RC=2.2 kΩ, RE=1.0 kΩ
    assert b'value="12.0"' in response.data   # VCC
    assert b'value="100"' in response.data    # R1 (kΩ)
    assert b'value="22"' in response.data     # R2 (kΩ)
    assert b'value="2.2"' in response.data    # RC (kΩ)
    assert b'value="1.0"' in response.data    # RE (kΩ)


def test_valid_post_shows_results(client):
    response = client.post("/", data={
        "VCC": "12", "R1": "100", "R2": "22",
        "RC": "2.2", "RE": "1.0", "beta": "100", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"active" in response.data.lower()
    assert b"V<sub>B</sub>" in response.data
    assert b"mA" in response.data  # ตารางผลลัพธ์แสดงผลจริง


def test_kohm_units_converted_to_ohm(client):
    """R1=100 kΩ ต้องให้ผลเหมือนคำนวณด้วย 100000 Ω"""
    response = client.post("/", data={
        "VCC": "12", "R1": "100", "R2": "22",
        "RC": "2.2", "RE": "1.0", "beta": "100", "VBE": "0.7"
    })
    assert response.status_code == 200
    # IC = 1.230 mA สำหรับชุดค่าเริ่มต้นของ Lab
    assert b"1.23" in response.data
    assert b"8.05" in response.data  # VCE


def test_invalid_post_shows_error(client):
    response = client.post("/", data={
        "VCC": "abc", "R1": "100", "R2": "22",
        "RC": "2.2", "RE": "1.0", "beta": "100", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_zero_resistance_rejected(client):
    response = client.post("/", data={
        "VCC": "12", "R1": "0", "R2": "22",
        "RC": "2.2", "RE": "1.0", "beta": "100", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_calculate_json_endpoint(client):
    response = client.post("/calculate", json={
        "VCC": 12, "R1": 100, "R2": 22,
        "RC": 2.2, "RE": 1.0, "beta": 100, "VBE": 0.7
    })
    assert response.status_code == 200
    data = response.get_json()
    assert "IC" in data
    assert "VCE" in data
    assert "VB" in data
    assert data["region"] == "active"
