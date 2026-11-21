"""青阶讲堂的确定性完工记录和待审工单。"""

from datetime import date, datetime, timedelta


_SERIES = ("城市更新案例", "古籍数字化", "开放课程工作坊", "材料科学午间讲座", "纪录片声音设计")


def demo_rows() -> list[dict]:
    rows = []
    start = date(2026, 10, 26)
    for index in range(30):
        duration = 24 + (index * 19) % 72
        low_confidence = 4 + (index * 7) % 26
        changes = 2 + (index * 13) % 34
        terms = 3 + (index * 17) % 43
        noise = (index * 11) % 9 - 4
        minutes = 7 + 0.52 * duration + 0.84 * low_confidence + 0.36 * changes + 0.65 * terms + noise
        rows.append({
            "job_id": f"QJ-H{index + 1:02d}",
            "job_date": (start + timedelta(days=index // 2)).isoformat(),
            "title": f"{_SERIES[index % len(_SERIES)]} · 第 {index // len(_SERIES) + 1} 场",
            "video_minutes": duration,
            "low_confidence_pct": low_confidence,
            "speaker_changes": changes,
            "term_count": terms,
            "actual_minutes": round(minutes, 2),
        })

    pending = (
        ("2026-11-10", "修复纸张的水分控制", 31, 6, 4, 7),
        ("2026-11-10", "校园口述史访谈", 76, 23, 30, 16),
        ("2026-11-11", "剪辑台上的无障碍叙事", 48, 13, 12, 22),
        ("2026-11-11", "非线性光学与量子测量", 106, 38, 24, 67),
    )
    for index, (day, title, duration, low_confidence, changes, terms) in enumerate(pending, 1):
        rows.append({
            "job_id": f"QJ-N{index:02d}",
            "job_date": day,
            "title": title,
            "video_minutes": duration,
            "low_confidence_pct": low_confidence,
            "speaker_changes": changes,
            "term_count": terms,
            "actual_minutes": None,
        })
    return rows


def _take(rows, job_id, actual):
    row = next(item for item in rows if item["job_id"] == job_id)
    return {**row, "actual_minutes": actual}


def demo_batches() -> list[tuple[str, str, list[dict], datetime]]:
    """演示时间线：班前批次、当晚补录、隔日实耗与更正，按收到时间先后入库。"""
    base = demo_rows()
    late = [_take(base, "QJ-N01", 34.15), _take(base, "QJ-N02", 87.04)]
    corrections = [_take(base, "QJ-N01", 36.5), _take(base, "QJ-N03", 61.5), _take(base, "QJ-N04", 146.23)]
    return [
        ("青阶讲堂字幕工单（11 月 9 日班前到）", "青阶讲堂字幕工时_20261109.csv",
         base, datetime(2026, 11, 9, 20, 0)),
        ("11 月 10 日补录实耗（当晚到）", "青阶讲堂补录_20261110.csv",
         late, datetime(2026, 11, 10, 21, 30)),
        ("11 月 12 日实耗与更正", "青阶讲堂更正_20261112.csv",
         corrections, datetime(2026, 11, 12, 8, 0)),
    ]
