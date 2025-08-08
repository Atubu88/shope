"""Timezone helpers for salon-specific localization."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

TZ_GROUPS_ORDER = ["Europe", "Asia", "America", "Africa", "Australia", "Others"]


def to_timezone(dt: datetime, tz_name: str | None) -> datetime:
    """Convert ``dt`` to given timezone.

    Naive datetimes are treated as UTC. If ``tz_name`` is ``None`` an
    explicit UTC timezone is used.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    target = ZoneInfo(tz_name or "UTC")
    return dt.astimezone(target)


def get_group_timezones(group: str) -> list[str]:
    """Return a sorted list of timezones for the specified group.

    Known groups are the continents from :data:`TZ_GROUPS_ORDER` except
    ``"Others"`` which aggregates all remaining timezones.
    """
    all_zones = available_timezones()
    if group in TZ_GROUPS_ORDER[:-1]:
        prefix = f"{group}/"
        zones = [tz for tz in all_zones if tz.startswith(prefix)]
    elif group == "Others":
        prefixes = [f"{g}/" for g in TZ_GROUPS_ORDER[:-1]]
        zones = [tz for tz in all_zones if all(not tz.startswith(p) for p in prefixes)]
    else:
        zones = []
    return sorted(zones)
