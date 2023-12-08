from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .airwater.const import WaterType as AirWaterWaterType
from .airwater.device import AirWaterDevice
from .const import ATTR_WATER_TYPE, DEVICES, DOMAIN
from .entity import AirWaterEntity

WATER_TYPE_TAP = "tap"
WATER_TYPE_FILTERED = "filtered"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    async_add_entities([AirWaterWaterTypeEntity(device, entry)])


class AirWaterWaterTypeEntity(AirWaterEntity, SelectEntity):
    _attr_translation_key = ATTR_WATER_TYPE
    _attr_icon = "mdi:hand-water"
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self._attr_translation_key}"

    @property
    def current_option(self) -> str | None:
        return {
            AirWaterWaterType.TAP: WATER_TYPE_TAP,
            AirWaterWaterType.FILTERED: WATER_TYPE_FILTERED,
        }[self._device.settings.water_type]

    @property
    def options(self) -> list[str]:
        return [WATER_TYPE_TAP, WATER_TYPE_FILTERED]

    async def async_select_option(self, option: str) -> None:
        await self._device.async_set_water_type(
            {
                WATER_TYPE_TAP: AirWaterWaterType.TAP,
                WATER_TYPE_FILTERED: AirWaterWaterType.FILTERED,
            }[option]
        )
