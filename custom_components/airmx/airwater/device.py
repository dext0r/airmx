import dataclasses
from datetime import datetime, timedelta
import hashlib
import json
import logging
from typing import Any, Callable, Optional, Self, TypeVar, cast

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util.json import json_loads_object
import paho.mqtt.client as mqtt

from ..mqtt.client import MQTTClient
from .const import AirWaterCommand, AirWaterMode, AirWaterModel, WaterType

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T", int, float)

AVAILABILITY_TIMEOUT = timedelta(seconds=30)
UPDATE_INTERVAL = 600
UPDATE_DURATION = 10
NULL_VALUE = 99999
STORAGE_VERSION = 1

CommandData = dict[str, int | str]
CommandType = dict[str, int | str | CommandData]
AirWaterSettingsStoreData = dict[str, int | str]


def _get_bool_from_command_data(data: CommandData, key: str, default: bool = False) -> bool:
    return bool(data.get(key, int(default)))


def _get_float_from_command_data(data: CommandData, key: str) -> float | None:
    value = int(data.get(key, NULL_VALUE))
    if value == NULL_VALUE:
        return None

    return value / 100


def _get_int_from_command_data(data: CommandData, key: str, default: int = 0) -> int:
    return int(data.get(key, default))


def _value_in_range(value: Optional[_T], low_high_range: tuple[_T, _T]) -> Optional[_T]:
    if value is None or value == NULL_VALUE:
        return None

    if low_high_range[0] <= value <= low_high_range[1]:
        return value

    return None


