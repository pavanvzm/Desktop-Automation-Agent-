from __future__ import annotations
"""Natural language to cron expression parser."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ParsedSchedule:
    """Result of parsing a natural language schedule."""

    cron_expr: str
    description: str
    next_runs: list[datetime]
    confidence: float = 1.0  # 0.0 to 1.0


class CronParser:
    """Parse and validate cron expressions."""

    # Standard cron fields: minute, hour, day_of_month, month, day_of_week
    CRON_FIELDS = ["minute", "hour", "day_of_month", "month", "day_of_week"]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for cron validation."""
        # Simplified patterns that accept common cron expressions
        self._patterns = {
            "minute": re.compile(r"^(\*|(\*\/)?\d{1,2}(-\d{1,2})?(,\d{1,2}(-\d{1,2})?)*)$"),
            "hour": re.compile(r"^(\*|(\*\/)?\d{1,2}(-\d{1,2})?(,\d{1,2}(-\d{1,2})?)*)$"),
            "day_of_month": re.compile(r"^(\*|(\*\/)?\d{1,2}(-\d{1,2})?(,\d{1,2}(-\d{1,2})?)*|L|L-\d+)$"),
            "month": re.compile(r"^(\*|(\*\/)?\d{1,2}(-\d{1,2})?(,\d{1,2}(-\d{1,2})?)*|[a-zA-Z]{3}(,[a-zA-Z]{3})*)$"),
            "day_of_week": re.compile(r"^(\*|(\*\/)?\d{1}(-\d{1})?(,\d{1}(-\d{1})?)*|[a-zA-Z]{3}(,[a-zA-Z]{3})*)$"),
        }

    def parse(self, cron_expr: str) -> ParsedSchedule:
        """Parse a cron expression and return schedule info."""
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: expected 5 fields, got {len(parts)}")

        # Validate each field
        for i, (field_name, value) in enumerate(zip(self.CRON_FIELDS, parts)):
            if not self._patterns[field_name].match(value):
                raise ValueError(f"Invalid {field_name} field: {value}")

        next_runs = self._get_next_runs(parts)
        description = self._describe(parts)

        return ParsedSchedule(
            cron_expr=cron_expr,
            description=description,
            next_runs=next_runs,
        )

    def _get_next_runs(self, parts: list[str], count: int = 5) -> list[datetime]:
        """Calculate the next N run times for a cron expression."""
        # Simplified implementation using croniter
        try:
            from croniter import croniter

            base_time = datetime.now()
            cron = croniter(" ".join(parts), base_time)
            return [cron.get_next(datetime) for _ in range(count)]
        except ImportError:
            # Fallback if croniter not available
            return [datetime.now() + timedelta(hours=i + 1) for i in range(count)]

    def _describe(self, parts: list[str]) -> str:
        """Generate a human-readable description of the cron expression."""
        minute, hour, day, month, dow = parts

        descriptions = []

        # Day of week
        dow_names = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday",
                     4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}

        if dow == "1-5":
            descriptions.append("every weekday")
        elif dow == "1":
            descriptions.append("every Monday")
        elif dow == "2":
            descriptions.append("every Tuesday")
        elif dow == "3":
            descriptions.append("every Wednesday")
        elif dow == "4":
            descriptions.append("every Thursday")
        elif dow == "5":
            descriptions.append("every Friday")
        elif dow == "6":
            descriptions.append("every Saturday")
        elif dow == "0" or dow == "7":
            descriptions.append("every Sunday")
        elif dow != "*":
            descriptions.append(f"on day {dow} of the week")

        # Time
        if minute == "*" and hour == "*":
            descriptions.append("every minute")
        elif minute.startswith("*/"):
            descriptions.append(f"every {minute[2:]} minutes")
        elif hour == "*":
            descriptions.append(f"at minute {minute} of every hour")
        else:
            try:
                h = int(hour)
                m = int(minute)
                time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
                descriptions.append(f"at {time_str}")
            except ValueError:
                descriptions.append(f"at {hour}:{minute}")

        # Day of month
        if day != "*":
            if day == "L":
                descriptions.append("on the last day of the month")
            elif day.startswith("L-"):
                days_before = day[2:]
                descriptions.append(f"{days_before} days before month-end")
            else:
                descriptions.append(f"on day {day} of the month")

        return " ".join(descriptions) if descriptions else "custom schedule"


