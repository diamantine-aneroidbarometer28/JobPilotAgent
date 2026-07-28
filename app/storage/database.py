import os
from datetime import date, datetime

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate
from app.schemas.models import utc_now


class ApplicationNotFoundError(KeyError):
    """Raised when an application record does not exist."""


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
        return ApplicationRead.model_validate(record, from_attributes=True)


def list_applications(*, status: str | None = None) -> list[ApplicationRead]:
    with Session(engine) as session:
        statement = select(ApplicationRecord)
        if status:
            statement = statement.where(ApplicationRecord.status == status)
        records = session.exec(statement).all()
        ordered_records = sorted(records, key=lambda record: record.created_at, reverse=True)
        return [
            ApplicationRead.model_validate(record, from_attributes=True)
            for record in ordered_records
        ]


def update_application(application_id: int, payload: ApplicationUpdate) -> ApplicationRead:
    with Session(engine) as session:
        record = session.get(ApplicationRecord, application_id)
        if record is None:
            raise ApplicationNotFoundError(str(application_id))
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        session.add(record)
        session.commit()
        session.refresh(record)
        return ApplicationRead.model_validate(record, from_attributes=True)


def delete_application(application_id: int) -> None:
    with Session(engine) as session:
        record = session.get(ApplicationRecord, application_id)
        if record is None:
            raise ApplicationNotFoundError(str(application_id))
        session.delete(record)
        session.commit()
