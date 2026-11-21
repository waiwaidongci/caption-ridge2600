"""启动时幂等执行的结构补齐：新列、历史批次的工单版本回填。"""

import logging
from sqlalchemy import func, inspect, select, text
from src.config.database import Session, engine

log = logging.getLogger(__name__)


def _ensure_columns():
    with engine.begin() as conn:
        columns = {column['name'] for column in inspect(conn).get_columns('runs')}
        if 'snapshot_id' not in columns:
            conn.execute(text('ALTER TABLE runs ADD COLUMN snapshot_id INT NULL'))
            log.info('Added column runs.snapshot_id')


def _backfill_records():
    # 升级前已存在的批次没有工单版本，按批次创建时间补一份，保证旧批次也能重放。
    from src.models.source import Dataset, JobRecord
    with Session.begin() as db:
        datasets = db.scalars(select(Dataset).order_by(Dataset.id)).all()
        missing = [item for item in datasets
                   if not db.scalar(select(func.count(JobRecord.id)).where(JobRecord.dataset_id == item.id))]
        for item in missing:
            for row in item.rows:
                db.add(JobRecord(job_id=row['job_id'], dataset_id=item.id,
                                 received_at=item.created_at, payload=row))
        if missing:
            log.info('Backfilled job records for %s dataset(s)', len(missing))


def migrate():
    _ensure_columns()
    _backfill_records()
