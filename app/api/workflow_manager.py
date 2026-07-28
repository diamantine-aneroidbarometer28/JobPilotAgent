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
from app.api.workflow_models import WorkflowRunResponse
from app.exporters import export_tailored_docx
from app.schemas import TailoringRequest, TailoringResult


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
        self._connection = sqlite3.connect(
            self.checkpoint_path,
            check_same_thread=False,
        )
        self._checkpointer = SqliteSaver(self._connection)
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
        self,
        request: TailoringRequest,
        *,
        thread_id: UUID | None = None,
    ) -> WorkflowRunResponse:
        workflow_id = thread_id or uuid4()
        with self._lock:
            existing = self.graph.get_state(self._config(workflow_id))
            if existing.values:
                raise WorkflowStateError(f"Workflow already exists: {workflow_id}")
            initial_state: JobPilotState = {"request": request.model_dump(mode="json")}
            output = self.graph.invoke(
                initial_state,
                config=self._config(workflow_id),
            )
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

    def decide(self, thread_id: UUID, *, approved: bool) -> WorkflowRunResponse:
        current = self.get(thread_id)
        if current.status != "pending_review":
            raise WorkflowStateError(f"Workflow is not waiting for review: {current.status}")
        with self._lock:
            command: Command[Any] = Command(resume={"approved": approved})
            output = self.graph.invoke(
                command,
                config=self._config(thread_id),
            )
        return self._response(thread_id, output)

    def export(self, thread_id: UUID) -> Path:
        current = self.get(thread_id)
        if current.status != "completed" or current.result is None:
            raise WorkflowStateError("Only approved, completed workflows can be exported.")
        destination = self.export_dir / f"{thread_id}.docx"
        export_tailored_docx(
            TailoringResult.model_validate(current.result),
            destination,
        )
        return destination

    @staticmethod
    def _response(
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
            claims=state_values.get("claims", []),
            blocked_claims=state_values.get("blocked_claims", []),
            token_usage=state_values.get("token_usage"),
            review=review or interrupt_review,
            result=state_values.get("result"),
        )
