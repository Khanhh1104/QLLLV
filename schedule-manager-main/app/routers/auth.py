import hashlib
import os
import secrets
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models, schemas, auth, mailer
from ..database import get_db
from ..timeutils import utcnow

router = APIRouter(prefix="/auth", tags=["Tài khoản"])


def base_url():
    """Địa chỉ gốc dùng trong email khôi phục mật khẩu.

    Trên Vercel, nếu chưa đặt APP_BASE_URL thì lấy domain của deployment.
    """
    configured = (os.getenv("APP_BASE_URL") or "").strip()
    if configured:
        return configured.rstrip("/")
    host = (
        os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL") or ""
    ).strip()
    if host:
        return f"https://{host}".rstrip("/")
    return "http://127.0.0.1:8000"


def limit(db, action, identity, count=8):
    key = hashlib.sha256(f"{action}:{identity}".encode()).hexdigest()
    cutoff = utcnow() - timedelta(minutes=15)
    db.query(models.AuthAttempt).filter(models.AuthAttempt.created_at < cutoff).delete()
    if (
        db.query(models.AuthAttempt).filter(models.AuthAttempt.key == key).count()
        >= count
    ):
        db.commit()
        raise HTTPException(
            429, "Thao tác quá nhiều lần. Vui lòng thử lại sau 15 phút."
        )
    db.add(models.AuthAttempt(key=key))
    db.commit()


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    limit(db, "register", request.client.host if request.client else "unknown", 20)
    if (
        db.query(models.User)
        .filter(
            (models.User.username == data.username)
            | (models.User.email == str(data.email).lower())
        )
        .first()
    ):
        raise HTTPException(400, "Tên đăng nhập hoặc email đã tồn tại")
    user = models.User(
        username=data.username,
        email=str(data.email).lower(),
        hashed_password=auth.hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Tên đăng nhập hoặc email đã tồn tại")
    db.refresh(user)
    for name, color in [
        ("Công việc", "#4f7b69"),
        ("Học tập", "#7275b6"),
        ("Cá nhân", "#cc9057"),
    ]:
        db.add(models.Category(owner_id=user.id, name=name, color=color))
    db.commit()
    return user


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    limit(db, "login", form.username.lower(), 15)
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not auth.verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    return {"access_token": auth.create_access_token(user), "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(auth.get_current_user)):
    return user


@router.put("/me", response_model=schemas.UserOut)
def profile(
    data: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if (
        db.query(models.User)
        .filter(models.User.email == str(data.email).lower(), models.User.id != user.id)
        .first()
    ):
        raise HTTPException(400, "Email đã được sử dụng")
    for key, value in data.model_dump().items():
        setattr(user, key, str(value).lower() if key == "email" else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Email đã được sử dụng")
    db.refresh(user)
    return user


@router.post("/change-password")
def change_password(
    data: schemas.ChangePassword,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    if not auth.verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    user.hashed_password = auth.hash_password(data.new_password)
    user.token_version += 1
    db.query(models.PasswordReset).filter(
        models.PasswordReset.owner_id == user.id, models.PasswordReset.used_at.is_(None)
    ).update({"used_at": utcnow()})
    db.commit()
    return {"message": "Đã đổi mật khẩu. Vui lòng đăng nhập lại."}


@router.post("/logout")
def logout(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    user.token_version += 1
    db.commit()
    return {"message": "Đã đăng xuất các phiên."}


@router.post("/forgot-password")
def forgot(data: schemas.ForgotPassword, db: Session = Depends(get_db)):
    if not mailer.configured():
        raise HTTPException(
            503, "Chưa cấu hình email khôi phục. Vui lòng liên hệ quản trị viên."
        )
    email = str(data.email).lower()
    limit(db, "reset", email, 3)
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        token = secrets.token_urlsafe(40)
        db.query(models.PasswordReset).filter(
            models.PasswordReset.owner_id == user.id,
            models.PasswordReset.used_at.is_(None),
        ).update({"used_at": utcnow()})
        reset = models.PasswordReset(
            owner_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=utcnow() + timedelta(minutes=30),
        )
        db.add(reset)
        db.commit()
        base = base_url()
        try:
            mailer.send_mail(
                email,
                "Đặt lại mật khẩu Lịch Làm Việc",
                f"Mở liên kết sau trong 30 phút để đặt lại mật khẩu:\n{base}/#reset={token}\n\nNếu bạn không yêu cầu, hãy bỏ qua email này.",
            )
        except Exception:
            logging.exception("Không gửi được email khôi phục")
            reset.used_at = utcnow()
            db.commit()
    return {"message": "Nếu email tồn tại, bạn sẽ nhận được liên kết đặt lại mật khẩu."}


@router.post("/reset-password")
def reset_password(data: schemas.ResetPassword, db: Session = Depends(get_db)):
    now = utcnow()
    record = (
        db.query(models.PasswordReset)
        .filter(
            models.PasswordReset.token_hash
            == hashlib.sha256(data.token.encode()).hexdigest(),
            models.PasswordReset.used_at.is_(None),
            models.PasswordReset.expires_at > now,
        )
        .first()
    )
    if not record:
        raise HTTPException(400, "Liên kết không hợp lệ hoặc đã hết hạn")
    claimed = (
        db.query(models.PasswordReset)
        .filter(
            models.PasswordReset.id == record.id, models.PasswordReset.used_at.is_(None)
        )
        .update({"used_at": now})
    )
    if not claimed:
        db.rollback()
        raise HTTPException(400, "Liên kết đã được sử dụng")
    user = db.get(models.User, record.owner_id)
    user.hashed_password = auth.hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    return {"message": "Đã đặt lại mật khẩu. Bạn có thể đăng nhập."}
