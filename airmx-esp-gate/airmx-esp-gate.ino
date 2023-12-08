#include "WiFiManager.h"  // https://github.com/tzapu/WiFiManager
#include <Preferences.h>  // https://github.com/vshymanskyy/Preferences
#include "TCPProxy.h"

#define RESET_PIN 4  // D2
#define LED_PIN 2    // D4
#define VERSION "v1"

uint16_t httpPort = 8888;
const char* prefsNamespace = "airmx-gate";
WiFiManagerParameter haAddressParam("ha_addr", "Home Assistant IP");
WiFiManagerParameter apSSIDParam("ap_ssid", "Access Point SSID");
WiFiManagerParameter apPasswordParam("ap_password", "Access Point Password");
WiFiEventHandler onStationModeGotIPHandler;

Preferences prefs;
WiFiManager wm;
IPAddress haAddress;

void setup() {
  Serial.begin(115200);

  wm.setConfigResetCallback(configResetCallback);
  pinMode(RESET_PIN, INPUT_PULLUP);
  if (digitalRead(RESET_PIN) == LOW) {
    wm.resetSettings();

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    return;
  }

  Serial.println();
  wm.setDebugOutput(true, WM_DEBUG_DEV);
  wm.setAPCallback(configModeCallback);
  wm.setSaveConfigCallback(saveConfigCallback);
  wm.setTitle("AIRMX Gate " VERSION);
  wm.setBreakAfterConfig(true);
  wm.setHttpPort(8888);

  prefs.begin(prefsNamespace);
  haAddress = prefs.getULong(haAddressParam.getID());
  haAddressParam.setValue(haAddress.toString().c_str(), 15);
  apSSIDParam.setValue(prefs.getString(apSSIDParam.getID(), "miaoxin").c_str(), 16);
  apPasswordParam.setValue(prefs.getString(apPasswordParam.getID(), "miaoxin666").c_str(), 16);
  wm.addParameter(&haAddressParam);
  wm.addParameter(&apSSIDParam);
  wm.addParameter(&apPasswordParam);
  prefs.end();

  onStationModeGotIPHandler = WiFi.onStationModeGotIP(WiFiGotIP);

  wm.autoConnect(apSSIDParam.getValue(), apPasswordParam.getValue());
  wm.startConfigPortal(apSSIDParam.getValue(), apPasswordParam.getValue());
}

void loop() {
  wm.process();
}

void configModeCallback(WiFiManager* myWiFiManager) {
  if (haAddress) {
    tcp_proxy_start(WiFi.softAPIP(), haAddress, httpPort);
  } else {
    Serial.println("No HA address, skipping proxy start");
  }
}

void saveConfigCallback() {
  Serial.println("Saving config");

  prefs.begin(prefsNamespace);
  IPAddress haAddress;
  haAddress.fromString(haAddressParam.getValue());
  prefs.putULong(haAddressParam.getID(), haAddress);
  if (strlen(apPasswordParam.getValue()) >= 8) {
    prefs.putString(apSSIDParam.getID(), apSSIDParam.getValue());
    prefs.putString(apPasswordParam.getID(), apPasswordParam.getValue());
  }
  prefs.end();

  ESP.restart();
}

void configResetCallback() {
  prefs.begin(prefsNamespace);
  prefs.clear();
  prefs.end();
}

void WiFiGotIP(const WiFiEventStationModeGotIP& event) {
  tcp_proxy_set_proxy_addr(WiFi.localIP());
}
