from __future__ import annotations
from .constants import DOMAIN, PLATFORMS
from .manager import Coordinator
from .public import locate_dir
# from .coordinator import DeviceCoordinator

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import service
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import logging

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)

async def _async_update_entry(hass, entry):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    await coordinator.async_refresh_maybe(entry)

async def async_setup_entry(hass: HomeAssistant, entry):
    data = entry.as_dict()["data"]

    coordinator = Coordinator(hass, entry)
    hass.data[DOMAIN]["devices"][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_entry))
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_load()

    for p in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, p)
        )
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    for p in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, p)
    await coordinator.async_unload()
    hass.data[DOMAIN]["devices"].pop(entry.entry_id)
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data[DOMAIN] = {"devices": {}}

    hass.http.register_static_path("/nspanel_ng/tft", f"{locate_dir()}/tft", cache_headers=False)

    async def async_update_panel(call):
        for entry_id in await service.async_extract_config_entry_ids(hass, call):
            if coordinator := hass.data[DOMAIN]["devices"].get(entry_id):
                await coordinator.async_service_update_panel(call.data)
    hass.services.async_register(DOMAIN, "update_panel", async_update_panel)

    async def async_upload_tft(call):
        for entry_id in await service.async_extract_config_entry_ids(hass, call):
            if coordinator := hass.data[DOMAIN]["devices"].get(entry_id):
                await coordinator.async_service_upload_tft(call.data)
    hass.services.async_register(DOMAIN, "upload_tft", async_upload_tft)

    async def async_play_sound(call):
        for entry_id in await service.async_extract_config_entry_ids(hass, call):
            if coordinator := hass.data[DOMAIN]["devices"].get(entry_id):
                await coordinator.async_service_play_sound(call.data)
    hass.services.async_register(DOMAIN, "play_sound", async_play_sound)
    return True
