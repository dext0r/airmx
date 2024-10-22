from dataclasses import dataclass
import logging
from typing import Self

from bleak import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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
DEFAULT_MQTT_PORT = 1883


@dataclass
class AirWaterBLEDevice:
    model: AirWaterModel
    device: BLEDevice

    @property
    def name(self) -> str:
        return self.device.name or ""

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
        self._data: ConfigType = {}
        self._wifi_devices: dict[int, AirWaterDeviceInfo] = {}
        self._ble_devices: dict[str, AirWaterBLEDevice] = {}

    async def async_step_user(self, user_input: ConfigType | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["select_device", "manual", "bind_ap"])

    async def async_step_select_device(self, user_input: ConfigType | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if device_id := int(user_input.get(CONF_ID, 0)):
                self._data[CONF_ID] = device_id
                return await self.async_step_select_model()

        try:
            await self._async_discover_wifi_devices()
        except Exception as e:
            _LOGGER.exception(e)
            return self.async_abort(reason="addon_connection_error")

        if not self._wifi_devices:
            return self.async_show_form(step_id="select_device", errors={"base": "device_not_found"})

        schema = vol.Schema(
            {
                vol.Optional(CONF_ID): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.LIST,
                        options=[
                            SelectOptionDict(value=str(device.id), label=device.name)
                            for device in self._wifi_devices.values()
                        ],
                    ),
                )
            }
        )
        return self.async_show_form(step_id="select_device", data_schema=schema)

    async def async_step_select_model(self, user_input: ConfigType | None = None) -> ConfigFlowResult:
        device = self._wifi_devices[self._data[CONF_ID]]
        if user_input is not None:
            device.model = AirWaterModel(user_input[CONF_MODEL])

        if device.model:
            self._data.update(
                {
                    CONF_MODEL: device.model,
                    CONF_SIGN_KEY: device.sign_key,
                    CONF_MQTT_HOST: ADDON_HOSTNAME,
                    CONF_MQTT_PORT: DEFAULT_MQTT_PORT,
                }
            )
            return self._create_or_update_config_entry(self._data)

        schema = vol.Schema({vol.Required(CONF_MODEL): self._model_selector})
        return self.async_show_form(
            step_id="select_model",
            data_schema=schema,
            description_placeholders={"device": device.name},
        )

    async def async_step_manual(self, user_input: ConfigType | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._create_or_update_config_entry(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_MODEL): self._model_selector,
                vol.Required(CONF_ID): cv.positive_int,
                vol.Required(CONF_SIGN_KEY): cv.string,
                vol.Required(CONF_MQTT_HOST, default=ADDON_HOSTNAME): cv.string,
                vol.Required(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="manual", data_schema=schema)

    async def async_step_bind_ap(self, user_input: ConfigType | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if device := user_input.get(CONF_DEVICE):
                self._data[CONF_DEVICE] = device
                return await self.async_step_bind_ap_confirm()

        self._discover_ble_devices()

        if not self._ble_devices:
            return self.async_show_form(step_id="bind_ap", errors={"base": "device_not_found"})

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.LIST,
                        options=[
                            SelectOptionDict(value=d.address, label=f"{d.name}: {d.address}")
                            for d in self._ble_devices.values()
                        ],
                    ),
                ),
            }
        )
        return self.async_show_form(step_id="bind_ap", data_schema=schema)

    async def async_step_bind_ap_confirm(self, user_input: ConfigType | None = None) -> ConfigFlowResult:
        if user_input is not None:
            device = self._ble_devices[self._data[CONF_DEVICE]]

            await AirWaterBLEConnector().bind_ap(device.device, user_input[CONF_SSID], user_input[CONF_PASSWORD])

            return self.async_abort(reason="bind_ap_done")

        schema = vol.Schema(
            {
                vol.Required(CONF_SSID): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
        return self.async_show_form(step_id="bind_ap_confirm", data_schema=schema)

    #
    @property
    def _model_selector(self) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=[SelectOptionDict(value=m, label=m.human_readable) for m in AirWaterModel.__members__.values()],
            ),
        )

    def _create_or_update_config_entry(self, data: ConfigType) -> ConfigFlowResult:
        title = f"{data[CONF_MODEL]}: {data[CONF_ID]}"

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_ID] == data[CONF_ID]:
                self.hass.config_entries.async_update_entry(entry, title=title, data=data)
                return self.async_abort(reason="updated_entry")

        return self.async_create_entry(title=title, data=data)

    def _discover_ble_devices(self) -> None:
        for ble_device in bluetooth.async_get_scanner(self.hass).discovered_devices:
            if ble_device.name is not None:
                try:
                    device = AirWaterBLEDevice(model=AirWaterModel(ble_device.name), device=ble_device)
                    self._ble_devices[device.address] = device
                except ValueError:
                    pass

    async def _async_discover_wifi_devices(self) -> None:
        self._discover_ble_devices()

        http = async_get_clientsession(self.hass)
        response = await http.get(f"http://{ADDON_HOSTNAME}/_devices")
        response.raise_for_status()
        for data in await response.json():
            device = AirWaterDeviceInfo.from_dict(data)

            if ble_device := self._ble_devices.get(device.ble_mac):
                device.model = ble_device.model

            self._wifi_devices[device.id] = device
