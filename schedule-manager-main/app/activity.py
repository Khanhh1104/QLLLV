from sqlalchemy.orm import Session

from . import models


def record_activity(
    db: Session,
    owner_id: int,
    action: str,
    task=None,
    task_title: str | None = None,
    details: dict | None = None,
):
    """Ghi lịch sử trong cùng transaction với thao tác chính."""
    db.add(
        models.ActivityLog(
            owner_id=owner_id,
            task_id=getattr(task, "id", None),
            action=action,
            task_title=task_title or getattr(task, "title", "Công việc"),
            details=details or {},
        )
    )
