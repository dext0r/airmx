from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .airwater.device import AirWaterDevice
from .const import CONF_SIGN_KEY, DEVICES, DOMAIN

TO_REDACT = {CONF_SIGN_KEY}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    device: AirWaterDevice = hass.data[DOMAIN][DEVICES][entry.entry_id]
    data = {"entry": async_redact_data(entry.as_dict(), TO_REDACT), "last_state_report": device.last_state_report}
    return data
