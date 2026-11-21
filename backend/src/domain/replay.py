"""按排班日重放开工前估算：训练与待审都只用当天以前收到的工单版本。

- 版本库只增不改，运行钉住一个快照高水位，页面与下载看到同一批版本。
- 已算出的排班日估算不再改写；迟到补录与更正实耗在重算时补齐验算。
"""

from datetime import date, datetime, time
from statistics import fmean

from sqlalchemy import func, select

from src.domain.analysis import analyze
from src.models.jobs import DayEstimate
from src.models.source import Dataset, JobRecord
from src.services.validation import normalize_params

MAX_REPLAY_DAYS = 62


def latest_snapshot(db):
    """版本库高水位，一次重算的页面与下载钉在同一批版本上。"""
    return db.scalar(select(func.max(JobRecord.id))) or 0


def _stamp(value):
    return value.strftime('%Y-%m-%d %H:%M')


def _source_label(record, datasets):
    if record is None:
        return '—'
    dataset = datasets.get(record.dataset_id)
    name = dataset.name if dataset else f'批次#{record.dataset_id}'
    return f'版本#{record.id} · {name} · {_stamp(record.received_at)} 收到'


def _table(title, columns, rows):
    return {"title": title, "columns": [{"key": key, "label": label} for key, label in columns], "rows": rows}


