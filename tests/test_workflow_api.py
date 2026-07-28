from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.api.main import app


def _payload() -> dict[str, object]:
    return {
        "job_description": "We require Python and FastAPI experience to build APIs.",
        "documents": [
            {
                "source_id": "project",
                "source_path": "README.md",
                "content": "Built Python FastAPI endpoints with validation.",
            }
        ],
        "language": "en",
    }


def test_workflow_api_approval_and_export(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    # pytest's MonkeyPatch is intentionally left structurally typed for strict app typing.
    setattr_env = monkeypatch.setenv
    setattr_env("JOBPILOT_CHECKPOINT_DB", str(tmp_path / "workflow.db"))
    setattr_env("JOBPILOT_EXPORT_DIR", str(tmp_path / "exports"))

    with TestClient(app) as client:
        started = client.post("/v1/workflows", json=_payload())
        assert started.status_code == 201
        body = started.json()
        assert body["status"] == "pending_review"
        thread_id = body["thread_id"]

        fetched = client.get(f"/v1/workflows/{thread_id}")
        assert fetched.status_code == 200
        assert fetched.json()["review"][0]["type"] == "claim_review"

        approved = client.post(
            f"/v1/workflows/{thread_id}/decision",
            json={"approved": True},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "completed"

        exported = client.get(f"/v1/workflows/{thread_id}/export")
        assert exported.status_code == 200
        assert exported.content.startswith(b"PK")


def test_workflow_api_rejects_duplicate_thread_id(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    setattr_env = monkeypatch.setenv
    setattr_env("JOBPILOT_CHECKPOINT_DB", str(tmp_path / "workflow.db"))
    setattr_env("JOBPILOT_EXPORT_DIR", str(tmp_path / "exports"))
    thread_id = "11111111-1111-4111-8111-111111111111"
    payload = {**_payload(), "thread_id": thread_id}

    with TestClient(app) as client:
        assert client.post("/v1/workflows", json=payload).status_code == 201
        duplicate = client.post("/v1/workflows", json=payload)

    assert duplicate.status_code == 409
