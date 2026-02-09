"""Tests for the Grocy calendar platform with timezone handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import icalendar
import pytest
from homeassistant.components.calendar import CalendarEvent
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grocy.calendar import GrocyCalendarEntity
from custom_components.grocy.const import (
    CONF_API_KEY,
    CONF_CALENDAR_FIX_TIMEZONE,
    CONF_CALENDAR_SYNC_INTERVAL,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)


class MockAsyncContextManager:
    """Mock async context manager for aiohttp session.get()."""

    def __init__(self, mock_response: MagicMock) -> None:
        """Initialize with a mock response."""
        self.mock_response = mock_response

    async def __aenter__(self):
        """Return the mock response on enter."""
        return self.mock_response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        return False


def _create_mock_session(ical_data: str, status: int = 200) -> MagicMock:
    """Create a properly mocked aiohttp session for calendar tests."""
    mock_response = MagicMock()
    mock_response.status = status
    # Use a regular function that returns a coroutine for text()
    async def mock_text():
        return ical_data
    mock_response.text = mock_text

    session = MagicMock()
    session.get.return_value = MockAsyncContextManager(mock_response)
    return session


@pytest.fixture(name="mock_coordinator")
def mock_coordinator_fixture() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.entities = []
    return coordinator


@pytest.fixture(name="calendar_config_entry_data")
def calendar_config_entry_data_fixture() -> dict[str, object]:
    """Config entry data with calendar settings."""
    return {
        CONF_URL: "https://demo.grocy.info",
        CONF_API_KEY: "test-token",
        CONF_PORT: 9192,
        CONF_VERIFY_SSL: False,
        CONF_CALENDAR_SYNC_INTERVAL: 5,
        CONF_CALENDAR_FIX_TIMEZONE: True,
    }


@pytest.fixture(name="calendar_config_entry")
def calendar_config_entry_fixture(
    calendar_config_entry_data: dict[str, object],
) -> MockConfigEntry:
    """Create a mock config entry for calendar tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Grocy",
        data=calendar_config_entry_data,
        entry_id="test-calendar-entry",
    )


def _create_ical_event(
    summary: str,
    start: datetime | None = None,
    end: datetime | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    uid: str = "test-uid",
    tzid: str | None = None,
) -> icalendar.Event:
    """Create an iCal event for testing.

    Args:
        summary: Event summary/title
        start: Start datetime (for timed events)
        end: End datetime (for timed events)
        start_date: Start date string YYYYMMDD (for all-day events)
        end_date: End date string YYYYMMDD (for all-day events)
        uid: Unique identifier
        tzid: Timezone ID for datetime events

    """
    event = icalendar.Event()
    event.add("summary", summary)
    event.add("uid", uid)

    if start is not None:
        if tzid:
            event.add("dtstart", start, parameters={"TZID": tzid})
        else:
            event.add("dtstart", start)

    if end is not None:
        if tzid:
            event.add("dtend", end, parameters={"TZID": tzid})
        else:
            event.add("dtend", end)

    if start_date is not None:
        # All-day event with date only
        dt_start = icalendar.vDate.from_ical(start_date)
        event.add("dtstart", dt_start)

    if end_date is not None:
        dt_end = icalendar.vDate.from_ical(end_date)
        event.add("dtend", dt_end)

    return event


