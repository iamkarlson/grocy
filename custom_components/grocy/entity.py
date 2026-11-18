"""Entity for Grocy."""

from __future__ import annotations

import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import GrocyCoordinatorData, GrocyDataUpdateCoordinator
from .json_encoder import CustomJSONEncoder

# The list attributes grow with the Grocy data. When the attributes of a state
# are bigger than 16 KB, the recorder stores them as empty, without the unit,
# and the statistics then log "unit is changing". Keep the lists out of the
# recorder. The live state still has them.
LIST_ATTRIBUTES = frozenset(
    {
        "batteries",
        "chores",
        "expired_products",
        "expiring_products",
        "meals",
        "missing_products",
        "overdue_batteries",
        "overdue_chores",
        "overdue_products",
        "overdue_tasks",
        "products",
        "recipes",
        "tasks",
    }
)


class GrocyEntity(CoordinatorEntity[GrocyDataUpdateCoordinator]):
    """Grocy base entity definition."""

    _attr_has_entity_name = True
    _unrecorded_attributes = LIST_ATTRIBUTES

    def __init__(
        self,
        coordinator: GrocyDataUpdateCoordinator,
        description: EntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}{description.key.lower()}"
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Grocy device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=NAME,
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
