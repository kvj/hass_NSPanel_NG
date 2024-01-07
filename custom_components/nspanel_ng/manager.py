from .constants import DOMAIN, DEFAULT_ICON, MDI_ICONS_MAP, OFF_COLOR, ON_COLOR, BRIGHT_COLOR, DISABLED_COLOR, normalize_icon, icon_from_state
from .config_flow import find_service

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.core import callback
from homeassistant.loader import async_get_integration

from homeassistant.helpers import event, entity_registry, template
from homeassistant.exceptions import HomeAssistantError

import copy
import logging

_LOGGER = logging.getLogger(__name__)

class CoordinatorEvent:

    async def async_on_event(self, event: str, data: dict):
        pass

    async def async_on_pixels(self, pixels: list):
        pass

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
        self._event_listeners = []
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

    def _color_hex_2_565(self, hex_color: str, def_color: str=None) -> int:
        if not hex_color:
            hex_color = def_color
        if hex_color[0] == "#":
            hex_color = hex_color[1:]
        rgb = int(hex_color, 16)
        return (((rgb & 0xf80000) >> 8) + ((rgb & 0xfc00) >> 5) + ((rgb & 0xf8) >> 3))

    def _icon_2_glyph(self, icon: str | None, state=None) -> int:
        if state:
            if not icon:
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

    async def _async_send_static_text_update(self, index: int, conf: dict | None, state: dict | None=None):
        if not conf:
            return await self._async_send_text_update(index, "", 0, 0)
        icon_str = template.render_complex(conf["icon_"], {"this": state})
        icon = self._icon_2_glyph(icon_str) if icon_str else 0
        color = self._color_hex_2_565(template.render_complex(conf["color_"], {"this": state}), BRIGHT_COLOR)
        if "text" in conf or not state:
            text = template.render_complex(conf["text_"], {"this": state})
        else:
            text = state.state
        return await self._async_send_text_update(index, text, icon, color)

    async def _async_send_text_update(self, index: int, text: str, icon: int=0, color: int=65535):
        data = {
            "index": index,
            "content": text,
            "icon": icon,
            "color": color,
        }
        if svc := self.services.get("update_text"):
            await self.hass.services.async_call("esphome", svc, data, blocking=False)

    async def _async_send_indicator_update(self, icon: int=0, color: int=65535, visibility: int=0):
        data = {
            "icon": icon,
            "color": color,
            "visibility": visibility
        }
        if svc := self.services.get("update_center_icon"):
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
            icon=self._icon_2_glyph(template.render_complex(conf["icon_"])),
            name=template.render_complex(conf["name_"]),
            color=self._color_hex_2_565(template.render_complex(conf["color_"]), OFF_COLOR),
        )

    def _state_2_color(self, state: str | None) -> str:
        if state == "undefined":
            return DISABLED_COLOR
        return ON_COLOR if state == "on" else OFF_COLOR

    async def _async_update_indicator(self):
        for i in self._config.get("indicator", []):
            state = None
            is_on = False
            if entity_id := i.get("entity_id"):
                state = self.hass.states.get(entity_id)
                is_on = state and state.state == "on"
                if not is_on:
                    continue
            visibility = template.render_complex(i["blink_"], {"this": state}) if "blink" in i else -1
            if visibility:
                visibility = int(visibility)
            icon = self._icon_2_glyph(template.render_complex(i["icon_"], {"this": state}), state)
            def_color = ON_COLOR if is_on else OFF_COLOR
            color = self._color_hex_2_565(template.render_complex(i["color_"], {"this": state}), def_color)
            await self._async_send_indicator_update(icon, color, visibility)
            return
        await self._async_send_indicator_update()


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
                    def_color = self._state_2_color(state.state)
                    icon = self._icon_2_glyph(template.render_complex(g["icon_"], {"this": state}), state)
                    name = template.render_complex(g["name_"], {"this": state}) if "name" in g else state.attributes.get("friendly_name", "")
                    color = self._color_hex_2_565(template.render_complex(g["color_"], {"this": state}), def_color)

                    await self._async_send_grid_update(
                        idx,
                        type_="button",
                        icon=icon,
                        name=name,
                        color=color,
                    )
                elif type_ == "entity":
                    icon = self._icon_2_glyph(template.render_complex(g["icon_"], {"this": state}), state)
                    name = template.render_complex(g["name_"], {"this": state}) if "name" in g else state.attributes.get("friendly_name", "")
                    color = self._color_hex_2_565(template.render_complex(g["color_"], {"this": state}), OFF_COLOR)
                    value = template.render_complex(g["value_"], {"this": state}) if "value" in g else str(state.state)
                    unit = template.render_complex(g["unit_"], {"this": state}) if "unit" in g else state.attributes.get("unit_of_measurement", "")
                    await self._async_send_grid_update(
                        idx,
                        type_="entity",
                        icon=icon,
                        name=name,
                        color=color,
                        value=value,
                        unit=unit,
                    )
                else:
                    _LOGGER.warn(f"Invalid grid config: {g}")
                    await self._async_send_grid_update(idx, type_="hidden")
            idx += 1
        idx = 0
        for t in self._config.get("texts", []):
            if t.get("entity_id") == entity_id:
                await self._async_send_static_text_update(idx, t, state)
            idx += 1
        for i in self._config.get("indicator", []):
            if i.get("entity_id") == entity_id:
                await self._async_update_indicator()
                break

    async def _async_on_state_change(self, entity_id: str, from_state, to_state):
        _LOGGER.debug(f"_async_on_state_change: {entity_id}")
        await self._async_update_entity(entity_id, to_state)


    async def async_refresh_panel(self, data=None):
        def _as_template(obj, names):
            for n in names:
                obj[f"{n}_"] = template.Template(str(obj.get(n, "")), self.hass)
        for l in self._panel_listeners:
            l()
        self._panel_listeners = []
        if data is None:
            data = copy.deepcopy(self.options["template_object"])
            self._loaded["template"] = self.options["template"]
        self._config = {
            "grid": [],
            "buttons": [{"relay": 0}, {"relay": 1}],
            "texts": [],
            "indicator": [],
            **data,
        }

        _entity_ids = []
        idx = 0
        for g in self._config.get("grid", []):
            _as_template(g, ("icon", "name", "color", "target", "value", "unit"))
            if entity_id := g.get("entity_id"):
                _entity_ids.append(entity_id)
            elif g.get("type") == "button":
                _LOGGER.debug(f"async_refresh_panel: Static item[{idx}]: {g}")
                await self._async_send_static_item(idx, g)
            else:
                await self._async_send_grid_update(idx, type_="hidden")
            idx += 1
        for i in range(idx, 7):
            await self._async_send_grid_update(i, type_="hidden")
        idx = 0
        for t in self._config.get("texts", []):
            _as_template(t, ("icon", "color", "text"))
            if entity_id := t.get("entity_id"):
                _entity_ids.append(entity_id)
            else:
                await self._async_send_static_text_update(idx, t)
            idx += 1
        for i in range(idx, 2):
            await self._async_send_static_text_update(i, None)
        has_indicator_entity = False
        for i in self._config.get("indicator", []):
            _as_template(i, ("icon", "color", "blink"))
            if entity_id := i.get("entity_id"):
                has_indicator_entity = True
                _entity_ids.append(entity_id)
        if len(_entity_ids):
            self._panel_listeners.append(event.async_track_state_change(self.hass, _entity_ids, action=self._async_on_state_change))
            for _id in _entity_ids:
                await self._async_update_entity(_id, self.hass.states.get(_id))
        if not has_indicator_entity:
            await self._async_update_indicator()
    
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
        for name in ("update_grid", "update_backlight", "update_relay", "update_text", "show_cancel_dialog", "send_metadata", "upload_tft", "play_sound", "update_center_icon", "update_pixels"):
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
        for l in self._event_listeners:
            await l.async_on_event("grid_click", {
                "index": index,
                "mode": mode,
                **(conf.get("extra", {}) if conf else {})
            })
        if conf and conf.get("tap", "single") == mode:
            if entity_id := template.render_complex(conf["target_"]) if "target" in conf else conf.get("entity_id"):
                await self._async_execute_action(entity_id, conf.get("service"), conf.get("extra", {}))
                return
        await self._async_fire_event("grid_click", {
            "index": index,
            "mode": mode,
            **(conf.get("extra", {}) if conf else {})
        })

    async def _async_handle_button_click(self, index: int, mode: str):
        conf = self._get_config_section("buttons", index)
        for l in self._event_listeners:
            await l.async_on_event("button_click", {
                "index": index,
                "mode": mode,
                **(conf.get("extra", {}) if conf else {})
            })
        if conf and conf.get("tap", "single") == mode:
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
        svc = self.services.get("upload_tft")
        if not svc:
            raise HomeAssistantError("Service not discovered")
        if path is None:
            variant = self.data["variant"]
            if variant is None:
                raise HomeAssistantError("Device not connected")
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

    async def async_service_play_sound(self, data: dict):
        svc = self.services.get("play_sound")
        if not svc:
            raise HomeAssistantError("Service not discovered")
        await self.hass.services.async_call("esphome", svc, { "rtttl_content": data["sound"] }, blocking=False)

    async def async_service_update_pixels(self, data: dict):
        _LOGGER.debug(f"async_service_update_pixels(): {data}")
        svc = self.services.get("update_pixels")
        if not svc:
            raise HomeAssistantError("Service not discovered")
        colors = []
        color_names = []
        for row in data.get("rows", []):
            for c in row.lower().split(" "):
                if c in ("xxxxxx", "#xxxxxx", "xxx", "#xxx"):
                    colors.append(-1)
                    color_names.append(None)
                else:
                    colors.append(self._color_hex_2_565(c))
                    color_names.append(c if c[0] == "#" else f"#{c}")
        await self.hass.services.async_call("esphome", svc, { "pixels": colors }, blocking=False)
        for l in self._event_listeners:
            await l.async_on_pixels(color_names)

    def add_event_listener(self, listener):
        self._event_listeners.append(listener)

    def remove_event_listener(self, listener):
        try:
            self._event_listeners.remove(listener)
        except:
            pass

    
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
