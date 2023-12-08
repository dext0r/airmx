from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .airwater.device import AirWaterDevice
from .const import ATTR_MALFUNCTION, ATTR_NEED_CLEANING, ATTR_UV, DEVICES, DOMAIN
from .entity import AirWaterEntity

BINARY_SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key=ATTR_UV,
        translation_key=ATTR_UV,
        icon="mdi:lightbulb",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key=ATTR_NEED_CLEANING,
        translation_key=ATTR_NEED_CLEANING,
        icon="mdi:hand-wash-outline",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key=ATTR_MALFUNCTION,
        translation_key=ATTR_MALFUNCTION,
        icon="mdi:alert-outline",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    entities: list[BinarySensorEntity] = []

    for description in BINARY_SENSOR_TYPES:
        entities.append(AirWaterGenericBinarySensor(device, entry, description))

    async_add_entities(entities)


class AirWaterGenericBinarySensor(AirWaterEntity, BinarySensorEntity):
    def __init__(self, device: AirWaterDevice, entry: ConfigEntry, description: BinarySensorEntityDescription) -> None:
        super().__init__(device, entry)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        return bool(getattr(self._device.status, self.entity_description.key))
