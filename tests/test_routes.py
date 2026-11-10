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
    assert b"100000" in response.data  # R1 default
    assert b"22000" in response.data   # R2 default


def test_valid_post_shows_results(client):
    response = client.post("/", data={
        "VCC": "12", "R1": "100000", "R2": "22000",
        "RC": "2200", "RE": "1000", "beta": "100", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"active" in response.data.lower()
    assert b"VB" in response.data
    assert b"mA" in response.data  # ตารางผลลัพธ์แสดงผลจริง


def test_invalid_post_shows_error(client):
    response = client.post("/", data={
        "VCC": "abc", "R1": "100000", "R2": "22000",
        "RC": "2200", "RE": "1000", "beta": "100", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_calculate_json_endpoint(client):
    response = client.post("/calculate", json={
        "VCC": 12, "R1": 100000, "R2": 22000,
        "RC": 2200, "RE": 1000, "beta": 100, "VBE": 0.7
    })
    assert response.status_code == 200
    data = response.get_json()
    assert "IC" in data
    assert "VCE" in data
    assert "VB" in data
    assert data["region"] == "active"
