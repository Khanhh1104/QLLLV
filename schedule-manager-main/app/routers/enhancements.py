from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..activity import record_activity
from ..database import get_db
from ..reports import build_tasks_pdf
from ..services import check_conflicts, owned, task_data, validate_category
from ..timeutils import aware_utc, naive_utc, utcnow

router = APIRouter(tags=["Tiện ích nâng cao"])


def _save_unique(db, message):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, message)


@router.get("/templates", response_model=list[schemas.TemplateOut])
def list_templates(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.TaskTemplate)
        .filter_by(owner_id=user.id)
        .order_by(models.TaskTemplate.name)
        .all()
    )


@router.post("/templates", response_model=schemas.TemplateOut, status_code=201)
def create_template(
    data: schemas.TemplateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    validate_category(db, user.id, data.category)
    row = models.TaskTemplate(owner_id=user.id, **data.model_dump())
    db.add(row)
    _save_unique(db, "Tên mẫu công việc đã tồn tại")
    db.refresh(row)
    return row


@router.put("/templates/{template_id}", response_model=schemas.TemplateOut)
def update_template(
    template_id: int,
    data: schemas.TemplateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    row = db.query(models.TaskTemplate).filter_by(id=template_id, owner_id=user.id).first()
    if not row:
        raise HTTPException(404, "Không tìm thấy mẫu công việc")
    validate_category(db, user.id, data.category)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    _save_unique(db, "Tên mẫu công việc đã tồn tại")
    db.refresh(row)
    return row


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    row = db.query(models.TaskTemplate).filter_by(id=template_id, owner_id=user.id).first()
    if not row:
        raise HTTPException(404, "Không tìm thấy mẫu công việc")
    db.delete(row)
    db.commit()


@router.get("/saved-filters", response_model=list[schemas.SavedFilterOut])
def list_saved_filters(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.SavedFilter)
        .filter_by(owner_id=user.id)
        .order_by(models.SavedFilter.name)
        .all()
    )


@router.post("/saved-filters", response_model=schemas.SavedFilterOut, status_code=201)
def create_saved_filter(
    data: schemas.SavedFilterIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    allowed = {"keyword", "status", "priority", "category", "date_from", "date_to", "overdue", "sort"}
    clean = {key: value for key, value in data.query.items() if key in allowed and value not in (None, "", False)}
    if len(str(clean)) > 3000:
        raise HTTPException(422, "Bộ lọc quá lớn")
    row = models.SavedFilter(owner_id=user.id, name=data.name, query=clean)
    db.add(row)
    _save_unique(db, "Tên bộ lọc đã tồn tại")
    db.refresh(row)
    return row


@router.delete("/saved-filters/{filter_id}", status_code=204)
def delete_saved_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    row = db.query(models.SavedFilter).filter_by(id=filter_id, owner_id=user.id).first()
    if not row:
        raise HTTPException(404, "Không tìm thấy bộ lọc")
    db.delete(row)
    db.commit()


@router.post("/tasks/{task_id}/duplicate", response_model=schemas.TaskOut, status_code=201)
def duplicate_task(
    task_id: int,
    data: schemas.DuplicateTaskIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    source = owned(db, task_id, user.id)
    values = task_data(source)
    shift = timedelta(days=data.offset_days)
    for field in ("start_time", "end_time", "deadline"):
        if values[field]:
            values[field] += shift
    values["title"] = f"{source.title} (bản sao)"
    values["status"] = models.TaskStatus.todo
    values["checklist"] = [
        {"text": item["text"], "done": False} for item in (source.checklist or [])
    ]
    task = models.Task(**values, owner_id=user.id, recurrence="none")
    check_conflicts(db, user.id, [task], data.allow_overlap)
    db.add(task)
    db.flush()
    record_activity(db, user.id, "duplicated", task, details={"source_id": source.id})
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/reschedule", response_model=schemas.TaskOut)
def reschedule_task(
    task_id: int,
    data: schemas.RescheduleTaskIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id)
    zone = ZoneInfo(task.timezone)
    local_start = aware_utc(task.start_time).astimezone(zone)
    target_local = datetime.combine(data.target_date, local_start.timetz().replace(tzinfo=None), tzinfo=zone)
    target_start = naive_utc(target_local)
    shift = target_start - task.start_time
    candidate = models.Task(**task_data(task), owner_id=user.id)
    candidate.start_time = target_start
    if candidate.end_time:
        candidate.end_time += shift
    if candidate.deadline:
        candidate.deadline += shift
    check_conflicts(db, user.id, [candidate], data.allow_overlap, [task.id])
    task.start_time = candidate.start_time
    task.end_time = candidate.end_time
    task.deadline = candidate.deadline
    task.status = models.TaskStatus.todo
    task.completed_at = None
    record_activity(db, user.id, "rescheduled", task, details={"target_date": data.target_date.isoformat()})
    db.commit()
    db.refresh(task)
    return task


@router.get("/timers/active", response_model=schemas.TaskOut | None)
def active_timer(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.Task)
        .filter_by(owner_id=user.id)
        .filter(models.Task.deleted_at.is_(None), models.Task.timer_started_at.isnot(None))
        .order_by(models.Task.timer_started_at)
        .first()
    )


@router.post("/tasks/{task_id}/timer/start", response_model=schemas.TaskOut)
def start_timer(
    task_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id)
    active = (
        db.query(models.Task)
        .filter_by(owner_id=user.id)
        .filter(models.Task.timer_started_at.isnot(None), models.Task.id != task.id)
        .first()
    )
    if active:
        raise HTTPException(409, f"Đang tính giờ cho: {active.title}")
    if not task.timer_started_at:
        task.timer_started_at = utcnow()
        record_activity(db, user.id, "timer_started", task)
        db.commit()
        db.refresh(task)
    return task


@router.post("/tasks/{task_id}/timer/stop", response_model=schemas.TaskOut)
def stop_timer(
    task_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id)
    if not task.timer_started_at:
        raise HTTPException(409, "Công việc này chưa bắt đầu tính giờ")
    elapsed = max(1, int((utcnow() - task.timer_started_at).total_seconds() // 60))
    task.actual_minutes = (task.actual_minutes or 0) + elapsed
    task.timer_started_at = None
    record_activity(db, user.id, "timer_stopped", task, details={"minutes": elapsed})
    db.commit()
    db.refresh(task)
    return task


@router.get("/activities")
def activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    base = db.query(models.ActivityLog).filter_by(owner_id=user.id)
    total = base.count()
    rows = (
        base.order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [schemas.ActivityOut.model_validate(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/reports/tasks.pdf")
def tasks_pdf(
    date_from: date,
    date_to: date,
    status: models.TaskStatus | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if date_from > date_to or (date_to - date_from).days > 366:
        raise HTTPException(422, "Khoảng báo cáo tối đa 367 ngày")
    zone = ZoneInfo(user.timezone)
    start = naive_utc(datetime.combine(date_from, time.min, tzinfo=zone))
    end = naive_utc(datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone))
    query = db.query(models.Task).filter(
        models.Task.owner_id == user.id,
        models.Task.deleted_at.is_(None),
        models.Task.start_time < end,
        ((models.Task.end_time > start) | (models.Task.end_time.is_(None) & (models.Task.start_time >= start))),
    )
    if status:
        query = query.filter(models.Task.status == status)
    if category:
        query = query.filter(models.Task.category == category)
    rows = query.order_by(models.Task.start_time, models.Task.id).all()
    content = build_tasks_pdf(rows, user, date_from, date_to)
    filename = f"bao-cao-lich-{date_from.isoformat()}-{date_to.isoformat()}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
