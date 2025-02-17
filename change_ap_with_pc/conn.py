import asyncio
from contextlib import suppress
from dataclasses import dataclass
import logging
from bleak import BleakClient, BleakError, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak import BLEDevice

# 设置日志记录，确保INFO级别的日志也能打印出来
logging.basicConfig(level=logging.DEBUG)  # 设置日志记录级别为DEBUG，INFO也会打印

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
        data += len(self.ssid).to_bytes(1, 'little')  # Added '1' as the byte length argument
        data += self.ssid.encode()
        data += len(self.password).to_bytes(1, 'little')  # Added '1' as the byte length argument
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
            if request_size % PACKET_SIZE > 0:
                packet_count += 1

            for seq in range(0, packet_count):
                csum = (seq + 1 << 4) + packet_count

                packet = b""
                packet += seq.to_bytes(1, 'little')  # Added '1' as the byte length argument
                packet += csum.to_bytes(1, 'little')  # Added '1' as the byte length argument
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

            ack_packet = (seq + 1).to_bytes(1, 'little') + b"\x11\x00\x16"
            _LOGGER.debug("> %s", ack_packet.hex())
            await client.write_gatt_char(COMMAND_UUID, ack_packet, response=True)

            with suppress(BleakError):
                await client.stop_notify(NOTIFICATION_UUID)

            _LOGGER.info(f"Successfully bound to {device.name} with SSID: {ssid}.")

# 扫描附近的蓝牙设备并列出设备供用户选择
async def scan_devices():
    devices = await BleakScanner.discover()
    if not devices:
        _LOGGER.error("No BLE devices found.")
        return []
    
    print("Found the following BLE devices:")
    for i, device in enumerate(devices):
        print(f"{i + 1}: {device.name} ({device.address})")

    return devices

# 让用户选择设备
def choose_device(devices):
    while True:
        try:
            choice = int(input(f"Please choose a device by number (1-{len(devices)}): "))
            if 1 <= choice <= len(devices):
                return devices[choice - 1]
            else:
                print("Invalid choice. Please select a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

# 异步主函数
async def main():
    devices = await scan_devices()
    if not devices:
        return  # No devices found, exit

    device = choose_device(devices)

    # 设置Wi-Fi信息
    ssid = "SSID"
    password = "PASSWORD"

    # 创建 AirWaterBLEConnector 实例并绑定 AP
    air_water_ble_connector = AirWaterBLEConnector()

    try:
        # 执行连接操作
        await air_water_ble_connector.bind_ap(device, ssid, password)
        print(f"AP binding was successful for {device.name}!")
    except Exception as e:
        print(f"Failed to bind AP to {device.name}. Error: {e}")

# 运行主程序
asyncio.run(main())
