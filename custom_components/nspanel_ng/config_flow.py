from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector
from homeassistant.helpers import device_registry, network
from homeassistant.util.yaml.loader import parse_yaml
from homeassistant.components import webhook

from .constants import DOMAIN

import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)

def find_service(hass, device_name: str, name: str) -> str | None:
    services = hass.services.async_services()["esphome"]
    svc_name = f"{device_name.replace('-', '_')}_{name}"
    if svc_name in services:
        return svc_name
    return None

def _validate(hass, input: dict) -> (str | None, dict):
    result = {}
    dreg = device_registry.async_get(hass)
    device = dreg.async_get(input["device"])
    if device is None:
        return "invalid_device", result
    conf_entry = hass.config_entries.async_get_entry(list(device.config_entries)[0])
    if conf_entry is None:
        return "invalid_device", result
    result["device"] = input["device"]
    result["hass_url"] = input["hass_url"]
    result["webhook"] = input["webhook"]
    conns = {val[0]: val[1] for val in device.connections}
    _LOGGER.debug(f"Connections: {conns}")
    if "mac" not in conns:
        return "invalid_device", result
    result["mac"] = conns["mac"]
    if "device_name" not in conf_entry.data:
        return "invalid_device", result
    result["name"] = conf_entry.data["device_name"]
    result["device_name"] = device.name

    try:
        yaml_obj = parse_yaml(input["template"])
        result["template"] = input["template"]
        result["template_object"] = yaml_obj
    except:
        _LOGGER.exception(f"Invalid yaml:")
        return "invalid_template", result
    return None, result

def _get_local_hass_url(hass) -> str:
    try:
        return network.get_url(hass, prefer_external=False, allow_ip=True)
    except:
        return "http://your-local-hass-url"

def _create_schema(hass, input: dict):
    hook_id =input["webhook"] if "webhook" in input else webhook.async_generate_id()
    schema = vol.Schema({
        vol.Required("device", default=input.get("device")): selector({
            "device": {
                "filter": {
                    "integration": "esphome"
                }
            }
        }),
        vol.Required("hass_url", default=input.get("hass_url", _get_local_hass_url(hass))): selector({
            "text": { "type": "url" }
        }),
        vol.Required("webhook", description={"suggested_value": hook_id}): selector({
            "text": { "type": "url" }
        }),
        vol.Required("template", default=input.get("template")): selector({
            "template": {}
        }),
    })
    return schema

class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):


    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_create_schema(self.hass, {
                "template": "# Extend as needed:\ngrid: []\n"
            }))
        else:
            _LOGGER.debug(f"Input: {user_input}")
            err, data = _validate(self.hass, user_input)
            if err is None:
                await self.async_set_unique_id(data["name"])
                self._abort_if_unique_id_configured()
                _LOGGER.debug(f"Ready to save: {data}")
                return self.async_create_entry(title=data["device_name"], options=data, data={})
            else:
                return self.async_show_form(step_id="user", data_schema=_create_schema(self.hass, user_input), errors=dict(base=err))

    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self, entry):
        self.config_entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is None:
            _LOGGER.debug(f"Making options: {self.config_entry.as_dict()}")
            return self.async_show_form(step_id="init", data_schema=_create_schema(self.hass, self.config_entry.as_dict()["options"]))
        else:
            _LOGGER.debug(f"Input: {user_input}")
            err, data = _validate(self.hass, user_input)
            if err is None:
                _LOGGER.debug(f"Ready to update: {data}")
                result = self.async_create_entry(title="", data=data)
                return result
            else:
                return self.async_show_form(step_id="init", data_schema=_create_schema(self.hass, user_input), errors=dict(base=err))
