from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import connection
from src.controllers.auth import current
from src.models.identity import User
from src.models.jobs import DayEstimate
from src.models.source import Dataset, JobRecord
from src.utils import views

router = APIRouter()


@router.get('/orders/{job_id}')
def trace(job_id: str, db: Session = Depends(connection), actor: User = Depends(current)):
    """每单可查：估算和验算各用了哪份工单记录。"""
    records = db.scalars(select(JobRecord).where(JobRecord.job_id == job_id)
                         .order_by(JobRecord.id)).all()
    estimates = db.scalars(select(DayEstimate).where(DayEstimate.job_id == job_id)
                           .order_by(DayEstimate.schedule_day)).all()
    if not records and not estimates:
        raise HTTPException(404, '找不到该工单的记录')
    datasets = {item.id: item.name for item in db.scalars(select(Dataset))}
    return views.order_trace(job_id, records, estimates, datasets)
