import os
from datetime import date, datetime

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.schemas import ApplicationCreate, ApplicationRead
from app.schemas.models import utc_now


class ApplicationRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company: str
    role: str
    status: str = "draft"
    next_action: str | None = None
    due_date: date | None = None
    created_at: datetime = Field(default_factory=utc_now)


DATABASE_URL = os.getenv("JOBPILOT_DATABASE_URL", "sqlite:///jobpilot.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def create_application(payload: ApplicationCreate) -> ApplicationRead:
    record = ApplicationRecord(**payload.model_dump())
    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        return ApplicationRead.model_validate(record)


def list_applications() -> list[ApplicationRead]:
    with Session(engine) as session:
        records = session.exec(select(ApplicationRecord)).all()
        ordered_records = sorted(records, key=lambda record: record.created_at)
        return [ApplicationRead.model_validate(record) for record in ordered_records]
