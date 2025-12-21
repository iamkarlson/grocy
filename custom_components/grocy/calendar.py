"""Calendar platform for Grocy."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import icalendar
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_KEY,
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
        self._unsub_update: Callable[[], None] | None = None
        self._last_update: datetime | None = None

        # Entity attributes
        self._attr_name = "Grocy calendar"
        self._attr_unique_id = f"{config_entry.entry_id}calendar"
        self._attr_available = True
        self._attr_icon = "mdi:calendar"

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

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        # Fetch iCal URL on startup (don't fail if it errors)
        try:
            await self._fetch_ical_url()
        except Exception as error:
            _LOGGER.warning("Error fetching iCal URL during startup: %s", error)
        # Set up periodic updates
        self._schedule_update()

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
        if not self._ical_url:
            await self._fetch_ical_url()
            if not self._ical_url:
                # Still mark as available even if URL fetch fails
                # The entity can retry later
                self._attr_available = True
                self.async_write_ha_state()
                return

        # Update events for a wide range (e.g., 1 year back, 1 year forward)
        # Use timezone-aware datetime
        now_utc = dt_util.utcnow()
        start_date = now_utc - timedelta(days=365)
        end_date = now_utc + timedelta(days=365)
        try:
            await self._update_events(start_date, end_date)
            self._last_update = dt_util.utcnow()
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
        if not self._events:
            should_refresh = True
        elif self._last_update is None:
            should_refresh = True
        else:
            # Refresh if last update was more than sync interval ago
            # Use timezone-aware datetime
            now_utc = dt_util.utcnow()
            if self._last_update.tzinfo is None:
                # If last_update is naive, assume UTC
                last_update_utc = self._last_update.replace(tzinfo=timezone.utc)
            else:
                last_update_utc = self._last_update
            time_since_update = now_utc - last_update_utc
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
        filtered_events = [
            event
            for event in self._events
            if start_date <= event.start <= end_date
        ]
        return filtered_events

    async def _fetch_ical_url(self) -> None:
        """Fetch the iCal sharing link from Grocy API."""
        try:
            url = self._config_entry.data[CONF_URL]
            api_key = self._config_entry.data[CONF_API_KEY]
            port = self._config_entry.data.get(CONF_PORT, 9192)
            verify_ssl = self._config_entry.data.get(CONF_VERIFY_SSL, False)

            (base_url, path) = extract_base_url_and_path(url)

            if path:
                api_url = (
                    f"{base_url}:{port}/{path}/api/calendar/ical/sharing-link"
                )
            else:
                api_url = f"{base_url}:{port}/api/calendar/ical/sharing-link"

            headers = {
                "GROCY-API-KEY": api_key,
                "accept": "application/json",
            }

            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)

            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self._ical_url = data.get("url")
                    _LOGGER.debug("Fetched iCal URL: %s", self._ical_url)
                else:
                    _LOGGER.error(
                        "Failed to fetch iCal URL: HTTP %s", response.status
                    )
        except Exception as error:
            _LOGGER.error("Error fetching iCal URL: %s", error)

    async def _update_events(
        self, start_date: datetime, end_date: datetime
    ) -> None:
        """Update events from iCal URL."""
        if not self._ical_url:
            return

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(self._ical_url) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch iCal data: HTTP %s", response.status
                    )
                    return

                ical_data = await response.text()
                calendar = icalendar.Calendar.from_ical(ical_data)

                events: list[CalendarEvent] = []

                for component in calendar.walk():
                    if component.name == "VEVENT":
                        summary = str(component.get("summary", ""))
                        start = component.get("dtstart")
                        end = component.get("dtend")
                        description = str(component.get("description", ""))
                        location = str(component.get("location", ""))
                        uid = str(component.get("uid", ""))

                        if start:
                            # Handle both date and datetime
                            if isinstance(start.dt, datetime):
                                event_start = start.dt
                                # Ensure timezone-aware
                                if event_start.tzinfo is None:
                                    # Assume UTC if no timezone info
                                    event_start = event_start.replace(tzinfo=timezone.utc)
                            else:
                                # Date-only events - convert to datetime at midnight UTC
                                event_start = datetime.combine(
                                    start.dt, datetime.min.time(), tzinfo=timezone.utc
                                )

                            # Filter events within the requested time range
                            if start_date <= event_start <= end_date:
                                if end:
                                    if isinstance(end.dt, datetime):
                                        event_end = end.dt
                                        # Ensure timezone-aware
                                        if event_end.tzinfo is None:
                                            # Assume UTC if no timezone info
                                            event_end = event_end.replace(tzinfo=timezone.utc)
                                    else:
                                        # Date-only end - convert to datetime at end of day UTC
                                        event_end = datetime.combine(
                                            end.dt, datetime.max.time(), tzinfo=timezone.utc
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

                self._events = events
                _LOGGER.debug("Fetched %d calendar events", len(events))

        except Exception as error:
            _LOGGER.error("Error parsing iCal data: %s", error)
            self._events = []
