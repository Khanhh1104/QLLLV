"""Điểm vào cho Vercel Serverless Function.

Vercel nạp biến `app` trong file này và chạy trực tiếp ứng dụng ASGI (FastAPI).
Toàn bộ request (/, /auth/*, /tasks/*, file tĩnh...) đều được vercel.json
chuyển về đây.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Chỉ /tmp là ghi được trên Vercel; đặt sẵn HOME để các thư viện không ghi nhầm chỗ.
os.environ.setdefault("HOME", "/tmp")

from app.main import app  # noqa: E402

__all__ = ["app"]
