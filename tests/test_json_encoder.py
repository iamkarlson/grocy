from __future__ import annotations

import datetime as dt
import json

import pytest

from custom_components.grocy.json_encoder import CustomJSONEncoder


def test_encodes_date() -> None:
    data = {"date": dt.date(2025, 6, 15)}
    result = json.dumps(data, cls=CustomJSONEncoder)
    assert '"2025-06-15"' in result


def test_encodes_time() -> None:
    data = {"time": dt.time(14, 30, 0)}
    result = json.dumps(data, cls=CustomJSONEncoder)
    assert '"14:30:00"' in result


def test_encodes_datetime_via_parent() -> None:
    data = {"dt": dt.datetime(2025, 6, 15, 14, 30, 0)}
    result = json.dumps(data, cls=CustomJSONEncoder)
    assert "2025-06-15" in result


def test_encodes_regular_types() -> None:
    data = {"number": 42, "text": "hello", "flag": True}
    result = json.dumps(data, cls=CustomJSONEncoder)
    parsed = json.loads(result)
    assert parsed == data


def test_encodes_date_min() -> None:
    data = {"date": dt.date.min}
    result = json.dumps(data, cls=CustomJSONEncoder)
    assert '"0001-01-01"' in result


def test_encodes_time_with_microseconds() -> None:
    data = {"time": dt.time(10, 5, 30, 123456)}
    result = json.dumps(data, cls=CustomJSONEncoder)
    parsed = json.loads(result)
    assert "10:05:30" in parsed["time"]