def replay(db, params, snapshot_id):
    """重放各排班日开工前的估算，返回 (结果, 新估算, 验算变更)。

    只读取 id <= snapshot_id 的工单版本，并发补录不会混入本次重算。
    """
    params = normalize_params(params)
    versions = db.scalars(
        select(JobRecord).where(JobRecord.id <= snapshot_id)
        .order_by(JobRecord.received_at, JobRecord.id)).all()
    if not versions:
        raise ValueError('版本库还没有工单记录，请先导入数据批次')
    datasets = {item.id: item for item in db.scalars(select(Dataset))}
    existing = {(row.schedule_day, row.job_id): row for row in db.scalars(select(DayEstimate))}

    # 截至快照每单最新一份带实耗的版本：迟到补录与更正实耗都用于补齐验算。
    latest_actual = {}
    for record in versions:
        if record.payload['actual_minutes'] is not None:
            latest_actual[record.job_id] = record

    days = sorted({record.payload['job_date'] for record in versions})
    view, cursor = {}, 0
    summaries, new_estimates = [], []
    attempts = 0
    last_outcome = last_day = None
    for day in days:
        cutoff = datetime.combine(date.fromisoformat(day), time.min)
        while cursor < len(versions) and versions[cursor].received_at < cutoff:
            record = versions[cursor]
            view[record.job_id] = record
            cursor += 1
        pending = [record for record in view.values()
                   if record.payload['actual_minutes'] is None and record.payload['job_date'] >= day]
        if not pending:
            continue
        attempts += 1
        if attempts > MAX_REPLAY_DAYS:
            raise ValueError(f'一次最多重放 {MAX_REPLAY_DAYS} 个排班日，请先对较早批次运行再增量补录')
        try:
            outcome = analyze([record.payload for record in view.values()], params)
        except ValueError as error:
            summaries.append({'schedule_day': day, 'training': '—', 'selection': '—', 'holdout': '—',
                              'group': '—', 'penalty': '—', 'holdout_mae': '—',
                              'pending': len(pending), 'new': 0, 'note': f'数据不足：{error}'})
            continue
        queue = [item for item in outcome['queue'] if item['job_date'] >= day]
        fresh = 0
        for item in queue:
            if (day, item['job_id']) in existing:
                continue  # 旧日估算不变
            record = view[item['job_id']]
            actual = latest_actual.get(item['job_id'])
            new_estimates.append({
                'schedule_day': day, 'job_id': item['job_id'], 'record_id': record.id,
                'estimated_minutes': item['estimated_minutes'], 'flagged': item['flagged'],
                'reason': item['reason'],
                'verify_record_id': actual.id if actual else None,
                'verify_actual': actual.payload['actual_minutes'] if actual else None,
                'verify_error': (round(item['estimated_minutes'] - actual.payload['actual_minutes'], 2)
                                 if actual else None),
            })
            fresh += 1
        stages = {stage['stage']: stage['count'] for stage in outcome['stages']}
        summaries.append({'schedule_day': day, 'training': stages.get('训练', 0),
                          'selection': stages.get('选型', 0), 'holdout': stages.get('留出', 0),
                          'group': outcome['selected']['group'], 'penalty': outcome['selected']['penalty'],
                          'holdout_mae': outcome['holdout_mae'], 'pending': len(queue),
                          'new': fresh, 'note': ''})
        last_outcome, last_day = outcome, day

    # 台账 = 已存量的旧日估算（原样保留）+ 本次新算，验算一律按快照内最新实耗列示。
    by_id = {record.id: record for record in versions}
    fresh = {(item['schedule_day'], item['job_id']): item for item in new_estimates}
    ledger, verify_changes = [], {}
    for day, job_id in sorted(set(existing) | set(fresh)):
        key = (day, job_id)
        actual = latest_actual.get(job_id)
        if key in fresh:
            estimate, origin = fresh[key], '本次新算'
            record_id = estimate['record_id']
        else:
            row = existing[key]
            estimate = {'estimated_minutes': row.estimated_minutes, 'flagged': row.flagged,
                        'reason': row.reason}
            record_id, origin = row.record_id, f'沿用运行#{row.run_id}'
            if actual and row.verify_record_id != actual.id:
                verify_changes[key] = {'verify_record_id': actual.id,
                                       'verify_actual': actual.payload['actual_minutes'],
                                       'verify_error': round(row.estimated_minutes
                                                             - actual.payload['actual_minutes'], 2)}
        source = by_id.get(record_id)
        payload = source.payload if source else {}
        ledger.append({
            'schedule_day': day, 'job_id': job_id,
            'job_date': payload.get('job_date', '—'), 'title': payload.get('title', '—'),
            'estimated_minutes': estimate['estimated_minutes'], 'flagged': estimate['flagged'],
            'reason': estimate['reason'],
            'verify_actual': actual.payload['actual_minutes'] if actual else None,
            'verify_error': (round(estimate['estimated_minutes'] - actual.payload['actual_minutes'], 2)
                             if actual else None),
            'estimate_source': _source_label(source, datasets),
            'verify_source': _source_label(actual, datasets) if actual else '待验算',
            'origin': origin,
        })

    verified = [row for row in ledger if row['verify_actual'] is not None]
    errors = [row['verify_error'] for row in verified]
    mae = round(fmean(abs(error) for error in errors), 4) if errors else None
    bias = round(fmean(errors), 4) if errors else None
    flagged = sum(row['flagged'] == '需核排' for row in ledger)
    success_days = [item for item in summaries if not item['note']]

    day_errors = {}
    for row in verified:
        day_errors.setdefault(row['schedule_day'], []).append(abs(row['verify_error']))
    charts = []
    if day_errors:
        charts.append({'title': '各排班日验算 MAE（分钟）', 'kind': 'bar', 'series': [
            {'label': day, 'value': round(fmean(values), 4)} for day, values in sorted(day_errors.items())]})
    if last_outcome:
        candidate = dict(last_outcome['charts'][0])
        candidate['title'] = f'最近排班日 {last_day} · {candidate["title"]}'
        charts.append(candidate)

    identifiers = (('schedule_day', '排班日'), ('job_id', '工单号'), ('job_date', '工单日期'),
                   ('title', '讲座标题'))
    tables = [
        _table('排班日估算与验算', identifiers + (
            ('estimated_minutes', '估算分钟'), ('flagged', '排班标记'), ('reason', '标记原因'),
            ('verify_actual', '验算实耗'), ('verify_error', '估算减实耗'),
            ('estimate_source', '估算依据'), ('verify_source', '验算依据'), ('origin', '估算来源')), ledger),
        _table('各排班日口径', (('schedule_day', '排班日'), ('training', '训练'), ('selection', '选型'),
                              ('holdout', '留出'), ('group', '入选特征组'), ('penalty', 'λ'),
                              ('holdout_mae', '留出 MAE'), ('pending', '当日待审'), ('new', '本次新算'),
                              ('note', '说明')), summaries),
    ]
    if last_outcome:
        for source in last_outcome['tables']:
            if source['title'] in ('选型集候选比较', '模型系数与特征尺度'):
                tables.append({**source, 'title': f'最近排班日 {last_day} · {source["title"]}'})
    batches = []
    for dataset in sorted(datasets.values(), key=lambda item: item.id):
        records = [record for record in versions if record.dataset_id == dataset.id]
        if records:
            batches.append({'dataset_id': dataset.id, 'name': dataset.name,
                            'received_at': _stamp(records[0].received_at), 'versions': len(records),
                            'actuals': sum(record.payload['actual_minutes'] is not None for record in records)})
    tables.append(_table('导入批次与版本', (('dataset_id', '批次'), ('name', '名称'),
                                          ('received_at', '收到时间'), ('versions', '版本行数'),
                                          ('actuals', '其中含实耗')), batches))

    kept = len(ledger) - len(new_estimates)
    result = {
        'state': 'warning' if flagged else 'ok',
        'headline': (f'重放 {len(success_days)} 个排班日：新估算 {len(new_estimates)} 条、'
                     f'沿用旧估算 {kept} 条，已验算 {len(verified)} 条、待验算 {len(ledger) - len(verified)} 条。'),
        'note': (f'版本快照 #{snapshot_id}（{len(versions)} 份工单版本）。各排班日只用当天以前收到的版本估算；'
                 '旧日估算不改写，验算随迟到与更正实耗补齐。'),
        'snapshot_id': snapshot_id,
        'metrics': [
            {'label': '重放排班日（个）', 'value': len(success_days),
             'detail': f'有待审工单且数据足够的排班日，最多重放 {MAX_REPLAY_DAYS} 个'},
            {'label': '本次新估算（条）', 'value': len(new_estimates), 'detail': '此前没有估算的排班日工单'},
            {'label': '沿用旧估算（条）', 'value': kept, 'detail': '已算出的旧日估算不再改写'},
            {'label': '已验算（条）', 'value': len(verified), 'detail': '快照内已收到实耗（含迟到与更正）'},
            {'label': '待验算（条）', 'value': len(ledger) - len(verified), 'detail': '实耗尚未收到'},
            {'label': '验算 MAE（分钟）', 'value': mae, 'detail': '已验算估算的平均绝对误差'},
            {'label': '验算平均偏差（分钟）', 'value': bias, 'detail': '平均估算减实耗，正值表示总体高估'},
        ],
        'tables': tables,
        'charts': charts,
        'sections': [{
            'title': '时点与验算口径',
            'text': ('每个排班日的估算只使用该日 00:00 前收到的工单版本，排班后才补录的实耗不参与当日的'
                     '训练与估算，避免回测高估当时的估算能力。已算出的排班日估算不再改写；验算使用截至本次'
                     '快照最新一份带实耗的版本，迟到补录与更正实耗都会在重算时补齐。每单的估算依据与验算依据'
                     '可在结果表和工单溯源中回查。'),
        }],
    }
    return result, new_estimates, verify_changes
