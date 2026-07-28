from fastapi.testclient import TestClient

from app.api.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tailor_end_to_end() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/tailor",
            json={
                "job_description": "We require Python and FastAPI experience to build APIs.",
                "documents": [
                    {
                        "source_id": "project",
                        "source_path": "README.md",
                        "content": "Built Python FastAPI endpoints with Pydantic validation.",
                    }
                ],
                "language": "en",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["claims"][0]["evidence_ids"] == ["project#chunk-1"]
