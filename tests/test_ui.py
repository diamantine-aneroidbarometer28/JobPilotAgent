from fastapi.testclient import TestClient

from app.api.main import app


def test_ui_and_static_assets_are_served() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        stylesheet = client.get("/static/styles.css")
        script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "Turn project evidence into claims you can defend." in page.text
    assert stylesheet.status_code == 200
    assert "--green:" in stylesheet.text
    assert script.status_code == 200
    assert 'apiRequest("/v1/workflows"' in script.text
