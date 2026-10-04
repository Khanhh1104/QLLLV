import hashlib
import os
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from . import models
from .database import get_db
from .timeutils import utcnow

def _fallback_secret():
    """Khóa dự phòng khi người dùng chưa đặt SECRET_KEY.

    Trên serverless mỗi request có thể chạy ở một tiến trình khác nhau, nếu sinh
    khóa ngẫu nhiên thì người dùng sẽ bị đăng xuất liên tục. Vì vậy ta tạo khóa
    tất định từ định danh cố định của project. Đây chỉ là giải pháp để trang chạy
    được ngay sau khi deploy — hãy đặt SECRET_KEY riêng trong Environment
    Variables để bảo mật đúng nghĩa.
    """
    seed = (
        os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
        or os.getenv("VERCEL_PROJECT_ID")
        or os.getenv("VERCEL_URL")
    )
    if seed:
        return hashlib.sha256(f"schedule-manager::{seed}".encode()).hexdigest()
    return secrets.token_urlsafe(48)


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = _fallback_secret()
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY phải có ít nhất 32 ký tự.")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    if len(plain_password.encode()) > 72:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user):
    return jwt.encode(
        {
            "sub": str(user.id),
            "ver": user.token_version,
            "exp": utcnow() + timedelta(days=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    error = HTTPException(
        401,
        "Phiên đăng nhập hết hạn, vui lòng đăng nhập lại.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, ValueError, KeyError, TypeError):
        raise error
    user = db.get(models.User, uid)
    if not user or payload.get("ver") != user.token_version:
        raise error
    return user
