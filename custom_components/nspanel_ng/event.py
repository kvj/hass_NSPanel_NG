from homeassistant.components import event
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity, CoordinatorEvent
from .constants import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_ClickEvent(coordinator)])

class _ClickEvent(BaseEntity, event.EventEntity, CoordinatorEvent):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name("click", "Click Event")
        self._attr_event_types = ["grid_click", "button_click"]
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self) -> None:
        self.coordinator.add_event_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.remove_event_listener(self)

    async def async_on_event(self, event, data):
        _LOGGER.debug(f"_async_on_event: {event} {data}")
        if event in self._attr_event_types:
            self._trigger_event(event, {
                **data
            })
            self.async_write_ha_state()
