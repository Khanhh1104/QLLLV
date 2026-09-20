from datetime import datetime, timedelta
from typing import Optional, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from .. import models, schemas, auth
from ..database import get_db
from ..services import (
    owned,
    recurring_tasks,
    validate_category,
    check_conflicts,
    task_data,
    clear_reminders,
)
from ..timeutils import naive_utc, aware_utc, utcnow

router = APIRouter(prefix="/tasks", tags=["Công việc"])


@router.get("", response_model=schemas.TaskPage)
def list_tasks(
    status_filter: Optional[models.TaskStatus] = Query(None, alias="status"),
    priority: Optional[models.TaskPriority] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    overdue: bool = False,
    unfinished: bool = False,
    due_from: Optional[datetime] = None,
    due_to: Optional[datetime] = None,
    trash: bool = False,
    sort: Literal["start", "deadline", "priority", "newest"] = "start",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Task).filter(models.Task.owner_id == user.id)
    q = q.filter(
        models.Task.deleted_at.isnot(None)
        if trash
        else models.Task.deleted_at.is_(None)
    )
    if status_filter:
        q = q.filter(models.Task.status == status_filter)
    if priority:
        q = q.filter(models.Task.priority == priority)
    if category:
        q = q.filter(models.Task.category == category)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.filter(
            models.Task.title.ilike(f"%{escaped}%", escape="\\")
            | models.Task.description.ilike(f"%{escaped}%", escape="\\")
        )
    if date_from and date_to and naive_utc(date_from) >= naive_utc(date_to):
        raise HTTPException(422, "Khoảng ngày không hợp lệ")
    if date_from:
        q = q.filter(
            (models.Task.end_time > naive_utc(date_from))
            | (
                models.Task.end_time.is_(None)
                & (models.Task.start_time >= naive_utc(date_from))
            )
        )
    if date_to:
        q = q.filter(models.Task.start_time < naive_utc(date_to))
    if overdue:
        q = q.filter(
            func.coalesce(models.Task.deadline, models.Task.end_time) < utcnow(),
            models.Task.status != models.TaskStatus.done,
        )
    if unfinished:
        q = q.filter(models.Task.status != models.TaskStatus.done)
    if due_from:
        q = q.filter(
            func.coalesce(models.Task.deadline, models.Task.end_time)
            >= naive_utc(due_from)
        )
    if due_to:
        q = q.filter(
            func.coalesce(models.Task.deadline, models.Task.end_time)
            < naive_utc(due_to)
        )
    total = q.count()
    order = {
        "start": models.Task.start_time.asc(),
        "deadline": func.coalesce(models.Task.deadline, models.Task.end_time)
        .asc()
        .nullslast(),
        "priority": case(
            (models.Task.priority == models.TaskPriority.high, 0),
            (models.Task.priority == models.TaskPriority.medium, 1),
            else_=2,
        ),
        "newest": models.Task.created_at.desc(),
    }[sort]
    return {
        "items": q.order_by(order, models.Task.start_time, models.Task.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all(),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=schemas.TaskOut, status_code=201)
def create_task(
    data: schemas.TaskCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    validate_category(db, user.id, data.category)
    tasks = recurring_tasks(data, user.id)
    check_conflicts(db, user.id, tasks, data.allow_overlap)
    db.add_all(tasks)
    db.commit()
    db.refresh(tasks[0])
    return tasks[0]


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    return owned(db, task_id, user.id)


@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id)
    updates = data.model_dump(exclude_unset=True, exclude={"scope", "allow_overlap"})
    targets = (
        db.query(models.Task)
        .filter_by(owner_id=user.id, series_id=task.series_id)
        .filter(models.Task.deleted_at.is_(None))
        .all()
        if data.scope == "series" and task.series_id
        else [task]
    )
    base_start = task.start_time
    try:
        zone = ZoneInfo(data.timezone or task.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise HTTPException(422, "Múi giờ không hợp lệ")
    new_start = (
        naive_utc(updates.get("start_time"))
        if updates.get("start_time")
        else base_start
    )
    wall_shift = aware_utc(new_start).astimezone(zone).replace(tzinfo=None) - aware_utc(
        base_start
    ).astimezone(zone).replace(tzinfo=None)
    candidates = []
    for target in targets:
        values = task_data(target)
        values.update(updates)
        if data.scope == "series":
            if "start_time" in updates:
                values["start_time"] = naive_utc(
                    aware_utc(target.start_time).astimezone(zone) + wall_shift
                )
            for field in ["end_time", "deadline"]:
                if field in updates:
                    values[field] = (
                        None
                        if updates[field] is None
                        else values["start_time"]
                        + (naive_utc(updates[field]) - new_start)
                    )
                elif "start_time" in updates and getattr(target, field):
                    values[field] = naive_utc(
                        aware_utc(getattr(target, field)).astimezone(zone) + wall_shift
                    )
        try:
            validated = schemas.TaskBase(**values)
        except (ValidationError, TypeError) as exc:
            raise HTTPException(422, str(exc))
        validate_category(db, user.id, validated.category)
        candidates.append(models.Task(**validated.model_dump(), owner_id=user.id))
    # Chỉ thay nội dung/checklist/ưu tiên không cần xác nhận trùng lại.
    if set(updates) & {"start_time", "end_time", "status"}:
        check_conflicts(
            db, user.id, candidates, data.allow_overlap, [t.id for t in targets]
        )
    for target, candidate in zip(targets, candidates):
        previous_status = target.status
        schedule_changed = any(
            getattr(target, k) != getattr(candidate, k)
            for k in ["start_time", "reminder_minutes"]
        )
        for key, value in task_data(candidate).items():
            setattr(target, key, value)
        if (
            target.status == models.TaskStatus.done
            and previous_status != models.TaskStatus.done
        ):
            target.completed_at = utcnow()
        elif target.status != models.TaskStatus.done:
            target.completed_at = None
        if schedule_changed or target.status == models.TaskStatus.done:
            clear_reminders(db, [target.id])
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    scope: Literal["one", "series"] = "one",
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id)
    targets = (
        db.query(models.Task)
        .filter_by(owner_id=user.id, series_id=task.series_id)
        .filter(models.Task.deleted_at.is_(None))
        .all()
        if scope == "series" and task.series_id
        else [task]
    )
    for target in targets:
        target.deleted_at = utcnow()
    clear_reminders(db, [t.id for t in targets])
    db.commit()


@router.post("/{task_id}/restore", response_model=schemas.TaskOut)
def restore(
    task_id: int,
    allow_overlap: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id, deleted=True)
    check_conflicts(db, user.id, [task], allow_overlap)
    task.deleted_at = None
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}/permanent", status_code=204)
def permanent(
    task_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    task = owned(db, task_id, user.id, deleted=True)
    clear_reminders(db, [task.id])
    db.delete(task)
    db.commit()
