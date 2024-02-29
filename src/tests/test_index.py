from fastapi.testclient import TestClient

from streamingprovider.__main__ import app

client = TestClient(app)


def test_url():
    url = "https://www.werstreamt.es/film/details/46517/"

    response = client.post(
        "/",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"werstreamtesLink": url},
    )

    assert response.status_code == 200