def _create_ical_calendar(events: list[icalendar.Event]) -> str:
    """Create an iCal calendar string from events."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Test//Test//EN")
    cal.add("version", "2.0")
    for event in events:
        cal.add_component(event)
    return cal.to_ical().decode("utf-8")


class TestCalendarEntityTimezoneFixEnabled:
    """Tests for calendar timezone fix when enabled (default)."""

    @pytest.mark.asyncio
    async def test_utc_event_treated_as_local_time_when_fix_enabled(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that UTC times are treated as local time when fix_timezone=True.

        This tests the Grocy addon bug where local times are incorrectly marked as UTC.
        When fix is enabled, a time like 14:00 UTC should be treated as 14:00 local time.
        """
        # Set up Home Assistant with a specific timezone
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create event at 14:00 UTC (which is actually 14:00 local time from Grocy addon)
        event_start_utc = datetime(2026, 2, 15, 14, 0, 0, tzinfo=UTC)
        event_end_utc = datetime(2026, 2, 15, 15, 0, 0, tzinfo=UTC)
        ical_event = _create_ical_event(
            summary="Test Event",
            start=event_start_utc,
            end=event_end_utc,
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        # With fix_timezone=True, the 14:00 UTC should be treated as 14:00 local
        # Not converted (which would make it 15:00 in Europe/Berlin during winter)
        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 2, 15, 14, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 2, 15, 15, 0, 0, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end

    @pytest.mark.asyncio
    async def test_naive_datetime_converted_from_utc(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that naive datetimes (no timezone) are assumed UTC and converted."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create event with naive datetime (no timezone info)
        event_start_naive = datetime(2026, 2, 15, 14, 0, 0)
        event_end_naive = datetime(2026, 2, 15, 15, 0, 0)
        ical_event = _create_ical_event(
            summary="Naive Event",
            start=event_start_naive,
            end=event_end_naive,
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        # Naive datetime is interpreted as UTC and converted to local
        # 14:00 UTC -> 15:00 Europe/Berlin (winter time, +1 hour)
        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 2, 15, 15, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 2, 15, 16, 0, 0, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end


class TestCalendarEntityTimezoneFixDisabled:
    """Tests for calendar when timezone fix is disabled."""

    @pytest.fixture(name="config_entry_fix_disabled")
    def config_entry_fix_disabled_fixture(self) -> MockConfigEntry:
        """Create config entry with timezone fix disabled."""
        return MockConfigEntry(
            domain=DOMAIN,
            title="Grocy",
            data={
                CONF_URL: "https://demo.grocy.info",
                CONF_API_KEY: "test-token",
                CONF_PORT: 9192,
                CONF_VERIFY_SSL: False,
                CONF_CALENDAR_SYNC_INTERVAL: 5,
                CONF_CALENDAR_FIX_TIMEZONE: False,
            },
            entry_id="test-calendar-entry-no-fix",
        )

    @pytest.mark.asyncio
    async def test_utc_event_converted_to_local_when_fix_disabled(
        self,
        hass,
        mock_coordinator,
        config_entry_fix_disabled,
    ) -> None:
        """Test that UTC times are properly converted when fix_timezone=False.

        This is the correct behavior for Grocy instances that properly send UTC times.
        """
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, config_entry_fix_disabled)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create event at 14:00 UTC (should be converted to 15:00 Berlin time)
        event_start_utc = datetime(2026, 2, 15, 14, 0, 0, tzinfo=UTC)
        event_end_utc = datetime(2026, 2, 15, 15, 0, 0, tzinfo=UTC)
        ical_event = _create_ical_event(
            summary="Test Event",
            start=event_start_utc,
            end=event_end_utc,
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        # With fix_timezone=False, 14:00 UTC should be converted to 15:00 Berlin
        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 2, 15, 15, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 2, 15, 16, 0, 0, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end


class TestCalendarEntityAllDayEvents:
    """Tests for all-day (date-only) events."""

    @pytest.mark.asyncio
    async def test_all_day_event_single_day(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that a single-day all-day event is handled correctly."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create all-day event for Feb 15, 2026
        # In iCal format, all-day events have DTEND as the day AFTER the event ends
        ical_event = _create_ical_event(
            summary="All Day Event",
            start_date="20260215",
            end_date="20260216",  # Exclusive end date
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        local_tz = ZoneInfo("Europe/Berlin")
        # Start should be at beginning of day (00:00:00)
        expected_start = datetime(2026, 2, 15, 0, 0, 0, tzinfo=local_tz)
        # End should be at end of day (23:59:59.999999)
        expected_end = datetime(2026, 2, 15, 23, 59, 59, 999999, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end

    @pytest.mark.asyncio
    async def test_all_day_event_multi_day(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that a multi-day all-day event spans correctly."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create all-day event spanning Feb 15-17, 2026
        ical_event = _create_ical_event(
            summary="Multi Day Event",
            start_date="20260215",
            end_date="20260218",  # Exclusive: means event ends on Feb 17
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 2, 15, 0, 0, 0, tzinfo=local_tz)
        # End is one day before exclusive end date, at end of day
        expected_end = datetime(2026, 2, 17, 23, 59, 59, 999999, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end

    @pytest.mark.asyncio
    async def test_all_day_event_no_end_date(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that an all-day event without end date ends at end of start day."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create all-day event with no end date
        ical_event = _create_ical_event(
            summary="All Day No End",
            start_date="20260215",
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 2, 15, 0, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 2, 15, 23, 59, 59, 999999, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end


class TestCalendarEntityEdgeCases:
    """Tests for edge cases in calendar event handling."""

    @pytest.mark.asyncio
    async def test_event_without_end_time_defaults_to_one_hour(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that a timed event without end time defaults to 1 hour duration."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create timed event with no end time
        event_start_utc = datetime(2026, 2, 15, 14, 0, 0, tzinfo=UTC)
        ical_event = _create_ical_event(
            summary="No End Time",
            start=event_start_utc,
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        # With fix_timezone=True, 14:00 UTC becomes 14:00 local
        # End should be 1 hour after start
        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 2, 15, 14, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 2, 15, 15, 0, 0, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end

    @pytest.mark.asyncio
    async def test_multiple_events_sorted_by_start_time(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that multiple events are sorted by start time."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # Create events out of order
        event1 = _create_ical_event(
            summary="Event B",
            start=datetime(2026, 2, 15, 14, 0, 0, tzinfo=UTC),
            end=datetime(2026, 2, 15, 15, 0, 0, tzinfo=UTC),
            uid="event-b",
        )
        event2 = _create_ical_event(
            summary="Event A",
            start=datetime(2026, 2, 15, 10, 0, 0, tzinfo=UTC),
            end=datetime(2026, 2, 15, 11, 0, 0, tzinfo=UTC),
            uid="event-a",
        )
        event3 = _create_ical_event(
            summary="Event C",
            start=datetime(2026, 2, 15, 18, 0, 0, tzinfo=UTC),
            end=datetime(2026, 2, 15, 19, 0, 0, tzinfo=UTC),
            uid="event-c",
        )
        ical_data = _create_ical_calendar([event1, event2, event3])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 3
        # Events should be sorted by start time
        assert entity._events[0].summary == "Event A"
        assert entity._events[1].summary == "Event B"
        assert entity._events[2].summary == "Event C"

    @pytest.mark.asyncio
    async def test_event_property_returns_next_event(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that the event property returns the next upcoming event."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        local_tz = ZoneInfo("Europe/Berlin")
        now = dt_util.now()

        # Create events: one past, one current, one future
        entity._events = [
            CalendarEvent(
                summary="Past Event",
                start=now - timedelta(hours=2),
                end=now - timedelta(hours=1),
            ),
            CalendarEvent(
                summary="Current Event",
                start=now - timedelta(minutes=30),
                end=now + timedelta(minutes=30),
            ),
            CalendarEvent(
                summary="Future Event",
                start=now + timedelta(hours=1),
                end=now + timedelta(hours=2),
            ),
        ]

        next_event = entity.event
        assert next_event is not None
        # Should return the current event (now is between start and end)
        assert next_event.summary == "Current Event"

    @pytest.mark.asyncio
    async def test_event_property_returns_none_when_no_events(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that the event property returns None when there are no events."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._events = []

        assert entity.event is None

    @pytest.mark.asyncio
    async def test_http_error_handling(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test that HTTP errors are handled gracefully."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"
        entity._events = []

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session("", status=500)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("Europe/Berlin"))

            # Should not raise, just return without updating events
            await entity._update_events(start_date, end_date)

        assert entity._events == []


class TestCalendarEntityTimezoneEdgeCases:
    """Tests for timezone handling edge cases."""

    @pytest.mark.asyncio
    async def test_daylight_saving_time_transition(
        self,
        hass,
        mock_coordinator,
        calendar_config_entry,
    ) -> None:
        """Test event during daylight saving time transition."""
        hass.config.time_zone = "Europe/Berlin"
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))

        entity = GrocyCalendarEntity(mock_coordinator, calendar_config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        # March 29, 2026 is when DST starts in Europe/Berlin
        # 14:00 UTC on this day should be treated as 14:00 local with fix enabled
        event_start_utc = datetime(2026, 3, 29, 14, 0, 0, tzinfo=UTC)
        event_end_utc = datetime(2026, 3, 29, 15, 0, 0, tzinfo=UTC)
        ical_event = _create_ical_event(
            summary="DST Event",
            start=event_start_utc,
            end=event_end_utc,
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 3, 1, tzinfo=ZoneInfo("Europe/Berlin"))
            end_date = datetime(2026, 3, 31, tzinfo=ZoneInfo("Europe/Berlin"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        # With fix_timezone=True, time should be treated as local
        local_tz = ZoneInfo("Europe/Berlin")
        expected_start = datetime(2026, 3, 29, 14, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 3, 29, 15, 0, 0, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end

    @pytest.mark.asyncio
    async def test_different_timezone_pacific(
        self,
        hass,
        mock_coordinator,
    ) -> None:
        """Test timezone handling with US/Pacific timezone."""
        hass.config.time_zone = "America/Los_Angeles"
        dt_util.set_default_time_zone(ZoneInfo("America/Los_Angeles"))

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Grocy",
            data={
                CONF_URL: "https://demo.grocy.info",
                CONF_API_KEY: "test-token",
                CONF_PORT: 9192,
                CONF_VERIFY_SSL: False,
                CONF_CALENDAR_SYNC_INTERVAL: 5,
                CONF_CALENDAR_FIX_TIMEZONE: True,
            },
            entry_id="test-pacific",
        )

        coordinator = MagicMock()
        coordinator.entities = []

        entity = GrocyCalendarEntity(coordinator, config_entry)
        entity.hass = hass
        entity._ical_url = "http://test.local/calendar.ics"

        event_start_utc = datetime(2026, 2, 15, 14, 0, 0, tzinfo=UTC)
        event_end_utc = datetime(2026, 2, 15, 15, 0, 0, tzinfo=UTC)
        ical_event = _create_ical_event(
            summary="Pacific Event",
            start=event_start_utc,
            end=event_end_utc,
        )
        ical_data = _create_ical_calendar([ical_event])

        with patch(
            "custom_components.grocy.calendar.async_get_clientsession"
        ) as mock_get_session:
            mock_get_session.return_value = _create_mock_session(ical_data)

            start_date = datetime(2026, 2, 1, tzinfo=ZoneInfo("America/Los_Angeles"))
            end_date = datetime(2026, 2, 28, tzinfo=ZoneInfo("America/Los_Angeles"))

            await entity._update_events(start_date, end_date)

        assert len(entity._events) == 1
        event = entity._events[0]

        # With fix_timezone=True, 14:00 UTC becomes 14:00 Pacific
        local_tz = ZoneInfo("America/Los_Angeles")
        expected_start = datetime(2026, 2, 15, 14, 0, 0, tzinfo=local_tz)
        expected_end = datetime(2026, 2, 15, 15, 0, 0, tzinfo=local_tz)

        assert event.start == expected_start
        assert event.end == expected_end


class TestCalendarEntityConfiguration:
    """Tests for calendar entity configuration."""

    def test_fix_timezone_defaults_to_true(
        self,
        mock_coordinator,
    ) -> None:
        """Test that fix_timezone defaults to True when not specified."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Grocy",
            data={
                CONF_URL: "https://demo.grocy.info",
                CONF_API_KEY: "test-token",
                CONF_PORT: 9192,
                CONF_VERIFY_SSL: False,
            },
            entry_id="test-no-tz-config",
        )

        entity = GrocyCalendarEntity(mock_coordinator, config_entry)
        assert entity._fix_timezone is True

    def test_fix_timezone_can_be_disabled(
        self,
        mock_coordinator,
    ) -> None:
        """Test that fix_timezone can be explicitly disabled."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Grocy",
            data={
                CONF_URL: "https://demo.grocy.info",
                CONF_API_KEY: "test-token",
                CONF_PORT: 9192,
                CONF_VERIFY_SSL: False,
                CONF_CALENDAR_FIX_TIMEZONE: False,
            },
            entry_id="test-tz-disabled",
        )

        entity = GrocyCalendarEntity(mock_coordinator, config_entry)
        assert entity._fix_timezone is False

    def test_sync_interval_default(
        self,
        mock_coordinator,
    ) -> None:
        """Test that sync interval defaults to 5 minutes."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Grocy",
            data={
                CONF_URL: "https://demo.grocy.info",
                CONF_API_KEY: "test-token",
                CONF_PORT: 9192,
                CONF_VERIFY_SSL: False,
            },
            entry_id="test-sync-default",
        )

        entity = GrocyCalendarEntity(mock_coordinator, config_entry)
        assert entity._sync_interval_minutes == 5

    def test_sync_interval_custom(
        self,
        mock_coordinator,
    ) -> None:
        """Test that sync interval can be customized."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Grocy",
            data={
                CONF_URL: "https://demo.grocy.info",
                CONF_API_KEY: "test-token",
                CONF_PORT: 9192,
                CONF_VERIFY_SSL: False,
                CONF_CALENDAR_SYNC_INTERVAL: 15,
            },
            entry_id="test-sync-custom",
        )

        entity = GrocyCalendarEntity(mock_coordinator, config_entry)
        assert entity._sync_interval_minutes == 15
