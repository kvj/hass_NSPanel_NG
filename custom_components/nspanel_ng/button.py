from homeassistant.components import button
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity
from .constants import DOMAIN


async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_RefreshButton(coordinator), _UploadTFTButton(coordinator)])

class _RefreshButton(BaseEntity, button.ButtonEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name("diag_refresh", "Refresh")
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_panel()
        
class _UploadTFTButton(BaseEntity, button.ButtonEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name("config_upload_tft", "Upload TFT")
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:file-refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_upload_tft()
