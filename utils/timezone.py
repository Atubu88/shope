from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def to_timezone(dt: datetime, tz_name: str):
    try:
        target = ZoneInfo(tz_name or "UTC")
    except ZoneInfoNotFoundError:
        print(f"[WARN] Таймзона '{tz_name}' не найдена, использую UTC")
        target = ZoneInfo("UTC")

    # Если datetime без tzinfo — считаем, что оно в UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.astimezone(target)
