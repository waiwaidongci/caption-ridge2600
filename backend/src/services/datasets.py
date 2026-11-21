import csv
import hashlib
import io
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.domain.demo import demo_rows
from src.domain.spec import SPEC
from src.models.source import Dataset, JobRecord
from src.utils.time import now


def checksum(rows):
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def save(db, name, filename, rows, actor, received=None):
    signature = checksum(rows)
    lookup = select(Dataset).where(Dataset.name == name, Dataset.checksum == signature)
    existing = db.scalar(lookup)
    if existing:
        return existing, False
    stamp = received or now()
    dataset = Dataset(name=name, filename=filename, checksum=signature, rows=rows,
                      row_count=len(rows), author=actor, created_at=stamp)
    try:
        with db.begin_nested():
            db.add(dataset)
            db.flush()
            # 每行按收到时间追加一条不可变工单版本，重放时按版本回查。
            db.add_all([JobRecord(job_id=row['job_id'], dataset_id=dataset.id,
                                  received_at=stamp, payload=row) for row in rows])
            db.flush()
    except IntegrityError:
        existing = db.scalar(lookup.with_for_update())
        if existing:
            return existing, False
        raise
    return dataset, True


def template():
    fields = [field['key'] for field in SPEC['fields']]
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    # The complete representative dataset also works as a reproducible import fixture.
    writer.writerows(demo_rows())
    return '\ufeff' + buffer.getvalue()
