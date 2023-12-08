from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .airwater.device import AirWaterDevice
from .const import DOMAIN


class AirWaterEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, device: AirWaterDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._entry = entry

    @property
    def unique_id(self) -> str:
        return f"airwater_{self._device.id}"

    @property
    def available(self) -> bool:
        return self._device.available

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, f"airwater_{self._device.id}")},
            name=self._device.name,
            manufacturer="AIRMX",
            model=self._device.model.human_readable,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.async_add_listener(self.async_write_ha_state))
