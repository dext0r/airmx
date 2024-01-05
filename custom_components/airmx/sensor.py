from dataclasses import asdict
from typing import Any, Mapping, cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .airwater.device import AirWaterDevice
from .const import ATTR_HUMIDITY, ATTR_REMOTE_SENSOR_RSSI, ATTR_STATUS, ATTR_WATER_LEVEL, ATTR_WUD, DEVICES, DOMAIN
from .entity import AirWaterEntity

SENSOR_TYPES = (
    SensorEntityDescription(
        key=ATTR_REMOTE_SENSOR_RSSI,
        translation_key=ATTR_REMOTE_SENSOR_RSSI,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_WATER_LEVEL,
        translation_key=ATTR_WATER_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cup-water",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_WUD,
        translation_key=ATTR_WUD,
        icon="mdi:liquid-spot",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    entities: list[SensorEntity] = [
        AirWaterTemperatureSensor(device, entry),
        AirWaterHumiditySensor(device, entry),
        AirWaterStatusSensor(device, entry),
    ]

    for description in SENSOR_TYPES:
        entities.append(AirWaterGenericSensor(device, entry, description))

    async_add_entities(entities)


class AirWaterGenericSensor(AirWaterEntity, SensorEntity):
    def __init__(self, device: AirWaterDevice, entry: ConfigEntry, description: SensorEntityDescription) -> None:
        super().__init__(device, entry)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.key}"

    @property
    def native_value(self) -> int | None:
        return cast(int | None, getattr(self._device.status, self.entity_description.key))


class AirWaterTemperatureSensor(AirWaterEntity, SensorEntity):
    entity_description = SensorEntityDescription(
        key=ATTR_TEMPERATURE,
        translation_key=ATTR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    )

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.key}"

    @property
    def native_value(self) -> float | None:
        if self._device.status.remote_sensor_online:
            value = self._device.status.remote_sensor_temperature
        else:
            value = self._device.status.internal_sensor_temperature

        if value:
            return round(value, 1)

        return None


class AirWaterHumiditySensor(AirWaterEntity, SensorEntity):
    entity_description = SensorEntityDescription(
        key=ATTR_HUMIDITY,
        translation_key=ATTR_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    )

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.key}"

    @property
    def native_value(self) -> int | None:
        if self._device.status.remote_sensor_online:
            value = self._device.status.remote_sensor_humidity
        else:
            value = self._device.status.internal_sensor_humidity

        if value:
            return int(value)

        return None


class AirWaterStatusSensor(AirWaterEntity, SensorEntity):
    entity_description = SensorEntityDescription(
        key=ATTR_STATUS,
        translation_key=ATTR_STATUS,
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self.entity_description.key}"

    @property
    def native_value(self) -> str:
        return ""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attrs = {}
        for prefix, data in (("status", self._device.status), ("settings", self._device.settings)):
            for key, value in asdict(data).items():  # type: ignore
                attrs[f"{prefix}.{key}"] = value

        return attrs
