from homeassistant.components import sensor
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity
from .constants import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_ComponentVersion(coordinator), _DeviceVersion(coordinator), _DisplayVersion(coordinator)])

class _ComponentVersion(BaseEntity, sensor.SensorEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name(f"diag_cmp_version", "Component Version")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:puzzle"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data["component_version"]

class _DeviceVersion(BaseEntity, sensor.SensorEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name(f"diag_dev_version", "Device Version")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:chip"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data["device_version"]

class _DisplayVersion(BaseEntity, sensor.SensorEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name(f"diag_display_version", "TFT Version")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:overscan"

    @property
    def native_value(self) -> str | None:
        version = self.coordinator.data["display_version"]
        variant = self.coordinator.data["variant"]
        if version is not None and variant is not None:
            return f"{version} / {variant.upper()}"
        return None
