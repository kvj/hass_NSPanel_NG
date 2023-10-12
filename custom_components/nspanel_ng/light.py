from homeassistant.components import light
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity
from .constants import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_BrightnessLight(coordinator)])

class _BrightnessLight(BaseEntity, light.LightEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name("brightness", "Backlight Brightness")
        self._attr_icon = "mdi:brightness-6"
        self._attr_color_mode = light.ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {light.ColorMode.BRIGHTNESS}
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return self.brightness > 0

    @property
    def brightness(self) -> int:
        return self.coordinator.brightness if self.coordinator.brightness > 0 else 0

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug(f"_BrightnessLight: turn ON: {kwargs}")
        if "brightness" in kwargs:
            await self.coordinator.set_brightness(kwargs["brightness"], True)
        else:
            await self.coordinator.set_brightness(self.coordinator.brightness, True)

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug(f"_BrightnessLight: turn OFF: {kwargs}")
        await self.coordinator.set_brightness(self.coordinator.brightness, False)


