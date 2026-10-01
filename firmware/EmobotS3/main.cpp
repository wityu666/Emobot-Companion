#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <BLEDevice.h>
#include <BLE2902.h>
#include "RobotHardware.h"
#include "CloudVoice.h"

using namespace emobot;
Hardware hardware;
CloudVoice voice;
Preferences network;
WebServer portal(80);
WiFiUDP discovery;
BLECharacteristic *control = nullptr;
QueueHandle_t inbox;
uint32_t booted = 0, advertised = 0, scanned = 0;
bool accessPoint = false;
constexpr size_t frameLimit = 8192;

bool enqueue(const String &message) {
  if (message.length() > frameLimit)
    return false;
  char *copy = strdup(message.c_str());
  if (!copy)
    return false;
  if (xQueueSend(inbox, &copy, 0) != pdTRUE) {
    free(copy);
    return false;
  }
  return true;
}
void announce(const String &message) {
  Serial.println(message);
  if (control) {
    // Notifications use small chunks so the same newline decoder works at any BLE MTU.
    String line = message + "\n";
    for (size_t at = 0; at < line.length(); at += 20) {
      control->setValue(reinterpret_cast<uint8_t *>(const_cast<char *>(line.c_str() + at)),
                        min(size_t(20), line.length() - at));
      control->notify();
    }
  }
}
class Assembler {
  String line;
  bool dropping = false;

public:
  void feed(const uint8_t *bytes, size_t length) {
    for (size_t i = 0; i < length; ++i) {
      if (bytes[i] == '\n') {
        if (!dropping && line.length())
          enqueue(line);
        line = "";
        dropping = false;
      } else if (!dropping) {
        line += char(bytes[i]);
        if (line.length() > frameLimit) {
          line = "";
          dropping = true;
        }
      }
    }
  }
};
Assembler serialLines;
class Receiver : public BLECharacteristicCallbacks {
  Assembler lines;
  void onWrite(BLECharacteristic *characteristic) override {
    std::string bytes = characteristic->getValue();
    lines.feed(reinterpret_cast<const uint8_t *>(bytes.data()), bytes.size());
  }
};
class ServerEvents : public BLEServerCallbacks {
  void onDisconnect(BLEServer *server) override { server->getAdvertising()->start(); }
};
void startBLE() {
  BLEDevice::init("Emobot-Companion");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerEvents);
  BLEService *service = server->createService("4db9a22d-6db4-d9fe-4d93-38e350abdc3c");
  control = service->createCharacteristic("ff1cdaef-0105-e4fb-7be2-018500c2e927",
                                          BLECharacteristic::PROPERTY_WRITE |
                                              BLECharacteristic::PROPERTY_NOTIFY);
  control->addDescriptor(new BLE2902);
  control->setCallbacks(new Receiver);
  service->start();
  BLEAdvertising *advertising = server->getAdvertising();
  advertising->addServiceUUID(service->getUUID());
  advertising->setScanResponse(true);
  advertising->start();
}
void startPortal() {
  if (accessPoint)
    return;
  WiFi.softAP("Desk-Emoji", EMOBOT_AP_PASSWORD);
  accessPoint = true;
  portal.on("/", HTTP_GET, [] {
    portal.send(
        200, "text/html; charset=utf-8",
        "<!doctype html><html lang='en'><meta name='viewport' "
        "content='width=device-width'><title>Emobot Wi-Fi</title><h1>Emobot Wi-Fi</h1><form "
        "method='post' action='/wifi'>SSID <input name='ssid' maxlength='32' required><br>Password "
        "<input name='password' type='password' maxlength='63'><br><button>Save and "
        "reconnect</button></form><p>Configuration stays on this device.</p></html>");
  });
  portal.on("/wifi", HTTP_POST, [] {
    String ssid = portal.arg("ssid"), password = portal.arg("password");
    if (!ssid.length() || ssid.length() > 32 || password.length() > 63 ||
        (password.length() > 0 && password.length() < 8)) {
      portal.send(400, "text/plain", "Invalid network credentials");
      return;
    }
    network.putString("ssid", ssid);
    network.putString("password", password);
    WiFi.begin(ssid.c_str(), password.c_str());
    portal.send(200, "text/plain", "Saved. Connecting; USB and Bluetooth remain available.");
  });
  portal.begin();
}
void process(const String &message) {
  JsonDocument request, response;
  if (deserializeJson(request, message)) {
    announce("{\"ok\":false,\"error\":\"invalid JSON\"}");
    return;
  }
  if (request["voice"].is<const char *>()) {
    announce(message);
    return;
  }
  bool ok = false;
  if (request["actions"].is<JsonArray>())
    ok = hardware.accept(request["actions"].as<JsonArrayConst>());
  else if (request["factory"].is<const char *>()) {
    String command = request["factory"].as<String>();
    if (command == "reset_wifi") {
      network.remove("ssid");
      network.remove("password");
      WiFi.disconnect();
      startPortal();
      ok = true;
    } else {
      String result = hardware.command(command);
      response["result"] = result;
      ok = result == "ok" || command == "mac_address";
    }
  } else if (request["preferences"].is<JsonObject>()) {
    if (voice.phase)
      response["error"] = "voice is busy";
    else {
      String lang = request["preferences"]["language"].as<String>(),
             persona = request["preferences"]["persona"].as<String>();
      if ((lang == "zh" || lang == "en") && persona.length() <= 3000) {
        voice.language = lang;
        voice.persona = persona;
        network.putString("language", lang);
        network.putString("persona", persona);
        ok = true;
      }
    }
  }
  response["ok"] = ok;
  if (!ok && response["error"].isNull())
    response["error"] = "invalid command or action player busy";
  String encoded;
  serializeJson(response, encoded);
  announce(encoded);
}
void setup() {
  Serial.begin(115200);
  booted = millis();
  inbox = xQueueCreate(4, sizeof(char *));
  if (!inbox) {
    Serial.println("{\"ok\":false,\"error\":\"queue allocation\"}");
    return;
  }
  hardware.begin();
  startBLE();
  network.begin("emobot-net", false);
  voice.language = network.getString("language", "zh");
  voice.persona = network.getString("persona", voice.persona);
  voice.begin([](const String &message) { enqueue(message); });
  WiFi.mode(WIFI_AP_STA);
  String ssid = network.getString("ssid", ""), password = network.getString("password", "");
  if (ssid.length())
    WiFi.begin(ssid.c_str(), password.c_str());
  else
    startPortal();
  configTime(0, 0, "pool.ntp.org", "time.cloudflare.com");
  discovery.begin(4210);
  announce("{\"ready\":true,\"version\":\"1.1.0\"}");
}
void loop() {
  if (!inbox) {
    delay(100);
    return;
  }
  while (Serial.available()) {
    uint8_t byte = Serial.read();
    serialLines.feed(&byte, 1);
  }
  char *message = nullptr;
  if (xQueueReceive(inbox, &message, 0) == pdTRUE) {
    process(String(message));
    free(message);
  }
  hardware.tick(voice.phase);
  uint32_t time = millis();
  if (!accessPoint && WiFi.status() != WL_CONNECTED && time - booted > 20000)
    startPortal();
  if (accessPoint)
    portal.handleClient();
  if (WiFi.status() == WL_CONNECTED && time - advertised > 5000) {
    discovery.beginPacket(IPAddress(255, 255, 255, 255), 4210);
    discovery.print(WiFi.localIP().toString());
    discovery.endPacket();
    advertised = time;
  }
  if (time - scanned > 100) {
    scanned = time;
    Gesture gesture = hardware.readGesture();
    const char *action = nullptr;
    switch (gesture) {
    case GES_FORWARD:
      if (!voice.trigger())
        announce("{\"voice\":\"unavailable or busy\"}");
      break;
    case GES_BACKWARD:
      action = "eye_blink";
      break;
    case GES_UP:
      action = "head_left";
      break;
    case GES_DOWN:
      action = "head_right";
      break;
    case GES_RIGHT:
      action = "head_up";
      break;
    case GES_LEFT:
      action = "head_down";
      break;
    case GES_CLOCKWISE:
      action = "eye_happy";
      break;
    case GES_ANTICLOCKWISE:
      action = clips[esp_random() % 42];
      break;
    case GES_WAVE:
      action = "head_shake";
      break;
    default:
      break;
    }
    if (action) {
      JsonDocument plan;
      plan["actions"][0]["action"] = action;
      plan["actions"][0]["duration"] = 900;
      hardware.accept(plan["actions"].as<JsonArrayConst>());
    }
  }
  delay(2);
}
