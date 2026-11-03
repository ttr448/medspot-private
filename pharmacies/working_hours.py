"""Parsing and checking the simple pharmacy opening-hours format."""

import re


DAY_NUMBERS = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}

DAY_PATTERN = r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
ENTRY_PATTERN = re.compile(
    rf"^{DAY_PATTERN}(?:\s*-\s*{DAY_PATTERN})?\s+"
    r"(?:(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})|(Closed))$",
    re.IGNORECASE,
)


def _minutes_from_time(value, allow_24=False):
    try:
        hour_text, minute_text = value.split(":")
        hour = int(hour_text)
        minute = int(minute_text)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Times must use HH:MM format.")

    if minute < 0 or minute > 59:
        raise ValueError("Minutes must be between 00 and 59.")

    if allow_24 and hour == 24 and minute == 0:
        return 24 * 60

    if hour < 0 or hour > 23:
        raise ValueError("Hours must be between 00 and 23.")

    return hour * 60 + minute


def parse_working_hours(value):
    """Return {weekday_number: [(start_minute, end_minute), ...]}.

    Accepted examples:
      Sat-Thu 08:00-22:00; Fri 16:00-22:00
      Mon-Fri 09:00-17:00; Sat Closed; Sun Closed

    Overnight periods are supported, e.g. Fri 20:00-02:00.
    """
    schedule = {}
    value = (value or "").strip()
    if not value:
        return schedule

    for raw_entry in value.split(";"):
        entry = raw_entry.strip()
        match = ENTRY_PATTERN.fullmatch(entry)
        if not match:
            raise ValueError(
                "Use entries like 'Sat-Thu 08:00-22:00; Fri 16:00-22:00'. "
                "Use three-letter English day names and separate days with semicolons."
            )

        first_day = match.group(1).title()
        last_day = (match.group(2) or first_day).title()
        start_text = match.group(3)
        end_text = match.group(4)
        is_closed = bool(match.group(5))

        first_number = DAY_NUMBERS[first_day]
        last_number = DAY_NUMBERS[last_day]

        days = []
        current_day = first_number
        while True:
            days.append(current_day)
            if current_day == last_number:
                break
            current_day = (current_day + 1) % 7

        if is_closed:
            for day in days:
                schedule[day] = []
            continue

        start_minute = _minutes_from_time(start_text)
        end_minute = _minutes_from_time(end_text, allow_24=True)

        if start_minute == end_minute:
            raise ValueError("Opening and closing times cannot be the same.")

        for day in days:
            schedule.setdefault(day, []).append((start_minute, end_minute))

    return schedule
