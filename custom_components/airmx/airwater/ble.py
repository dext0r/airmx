import asyncio
from contextlib import suppress
from dataclasses import dataclass
import logging

from bleak import BleakClient, BleakError, BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic

_LOGGER = logging.getLogger(__name__)

PACKET_SIZE = 16
NOTIFICATION_UUID = "22210002-554a-4546-5542-46534450464d"
COMMAND_UUID = "22210001-554a-4546-5542-46534450464d"


@dataclass
class BindAPRequest:
    ssid: str
    password: str

    @property
    def as_bytes(self) -> bytes:
        data = b""
        data += len(self.ssid).to_bytes()
        data += self.ssid.encode()
        data += len(self.password).to_bytes()
        data += self.password.encode()
        return data


class AirWaterBLEConnector:
    _bind_ap_done = False

    def _notification_handler(self, _: BleakGATTCharacteristic, data: bytearray) -> None:
        _LOGGER.debug("< %s", data.hex())
        if data != b"\x00\x11\x00\x15\x01":
            _LOGGER.error(f"Unexpected data: {data.hex()}")
        else:
            self._bind_ap_done = True

    async def bind_ap(self, device: BLEDevice, ssid: str, password: str) -> None:
        _LOGGER.debug(f"Connecting to {device}...")

        async with BleakClient(device) as client:
            await client.start_notify(NOTIFICATION_UUID, self._notification_handler)

            request = BindAPRequest(ssid, password).as_bytes
            request_size = len(request)
            packet_count = int(request_size / PACKET_SIZE)
            if request_size % 16 > 0:
                packet_count += 1

            for seq in range(0, packet_count):
                csum = (seq + 1 << 4) + packet_count

                packet = b""
                packet += seq.to_bytes()
                packet += csum.to_bytes()
                packet += b"\x00\x15"

                f = seq * PACKET_SIZE
                s = seq * PACKET_SIZE + PACKET_SIZE
                packet += request[f:s]

                _LOGGER.debug("> %s", packet.hex())
                await client.write_gatt_char(COMMAND_UUID, packet, response=True)

            for _ in range(0, 60):
                await asyncio.sleep(0.3)
                if self._bind_ap_done:
                    break

            if not self._bind_ap_done:
                raise Exception("AP binding timeout")

            ack_packet = (seq + 1).to_bytes() + b"\x11\x00\x16"
            _LOGGER.debug("> %s", ack_packet.hex())
            await client.write_gatt_char(COMMAND_UUID, packet, response=True)

            with suppress(BleakError):
                await client.stop_notify(NOTIFICATION_UUID)
