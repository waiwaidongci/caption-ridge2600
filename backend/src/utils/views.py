from src.utils.time import iso


def dataset(item):
    return {'id': item.id, 'name': item.name, 'filename': item.filename, 'row_count': item.row_count,
            'checksum': item.checksum, 'author': item.author, 'created_at': iso(item.created_at)}


def run(item, detail=False):
    item_view = {'id': item.id, 'dataset_id': item.dataset_id, 'name': item.name, 'status': item.status,
                 'author': item.author, 'review': item.review, 'decision': item.decision,
                 'created_at': iso(item.created_at), 'finished_at': iso(item.finished_at),
                 'scheduled_at': iso(item.scheduled_at), 'schedule_id': item.schedule_id,
                 'snapshot_id': item.snapshot_id, 'has_export': bool(item.export_file), 'error': item.error}
    if detail:
        item_view.update(params=item.params, result=item.result, review_note=item.review_note)
    return item_view


def schedule(item):
    from src.domain.spec import SPEC
    return {'id': item.id, 'name': item.name, 'dataset_id': item.dataset_id, 'recipient': item.recipient,
            'next_at': iso(item.next_at), 'repeat_daily': item.repeat_daily, 'enabled': item.enabled,
            'next_report_day': item.params.get(SPEC['schedule_date_param']) if item.enabled else None}


def delivery(item):
    return {'id': item.id, 'run_id': item.run_id, 'recipient': item.recipient,
            'state': item.state, 'detail': item.detail, 'created_at': iso(item.created_at)}


def _source_label(record, datasets):
    if record is None:
        return None
    name = datasets.get(record.dataset_id, f'批次#{record.dataset_id}')
    return f'版本#{record.id} · {name} · {iso(record.received_at)[:16].replace("T", " ")} 收到'


def order_trace(job_id, records, estimates, datasets):
    by_id = {record.id: record for record in records}
    return {
        'job_id': job_id,
        'records': [{'id': record.id, 'dataset_id': record.dataset_id,
                     'dataset': datasets.get(record.dataset_id, f'批次#{record.dataset_id}'),
                     'received_at': iso(record.received_at),
                     'job_date': record.payload.get('job_date'), 'title': record.payload.get('title'),
                     'actual_minutes': record.payload.get('actual_minutes')} for record in records],
        'estimates': [{'schedule_day': row.schedule_day, 'run_id': row.run_id,
                       'estimated_minutes': row.estimated_minutes, 'flagged': row.flagged,
                       'reason': row.reason,
                       'estimate_source': _source_label(by_id.get(row.record_id), datasets),
                       'verify_actual': row.verify_actual, 'verify_error': row.verify_error,
                       'verify_source': _source_label(by_id.get(row.verify_record_id), datasets),
                       'verified_at': iso(row.verified_at), 'created_at': iso(row.created_at)}
                      for row in estimates],
    }
