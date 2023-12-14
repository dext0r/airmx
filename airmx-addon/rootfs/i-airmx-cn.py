#!/usr/bin/env python3
import argparse
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
import json
from json import JSONDecodeError
import logging
import os.path
from typing import Any

from flask import Flask, request
from werkzeug import exceptions as HTTPException

DEVICE_STORE_PATH = "/data/devices.json"

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


@dataclass
class Device:
    id: int
    key: str
    wifi_mac: str
    ble_mac: str
    type: int
    ts: int


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)

        return super().default(o)


def _load_devices(path: str) -> dict[int, Device]:
    rv: dict[int, Device] = {}
    if os.path.isfile(path):
        with open(path, "r") as f:
            try:
                for item in json.load(f).values():
                    device = Device(**item)
                    rv[device.id] = device
            except JSONDecodeError:
                app.logger.exception("Failed to load devices.json")

    return rv


devices: dict[int, Device] = _load_devices(DEVICE_STORE_PATH)


@app.route("/")
def root() -> str:
    return "AIRMX addon\n"


@app.route("/aw")
def aw() -> dict[str, Any] | str:
    if (path := request.args.get("path")) != "aw/GET/genId":
        app.logger.error(f"Unsupported path {path}")
        raise HTTPException.NotImplemented()

    params = json.loads(request.args.get("params", ""))
    wifi_mac = int.from_bytes(bytearray.fromhex(params["mac"]), byteorder="little")
    ble_mac = wifi_mac + 2
    device = Device(
        id=int.from_bytes(bytearray.fromhex(params["mac"])[:2], byteorder="little"),
        wifi_mac=wifi_mac.to_bytes(6, byteorder="big").hex(),
        ble_mac=ble_mac.to_bytes(6, byteorder="big").hex(),
        key=params["key"],
        type=int(params["type"]),
        ts=int(datetime.now().timestamp()),
    )

    data: dict[str, Any] | None = None
    match device.type:
        case 11:  # A5
            pass
        case 21:  # A3S_V2 / Iris
            data = {
                "awId": device.id,
                "electrolysisLevel4OffTime": 1800,
                "electrolysisLevel2OpenTime": 600,
                "electrolysisLevel3OpenTime": 1200,
                "electrolysisLevel4OpenTime": 1800,
                "electrolysisLevel2OffTime": 600,
                "electrolysisLevel1OpenTime": 60,
                "electrolysisLevel3OffTime": 1200,
                "electrolysisLevel1OffTime": 120,
            }
        case _:
            app.logger.error(f"Unsupported device: {device}")
            raise HTTPException.NotImplemented()

    app.logger.info(f"New device registered: {device}")
    devices[device.id] = device

    with open(DEVICE_STORE_PATH, "w") as f:
        json.dump(devices, f, cls=EnhancedJSONEncoder)

    if not data:
        return '{"status":200,"data":{"awId":%d}}' % device.id

    return {"status": 200, "data": data}


@app.route("/gettime")
def gettime() -> dict[str, int]:
    return {"time": int(datetime.now().timestamp())}


@app.route("/check/airwater/washCleanNotify")
def wash_clean_notify() -> dict[str, int]:
    return {"status": 200}


@app.route("/_devices")
def get_devices() -> list[dict[str, str | int]]:
    return [asdict(device) for device in sorted(devices.values(), key=lambda d: d.ts * -1)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=80, type=int)
    args = parser.parse_args()

    app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)
