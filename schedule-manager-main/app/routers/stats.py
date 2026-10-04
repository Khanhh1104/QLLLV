from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import models, auth
from ..database import get_db
from ..timeutils import utcnow, naive_utc, aware_utc

router = APIRouter(prefix="/stats", tags=["Thống kê"])


@router.get("")
def stats(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    base = (
        db.query(models.Task)
        .filter_by(owner_id=user.id)
        .filter(models.Task.deleted_at.is_(None))
    )
    total = base.count()
    status = {
        s.value: base.filter(models.Task.status == s).count() for s in models.TaskStatus
    }
    overdue = base.filter(
        func.coalesce(models.Task.deadline, models.Task.end_time) < utcnow(),
        models.Task.status != models.TaskStatus.done,
    ).count()
    zone = ZoneInfo(user.timezone)
    today = aware_utc(utcnow()).astimezone(zone).date()
    start = date_from or today - timedelta(days=6)
    end = date_to or today
    if start > end or (end - start).days > 366:
        raise HTTPException(422, "Chọn khoảng ngày từ 1 đến 367 ngày")
    start_utc = naive_utc(datetime.combine(start, time.min, tzinfo=zone))
    end_utc = naive_utc(
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone)
    )
    scheduled = base.filter(
        models.Task.start_time >= start_utc, models.Task.start_time < end_utc
    ).all()
    completed = base.filter(
        models.Task.completed_at >= start_utc,
        models.Task.completed_at < end_utc,
        models.Task.status == models.TaskStatus.done,
    ).all()
    daily = {
        (start + timedelta(days=i)).isoformat(): {"scheduled": 0, "completed": 0}
        for i in range((end - start).days + 1)
    }
    categories = {}
    on_time = 0
    for task in scheduled:
        key = aware_utc(task.start_time).astimezone(zone).date().isoformat()
        daily[key]["scheduled"] += 1
        label = task.category or "Chưa phân loại"
        categories[label] = categories.get(label, 0) + 1
    for task in completed:
        key = aware_utc(task.completed_at).astimezone(zone).date().isoformat()
        daily[key]["completed"] += 1
        due = task.deadline or task.end_time
        if due and task.completed_at <= due:
            on_time += 1
    scheduled_done = sum(t.status == models.TaskStatus.done for t in scheduled)
    return {
        "total": total,
        **status,
        "overdue": overdue,
        "period": {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "scheduled": len(scheduled),
            "scheduled_done": scheduled_done,
            "completed": len(completed),
            "on_time": on_time,
            "completion_rate": (
                round(100 * scheduled_done / len(scheduled), 1) if scheduled else 0
            ),
        },
        "daily": [{"date": k, **v} for k, v in daily.items()],
        "categories": [
            {"name": k, "count": v}
            for k, v in sorted(categories.items(), key=lambda p: -p[1])
        ],
        "legacy_completed_without_date": base.filter(
            models.Task.status == models.TaskStatus.done,
            models.Task.completed_at.is_(None),
        ).count(),
    }
