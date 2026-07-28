from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.schemas import (
    ApplicationCreate,
    ApplicationRead,
    TailoringRequest,
    TailoringResult,
)
from app.services.tailoring import tailor
from app.storage.database import create_application, create_db_and_tables, list_applications


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


app = FastAPI(
    title="JobPilot Agent",
    version="0.1.0",
    description="Evidence-grounded job application copilot",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/tailor", response_model=TailoringResult)
def tailor_application(request: TailoringRequest) -> TailoringResult:
    return tailor(request)


@app.post("/v1/applications", response_model=ApplicationRead, status_code=201)
def add_application(request: ApplicationCreate) -> ApplicationRead:
    return create_application(request)


@app.get("/v1/applications", response_model=list[ApplicationRead])
def get_applications() -> list[ApplicationRead]:
    return list_applications()
