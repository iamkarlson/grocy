"""Calendar platform for Grocy."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import icalendar
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_KEY,
    CONF_CALENDAR_FIX_TIMEZONE,
    CONF_CALENDAR_SYNC_INTERVAL,
    CONF_PORT,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_CALENDAR_SYNC_INTERVAL,
    DOMAIN,
    NAME,
    VERSION,
)
from .coordinator import GrocyDataUpdateCoordinator
from .helpers import extract_base_url_and_path

_LOGGER = logging.getLogger(__name__)

HTTP_OK = 200


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Grocy calendar platform."""
    coordinator: GrocyDataUpdateCoordinator = hass.data[DOMAIN]

    entity = GrocyCalendarEntity(coordinator, config_entry)
    coordinator.entities.append(entity)
    async_add_entities([entity], True)


class GrocyCalendarEntity(CalendarEntity):
    """Grocy calendar entity definition."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: GrocyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__()
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._ical_url: str | None = None
        self._events: list[CalendarEvent] = []
        self._sync_interval_minutes: int = config_entry.data.get(
            CONF_CALENDAR_SYNC_INTERVAL, DEFAULT_CALENDAR_SYNC_INTERVAL
        )
        self._fix_timezone: bool = config_entry.data.get(
            CONF_CALENDAR_FIX_TIMEZONE, True
        )
        self._unsub_update: Callable[[], None] | None = None
        self._last_update: datetime | None = None

        # Entity attributes
        self._attr_name = "Grocy calendar"
        self._attr_unique_id = f"{config_entry.entry_id}calendar"
        self._attr_available = True
        self._attr_icon = "mdi:calendar"

        # Add entity_description for coordinator compatibility
        # (even though calendar doesn't use coordinator data)
        self.entity_description = EntityDescription(
            key="calendar",
            name="Grocy calendar",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Grocy device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        # Find events that are currently happening or upcoming
        # An event is "current" if now is between start and end (inclusive)
        # An event is "upcoming" if start is in the future
        current_or_upcoming = [
            event
            for event in self._events
            if event.start <= now <= event.end or event.start > now
        ]

        if not current_or_upcoming:
            # Always return a placeholder event so calendar shows "on" when enabled
            # This allows the sensor to show the count (0) while calendar is "on"
            future_date = now + timedelta(days=365)
            return CalendarEvent(
                summary="No upcoming events",
                start=future_date,
                end=future_date,
            )
        # Return the earliest event (current or upcoming)
        return min(current_or_upcoming, key=lambda e: e.start)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Fetch iCal URL on startup (don't fail if it errors)
        try:
            await self._fetch_ical_url()
        except Exception as error:
            _LOGGER.warning("Error fetching iCal URL during startup: %s", error)
        # Set up periodic updates
        self._schedule_update()
        # Trigger immediate update if entity is enabled
        if self.enabled:
            _LOGGER.debug(
                "Calendar entity enabled on startup, triggering immediate update"
            )
            # Schedule immediate update in the event loop
            self.hass.async_create_task(self._async_update_calendar(dt_util.now()))
        # Write state immediately to ensure correct state when enabled
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

    def _schedule_update(self) -> None:
        """Schedule the next update."""
        if self._unsub_update:
            self._unsub_update()
        # Get current sync interval from config entry
        self._sync_interval_minutes = self._config_entry.data.get(
            CONF_CALENDAR_SYNC_INTERVAL, DEFAULT_CALENDAR_SYNC_INTERVAL
        )
        interval = timedelta(minutes=self._sync_interval_minutes)
        self._unsub_update = async_track_time_interval(
            self.hass, self._async_update_calendar, interval
        )

    async def _async_update_calendar(self, now: datetime) -> None:
        """Update calendar events periodically."""
        # Only update if entity is enabled
        if not self.enabled:
            _LOGGER.debug("Calendar entity is disabled, skipping update")
            return

        if not self._ical_url:
            await self._fetch_ical_url()
            if not self._ical_url:
                # Still mark as available even if URL fetch fails
                # The entity can retry later
                self._attr_available = True
                self.async_write_ha_state()
                return

        # Update events for a wide range (e.g., 1 year back, 1 year forward)
        # Use local timezone
        now = dt_util.now()
        start_date = now - timedelta(days=365)
        end_date = now + timedelta(days=365)
        try:
            await self._update_events(start_date, end_date)
            self._last_update = dt_util.now()
            self._attr_available = True
            self.async_write_ha_state()
        except Exception as error:
            _LOGGER.error("Error updating calendar events: %s", error)
            # Keep entity available even on error, so it can retry
            self._attr_available = True
            self.async_write_ha_state()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        if not self._ical_url:
            await self._fetch_ical_url()

        if not self._ical_url:
            _LOGGER.warning("Unable to fetch iCal URL from Grocy")
            return []

        # Check if we need to refresh events
        should_refresh = False
        if not self._events or self._last_update is None:
            should_refresh = True
        else:
            # Refresh if last update was more than sync interval ago
            # Use local timezone
            now = dt_util.now()
            if self._last_update.tzinfo is None:
                # If last_update is naive, assume local timezone
                local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
                last_update_local = self._last_update.replace(tzinfo=local_tz)
            else:
                last_update_local = dt_util.as_local(self._last_update)
            time_since_update = now - last_update_local
            if time_since_update >= timedelta(minutes=self._sync_interval_minutes):
                should_refresh = True

        if should_refresh:
            # Expand range to ensure we have enough events cached
            expanded_start = start_date - timedelta(days=30)
            expanded_end = end_date + timedelta(days=30)
            try:
                await self._update_events(expanded_start, expanded_end)
            except Exception as error:
                _LOGGER.error("Error fetching calendar events: %s", error)

        # Filter events to requested time range
        return [
            event for event in self._events if start_date <= event.start <= end_date
        ]

    async def _fetch_ical_url(self) -> None:
        """Fetch the iCal sharing link from Grocy API."""
        try:
            url = self._config_entry.data[CONF_URL]
            api_key = self._config_entry.data[CONF_API_KEY]
            port = self._config_entry.data.get(CONF_PORT, 9192)
            verify_ssl = self._config_entry.data.get(CONF_VERIFY_SSL, False)

            (base_url, path) = extract_base_url_and_path(url)

            if path:
                api_url = f"{base_url}:{port}/{path}/api/calendar/ical/sharing-link"
            else:
                api_url = f"{base_url}:{port}/api/calendar/ical/sharing-link"

            headers = {
                "GROCY-API-KEY": api_key,
                "accept": "application/json",
            }

            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)

            async with session.get(api_url, headers=headers) as response:
                if response.status == HTTP_OK:
                    data = await response.json()
                    self._ical_url = data.get("url")
                    _LOGGER.debug("Fetched iCal URL: %s", self._ical_url)
                else:
                    _LOGGER.error("Failed to fetch iCal URL: HTTP %s", response.status)
        except Exception as error:
            _LOGGER.error("Error fetching iCal URL: %s", error)

    def _convert_datetime_to_local(
        self, dt: datetime, summary: str, is_end: bool = False
    ) -> datetime:
        """Convert datetime to local timezone, handling Grocy timezone fix."""
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        if dt.tzinfo is None:
            # Naive datetime - assume UTC and convert to local
            dt_utc = dt.replace(tzinfo=UTC)
            return dt_util.as_local(dt_utc)

        # Has timezone info
        original_dt = dt
        original_tz = dt.tzinfo
        is_utc = (
            dt.tzinfo == UTC
            or str(dt.tzinfo) == "UTC"
            or (hasattr(dt.tzinfo, "zone") and dt.tzinfo.zone == "UTC")
        )

        if self._fix_timezone and is_utc:
            # Fix for Grocy addon: treat UTC as local time
            result = dt.replace(tzinfo=local_tz)
            _LOGGER.debug(
                "Event '%s'%s: Fix timezone enabled - treating UTC as local: %s (tz: %s) -> %s (tz: %s), fix_timezone=%s",
                summary,
                " (end)" if is_end else "",
                original_dt,
                original_tz,
                result,
                result.tzinfo,
                self._fix_timezone,
            )
            return result

        # Standard timezone conversion
        result = dt_util.as_local(dt)
        _LOGGER.debug(
            "Event '%s'%s: Standard timezone conversion: %s (tz: %s) -> %s (tz: %s), fix_timezone=%s",
            summary,
            " (end)" if is_end else "",
            original_dt,
            original_tz,
            result,
            result.tzinfo,
            self._fix_timezone,
        )
        return result

    def _parse_ical_events(self, calendar: icalendar.Calendar) -> list[CalendarEvent]:
        """Parse iCal calendar and return list of CalendarEvent objects."""
        events: list[CalendarEvent] = []

        for component in calendar.walk():
            if component.name == "VEVENT":
                summary = str(component.get("summary", ""))
                start = component.get("dtstart")
                end = component.get("dtend")
                description = str(component.get("description", ""))
                location = str(component.get("location", ""))
                uid = str(component.get("uid", ""))

                _LOGGER.debug(
                    "Parsing event '%s': fix_timezone=%s",
                    summary,
                    self._fix_timezone,
                )

                if start:
                    # Check if this is a date-only (all-day) event
                    is_all_day = not isinstance(start.dt, datetime)

                    # Get local timezone
                    local_tz = dt_util.get_time_zone(self.hass.config.time_zone)

                    # Handle both date and datetime
                    if isinstance(start.dt, datetime):
                        event_start = self._convert_datetime_to_local(start.dt, summary)
                    else:
                        # Date-only events (all-day) - convert to datetime at start of day in local timezone
                        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
                        event_start = datetime.combine(
                            start.dt, datetime.min.time(), tzinfo=local_tz
                        )

                    # Don't filter here - cache all events, filter when needed
                    if end:
                        if isinstance(end.dt, datetime):
                            event_end = self._convert_datetime_to_local(
                                end.dt, summary, is_end=True
                            )
                        else:
                            # Date-only end - for all-day events, end date is exclusive
                            # In iCal, if an event is on Dec 21, end date is Dec 22
                            # So we subtract 1 day and set to end of that day
                            end_date = end.dt
                            if isinstance(end_date, date):
                                # End date is exclusive, so subtract 1 day for the actual end
                                # Then set to end of that day (23:59:59.999999) in local timezone
                                actual_end_date = end_date - timedelta(days=1)
                                event_end = datetime.combine(
                                    actual_end_date,
                                    datetime.max.time(),
                                    tzinfo=local_tz,
                                )
                            else:
                                # Shouldn't happen, but handle it
                                event_end = datetime.combine(
                                    end_date,
                                    datetime.max.time(),
                                    tzinfo=local_tz,
                                )
                    elif is_all_day:
                        # All-day event with no end - ends at end of start day in local timezone
                        event_end = datetime.combine(
                            start.dt,
                            datetime.max.time(),
                            tzinfo=local_tz,
                        )
                    else:
                        # If no end time, assume 1 hour duration
                        event_end = event_start + timedelta(hours=1)

                    events.append(
                        CalendarEvent(
                            summary=summary,
                            start=event_start,
                            end=event_end,
                            description=description,
                            location=location,
                            uid=uid,
                        )
                    )

        # Sort events by start time for better performance
        events.sort(key=lambda e: e.start)
        return events

    async def _update_events(self, start_date: datetime, end_date: datetime) -> None:
        """Update events from iCal URL."""
        if not self._ical_url:
            return

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(self._ical_url) as response:
                if response.status != HTTP_OK:
                    _LOGGER.error("Failed to fetch iCal data: HTTP %s", response.status)
                    return

                ical_data = await response.text()
                # Run icalendar parsing in executor to avoid blocking I/O
                calendar = await self.hass.async_add_executor_job(
                    icalendar.Calendar.from_ical, ical_data
                )

                # Parse events in executor to avoid blocking I/O
                events = await self.hass.async_add_executor_job(
                    self._parse_ical_events, calendar
                )

                self._events = events
                _LOGGER.debug("Fetched %d calendar events", len(events))

        except Exception as error:
            _LOGGER.error("Error parsing iCal data: %s", error)
            self._events = []
