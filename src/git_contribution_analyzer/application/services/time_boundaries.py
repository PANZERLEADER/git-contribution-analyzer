from __future__ import annotations

from datetime import datetime, time


def parse_boundary(value: str | None, *, end_of_day: bool) -> datetime | None:
    if value is None:
        return None
    try:
        if "T" not in value and " " not in value:
            parsed_date = datetime.fromisoformat(value).date()
            parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date/time: {value}") from exc
    return parsed if parsed.tzinfo is not None else localize_system_time(parsed)


def localize_system_time(value: datetime) -> datetime:
    return value.astimezone()


def uses_system_timezone(*values: str | None) -> bool:
    for value in values:
        if value is None:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return True
    return False


def parse_boundaries(
    since: str | None,
    until: str | None,
) -> tuple[datetime | None, datetime | None]:
    parsed_since = parse_boundary(since, end_of_day=False)
    parsed_until = parse_boundary(until, end_of_day=True)
    if (
        parsed_since is not None
        and parsed_until is not None
        and parsed_since > parsed_until
    ):
        raise ValueError("since must be earlier than or equal to until")
    return parsed_since, parsed_until
