from .constants import DOMAIN, DEFAULT_ICON, MDI_ICONS_MAP, OFF_COLOR, ON_COLOR, BRIGHT_COLOR, normalize_icon, icon_from_state
from .config_flow import find_service

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.core import callback
from homeassistant.loader import async_get_integration

from homeassistant.helpers import event, entity_registry
from homeassistant.exceptions import HomeAssistantError

import logging

_LOGGER = logging.getLogger(__name__)

class Coordinator(DataUpdateCoordinator):

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update,
        )
        self._entry = entry
        self._panel_listeners = []
        self._device_listeners = []
        self._loaded = {"device": None, "template": None}

    async def _async_update(self):
        data = self._entry.as_dict()["data"]
        _LOGGER.debug(f"_async_update: {data}")
        return {
            "available": False,
            "brightness": data.get("brightness", 255),
            "off_brightness": data.get("off_brightness", 1),
            "relays": data.get("relays", [False, False]),
            "component_version": None,
            "device_version": None,
            "display_version": None,
            "variant": None,
        }

    async def async_refresh_maybe(self, entry):
        options = entry.as_dict()["options"]
        if options["device"] != self._loaded["device"]:
            _LOGGER.debug(f"async_refresh_maybe: Full refresh, device has changed")
            await self.async_unload()
            await self.async_load()
        elif options["template"] != self._loaded["template"]:
            _LOGGER.debug(f"async_refresh_maybe: Panel refresh, template has changed")
            self.options = options
            await self.async_refresh_panel()
        else:
            _LOGGER.debug(f"async_refresh_maybe: Ignoring refresh: ")

    def _color_hex_2_565(self, hex_color: str) -> int:
        if hex_color[0] == "#":
            hex_color = hex_color[1:]
        rgb = int(hex_color, 16)
        return (((rgb & 0xf80000) >> 8) + ((rgb & 0xfc00) >> 5) + ((rgb & 0xf8) >> 3))

    def _icon_2_glyph(self, icon: str | None, state=None) -> int:
        if state:
            if icon is None:
                icon = state.attributes.get("icon")
        if icon and icon[:4] == "mdi:":
            icon = icon[4:]
        else:
            icon = normalize_icon(icon_from_state(state)) if state else DEFAULT_ICON
        _LOGGER.debug(f"_icon_2_glyph: icon = {icon}, {state}")
        return 0xAC00 + (MDI_ICONS_MAP.get(icon, 0xF00C0) - 0xF0001)

    async def _async_send_grid_update(self, index: int, *, type_: str="hidden", icon: int=0, name: str="", value: str="", unit: str="", color: int=0):
        data = {
            "index": index,
            "type": type_,
            "icon": icon,
            "name": name,
            "value": value,
            "unit": unit,
            "color": color,
        }
        if svc := self.services.get("update_grid"):
            await self.hass.services.async_call("esphome", svc, data, blocking=False)

    async def _async_send_static_text_update(self, index: int, conf: dict):
        icon = self._icon_2_glyph(conf["icon"]) if "icon" in conf else 0
        color = self._color_hex_2_565(conf.get("color", BRIGHT_COLOR))
        return await self._async_send_text_update(index, conf.get("text", ""), icon, color)

    async def _async_send_text_update(self, index: int, text: str, icon: int=0, color: int=65535):
        data = {
            "index": index,
            "content": text,
            "icon": icon,
            "color": color,
        }
        if svc := self.services.get("update_text"):
            await self.hass.services.async_call("esphome", svc, data, blocking=False)

    async def _async_send_brightness(self):
        value = self.data["brightness"]
        off_value = self.data["off_brightness"]
        if svc := self.services.get("update_backlight"):
            await self.hass.services.async_call("esphome", svc, {
                "value": value if value > 0 else 0,
                "off_value": off_value,
            }, blocking=False)

    async def _async_send_relay_state(self, index, state):
        if svc := self.services.get("update_relay"):
            await self.hass.services.async_call("esphome", svc, {"index": index, "state": state}, blocking=False)

    async def _async_request_metadata(self):
        if svc := self.services.get("send_metadata"):
            await self.hass.services.async_call("esphome", svc, {}, blocking=False)

    async def _async_send_static_item(self, index: int, conf: dict):
        await self._async_send_grid_update(
            index,
            type_="button",
            icon=self._icon_2_glyph(conf.get("icon")),
            name=conf.get("name", ""),
            color=self._color_hex_2_565(conf.get("color", OFF_COLOR)),
        )

    async def _async_update_entity(self, entity_id: str, state):
        _LOGGER.debug(f"_async_update_entity: {entity_id}, {state}")
        idx = 0
        for g in self._config.get("grid", []):
            if g.get("entity_id") == entity_id:
                # Trigger grid cell update
                type_ = g.get("type")
                if state is None:
                    _LOGGER.warn(f"Invalid state: {entity_id}")
                    await self._async_send_grid_update(idx, type_="hidden")
                elif type_ == "button":
                    color = ON_COLOR if state.state == "on" else OFF_COLOR
                    await self._async_send_grid_update(
                        idx,
                        type_="button",
                        icon=self._icon_2_glyph(g.get("icon"), state),
                        name=g.get("name", state.attributes.get("friendly_name", "")),
                        color=self._color_hex_2_565(g.get("color", color)),
                    )
                elif type_ == "entity":
                    await self._async_send_grid_update(
                        idx,
                        type_="entity",
                        icon=self._icon_2_glyph(g.get("icon"), state),
                        name=g.get("name", state.attributes.get("friendly_name", "")),
                        color=self._color_hex_2_565(g.get("color", OFF_COLOR)),
                        value=str(state.state),
                        unit=state.attributes.get("unit_of_measurement", ""),
                    )
                else:
                    _LOGGER.warn(f"Invalid grid config: {g}")
                    await self._async_send_grid_update(idx, type_="hidden")
            idx += 1
        idx = 0
        for t in self._config.get("texts", []):
            if t.get("entity_id") == entity_id:
                await self._async_send_text_update(idx, state.state)
            idx += 1

    async def _async_on_state_change(self, entity_id: str, from_state, to_state):
        _LOGGER.debug(f"_async_on_state_change: {entity_id}")
        await self._async_update_entity(entity_id, to_state)

    async def async_refresh_panel(self, data=None):
        for l in self._panel_listeners:
            l()
        self._panel_listeners = []
        if data is None:
            data = self.options["template_object"]
            self._loaded["template"] = self.options["template"]
        self._config = {
            "grid": [],
            "buttons": [{"relay": 0}, {"relay": 1}],
            "texts": [],
            **data,
        }
        _entity_ids = []
        idx = 0
        for g in self._config.get("grid", []):
            if entity_id := g.get("entity_id"):
                _entity_ids.append(entity_id)
            elif g.get("type") == "button":
                _LOGGER.debug(f"async_refresh_panel: Static item[{idx}]: {g}")
                await self._async_send_static_item(idx, g)
            else:
                await self._async_send_grid_update(idx, type_="hidden")
            idx += 1
        for i in range(idx, 8):
            await self._async_send_grid_update(i, type_="hidden")
        idx = 0
        for t in self._config.get("texts", []):
            if entity_id := t.get("entity_id"):
                _entity_ids.append(entity_id)
            else:
                await self._async_send_static_text_update(idx, t)
            idx += 1
        for i in range(idx, 2):
            await self._async_send_static_text_update(i, {})
        
        if len(_entity_ids):
            self._panel_listeners.append(event.async_track_state_change(self.hass, _entity_ids, action=self._async_on_state_change))
            for _id in _entity_ids:
                await self._async_update_entity(_id, self.hass.states.get(_id))
    
    def _find_device_entity(self, device_id):
        reg = entity_registry.async_get(self.hass)
        entities = entity_registry.async_entries_for_device(reg, device_id)
        if len(entities):
            return entities[0].entity_id
        return None

    async def _async_update_state(self, data: dict):
        self.async_set_updated_data({
            **self.data,
            **data,
        })

    async def _async_update_storage(self, data: dict):
        self.hass.config_entries.async_update_entry(self._entry, data={
            **self._entry.as_dict()["data"],
            **data,
        })

    async def _async_fire_event(self, type_: str, extra: dict | None):
        _LOGGER.debug(f"_async_fire_event: {type_}: {extra}")
        self.hass.bus.async_fire(f"nspanel_ng_{type_}", {
            "device_name": self.options["name"],
            "device_id": self.options["device"],
            **(extra if extra else {}),
            **self._config.get("event_extra", {}),
        })

    async def _async_on_device_state_change(self, _entity_id, _from_state, state):
        _LOGGER.debug(f"_async_on_device_state_change: {state}")
        available = state.state != "unavailable"
        changed = available != self.data["available"]
        await self._async_update_state({
            "available": available,
        })
        if available and changed:
            self.services = self._discover_services()
            await self._async_send_brightness()
            await self._async_send_relay_state(0, self.data["relays"][0])
            await self._async_send_relay_state(1, self.data["relays"][1])
            await self._async_request_metadata()
            await self.async_refresh_panel()
        if changed:
            await self._async_fire_event("connected", { "connected": available })

    def _discover_services(self):
        result = {}
        for name in ("update_grid", "update_backlight", "update_relay", "update_text", "show_cancel_dialog", "send_metadata", "upload_tft"):
            svc = find_service(self.hass, self.options["name"], name)
            if not svc:
                _LOGGER.warn(f"Failed to find service: {name}")
            else:
                result[name] = svc
        return result

    def _get_config_section(self, section: str, index: int) -> dict | None:
        if self._config and section in self._config:
            items = self._config[section]
            if len(items) > index and index >= 0:
                return items[index]
        return None

    async def _async_execute_action(self, entity_id: str, service: str, extra: dict | None):
        [domain, name] = entity_id.split(".")
        action = "homeassistant.toggle"
        if domain == "script":
            action = entity_id
        elif domain == "automation":
            action = "automation.trigger"
        elif domain == "scene":
            action = "scene.apply"
        elif domain == "button":
            action = "button.press"
        if service:
            action = service
        
        _LOGGER.debug(f"_async_execute_action: action = {action}, entity = {entity_id}, extra={extra}")
        [domain, name] = action.split(".")
        await self.hass.services.async_call(domain, name, {
            "entity_id": entity_id,
            **extra,
        }, blocking=False)

    async def _async_handle_grid_click(self, index: int, mode: str):
        conf = self._get_config_section("grid", index)
        if conf:
            if entity_id := conf.get("target", conf.get("entity_id")):
                await self._async_execute_action(entity_id, conf.get("service"), conf.get("extra", {}))
                return
        await self._async_fire_event("grid_click", {
            "index": index,
            "mode": mode,
            **(conf.get("extra", {}) if conf else {})
        })

    async def _async_handle_button_click(self, index: int, mode: str):
        conf = self._get_config_section("buttons", index)
        if conf:
            if "relay" in conf:
                _LOGGER.debug(f"_async_handle_button_click: toggle relay: {index}")
                await self.set_relay(index, None)
                return
            if entity_id := conf.get("target"):
                await self._async_execute_action(entity_id, conf.get("service"), conf.get("extra", {}))
                return
        await self._async_fire_event("button_click", {
            "index": index,
            "mode": mode,
            **(conf.get("extra", {}) if conf else {})
        })

    async def _async_on_device_event(self, event):
        _LOGGER.debug(f"_async_on_device_event: {event}")
        type_ = event.data.get("type")
        if type_ == "wake":
            await self.set_brightness(self.brightness, True)
        elif type_ == "grid_click":
            await self._async_handle_grid_click(int(event.data.get("cell", -1)), event.data.get("mode"))
        elif type_ == "button_click":
            await self._async_handle_button_click(int(event.data.get("index", -1)), event.data.get("mode"))
        elif type_ == "metadata":
            await self._async_update_state({
                "device_version": event.data.get("component_version"),
                "display_version": event.data.get("display_version"),
                "variant": event.data.get("display_type"),
            })

    @callback
    def _event_filter(self, event) -> bool:
        return event.data.get("device_id") == self.options["device"]

    async def async_load(self):
        component = await async_get_integration(self.hass, DOMAIN)
        await self._async_update_state({
            "component_version": component.manifest["version"]
        })
        self.options = self._entry.as_dict()["options"]
        _LOGGER.debug(f"async_load: {self.options}")
        device_entity = self._find_device_entity(self.options["device"])
        self._loaded["device"] = self.options["device"]
        if device_entity:
            self._device_listeners.append(event.async_track_state_change(self.hass, [device_entity], action=self._async_on_device_state_change))
            await self._async_on_device_state_change(device_entity, None, self.hass.states.get(device_entity))
        else:
            _LOGGER.warn(f"Couldn't find any device entity")
        self._device_listeners.append(self.hass.bus.async_listen("esphome.NSPanel_NG_Device_Event", self._async_on_device_event, self._event_filter))


    async def async_unload(self):
        _LOGGER.debug(f"async_unload: {self.options}")
        for l in self._device_listeners:
            l()
        self._device_listeners = []
        for l in self._panel_listeners:
            l()
        self._panel_listeners = []
        await self._async_update_state({
            "available": False,
        })

    @property
    def brightness(self):
        return self.data["brightness"]

    @property
    def off_brightness(self):
        return self.data["off_brightness"]

    def relay(self, index: int):
        return self.data["relays"][index]

    async def set_relay(self, index: int, state: bool | None):
        data = list(self.data["relays"])
        if state is None:
            state = not data[index]
        data[index] = state
        await self._async_update_state({"relays": data})
        await self._async_update_storage({"relays": data})
        await self._async_send_relay_state(index, state)

    async def set_brightness(self, value: int, set_on: bool | None = None):
        if set_on == True:
            if value < 0:
                value = -value
            elif value == 0:
                value = 255
        elif set_on == False:
            if value > 0:
                value = -value
        await self._async_update_state({"brightness": value})
        await self._async_update_storage({"brightness": value})
        await self._async_send_brightness()

    async def set_off_brightness(self, value: int):
        await self._async_update_state({"off_brightness": value})
        await self._async_update_storage({"off_brightness": value})
        await self._async_send_brightness()

    async def async_upload_tft(self, path: str = None):
        variant = self.data["variant"]
        if variant is None:
            raise HomeAssistantError("Device not connected")
        svc = self.services.get("upload_tft")
        if not svc:
            raise HomeAssistantError("Service not discovered")

        if path is None:
            url = self.options["hass_url"]
            path = f"{url}/nspanel_ng/tft/nspanel_ng_{variant}.tft"

        _LOGGER.debug(f"async_upload_tft: Uploading TFT: {path}")
        await self.hass.services.async_call("esphome", svc, { "path": path }, blocking=False)
    
    async def async_service_update_panel(self, data: dict):
        _LOGGER.debug(f"async_service_update_panel: {data}")
        await self.async_refresh_panel(data.get("template"))

    async def async_service_upload_tft(self, data: dict):
        _LOGGER.debug(f"async_service_upload_tft: {data}")
        await self.async_upload_tft(data["path"])

    
class BaseEntity(CoordinatorEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        # self._attr_available = False

    def with_name(self, suffix: str, name: str):
        self._attr_has_entity_name = True
        entry_id = self.coordinator._entry.entry_id
        self._attr_unique_id = f"ns_panel_ng_{entry_id}_{suffix}"
        self._attr_name = name
        return self

    @property
    def device_info(self):
        return {
            "identifiers": {
                ("mac", self.coordinator.options["mac"]), 
                ("device", self.coordinator.options["name"])
            },
            "name": self.coordinator.options["device_name"],
        }

    @property
    def available(self):
        return self.coordinator.data["available"]
