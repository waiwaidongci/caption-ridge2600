from datetime import datetime
from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
from src.constants.enums import Review, Status
from src.utils.time import now

class Schedule(Base):
    __tablename__ = 'schedules'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    params: Mapped[dict] = mapped_column(JSON)
    recipient: Mapped[str] = mapped_column(String(100))
    next_at: Mapped[datetime] = mapped_column(index=True)
    repeat_daily: Mapped[bool]
    enabled: Mapped[bool] = mapped_column(default=True)
    author: Mapped[str] = mapped_column(String(64))

class Run(Base):
    __tablename__ = 'runs'
    __table_args__ = (UniqueConstraint('schedule_id', 'scheduled_at'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey('schedules.id'))
    scheduled_at: Mapped[datetime | None]
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default=Status.QUEUED, index=True)
    params: Mapped[dict] = mapped_column(JSON)
    snapshot_id: Mapped[int | None]
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))
    export_file: Mapped[str | None] = mapped_column(String(100))
    review: Mapped[str] = mapped_column(String(20), default=Review.PENDING)
    review_note: Mapped[str | None] = mapped_column(String(500))
    decision: Mapped[str | None] = mapped_column(String(120))
    attempt: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[datetime | None]
    author: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=now)
    finished_at: Mapped[datetime | None]

class DayEstimate(Base):
    """排班日开工前估算：算出后不再改写；验算随迟到与更正实耗补齐。"""
    __tablename__ = 'day_estimates'
    __table_args__ = (UniqueConstraint('schedule_day', 'job_id'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_day: Mapped[str] = mapped_column(String(10))
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'))
    record_id: Mapped[int] = mapped_column(ForeignKey('job_records.id'))
    snapshot_id: Mapped[int]
    estimated_minutes: Mapped[float]
    flagged: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=now)
    verify_record_id: Mapped[int | None] = mapped_column(ForeignKey('job_records.id'))
    verify_actual: Mapped[float | None]
    verify_error: Mapped[float | None]
    verified_at: Mapped[datetime | None]

class Delivery(Base):
    __tablename__ = 'deliveries'

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('runs.id'), unique=True)
    recipient: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=now)
