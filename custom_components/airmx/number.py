from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .airwater.device import AirWaterDevice
from .const import ATTR_FAN_SPEED, DEVICES, DOMAIN
from .entity import AirWaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    async_add_entities([AirWaterFanSpeedEntity(device, entry)])


class AirWaterFanSpeedEntity(AirWaterEntity, NumberEntity):
    _attr_translation_key = ATTR_FAN_SPEED
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self._attr_translation_key}"

    @property
    def native_value(self) -> float:
        return self._device.status.fan_speed

    async def async_set_native_value(self, value: float) -> None:
        await self._device.async_set_fan_speed(int(value))
