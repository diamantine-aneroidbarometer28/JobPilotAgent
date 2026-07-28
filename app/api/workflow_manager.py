from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.agents.workflow import JobPilotState, build_workflow
from app.agents.writer import EvidenceWriter, OpenAIResponsesBackend
from app.api.workflow_models import EditableClaim, WorkflowRunResponse
from app.exporters import export_tailored_docx
from app.schemas import Claim, EvidenceMap, TailoringRequest, TailoringResult
from app.schemas.models import SupportStatus
from app.services.validator import validate_claim


class WorkflowNotFoundError(KeyError):
    """Raised when a workflow thread has no saved checkpoint."""


class WorkflowStateError(RuntimeError):
    """Raised when an operation is invalid for the current workflow state."""


class WorkflowManager:
    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        export_dir: str | Path = "data/generated",
        use_model: bool | None = None,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.checkpoint_path, check_same_thread=False)
        self._checkpointer = SqliteSaver(self._connection)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS workflow_catalog ("
            "thread_id TEXT PRIMARY KEY, archived INTEGER NOT NULL DEFAULT 0)"
        )
        self._connection.commit()
        model_enabled = bool(os.getenv("OPENAI_API_KEY")) if use_model is None else use_model
        writer = EvidenceWriter(OpenAIResponsesBackend()) if model_enabled else None
        self.graph = build_workflow(self._checkpointer, writer=writer)
        self._lock = RLock()

    @staticmethod
    def _config(thread_id: UUID) -> RunnableConfig:
        return {"configurable": {"thread_id": str(thread_id)}}

    def close(self) -> None:
        self._connection.close()

    def start(
        self, request: TailoringRequest, *, thread_id: UUID | None = None
    ) -> WorkflowRunResponse:
        workflow_id = thread_id or uuid4()
        with self._lock:
            existing = self.graph.get_state(self._config(workflow_id))
            if existing.values:
                raise WorkflowStateError(f"Workflow already exists: {workflow_id}")
            initial_state: JobPilotState = {"request": request.model_dump(mode="json")}
            output = self.graph.invoke(initial_state, config=self._config(workflow_id))
            self._connection.execute(
                "INSERT OR REPLACE INTO workflow_catalog(thread_id, archived) VALUES (?, 0)",
                (str(workflow_id),),
            )
            self._connection.commit()
        return self._response(workflow_id, output)

    def get(self, thread_id: UUID) -> WorkflowRunResponse:
        with self._lock:
            snapshot = self.graph.get_state(self._config(thread_id))
        if not snapshot.values:
            raise WorkflowNotFoundError(str(thread_id))
        values = dict(snapshot.values)
        review = [
            interrupt.value
            for task in snapshot.tasks
            for interrupt in task.interrupts
            if isinstance(interrupt.value, dict)
        ]
        return self._response(thread_id, values, review=review)

    def list_workflows(
        self, *, limit: int = 50, include_archived: bool = False
    ) -> list[WorkflowRunResponse]:
        thread_ids: list[UUID] = []
        seen: set[str] = set()
        with self._lock:
            checkpoints = self._checkpointer.list(None)
            for checkpoint in checkpoints:
                raw_id = str(checkpoint.config.get("configurable", {}).get("thread_id", ""))
                if raw_id and raw_id not in seen:
                    seen.add(raw_id)
                    thread_ids.append(UUID(raw_id))
                    if len(thread_ids) >= limit:
                        break
        workflows = [self.get(thread_id) for thread_id in thread_ids]
        return workflows if include_archived else [item for item in workflows if not item.archived]

    def decide(
        self, thread_id: UUID, *, approved: bool, claims: list[EditableClaim] | None = None
    ) -> WorkflowRunResponse:
        current = self.get(thread_id)
        if current.status != "pending_review":
            raise WorkflowStateError(f"Workflow is not waiting for review: {current.status}")
        config = self._config(thread_id)
        with self._lock:
            if claims is not None:
                snapshot = self.graph.get_state(config)
                mappings = [
                    EvidenceMap.model_validate(item)
                    for item in snapshot.values.get("evidence_map", [])
                ]
                evidence_by_id = {
                    evidence.source_id: evidence
                    for mapping in mappings
                    for evidence in mapping.evidence
                }
                validated: list[Claim] = []
                for edited in claims:
                    evidence = [
                        evidence_by_id[item]
                        for item in edited.evidence_ids
                        if item in evidence_by_id
                    ]
                    if len(evidence) != len(edited.evidence_ids):
                        raise WorkflowStateError("An edited claim references unknown evidence.")
                    claim = validate_claim(edited.text, evidence)
                    if claim.support_status != SupportStatus.SUPPORTED:
                        raise WorkflowStateError(
                            claim.review_reason or "Edited claim is not supported."
                        )
                    validated.append(claim)
                self.graph.update_state(
                    config, {"claims": [claim.model_dump(mode="json") for claim in validated]}
                )
            command: Command[Any] = Command(resume={"approved": approved})
            output = self.graph.invoke(command, config=config)
        return self._response(thread_id, output)

    def clone(self, thread_id: UUID) -> WorkflowRunResponse:
        with self._lock:
            snapshot = self.graph.get_state(self._config(thread_id))
        if not snapshot.values:
            raise WorkflowNotFoundError(str(thread_id))
        request = TailoringRequest.model_validate(snapshot.values["request"])
        return self.start(request)

    def archive(self, thread_id: UUID, *, archived: bool = True) -> WorkflowRunResponse:
        self.get(thread_id)
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO workflow_catalog(thread_id, archived) VALUES (?, ?)",
                (str(thread_id), int(archived)),
            )
            self._connection.commit()
        return self.get(thread_id)

    def _is_archived(self, thread_id: UUID) -> bool:
        row = self._connection.execute(
            "SELECT archived FROM workflow_catalog WHERE thread_id = ?",
            (str(thread_id),),
        ).fetchone()
        return bool(row[0]) if row else False

    def delete(self, thread_id: UUID) -> None:
        self.get(thread_id)
        with self._lock:
            self._checkpointer.delete_thread(str(thread_id))
            self._connection.execute(
                "DELETE FROM workflow_catalog WHERE thread_id = ?", (str(thread_id),)
            )
            self._connection.commit()
        export_path = self.export_dir / f"{thread_id}.docx"
        export_path.unlink(missing_ok=True)

    def export(self, thread_id: UUID) -> Path:
        current = self.get(thread_id)
        if current.status != "completed" or current.result is None:
            raise WorkflowStateError("Only approved, completed workflows can be exported.")
        destination = self.export_dir / f"{thread_id}.docx"
        export_tailored_docx(TailoringResult.model_validate(current.result), destination)
        return destination

    def _response(
        self,
        thread_id: UUID,
        state: dict[str, Any] | JobPilotState,
        *,
        review: list[dict[str, Any]] | None = None,
    ) -> WorkflowRunResponse:
        state_values: dict[str, Any] = dict(state)
        raw_interrupts = state_values.get("__interrupt__", [])
        interrupt_review = [
            item.value for item in raw_interrupts if isinstance(getattr(item, "value", None), dict)
        ]
        approval_status = state_values.get("approval_status")
        if raw_interrupts or review:
            status = "pending_review"
        elif approval_status == "approved":
            status = "completed"
        elif approval_status == "rejected":
            status = "rejected"
        else:
            status = "running"
        return WorkflowRunResponse(
            thread_id=thread_id,
            status=status,
            archived=self._is_archived(thread_id),
            claims=state_values.get("claims", []),
            blocked_claims=state_values.get("blocked_claims", []),
            token_usage=state_values.get("token_usage"),
            review=review or interrupt_review,
            result=state_values.get("result"),
        )
