from homeassistant.components import switch
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity
from .constants import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_RelaySwitch(coordinator, 0), _RelaySwitch(coordinator, 1), _Screensaver(coordinator)])

class _RelaySwitch(BaseEntity, switch.SwitchEntity):

    def __init__(self, coordinator, index: int):
        super().__init__(coordinator)
        self.index = index
        self._attr_device_class = "switch"
        self.with_name(f"relay_{index}", "Left" if index == 0 else "Right")

    @property
    def is_on(self) -> bool:
        return self.coordinator.relay(self.index)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.set_relay(self.index, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.set_relay(self.index, False)


class _Screensaver(BaseEntity, switch.SwitchEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_device_class = "switch"
        self._attr_icon = "mdi:monitor-star"
        self.with_name(f"screensaver", "Screensaver")
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return self.coordinator.screensaver

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_screensaver(True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_screensaver(False)
