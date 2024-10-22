from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .airwater.const import AirWaterFeature
from .airwater.device import AirWaterDevice
from .const import ATTR_ANION, ATTR_CHILD_LOCK, ATTR_HEATER, ATTR_PROXIMITY_SENSOR, DEVICES, DOMAIN
from .entity import AirWaterEntity


@dataclass(frozen=True)
class AirWaterSwitchDescriptionMixin:
    feature: int | None
    setting: bool
    method_on: str
    method_off: str
    icon_on: str
    icon_off: str


@dataclass(frozen=True)
class AirWaterSwitchDescription(SwitchEntityDescription, AirWaterSwitchDescriptionMixin):
    ...


SWITCH_TYPES = (
    AirWaterSwitchDescription(
        key=ATTR_ANION,
        translation_key=ATTR_ANION,
        icon_on="mdi:atom",
        icon_off="mdi:atom",
        feature=AirWaterFeature.ANION,
        setting=False,
        method_on="async_set_anion_on",
        method_off="async_set_anion_off",
        entity_category=EntityCategory.CONFIG,
    ),
    AirWaterSwitchDescription(
        key=ATTR_CHILD_LOCK,
        translation_key=ATTR_CHILD_LOCK,
        icon_on="mdi:lock-outline",
        icon_off="mdi:lock-open-outline",
        feature=None,
        setting=False,
        method_on="async_set_child_lock_on",
        method_off="async_set_child_lock_off",
        entity_category=EntityCategory.CONFIG,
    ),
    AirWaterSwitchDescription(
        key=ATTR_HEATER,
        translation_key=ATTR_HEATER,
        icon_on="mdi:radiator",
        icon_off="mdi:radiator-off",
        feature=AirWaterFeature.HEATER,
        setting=True,
        method_on="async_set_heater_on",
        method_off="async_set_heater_off",
        entity_category=EntityCategory.CONFIG,
    ),
    AirWaterSwitchDescription(
        key=ATTR_PROXIMITY_SENSOR,
        translation_key=ATTR_PROXIMITY_SENSOR,
        icon_on="mdi:motion-sensor",
        icon_off="mdi:motion-sensor-off",
        feature=None,
        setting=True,
        method_on="async_set_proximity_sensor_on",
        method_off="async_set_proximity_sensor_off",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    entities: list[SwitchEntity] = []

    for description in SWITCH_TYPES:
        if description.feature is None or bool(device.model.features & description.feature):
            entities.append(AirWaterGenericSwitch(device, entry, description))

    async_add_entities(entities)


class AirWaterGenericSwitch(AirWaterEntity, SwitchEntity):
    entity_description: AirWaterSwitchDescription

    def __init__(self, device: AirWaterDevice, entry: ConfigEntry, description: AirWaterSwitchDescription) -> None:
        super().__init__(device, entry)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.setting:
            return bool(getattr(self._device.settings, self.entity_description.key))

        return bool(getattr(self._device.status, self.entity_description.key))

    @property
    def icon(self) -> str:
        return self.entity_description.icon_on if self.is_on else self.entity_description.icon_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        method = getattr(self._device, self.entity_description.method_on)
        await method()

    async def async_turn_off(self, **kwargs: Any) -> None:
        method = getattr(self._device, self.entity_description.method_off)
        await method()
