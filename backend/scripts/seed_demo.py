import json
from sqlalchemy import func, select
from src.config.database import Session
from src.constants.enums import Role
from src.domain.demo import demo_batches
from src.models.identity import User
from src.models.jobs import DayEstimate
from src.models.source import Dataset, JobRecord
from src.services.datasets import save
from src.utils.security import hash_password


def seed():
    with Session.begin() as db:
        for role in Role:
            if not db.get(User, role.value):
                db.add(User(username=role.value, role=role, password_hash=hash_password(f'{role.value}-demo-2611')))
        batches = []
        for name, filename, rows, received in demo_batches():
            item, created = save(db, name, filename, rows, 'seed', received=received)
            batches.append({'id': item.id, 'name': name, 'rows': item.row_count, 'created': created})
        return {'users': db.scalar(select(func.count()).select_from(User)),
                'datasets': db.scalar(select(func.count()).select_from(Dataset)),
                'job_records': db.scalar(select(func.count()).select_from(JobRecord)),
                'day_estimates': db.scalar(select(func.count()).select_from(DayEstimate)),
                'batches': batches}


if __name__ == '__main__':
    print(json.dumps(seed(), ensure_ascii=False))