@dataclasses.dataclass
class AirWaterDeviceSettings:
    water_type: WaterType = WaterType.TAP
    target_humidity: int = 45
    heater: bool = True
    proximity_sensor: bool = True
    auto_shake: bool = True

    # unknown fields
    clean_notify: bool = True
    electrolysis: int = 0
    electrolysis_level: int = 0

    def update_from_command_data(self, data: CommandData) -> Self:
        return self.with_changes(
            target_humidity=int(data.get("hThreshold", 0)),
            heater=_get_bool_from_command_data(data, "powerHeat"),
            proximity_sensor=_get_bool_from_command_data(data, "pirLock"),
            auto_shake=_get_bool_from_command_data(data, "autoShakeEnable"),
            clean_notify=_get_bool_from_command_data(data, "cleanNotify"),
            electrolysis=_get_bool_from_command_data(data, "electrolysis"),
            electrolysis_level=_get_bool_from_command_data(data, "electrolysisLevel"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            water_type=WaterType(data["water_type"]),
            target_humidity=int(data["target_humidity"]),
            heater=bool(data["heater"]),
            proximity_sensor=bool(data["proximity_sensor"]),
            auto_shake=bool(data["auto_shake"]),
            clean_notify=bool(data["clean_notify"]),
            electrolysis=int(data["electrolysis"]),
            electrolysis_level=int(data["electrolysis_level"]),
        )

    @property
    def as_command_data(self) -> CommandData:
        return {
            "hThreshold": self.target_humidity,
            "powerHeat": int(self.heater),
            "pirLock": int(self.proximity_sensor),
            "autoShakeEnable": int(self.auto_shake),
            "cleanNotify" "": int(self.clean_notify),
            "electrolysis": int(self.electrolysis),
            "electrolysisLevel": int(self.electrolysis_level),
        }

    def with_changes(self, **changes: Any) -> Self:
        return dataclasses.replace(self, **changes)


class AirWaterSettingsStore(Store[AirWaterSettingsStoreData]):
    pass


@dataclasses.dataclass
class AirWaterDeviceStatus:
    power: bool = False
    mode: AirWaterMode = AirWaterMode.AUTO
    fan_speed: int = 0
    child_lock: bool = False
    uv: bool = True
    anion: bool = True
    target_humidity: int = 0
    water_level: int | None = None
    internal_sensor_humidity: float | None = None
    internal_sensor_temperature: float | None = None
    remote_sensor_online: bool = False
    remote_sensor_rssi: int = -100
    remote_sensor_humidity: float | None = None
    remote_sensor_temperature: float | None = None
    need_cleaning: bool = False
    heater: bool = False
    wud: int = 0
    malfunction: bool = False
    firmware_version: str | None = None

    # unknown fields
    electrolysis: int = 0
    wet_film: int | None = None

    @classmethod
    def from_command_data(cls, data: CommandData) -> Self:
        status = cls(
            power=_get_bool_from_command_data(data, "power"),
            mode=AirWaterMode(_get_int_from_command_data(data, "mode")),
            fan_speed=_get_int_from_command_data(data, "cadr"),
            child_lock=_get_bool_from_command_data(data, "lock"),
            uv=_get_bool_from_command_data(data, "uv"),
            anion=_get_bool_from_command_data(data, "anion"),
            target_humidity=_get_int_from_command_data(data, "hThreshold"),
            water_level=_value_in_range(_get_int_from_command_data(data, "water"), (0, 120)),
            internal_sensor_humidity=_value_in_range(_get_float_from_command_data(data, "h0"), (0.1, 100)),
            internal_sensor_temperature=_value_in_range(_get_float_from_command_data(data, "t0"), (0.1, 100)),
            remote_sensor_online=_get_bool_from_command_data(data, "gooseOnline"),
            remote_sensor_rssi=_get_int_from_command_data(data, "bleSignal", -100),
            remote_sensor_humidity=_value_in_range(_get_float_from_command_data(data, "h"), (0.1, 100)),
            remote_sensor_temperature=_value_in_range(_get_float_from_command_data(data, "t"), (0.1, 100)),
            need_cleaning=_get_bool_from_command_data(data, "isNeedClean"),
            heater=_get_bool_from_command_data(data, "powerHeatStatus"),
            wud=_get_int_from_command_data(data, "WUD"),
            firmware_version=str(data.get("version")) if "version" in data else None,
            electrolysis=_get_int_from_command_data(data, "electrolysis"),
            wet_film=_get_int_from_command_data(data, "wetFilm"),
        )

        if status.mode == AirWaterMode.MALFUNCTION:
            status.mode = AirWaterMode.AUTO
            status.malfunction = True

        return status

    @property
    def as_command_data(self) -> CommandData:
        return {
            "power": int(self.power),
            "mode": self.mode,
            "cadr": self.fan_speed,
            "lock": int(self.child_lock),
            "uv": int(self.uv),
            "anion": int(self.anion),
        }

    def with_changes(self, **changes: Any) -> Self:
        return dataclasses.replace(self, **changes)


class AirWaterDevice:
    _settings: AirWaterDeviceSettings
    _unsub_subscribe_for_updates: CALLBACK_TYPE | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: int,
        model: AirWaterModel,
        settings_store: AirWaterSettingsStore,
        sign_key: str,
        mqtt_host: str,
        mqtt_port: int,
    ):
        self.id = device_id
        self.model = model
        self.last_state_report: dict[Any, dict[Any, Any]] = {}

        self._hass = hass
        self._mqttc = MQTTClient(hass, mqtt_host, mqtt_port, f"aw_{device_id}", sign_key)
        self._mqttc.subscribe_topics = [f"airwater/01/0/1/1/{self.id}"]
        self._mqttc.on_message = self._async_handle_mqtt_message
        self._mqttc.on_connect = self._async_subscribe_for_updates
        self._mqttc.on_disconnect = self._async_notify
        self._sign_key = sign_key
        self._status = AirWaterDeviceStatus()
        self._settings_store = settings_store
        self._listeners: list[Callable[[], None]] = []
        self._last_update: datetime | None = None

    async def async_setup(self) -> None:
        self._settings = await self._async_load_settings()
        await self._mqttc.async_connect()
        self._unsub_subscribe_for_updates = async_track_time_interval(
            self._hass, self._async_subscribe_for_updates, timedelta(seconds=UPDATE_DURATION)
        )
        await self._async_subscribe_for_updates()

    async def async_stop(self, _: Event | None = None) -> None:
        if self._unsub_subscribe_for_updates:
            self._unsub_subscribe_for_updates()

        await self._mqttc.async_disconnect()

    @property
    def name(self) -> str:
        return f"{self.model.value} {self.id}"

    @property
    def available(self) -> bool:
        if not self._mqttc.connected or not self._last_update:
            return False

        if datetime.now() - self._last_update >= AVAILABILITY_TIMEOUT:
            return False

        return True

    @property
    def status(self) -> AirWaterDeviceStatus:
        return self._status

    @property
    def settings(self) -> AirWaterDeviceSettings:
        return self._settings

    async def async_turn_on(self) -> None:
        await self._async_control(self.status.with_changes(power=True))

    async def async_turn_off(self) -> None:
        await self._async_control(self.status.with_changes(power=False))

    async def async_set_mode(self, mode: AirWaterMode) -> None:
        await self._async_control(self.status.with_changes(mode=mode))

    async def async_set_target_humidity(self, humidity: int) -> None:
        await self._async_set(self.settings.with_changes(target_humidity=humidity))

    async def async_set_fan_speed(self, speed: int) -> None:
        await self._async_control(self.status.with_changes(fan_speed=speed, mode=AirWaterMode.MANUAL))

    async def async_set_child_lock_on(self) -> None:
        await self._async_control(self.status.with_changes(child_lock=True))

    async def async_set_child_lock_off(self) -> None:
        await self._async_control(self.status.with_changes(child_lock=False))

    async def async_set_anion_on(self) -> None:
        await self._async_control(self.status.with_changes(anion=True))

    async def async_set_anion_off(self) -> None:
        await self._async_control(self.status.with_changes(anion=False))

    async def async_set_heater_on(self) -> None:
        await self._async_set(self.settings.with_changes(heater=True))

    async def async_set_heater_off(self) -> None:
        await self._async_set(self.settings.with_changes(heater=False))

    async def async_set_proximity_sensor_on(self) -> None:
        await self._async_set(self.settings.with_changes(proximity_sensor=True))

    async def async_set_proximity_sensor_off(self) -> None:
        await self._async_set(self.settings.with_changes(proximity_sensor=False))

    async def async_set_water_type(self, water_type: WaterType) -> None:
        await self._async_update_settings(self.settings.with_changes(water_type=water_type))
        await self._async_subscribe_for_updates()

    async def async_send_command(self, command: AirWaterCommand, data: CommandData) -> None:
        await self._mqttc.async_publish(
            f"airwater/01/1/0/1/{self.id}",
            self._get_signed_command(command, data),
        )

    def async_add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Add a listener to notify when data is updated."""

        def unsub() -> None:
            self._listeners.remove(cb)

        self._listeners.append(cb)
        return unsub

    async def _async_handle_mqtt_message(self, message: mqtt.MQTTMessage) -> None:
        state_report = cast(CommandType, json_loads_object(cast(bytes, message.payload)))
        self._last_update = datetime.now()
        self.last_state_report[state_report["cmdId"]] = state_report

        match state_report["cmdId"]:
            case AirWaterCommand.STATUS_INFO:
                await self._async_handle_new_status(cast(CommandData, state_report["data"]))
            case AirWaterCommand.SET_INFO:
                await self._async_handle_new_settings(cast(CommandData, state_report["data"]))
            case _:
                _LOGGER.error(f"Unknown command: {state_report['cmdId']}")

        await self._async_notify()

    async def _async_notify(self) -> None:
        """Notify all listeners that data has been updated."""
        for listener in self._listeners:
            listener()

    async def _async_control(self, new_status: AirWaterDeviceStatus) -> None:
        await self.async_send_command(AirWaterCommand.CONTROL, new_status.as_command_data)

    async def _async_set(self, new_settings: AirWaterDeviceSettings) -> None:
        await self.async_send_command(AirWaterCommand.SET, new_settings.as_command_data)

    async def _async_subscribe_for_updates(self, _: datetime | None = None) -> None:
        await self._async_notify()

        if self._mqttc.connected:
            await self.async_send_command(
                AirWaterCommand.GET_STATUS,
                {
                    "cleanTime": self._settings.water_type.cleaning_time,
                    "water_type": int(self._settings.water_type),
                    "frequencyTime": UPDATE_INTERVAL,
                    "durationTime": UPDATE_DURATION,
                },
            )

    async def _async_handle_new_status(self, data: CommandData) -> None:
        self._status = AirWaterDeviceStatus.from_command_data(data)
        await self._async_update_settings(self.settings.with_changes(target_humidity=self._status.target_humidity))

    async def _async_handle_new_settings(self, data: CommandData) -> None:
        await self._async_update_settings(self._settings.update_from_command_data(data))

    async def _async_update_settings(self, settings: AirWaterDeviceSettings) -> None:
        if self._settings != settings:
            self._settings = settings
            self._settings_store.async_delay_save(lambda: dataclasses.asdict(self._settings), 10)

    async def _async_load_settings(self) -> AirWaterDeviceSettings:
        if (restored := await self._settings_store.async_load()) is None:
            return AirWaterDeviceSettings()

        return AirWaterDeviceSettings.from_dict(restored)

    def _get_signed_command(self, command: AirWaterCommand, data: CommandData) -> bytes:
        def _dump(v: Any) -> str:
            return json.dumps(v, separators=(",", ":"))

        cmd: CommandType = {"cmdId": int(command), "time": int(datetime.now().timestamp()), "data": data}

        to_sign = _dump(cmd)[1:-1]
        cmd["sig"] = hashlib.md5(f"{to_sign},{self._sign_key}".encode()).hexdigest()

        return _dump(cmd).encode()
