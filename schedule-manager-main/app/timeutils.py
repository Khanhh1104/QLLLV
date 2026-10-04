from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        # Dữ liệu cũ được lưu dưới dạng UTC không kèm múi giờ.
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def aware_utc(value):
    if value is None:
        return None
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def valid_zone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Múi giờ không hợp lệ")
    return value
