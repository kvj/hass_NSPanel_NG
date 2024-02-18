from homeassistant.components import camera
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity, CoordinatorEvent
from .constants import DOMAIN

from datetime import datetime
import math

from PIL import Image, ImageDraw
import io

import logging
_LOGGER = logging.getLogger(__name__)

PIXELS_GAP = 8
PIXELS_SIZE = 400

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_Pixels(coordinator)])

class _Pixels(BaseEntity, camera.Camera, CoordinatorEvent):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        camera.Camera.__init__(self)
        self.with_name("pixels", "Pixels")
        self._attr_icon = "mdi:grid"
        self._attr_supported_features = camera.CameraEntityFeature(1)
        self._attr_is_on = False
        self._colors = []

    async def async_added_to_hass(self) -> None:
        self.coordinator.add_event_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.remove_event_listener(self)

    async def async_on_pixels(self, colors):
        _LOGGER.debug(f"async_on_pixels() New colors array = {len(colors)}")
        self._colors = colors
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        w = width if width else PIXELS_SIZE
        h = height if height else PIXELS_SIZE
        # _LOGGER.debug(f"async_camera_image(): {len(self._colors)}, {w}({width}) / {h}({height})")
        sq_size = min(w, h)
        left_gap = (w - sq_size) / 2
        top_gap = (h - sq_size) / 2
        size = int(math.sqrt(len(self._colors)))
        if size * size != len(self._colors):
            _LOGGER.warn(f"async_image(): Pixels aren't square, exiting")
            return None
        
        img = Image.new("RGB", (w, h), "#000")
        if size > 0:
            draw = ImageDraw.Draw(img)
            pixel_size = int(sq_size / size)
            half_gap = int(PIXELS_GAP / 2)
            for i in range(size):
                for j in range(size):
                    col = self._colors[i * size + j]
                    if col:
                        draw.rectangle([
                            left_gap + j * pixel_size + half_gap, 
                            top_gap + i * pixel_size + half_gap, 
                            left_gap + (j+1) * pixel_size - half_gap, 
                            top_gap + (i+1) * pixel_size - half_gap
                        ], fill=col)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="jpeg")
        return img_bytes.getvalue()
