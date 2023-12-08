from dataclasses import dataclass
import logging
from typing import Self

from bleak import BLEDevice
from homeassistant import data_entry_flow
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_MODEL, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .airwater.ble import AirWaterBLEConnector
from .airwater.const import AirWaterModel
from .const import CONF_MQTT_HOST, CONF_MQTT_PORT, CONF_SIGN_KEY, CONF_SSID, DOMAIN

_LOGGER = logging.getLogger(__name__)

ADDON_HOSTNAME = "a06532c7-airmx-addon"
ADDON_MQTT_PORT = 25883


@dataclass
class AirWaterBLEDevice:
    model: AirWaterModel
    device: BLEDevice

    @property
    def address(self) -> str:
        return self.device.address


@dataclass
class AirWaterDeviceInfo:
    id: int
    ble_mac: str
    sign_key: str
    model: AirWaterModel | None = None

    @classmethod
    def from_dict(cls, data: ConfigType) -> Self:
        return cls(id=data["id"], sign_key=data["key"], ble_mac=format_mac(data["ble_mac"]).upper())

    @property
    def name(self) -> str:
        if self.model:
            return f"{self.ble_mac} ({self.model.human_readable})"

        return self.ble_mac


class FlowHandler(ConfigFlow, domain=DOMAIN):
    def __init__(self) -> None:
        self._registered_devices: dict[int, AirWaterDeviceInfo] = {}
        self._discovered_devices: dict[str, AirWaterBLEDevice] = {}
        self._data: ConfigType = {}

        for ble_device in bluetooth.async_get_scanner(self.hass).discovered_devices:
            if ble_device.name is not None:
                try:
                    device = AirWaterBLEDevice(model=AirWaterModel(ble_device.name), device=ble_device)
                    self._discovered_devices[device.address] = device
                except ValueError:
                    pass

    async def async_step_user(self, user_input: ConfigType | None = None) -> data_entry_flow.FlowResult:
        return self.async_show_menu(step_id="user", menu_options=["addon", "manual", "bind_ap"])

    async def async_step_addon(self, user_input: ConfigType | None = None) -> data_entry_flow.FlowResult:
        if user_input is not None:
            self._data[CONF_ID] = int(user_input[CONF_ID])
            return await self.async_step_select_model()

        http = async_get_clientsession(self.hass)
        try:
            devices_response = await http.get(f"http://{ADDON_HOSTNAME}/_devices")
            devices_response.raise_for_status()
            devices: list[AirWaterDeviceInfo] = [AirWaterDeviceInfo.from_dict(d) for d in await devices_response.json()]
        except Exception as e:
            _LOGGER.exception(e)
            return self.async_abort(reason="addon_connection_error")

        if not devices:
            return self.async_abort(reason="wifi_device_not_found")

        options: list[SelectOptionDict] = []
        for device in devices:
            if ble_device := self._discovered_devices.get(device.ble_mac):
                device.model = ble_device.model

            self._registered_devices[device.id] = device

            options.append(SelectOptionDict(value=str(device.id), label=device.name))

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): SelectSelector(
                    SelectSelectorConfig(mode=SelectSelectorMode.LIST, options=options),
                )
            }
        )
        return self.async_show_form(step_id="addon", data_schema=schema)

    async def async_step_select_model(self, user_input: ConfigType | None = None) -> data_entry_flow.FlowResult:
        device = self._registered_devices[self._data[CONF_ID]]
        if user_input is not None:
            device.model = AirWaterModel(user_input[CONF_MODEL])

        if device.model:
            self._data.update(
                {
                    CONF_MODEL: device.model,
                    CONF_SIGN_KEY: device.sign_key,
                    CONF_MQTT_HOST: ADDON_HOSTNAME,
                    CONF_MQTT_PORT: ADDON_MQTT_PORT,
                }
            )
            return self._create_or_update_config_entry(self._data)

        schema = vol.Schema({vol.Required(CONF_MODEL): self._model_selector})
        return self.async_show_form(
            step_id="select_model",
            data_schema=schema,
            description_placeholders={"device": device.name},
        )

    async def async_step_manual(self, user_input: ConfigType | None = None) -> data_entry_flow.FlowResult:
        if user_input is not None:
            return self._create_or_update_config_entry(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_MODEL): self._model_selector,
                vol.Required(CONF_ID): cv.positive_int,
                vol.Required(CONF_SIGN_KEY): cv.string,
                vol.Required(CONF_MQTT_HOST, default=ADDON_HOSTNAME): cv.string,
                vol.Required(CONF_MQTT_PORT, default=ADDON_MQTT_PORT): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="manual", data_schema=schema)

    async def async_step_bind_ap(self, user_input: ConfigType | None = None) -> data_entry_flow.FlowResult:
        devices: dict[str, BLEDevice] = {}
        for device in bluetooth.async_get_scanner(self.hass).discovered_devices:
            if device.name is not None:
                try:
                    AirWaterModel(device.name)
                    devices[device.address] = device
                except ValueError:
                    pass

        if not devices:
            return self.async_abort(reason="ble_device_not_found")

        if user_input is not None:
            try:
                device = devices[user_input[CONF_DEVICE]]
            except KeyError:
                return self.async_abort(reason="ble_device_not_found")

            await AirWaterBLEConnector().bind_ap(device, user_input[CONF_SSID], user_input[CONF_PASSWORD])

            return self.async_abort(reason="bind_ap_done")

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=[
                            SelectOptionDict(value=d.address, label=f"{d.name}: {d.address}") for d in devices.values()
                        ],
                    ),
                ),
                vol.Required(CONF_SSID): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
        return self.async_show_form(step_id="bind_ap", data_schema=schema)

    @property
    def _model_selector(self) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=[SelectOptionDict(value=m, label=m.human_readable) for m in AirWaterModel.__members__.values()],
            ),
        )

    def _create_or_update_config_entry(self, data: ConfigType) -> data_entry_flow.FlowResult:
        title = f"{data[CONF_MODEL]}: {data[CONF_ID]}"

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_ID] == data[CONF_ID]:
                self.hass.config_entries.async_update_entry(entry, title=title, data=data)
                return self.async_abort(reason="updated_entry")

        return self.async_create_entry(title=title, data=data)
