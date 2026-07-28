from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.workflow_manager import (
    WorkflowManager,
    WorkflowNotFoundError,
    WorkflowStateError,
)
from app.api.workflow_models import (
    WorkflowDecision,
    WorkflowRunResponse,
    WorkflowStartRequest,
)
from app.schemas import TailoringRequest

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


def _manager(request: Request) -> WorkflowManager:
    manager = request.app.state.workflow_manager
    if not isinstance(manager, WorkflowManager):
        raise RuntimeError("Workflow manager is not initialized.")
    return manager


def _translate_error(error: Exception) -> HTTPException:
    if isinstance(error, WorkflowNotFoundError):
        return HTTPException(status_code=404, detail="Workflow not found.")
    return HTTPException(status_code=409, detail=str(error))


@router.post("", response_model=WorkflowRunResponse, status_code=201)
def start_workflow(
    payload: WorkflowStartRequest,
    request: Request,
) -> WorkflowRunResponse:
    manager = _manager(request)
    tailoring_request = TailoringRequest.model_validate(payload.model_dump(exclude={"thread_id"}))
    try:
        return manager.start(tailoring_request, thread_id=payload.thread_id)
    except WorkflowStateError as error:
        raise _translate_error(error) from error


@router.get("/{thread_id}", response_model=WorkflowRunResponse)
def get_workflow(thread_id: UUID, request: Request) -> WorkflowRunResponse:
    try:
        return _manager(request).get(thread_id)
    except WorkflowNotFoundError as error:
        raise _translate_error(error) from error


@router.post("/{thread_id}/decision", response_model=WorkflowRunResponse)
def decide_workflow(
    thread_id: UUID,
    payload: WorkflowDecision,
    request: Request,
) -> WorkflowRunResponse:
    try:
        return _manager(request).decide(thread_id, approved=payload.approved)
    except (WorkflowNotFoundError, WorkflowStateError) as error:
        raise _translate_error(error) from error


@router.get("/{thread_id}/export", response_class=FileResponse)
def export_workflow(thread_id: UUID, request: Request) -> FileResponse:
    try:
        path: Path = _manager(request).export(thread_id)
    except (WorkflowNotFoundError, WorkflowStateError) as error:
        raise _translate_error(error) from error
    return FileResponse(
        path,
        media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        filename=f"jobpilot-{thread_id}.docx",
    )
