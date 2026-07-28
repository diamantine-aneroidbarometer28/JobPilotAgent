import logging
import os
import secrets
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.workflow_manager import WorkflowManager
from app.api.workflow_routes import router as workflow_router
from app.schemas import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    EvidenceDocument,
    TailoringRequest,
    TailoringResult,
)
from app.services.ingestion import UnsupportedDocumentError, load_uploaded_document
from app.services.tailoring import tailor
from app.storage.database import (
    ApplicationNotFoundError,
    create_application,
    create_db_and_tables,
    delete_application,
    list_applications,
    update_application,
)

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
LOGGER = logging.getLogger("jobpilot.api")
RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
RATE_LOCK = Lock()
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
    version="0.7.0",
    description="Evidence-grounded job application copilot",
    lifespan=lifespan,
)


@app.middleware("http")
async def operational_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = time.perf_counter()
    if request.url.path.startswith("/v1/"):
        expected_token = os.getenv("JOBPILOT_ACCESS_TOKEN", "")
        supplied_token = request.headers.get("X-JobPilot-Token", "")
        if expected_token and not secrets.compare_digest(expected_token, supplied_token):
            return JSONResponse(status_code=401, content={"detail": "Invalid access token."})
        rate_limit = int(os.getenv("JOBPILOT_RATE_LIMIT_PER_MINUTE", "0"))
        if rate_limit > 0:
            client_key = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with RATE_LOCK:
                bucket = RATE_BUCKETS[client_key]
                while bucket and bucket[0] <= now - 60:
                    bucket.popleft()
                if len(bucket) >= rate_limit:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded."},
                        headers={"Retry-After": "60"},
                    )
                bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    LOGGER.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


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
def get_applications(status: str | None = None) -> list[ApplicationRead]:
    return list_applications(status=status)


@app.patch("/v1/applications/{application_id}", response_model=ApplicationRead)
def edit_application(application_id: int, request: ApplicationUpdate) -> ApplicationRead:
    try:
        return update_application(application_id, request)
    except ApplicationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Application not found.") from error


@app.delete("/v1/applications/{application_id}", status_code=204)
def remove_application(application_id: int) -> Response:
    try:
        delete_application(application_id)
    except ApplicationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Application not found.") from error
    return Response(status_code=204)
