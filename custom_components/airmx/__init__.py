import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_MODEL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store

from .airwater.const import AirWaterModel
from .airwater.device import STORAGE_VERSION, AirWaterDevice, AirWaterSettingsStore
from .const import CONF_MQTT_HOST, CONF_MQTT_PORT, CONF_SIGN_KEY, DEVICES, DOMAIN, PLATFORMS, SETTING_STORES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device_id = entry.data[CONF_ID]
    settings_store = AirWaterSettingsStore(
        hass,
        STORAGE_VERSION,
        f"{DOMAIN}.airwater_{device_id}",
        encoder=JSONEncoder,
    )
    device = AirWaterDevice(
        hass,
        device_id,
        AirWaterModel(entry.data[CONF_MODEL]),
        settings_store,
        entry.data[CONF_SIGN_KEY],
        entry.data[CONF_MQTT_HOST],
        entry.data[CONF_MQTT_PORT],
    )
    await device.async_setup()

    hass.data.setdefault(DOMAIN, {SETTING_STORES: {}, DEVICES: {}})
    hass.data[DOMAIN][DEVICES][entry.entry_id] = device
    hass.data[DOMAIN][SETTING_STORES][entry.entry_id] = settings_store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.async_stop))
    entry.async_on_unload(entry.add_update_listener(_async_entry_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    await device.async_stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN][DEVICES].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    settings_store: Store[Any] | None = hass.data.get(DOMAIN, {}).get(SETTING_STORES, {}).get(entry.entry_id)
    if settings_store:
        await settings_store.async_remove()


async def _async_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
