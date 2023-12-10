from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .airwater.const import AirWaterFeature
from .airwater.device import AirWaterDevice
from .const import ATTR_FAN_SPEED, DEVICES, DOMAIN
from .entity import AirWaterEntity


@dataclass
class AirWaterFanSpeedDescriptionMixin:
    feature: int


@dataclass
class AirWaterFanSpeedDescription(NumberEntityDescription, AirWaterFanSpeedDescriptionMixin):
    ...


FAN_SPEED_TYPES = (
    AirWaterFanSpeedDescription(
        key=ATTR_FAN_SPEED,
        translation_key=ATTR_FAN_SPEED,
        icon="mdi:fan",
        feature=AirWaterFeature.FAN_SPEED_PERCENTAGE,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
    ),
    AirWaterFanSpeedDescription(
        key=ATTR_FAN_SPEED,
        translation_key=ATTR_FAN_SPEED,
        icon="mdi:fan",
        feature=AirWaterFeature.FAN_SPEED_STEPS,
        native_min_value=0,
        native_max_value=6,
        native_step=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    entities: list[NumberEntity] = []

    for description in FAN_SPEED_TYPES:
        if bool(device.model.features & description.feature):
            entities.append(AirWaterGenericFanSpeedEntity(device, entry, description))

    async_add_entities(entities)


class AirWaterGenericFanSpeedEntity(AirWaterEntity, NumberEntity):
    entity_description: AirWaterFanSpeedDescription

    def __init__(self, device: AirWaterDevice, entry: ConfigEntry, description: AirWaterFanSpeedDescription) -> None:
        super().__init__(device, entry)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.translation_key}"

    @property
    def native_value(self) -> float:
        return self._device.status.fan_speed

    async def async_set_native_value(self, value: float) -> None:
        await self._device.async_set_fan_speed(int(value))
