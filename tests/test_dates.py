from datetime import date

from tally.storage import parse_started

def test_parse_started_with_valid_date():
    result = parse_started("2026-10-25")

    assert result == date(2026, 10, 25)

def test_parse_started_with_invalid_date():
    result = parse_started("2026-02-30")

    assert result is None

def test_parse_started_with_none():
    result = parse_started(None)

    assert result is None