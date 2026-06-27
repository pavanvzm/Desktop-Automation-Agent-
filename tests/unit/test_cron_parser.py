"""Unit tests for the cron parser."""

import pytest
from src.scheduler.cron_parser import CronParser, NaturalLanguageParser, ParsedSchedule


class TestCronParser:
    """Tests for CronParser."""

    def test_parse_valid_cron(self):
        """Test parsing a valid cron expression."""
        parser = CronParser()
        result = parser.parse("0 9 * * 1-5")

        assert result.cron_expr == "0 9 * * 1-5"
        assert len(result.next_runs) == 5

    def test_parse_invalid_cron(self):
        """Test parsing an invalid cron expression."""
        parser = CronParser()

        with pytest.raises(ValueError):
            parser.parse("invalid")

    def test_parse_too_many_fields(self):
        """Test parsing cron with too many fields."""
        parser = CronParser()

        with pytest.raises(ValueError):
            parser.parse("0 9 * * 1-5 extra")

    def test_describe_weekday(self):
        """Test description of weekday cron."""
        parser = CronParser()
        result = parser.parse("0 9 * * 1-5")

        assert "weekday" in result.description.lower() or "day" in result.description.lower()


class TestNaturalLanguageParser:
    """Tests for NaturalLanguageParser."""

    def test_parse_every_weekday_at_9am(self):
        """Test parsing 'every weekday at 9am'."""
        parser = NaturalLanguageParser()
        result = parser.parse("every weekday at 9am")

        assert result.cron_expr == "0 9 * * 1-5"
        assert "weekday" in result.description.lower()

    def test_parse_every_15_minutes(self):
        """Test parsing 'every 15 minutes'."""
        parser = NaturalLanguageParser()
        result = parser.parse("every 15 minutes")

        assert "*/15" in result.cron_expr

    def test_parse_daily_at_time(self):
        """Test parsing 'every day at X'."""
        parser = NaturalLanguageParser()
        result = parser.parse("every day at 3pm")

        assert "15" in result.cron_expr.split()[1]  # Hour should be 15

    def test_parse_weekly(self):
        """Test parsing weekly schedule."""
        parser = NaturalLanguageParser()
        result = parser.parse("every monday at 8am")

        assert result.cron_expr.endswith("1")  # Monday = 1

    def test_parse_hourly(self):
        """Test parsing 'hourly'."""
        parser = NaturalLanguageParser()
        result = parser.parse("hourly")

        assert "0 * * * *" == result.cron_expr

    def test_invalid_input(self):
        """Test handling of invalid input."""
        parser = NaturalLanguageParser()

        with pytest.raises(ValueError):
            parser.parse("this is not a schedule")
