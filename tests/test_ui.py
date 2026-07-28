from fastapi.testclient import TestClient

from app.api.main import app


def test_ui_and_static_assets_are_served() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        stylesheet = client.get("/static/styles.css")
        script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "Every strong claim starts with" in page.text
    assert stylesheet.status_code == 200
    assert "--green:" in stylesheet.text
    assert script.status_code == 200
    assert 'jsonRequest("/v1/workflows"' in script.text
    assert "/v1/documents/upload" in script.text


def test_document_upload_returns_evidence_document() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/documents/upload",
            files={"files": ("project.md", b"Built a FastAPI service.", "text/markdown")},
        )

    assert response.status_code == 200
    assert response.json()[0]["source_path"] == "project.md"
    assert response.json()[0]["content"] == "Built a FastAPI service."


def test_document_upload_rejects_unsupported_extension() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/documents/upload",
            files={"files": ("project.csv", b"skill,Python", "text/csv")},
        )

    assert response.status_code == 422
    assert "Unsupported document type" in response.json()["detail"]
