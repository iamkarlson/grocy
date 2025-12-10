"""Entity for Grocy."""

from __future__ import annotations

import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_URL, DOMAIN, NAME, VERSION
from .coordinator import GrocyCoordinatorData, GrocyDataUpdateCoordinator
from .json_encoder import CustomJSONEncoder


class GrocyEntity(CoordinatorEntity[GrocyDataUpdateCoordinator]):
    """Grocy base entity definition."""

    def __init__(
        self,
        coordinator: GrocyDataUpdateCoordinator,
        description: EntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._attr_name = description.name
        self._attr_unique_id = f"{config_entry.entry_id}{description.key.lower()}"
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Grocy device information."""
        url = self.coordinator.config_entry.data.get(CONF_URL, "")
        device_name = f"{NAME} ({url})" if url else NAME
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=device_name,
            manufacturer=NAME,
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def extra_state_attributes(self) -> GrocyCoordinatorData | None:
        """Return the extra state attributes."""
        data = self.coordinator.data[self.entity_description.key]
        if data and hasattr(self.entity_description, "attributes_fn"):
            return json.loads(
                json.dumps(
                    self.entity_description.attributes_fn(data),
                    cls=CustomJSONEncoder,
                )
            )

        return None