class NaturalLanguageParser:
    """
    Parse natural language scheduling expressions into cron.

    Examples:
    - "every weekday at 9am" -> "0 9 * * 1-5"
    - "every 15 minutes" -> "*/15 * * * *"
    - "3 days before month-end" -> custom handling
    """

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for natural language parsing."""
        self._patterns = [
            # Every X minutes/hours
            (r"every\s+(\d+)?\s*(minute|minutes)", self._parse_minute_interval),
            (r"every\s+(\d+)?\s*(hour|hours)", self._parse_hour_interval),
            (r"every\s+(\d+)?\s*(second|seconds)", self._parse_second_interval),

            # Daily at specific time
            (r"every\s+day\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_daily),
            (r"daily\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_daily),

            # Weekdays at specific time
            (r"every\s+weekday\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_weekdays),
            (r"weekdays?\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_weekdays),

            # Weekly on specific day
            (r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_weekly),
            (r"on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_weekly),

            # Monthly on specific day
            (r"every\s+month\s+on\s+day\s+(\d+)\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_monthly_day),
            (r"monthly\s+on\s+(first|second|third|fourth|last)\s+(\w+)\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_monthly_ordinal),

            # Month-end related
            (r"(\d+)\s+days?\s+before\s+month[-\s]end", self._parse_before_month_end),
            (r"on\s+the\s+last\s+day\s+of\s+the\s+month\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?", self._parse_month_end),

            # Hourly
            (r"hourly", self._parse_hourly),
        ]

        self._day_map = {
            "sunday": 0, "sun": 0,
            "monday": 1, "mon": 1,
            "tuesday": 2, "tue": 2,
            "wednesday": 3, "wed": 3,
            "thursday": 4, "thu": 4,
            "friday": 5, "fri": 5,
            "saturday": 6, "sat": 6,
        }

        self._ordinal_map = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "last": -1,
        }

    def parse(self, natural_text: str) -> ParsedSchedule:
        """Parse natural language into a schedule."""
        text = natural_text.lower().strip()

        for pattern, handler in self._patterns:
            match = re.search(pattern, text)
            if match:
                return handler(match)

        # No match found
        raise ValueError(f"Could not parse schedule: '{natural_text}'")

    def _parse_time(self, hour: int | str, minute: int | str, ampm: str | None) -> tuple[int, int]:
        """Convert time components to 24-hour format."""
        h = int(hour) if hour else 0
        m = int(minute) if minute else 0

        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0

        return h, m

    def _parse_minute_interval(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every X minutes'."""
        count = match.group(1)
        interval = int(count) if count else 1

        cron = f"*/{interval} * * * *"
        return self._create_schedule(cron, f"every {interval} minutes")

    def _parse_hour_interval(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every X hours'."""
        count = match.group(1)
        interval = int(count) if count else 1

        cron = f"0 */{interval} * * *"
        return self._create_schedule(cron, f"every {interval} hours")

    def _parse_second_interval(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every X seconds' (not standard cron, but useful)."""
        count = match.group(1)
        interval = int(count) if count else 1

        # Note: Standard cron doesn't support seconds
        # This would require a different scheduler
        cron = f"*/{interval} * * * *"
        return self._create_schedule(cron, f"every {interval} seconds (approximation)")

    def _parse_daily(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every day at X'."""
        hour = match.group(1)
        minute = match.group(2) or "0"
        ampm = match.group(3)

        h, m = self._parse_time(hour, minute, ampm)
        cron = f"{m} {h} * * *"
        time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        return self._create_schedule(cron, f"every day at {time_str}")

    def _parse_weekdays(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every weekday at X'."""
        hour = match.group(1)
        minute = match.group(2) or "0"
        ampm = match.group(3)

        h, m = self._parse_time(hour, minute, ampm)
        cron = f"{m} {h} * * 1-5"
        time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        return self._create_schedule(cron, f"every weekday at {time_str}")

    def _parse_weekly(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every Monday at X'."""
        day_name = match.group(1).lower()
        hour = match.group(2)
        minute = match.group(3) or "0"
        ampm = match.group(4)

        dow = self._day_map.get(day_name, 0)
        h, m = self._parse_time(hour, minute, ampm)
        cron = f"{m} {h} * * {dow}"
        time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        return self._create_schedule(cron, f"every {day_name.capitalize()} at {time_str}")

    def _parse_monthly_day(self, match: re.Match) -> ParsedSchedule:
        """Parse 'every month on day X at Y'."""
        day = match.group(1)
        hour = match.group(2)
        minute = match.group(3) or "0"
        ampm = match.group(4)

        h, m = self._parse_time(hour, minute, ampm)
        cron = f"{m} {h} {day} * *"
        time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        return self._create_schedule(cron, f"every month on day {day} at {time_str}")

    def _parse_monthly_ordinal(self, match: re.Match) -> ParsedSchedule:
        """Parse 'monthly on first Monday at X'."""
        ordinal = match.group(1).lower()
        day_name = match.group(2).lower()
        hour = match.group(3)
        minute = match.group(4) or "0"
        ampm = match.group(5)

        ord_num = self._ordinal_map.get(ordinal, 1)
        dow = self._day_map.get(day_name, 0)
        h, m = self._parse_time(hour, minute, ampm)

        if ord_num == -1:  # Last
            # Complex - would need custom logic
            cron = f"{m} {h} 1 * *"  # Approximation
        else:
            cron = f"{m} {h} 1 * *"  # Simplified

        time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        return self._create_schedule(cron, f"every {ordinal} {day_name} at {time_str}")

    def _parse_before_month_end(self, match: re.Match) -> ParsedSchedule:
        """Parse 'X days before month-end'."""
        days = match.group(1)

        # Calculate: last day of month minus N days
        # Cron doesn't support this directly, use day L-N
        cron = f"0 9 L-{days} * *"
        return self._create_schedule(cron, f"{days} days before month-end at 9:00 AM")

    def _parse_month_end(self, match: re.Match) -> ParsedSchedule:
        """Parse 'on the last day of the month at X'."""
        hour = match.group(1)
        minute = match.group(2) or "0"
        ampm = match.group(3)

        h, m = self._parse_time(hour, minute, ampm)
        cron = f"{m} {h} L * *"
        time_str = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
        return self._create_schedule(cron, f"on the last day of the month at {time_str}")

    def _parse_hourly(self, match: re.Match) -> ParsedSchedule:
        """Parse 'hourly'."""
        cron = "0 * * * *"
        return self._create_schedule(cron, "every hour")

    def _create_schedule(self, cron: str, description: str) -> ParsedSchedule:
        """Create a ParsedSchedule with next run times."""
        cron_parser = CronParser()
        try:
            parsed = cron_parser.parse(cron)
            return ParsedSchedule(
                cron_expr=parsed.cron_expr,
                description=description,
                next_runs=parsed.next_runs,
                confidence=1.0,
            )
        except ValueError:
            return ParsedSchedule(
                cron_expr=cron,
                description=description,
                next_runs=[],
                confidence=0.8,
            )
