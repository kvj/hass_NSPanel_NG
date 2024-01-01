from homeassistant.components import image
from homeassistant.helpers.entity import EntityCategory

from .manager import BaseEntity, CoordinatorEvent
from .constants import DOMAIN

from datetime import datetime
import math

from PIL import Image, ImageDraw
import io

import logging
_LOGGER = logging.getLogger(__name__)

PIXELS_SIZE = 400
PIXELS_GAP = 8

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_Pixels(coordinator)])

class _Pixels(BaseEntity, image.ImageEntity, CoordinatorEvent):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        image.ImageEntity.__init__(self, coordinator.hass)
        self.with_name("pixels", "Pixels")
        self._attr_content_type = "image/png"
        self._attr_image_last_updated = None
        self._attr_icon = "mdi:grid"
        self._colors = []

    async def async_added_to_hass(self) -> None:
        self.coordinator.add_event_listener(self)

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.remove_event_listener(self)

    async def async_on_pixels(self, colors):
        _LOGGER.debug(f"async_on_pixels() New colors array = {len(colors)}")
        self._colors = colors
        self._attr_image_last_updated = datetime.now()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        _LOGGER.debug(f"async_image(): {len(self._colors)}, {self._colors}")
        size = int(math.sqrt(len(self._colors)))
        if size * size != len(self._colors):
            _LOGGER.warn(f"async_image(): Pixels aren't square, exiting")
            return None
        
        img = Image.new("RGBA", (PIXELS_SIZE, PIXELS_SIZE), "#0000")
        if size > 0:
            draw = ImageDraw.Draw(img)
            pixel_size = int(PIXELS_SIZE / size)
            half_gap = int(PIXELS_GAP / 2)
            for i in range(size):
                for j in range(size):
                    col = self._colors[i * size + j]
                    if col:
                        draw.rectangle([j * pixel_size + half_gap, i * pixel_size + half_gap, (j+1) * pixel_size - half_gap, (i+1) * pixel_size - half_gap], fill=col)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="png")
        return img_bytes.getvalue()
