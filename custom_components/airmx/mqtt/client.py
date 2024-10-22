import asyncio
import logging
from typing import Any, Callable, Coroutine

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


class MQTTClient:
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
    ):
        self._hass = hass
        self._client = mqtt.Client()
        self._client.on_connect = self._mqtt_on_connect
        self._client.on_message = self._mqtt_on_message
        self._client.on_disconnect = self._mqtt_on_disconnect
        self._host = host
        self._port = port
        self._lock = asyncio.Lock()

        self.subscribe_topics: list[str] = []
        self.on_message: Callable[[mqtt.MQTTMessage], Coroutine[Any, Any, None]] | None = None
        self.on_connect: Callable[[], Coroutine[Any, Any, None]] | None = None
        self.on_disconnect: Callable[[], Coroutine[Any, Any, None]] | None = None

        if username and password:
            self._client.username_pw_set(username, password)

    async def async_connect(self) -> None:
        result: int | None = None

        try:
            result = await self._hass.async_add_executor_job(self._client.connect, self._host, self._port)
        except OSError as err:
            _LOGGER.error(f"Failed to connect to MQTT server due to exception: {err}")

        if result is not None and result != 0:
            _LOGGER.error("Failed to connect to MQTT server: %s", mqtt.error_string(result))

        self._client.loop_start()

    async def async_disconnect(self) -> None:
        async with self._lock:
            await self._hass.async_add_executor_job(lambda: self._client.disconnect())

    async def async_publish(self, topic: str, payload: bytes) -> None:
        async with self._lock:
            msg_info = await self._hass.async_add_executor_job(self._client.publish, topic, payload)

        _LOGGER.debug(f"Transmitting message on {topic}: {payload!r}")
        self._raise_on_error(msg_info.rc)

    @property
    def connected(self) -> bool:
        return self._client.is_connected()

    def _mqtt_on_connect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        _flags: dict[str, int],
        result_code: int,
        _properties: mqtt.Properties | None = None,
    ) -> None:
        _LOGGER.info(f"Connected to MQTT server ({result_code})")

        for topic in self.subscribe_topics:
            _LOGGER.info(f"Subscribe to {topic}")
            self._client.subscribe(topic)

        if self.on_connect is not None:
            self._hass.add_job(self.on_connect())

    def _mqtt_on_disconnect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        result_code: int,
        _properties: mqtt.Properties | None = None,
    ) -> None:
        _LOGGER.info(f"Disconnected from MQTT server ({result_code})")

        if self.on_disconnect:
            self._hass.add_job(self.on_disconnect())

    def _mqtt_on_message(self, _mqttc: mqtt.Client, _userdata: None, msg: mqtt.MQTTMessage) -> None:
        _LOGGER.debug(f"Received from MQTT: {msg.payload!r}")

        if self.on_message:
            self._hass.add_job(self.on_message(msg))

    @staticmethod
    def _raise_on_error(result_code: int) -> None:
        if result_code and (message := mqtt.error_string(result_code)):
            raise HomeAssistantError(f"Error talking to MQTT: {message}")
