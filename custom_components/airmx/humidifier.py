import json
from typing import Any

from homeassistant.components.humidifier import (
    MODE_AUTO,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.components.humidifier.const import MODE_SLEEP
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import voluptuous as vol

from .airwater.const import AirWaterCommand, AirWaterMode
from .airwater.device import AirWaterDevice
from .const import ATTR_COMMAND_DATA, ATTR_COMMAND_ID, DEVICES, DOMAIN, MODE_MANUAL, SERVICE_SEND_COMMAND
from .entity import AirWaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    async_add_entities([AirWaterHumidifier(device, entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        vol.Schema(
            {
                vol.Required(ATTR_ENTITY_ID): cv.entity_id,
                vol.Required(ATTR_COMMAND_ID): vol.Coerce(int),
                vol.Required(ATTR_COMMAND_DATA): cv.string,
            }
        ),
        "async_send_command",
    )


class AirWaterHumidifier(AirWaterEntity, HumidifierEntity):
    _attr_name = None
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = [MODE_AUTO, MODE_MANUAL, MODE_SLEEP]
    _attr_translation_key = "humidifier"

    @property
    def is_on(self) -> bool | None:
        return self._device.status.power

    @property
    def current_humidity(self) -> int | None:
        if self._device.status.remote_sensor_online:
            value = self._device.status.remote_sensor_humidity
        else:
            value = self._device.status.internal_sensor_humidity

        if value:
            return int(value)

        return None

    @property
    def target_humidity(self) -> int | None:
        if self.mode == MODE_MANUAL:
            return None

        return self._device.status.target_humidity

    @property
    def mode(self) -> str | None:
        return {
            AirWaterMode.SLEEP: MODE_SLEEP,
            AirWaterMode.MANUAL: MODE_MANUAL,
        }.get(self._device.status.mode, MODE_AUTO)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_turn_off()

    async def async_set_humidity(self, humidity: int) -> None:
        await self._device.async_set_target_humidity(humidity)

    async def async_set_mode(self, mode: str) -> None:
        await self._device.async_set_mode(
            {
                MODE_SLEEP: AirWaterMode.SLEEP,
                MODE_MANUAL: AirWaterMode.MANUAL,
            }.get(mode, AirWaterMode.AUTO)
        )

    async def async_send_command(self, command_id: int, command_data: str) -> None:
        await self._device.async_send_command(AirWaterCommand(command_id), json.loads(command_data))

    @callback
    def async_write_ha_state(self) -> None:
        super().async_write_ha_state()

        if self.device_info and self.device_info.get("sw_version") != self._device.status.firmware_version:
            self._update_device_info()

    def _update_device_info(self) -> None:
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device({(DOMAIN, self.unique_id)})
        if device:
            device_registry.async_update_device(device.id, sw_version=self._device.status.firmware_version)
