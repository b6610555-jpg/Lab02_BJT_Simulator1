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


def test_valid_post_shows_results(client):
    response = client.post("/", data={
        "VCC": "12", "R1": "47000", "R2": "10000",
        "RC": "2200", "RE": "470", "beta": "150", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"active" in response.data.lower()


def test_invalid_post_shows_error(client):
    response = client.post("/", data={
        "VCC": "abc", "R1": "47000", "R2": "10000",
        "RC": "2200", "RE": "470", "beta": "150", "VBE": "0.7"
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()
