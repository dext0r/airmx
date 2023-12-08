from homeassistant.const import Platform

DOMAIN = "airmx"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.HUMIDIFIER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

DEVICES = "devices"
SETTING_STORES = "settings_stores"

CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_SIGN_KEY = "sign_key"
CONF_SSID = "ssid"

ATTR_ANION = "anion"
ATTR_CHILD_LOCK = "child_lock"
ATTR_COMMAND = "command"
ATTR_FAN_SPEED = "fan_speed"
ATTR_HEATER = "heater"
ATTR_HUMIDITY = "humidity"
ATTR_MALFUNCTION = "malfunction"
ATTR_NEED_CLEANING = "need_cleaning"
ATTR_PROXIMITY_SENSOR = "proximity_sensor"
ATTR_REMOTE_SENSOR_RSSI = "remote_sensor_rssi"
ATTR_STATUS = "status"
ATTR_UV = "uv"
ATTR_WATER_LEVEL = "water_level"
ATTR_WATER_TYPE = "water_type"
ATTR_WUD = "wud"

MODE_MANUAL = "manual"

SERVICE_SEND_COMMAND = "send_command"
ATTR_COMMAND_ID = "command_id"
ATTR_COMMAND_DATA = "command_data"
