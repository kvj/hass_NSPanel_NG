import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import nextion, switch, binary_sensor, api, rtttl

from esphome.const import (
    CONF_ID,
    CONF_NAME,
)

CODEOWNERS = ["@kvj"]
DEPENDENCIES = []
AUTO_LOAD = ["json"]

MULTI_CONF = False

CONF_DISPLAY = "display"
CONF_API = "api"
CONF_RELAY1 = "relay1"
CONF_RELAY2 = "relay2"
CONF_BUTTON1 = "button1"
CONF_BUTTON2 = "button2"
CONF_VARIANT = "variant"
CONF_RTTTL = "rtttl"

_ns = cg.esphome_ns.namespace("nspanel_ng")
_cls = _ns.class_("NSPanelNG", cg.Component)

CONFIG_SCHEMA = (
    cv.Schema({
        cv.GenerateID(): cv.declare_id(_cls),
        cv.GenerateID(CONF_DISPLAY): cv.use_id(nextion.Nextion),
        cv.GenerateID(CONF_API): cv.use_id(api.APIServer),
        cv.GenerateID(CONF_RELAY1): cv.use_id(switch.Switch),
        cv.GenerateID(CONF_RELAY2): cv.use_id(switch.Switch),
        cv.GenerateID(CONF_BUTTON1): cv.use_id(binary_sensor.BinarySensor),
        cv.GenerateID(CONF_BUTTON2): cv.use_id(binary_sensor.BinarySensor),
        cv.Required(CONF_VARIANT): cv.string,
        cv.GenerateID(CONF_RTTTL): cv.use_id(rtttl.Rtttl),
    })
    .extend(cv.COMPONENT_SCHEMA)
)

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    cg.add(var.set_variant(config[CONF_VARIANT]))
    cg.add(var.set_display(await cg.get_variable(config[CONF_DISPLAY])))
    cg.add(var.set_api_server(await cg.get_variable(config[CONF_API])))
    cg.add(var.set_relays(await cg.get_variable(config[CONF_RELAY1]), await cg.get_variable(config[CONF_RELAY2])))
    cg.add(var.set_buttons(await cg.get_variable(config[CONF_BUTTON1]), await cg.get_variable(config[CONF_BUTTON2])))
    cg.add(var.set_rtttl_player(await cg.get_variable(config[CONF_RTTTL])))
    await cg.register_component(var, config)
