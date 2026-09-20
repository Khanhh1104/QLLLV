import os
import secrets
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .. import models, schemas, auth
from ..database import get_db
from ..reminders import generate, dispatch
from ..timeutils import utcnow

router = APIRouter(tags=["Thông báo"])


@router.get("/notifications")
def notifications(
    page: int = 1,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if page < 1:
        raise HTTPException(422, "Trang không hợp lệ")
    generate(db, user.id)
    base = db.query(models.Notification).filter_by(owner_id=user.id)
    return {
        "items": [
            schemas.NotificationOut.model_validate(n)
            for n in base.order_by(
                models.Notification.created_at.desc(), models.Notification.id.desc()
            )
            .offset((page - 1) * 30)
            .limit(30)
        ],
        "unread": base.filter(models.Notification.read_at.is_(None)).count(),
        "total": base.count(),
        "page": page,
    }


@router.post("/notifications/read-all")
def read_all(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    db.query(models.Notification).filter_by(owner_id=user.id).filter(
        models.Notification.read_at.is_(None)
    ).update({"read_at": utcnow()})
    db.commit()
    return {"message": "Đã đánh dấu tất cả đã đọc"}


@router.post("/notifications/{notice_id}/read")
def read(
    notice_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    row = (
        db.query(models.Notification).filter_by(id=notice_id, owner_id=user.id).first()
    )
    if not row:
        raise HTTPException(404, "Không tìm thấy thông báo")
    row.read_at = utcnow()
    db.commit()
    return {"message": "Đã đọc"}


@router.api_route("/internal/reminders", methods=["GET", "POST"])
def cron(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    secret = os.getenv("CRON_SECRET")
    if (
        not secret
        or not authorization
        or not secrets.compare_digest(authorization, "Bearer " + secret)
    ):
        raise HTTPException(401, "Không được phép")
    return dispatch(db)
