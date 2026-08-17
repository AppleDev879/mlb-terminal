import datetime as dt

import pytest

from mlb.util import dig, local_time, ordinal, parse_date, parse_iso, record


def test_dig_walks_nested_structures():
    payload = {"a": {"b": [{"c": 1}, {"c": 2}]}}
    assert dig(payload, "a.b.0.c") == 1
    assert dig(payload, "a.b.1.c") == 2
    assert dig(payload, "a.b.-1.c") == 2


@pytest.mark.parametrize(
    "path",
    ["a.missing", "a.b.9.c", "a.b.x.c", "nope", "a.b.0.c.deeper"],
)
def test_dig_returns_default_on_any_miss(path):
    payload = {"a": {"b": [{"c": 1}]}}
    assert dig(payload, path, "fallback") == "fallback"


def test_dig_treats_explicit_null_as_missing():
    assert dig({"score": None}, "score", 0) == 0


def test_dig_does_not_index_strings():
    assert dig({"name": "Judge"}, "name.0", "x") == "x"


@pytest.mark.parametrize(
    "value,expected",
    [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
     (12, "12th"), (13, "13th"), (21, "21st"), (None, "")],
)
def test_ordinal(value, expected):
    assert ordinal(value) == expected


def test_parse_date_relative_words():
    today = dt.date(2025, 8, 16)
    assert parse_date("today", today) == today
    assert parse_date("yesterday", today) == dt.date(2025, 8, 15)
    assert parse_date("tomorrow", today) == dt.date(2025, 8, 17)
    assert parse_date(None, today) == today


def test_parse_date_offsets_and_formats():
    today = dt.date(2025, 8, 16)
    assert parse_date("-2", today) == dt.date(2025, 8, 14)
    assert parse_date("+1", today) == dt.date(2025, 8, 17)
    assert parse_date("2025-07-04", today) == dt.date(2025, 7, 4)
    assert parse_date("07/04/2025", today) == dt.date(2025, 7, 4)
    assert parse_date("7/4", today) == dt.date(2025, 7, 4)


def test_parse_date_rejects_nonsense():
    with pytest.raises(ValueError):
        parse_date("opening day")


def test_parse_iso_handles_zulu_suffix():
    stamp = parse_iso("2025-08-16T23:05:00Z")
    assert stamp is not None
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == dt.timedelta(0)
    assert stamp.hour == 23


def test_parse_iso_tolerates_garbage():
    assert parse_iso("") is None
    assert parse_iso(None) is None
    assert parse_iso("not a date") is None


def test_local_time_renders_something_clockish():
    text = local_time("2025-08-16T23:05:00Z")
    assert ":" in text and text.strip()


def test_record_formatting():
    assert record(68, 54) == "(68-54)"
    assert record(None, 54) == ""
