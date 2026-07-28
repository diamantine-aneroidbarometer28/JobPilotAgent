from fastapi.testclient import TestClient

from app.api.main import RATE_BUCKETS, app


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


def test_security_headers_are_present() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_optional_access_token_protects_v1(monkeypatch: object) -> None:
    monkeypatch.setenv("JOBPILOT_ACCESS_TOKEN", "test-secret")  # type: ignore[attr-defined]
    with TestClient(app) as client:
        denied = client.get("/v1/applications")
        allowed = client.get(
            "/v1/applications",
            headers={"X-JobPilot-Token": "test-secret"},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_optional_rate_limit_returns_429(monkeypatch: object) -> None:
    monkeypatch.setenv("JOBPILOT_RATE_LIMIT_PER_MINUTE", "1")  # type: ignore[attr-defined]
    RATE_BUCKETS.clear()
    with TestClient(app) as client:
        first = client.get("/v1/applications")
        limited = client.get("/v1/applications")

    RATE_BUCKETS.clear()
    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
