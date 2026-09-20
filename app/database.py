import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

# Trên Vercel (và serverless nói chung) toàn bộ ổ đĩa là chỉ-đọc, chỉ /tmp ghi được.
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

# Tham số psycopg2 không hiểu, thường do Prisma/PgBouncer thêm vào.
UNSUPPORTED_PARAMS = {"pgbouncer", "schema", "connection_limit", "pool_timeout"}


def _raw_url():
    """Ưu tiên DATABASE_URL; nếu gắn Vercel Postgres/Neon/Supabase thì nhận POSTGRES_*."""
    for key in (
        "DATABASE_URL",
        "POSTGRES_URL_NON_POOLING",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
    ):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    # Không cấu hình gì: dùng SQLite để trang web vẫn chạy được ngay.
    return "sqlite:////tmp/schedule.db" if IS_SERVERLESS else "sqlite:///./schedule.db"


def _clean_query(url):
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in UNSUPPORTED_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def _normalize(url):
    # Heroku/Neon/Supabase hay trả về postgres:// mà SQLAlchemy 2 không chấp nhận.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    if url.startswith("postgresql"):
        return _clean_query(url)
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        # Đổi đường dẫn tương đối thành tuyệt đối để không phụ thuộc thư mục làm việc.
        relative = url[len("sqlite:///") :]
        base = Path("/tmp") if IS_SERVERLESS else Path(__file__).resolve().parent.parent
        url = "sqlite:///" + str(base / relative)
    return url


DATABASE_URL = _normalize(_raw_url())
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False} if IS_SQLITE else {"connect_timeout": 10},
}
if IS_SERVERLESS and not IS_SQLITE:
    # Mỗi request là một tiến trình ngắn: không giữ connection pool.
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
