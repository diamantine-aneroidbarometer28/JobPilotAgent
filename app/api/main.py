import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.workflow_manager import WorkflowManager
from app.api.workflow_routes import router as workflow_router
from app.schemas import (
    ApplicationCreate,
    ApplicationRead,
    EvidenceDocument,
    TailoringRequest,
    TailoringResult,
)
from app.services.ingestion import UnsupportedDocumentError, load_uploaded_document
from app.services.tailoring import tailor
from app.storage.database import create_application, create_db_and_tables, list_applications

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
MAX_UPLOAD_FILES = 5
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    manager = WorkflowManager(
        os.getenv("JOBPILOT_CHECKPOINT_DB", "workflow_checkpoints.db"),
        export_dir=os.getenv("JOBPILOT_EXPORT_DIR", "data/generated"),
    )
    app.state.workflow_manager = manager
    try:
        yield
    finally:
        manager.close()


app = FastAPI(
    title="JobPilot Agent",
    version="0.4.0",
    description="Evidence-grounded job application copilot",
    lifespan=lifespan,
)
app.include_router(workflow_router)
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
def user_interface() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/documents/upload", response_model=list[EvidenceDocument])
async def upload_documents(
    files: Annotated[
        list[UploadFile],
        File(min_length=1, max_length=MAX_UPLOAD_FILES),
    ],
) -> list[EvidenceDocument]:
    documents: list[EvidenceDocument] = []
    for upload in files:
        try:
            filename = Path(upload.filename or "").name
            if not filename:
                raise HTTPException(status_code=400, detail="Every upload requires a filename.")
            content = await upload.read(MAX_UPLOAD_BYTES + 1)
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"{filename} exceeds the 5 MB upload limit.",
                )
            try:
                documents.append(load_uploaded_document(filename, content))
            except (UnsupportedDocumentError, ValueError) as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await upload.close()
    return documents


@app.post("/v1/tailor", response_model=TailoringResult)
def tailor_application(request: TailoringRequest) -> TailoringResult:
    return tailor(request)


@app.post("/v1/applications", response_model=ApplicationRead, status_code=201)
def add_application(request: ApplicationCreate) -> ApplicationRead:
    return create_application(request)


@app.get("/v1/applications", response_model=list[ApplicationRead])
def get_applications() -> list[ApplicationRead]:
    return list_applications()
