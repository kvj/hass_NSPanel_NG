from homeassistant.components import number
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity
from .constants import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_OffBrightness(coordinator)])

class _OffBrightness(BaseEntity, number.NumberEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name(f"conf_off_bri", "Sleep Brightness")
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:power-sleep"
        self._attr_mode = "slider"
        self._attr_native_max_value = 100
        self._attr_native_min_value = 0
        self._attr_native_step = 1.0
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self):
        return self.coordinator.off_brightness

    async def async_set_native_value(self, value):
        await self.coordinator.set_off_brightness(int(value))
