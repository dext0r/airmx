# AIRMX and Tion Iris humidifiers component for Home Assistant

**English** | [Русский](./README.ru.md) | [中文](./README.zh.md)

The component allows you to control AIRMX and Tion Iris humidifiers via Home Assistant completely locally. Simultaneous control via HA and the original Chinese AIRMX app is not possible.

List of steps:

* Install the addon
* Install the component
* Make settings on the router or start a dedicated access point on the ESP8266
* Reset the humidifier by holding the Power + Refill buttons for 3 seconds
* Add the humidifier to the Home Assistant
* Optional: connect the humidifier to a "home" access point

Integration chat: [@homeassistant_airmx](https://t.me/homeassistant_airmx)

## Supported devices

* AirWater A2
* AirWater A3
* AirWater A3S
* AirWater A3S V2 (aka Tion Iris)
* AirWater A5

## Install the addon

The component requires an additional addon to be installed. Requests that the device tries to send to the Chinese servers `i.airmx.cn` and `awm.airmx.cn` will be redirected to it.

To install the addon:

* Settings > Add-ons > Add-on Store
* 3 dots (upper right corner) > Repositories
* Enter `https://github.com/dext0r/airmx` and click Add
* 3 dots (top right corner) > Check for updates > Refresh the page
* Type `airmx` in the search and install the addon

Don't forget to run the addon and be sure to enable starting on boot.

## Install the component

**Recommended method:** [HACS](https://hacs.xyz/)

* Install and configure [HACS](https://hacs.xyz/docs/use/#getting-started-with-hacs)
* Open HACS > Three dots in the upper right corner > Custom Repositories
* Add the `dext0r/airmx` repository (type `Integration`)
* Search for and open `AIRMX` > Download
* Reboot Home Assistant

**Manual method:**

* Download `airmx.zip` archive from [latest release](https://github.com/dext0r/airmx/releases/latest)
* Create a subdirectory `custom_components/airmx` in the directory where the `configuration.yaml` file is located.
* Extract the contents of the archive to `custom_components/airmx`.
* Reboot Home Assistant

## Redirect requests to the addon

### Keenetic router

1. Create a dedicated [network segment](https://help.keenetic.com/hc/en/articles/360005236300):
   * Segment name: any (e.g. `airmx`)
   * Wireless network: enable
   * Network name (SSID): `miaoxin`.
   * Network protection: `WPA2-PSK`.
   * Password: `miaoxin666`.
   * Use NAT: enable
   * Connection policy: No Internet access
2. Open [command line](https://help.keenetic.com/hc/en/articles/213965889) via web interface at `my.keenetic.ru/a` (or `192.168.1.1/a`)
3. Execute the commands in sequence (replace `X.X.X.X` with your HA server IP):
   * `ip static tcp 82.157.56.105 255.255.255.255 80 X.X.X.X 25880 !i.airmx.cn`
   * `ip static tcp 140.143.130.176 255.255.255.255 1883 X.X.X.X 25883 !awm.airmx.cn`
   * `ip host i.airmx.cn 82.157.56.105`
   * `ip host awm.airmx.cn 140.143.130.176`
   * `system configuration save`

### Mikrotik router

1. Create a WiFi interface with SSID `miaoxin` and password `miaoxin666`
2. Create DNAT rules and static DNS entries:

```text
# replace X.X.X.X with your HA server IP
# (you can use the same IP for i and awm if you want)
/ip dns static add address=82.157.56.105 name=i.airmx.cn ttl=30s
/ip dns static add address=140.143.130.176 name=awm.airmx.cn ttl=30s
/ip firewall address-list add address=82.157.56.105 comment=i.airmx.cn list=airmx
/ip firewall address-list add address=140.143.130.176 comment=awm.airmx.cn list=airmx
/ip firewall mangle add action=mark-connection chain=prerouting comment=airmx dst-address-list=airmx new-connection-mark=airmx passthrough=no
/ip firewall nat add action=masquerade chain=srcnat comment=airmx-masquarade connection-mark=airmx
/ip firewall nat add action=dst-nat chain=dstnat comment=airmx-http dst-address-list=airmx dst-port=80 protocol=tcp to-addresses=X.X.X.X to-ports=25880
/ip firewall nat add action=dst-nat chain=dstnat comment=airmx-mqtt dst-address-list=airmx dst-port=1883 protocol=tcp to-addresses=X.X.X.X to-ports=25883
```

### Other routers

1. Create a network with SSID `miaoxin` and password `miaoxin666`
2. Configure DNATs (port forwarding, replace X.X.X.X with your HA server IP):

   * `i.airmx.cn 82.157.56.105 80/tcp` на `X.X.X.X:25880`
   * `awm.airmx.cn 140.143.130.176 1883/tcp` на `X.X.X.X:25883`

### Mini router on ESP8266

If you don't have either Keenetic or Mikrotik, and your router is too dumb - there's one last option: create an access point on ESP8266.

To do this:

1. Flash this firmware into ESP8266 using any flasher: [airmx-esp-gate.ino.bin](https://github.com/dext0r/airmx/raw/main/airmx-esp-gate/build/esp8266.esp8266.nodemcu/airmx-esp-gate.ino.bin)
2. Once booted, connect to the `miaoxin` access point with the password `miaoxin666`
3. Open the configurator page: `http://192.168.4.1:8888` -> WIFI
4. Select your home access point and make sure to specify the Home Assistant server IP

## Adding the humidifier to Home Assistant

Before connecting, make sure that all network settings are correct. To do this, connect to the `miaoxin` access point and go to `http://i.airmx.cn` - you should see the message `AIRMX addon`.

To add a humidifier:

1. Reset the humidifier by holding the Power + Refill buttons for 3 seconds (it should beep)
2. After reset, the humidifier will automatically connect to the `miaoxin/miaoxin666` access point and make a request to `http://i.airmx.cn`, this request will be forwarded to the addon.
3. In Home Assistant, open Settings > Devices & Services > Add Integration > AIRMX (if not in the list - refresh the page)
4. Select "Automatic Setup"

## Connect the humidifier to home access point

Optional but recommended step.

Using Home Assistant (requires a configured Bluetooth adapter):

* Open Settings > Devices & Services > Add integration > AIRMX
* Select "Bind device to the Access Point"

Using the native AIRMX app (not working as Nov 2024):

* Requires login via Apple ID or Chinese phone number
* Follow [screenshots](./images/ios) (make sure to give geolocation permissions)
* After entering SSID and password, wait 20-30 seconds and you can close the application

Using Windows PC with ble controller.

* Env: Python >= 3.7, "pip install bleak"
* Edit SSID and PASSWOR in ./change_ap_with_pc/conn.py
* Run "pyhon ./change_ap_with_pc/conn.py", will scan nearby ble devices, choose each AIRMX device.

## Other

* Changing AP binding can be done at any time, no need to remove the device from HA
