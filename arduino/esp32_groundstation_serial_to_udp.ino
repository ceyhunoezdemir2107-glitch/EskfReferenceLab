// ESP32 ground station bridge for ESKF Reference Lab.
//
// Use this when the aircraft sends JSON lines over a transparent serial radio
// or telemetry modem. The ground station reads those lines on Serial2 and
// forwards them to:
//   1) USB Serial, so the Python logger can use --serial COMx
//   2) UDP, so the Python logger can use --udp-port 5555

#include <WiFi.h>
#include <WiFiUdp.h>

#define FORWARD_TO_USB_SERIAL 1
#define FORWARD_TO_UDP 1
#define DEBUG_STATUS_TO_USB_SERIAL 0

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

IPAddress PC_IP(192, 168, 0, 112);
const uint16_t PC_UDP_PORT = 5555;
const uint16_t LOCAL_UDP_PORT = 5557;

const uint32_t RADIO_SERIAL_BAUD = 57600;
const int RADIO_RX_PIN = 16;
const int RADIO_TX_PIN = 17;

WiFiUDP udp;
String radioLine;

static void debugPrint(const char* text) {
#if DEBUG_STATUS_TO_USB_SERIAL
  Serial.print(text);
#else
  (void)text;
#endif
}

static void debugPrintln(const char* text) {
#if DEBUG_STATUS_TO_USB_SERIAL
  Serial.println(text);
#else
  (void)text;
#endif
}

static void connectWifi() {
#if FORWARD_TO_UDP
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  debugPrint("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    debugPrint(".");
  }
#if DEBUG_STATUS_TO_USB_SERIAL
  Serial.println();
  Serial.print("Ground station IP: ");
  Serial.println(WiFi.localIP());
#endif
  udp.begin(LOCAL_UDP_PORT);
#endif
}

static void forwardLine(const String& line) {
  if (line.length() == 0) {
    return;
  }
#if FORWARD_TO_USB_SERIAL
  Serial.println(line);
#endif
#if FORWARD_TO_UDP
  if (WiFi.status() == WL_CONNECTED) {
    udp.beginPacket(PC_IP, PC_UDP_PORT);
    udp.write(reinterpret_cast<const uint8_t*>(line.c_str()), line.length());
    udp.endPacket();
  }
#endif
}

static void pollRadio() {
  while (Serial2.available() > 0) {
    char c = static_cast<char>(Serial2.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      forwardLine(radioLine);
      radioLine = "";
      continue;
    }
    if (radioLine.length() < 900) {
      radioLine += c;
    } else {
      radioLine = "";
      debugPrintln("Dropped oversized radio line");
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(RADIO_SERIAL_BAUD, SERIAL_8N1, RADIO_RX_PIN, RADIO_TX_PIN);
  delay(200);
  debugPrintln("ESKF ground station bridge");
  connectWifi();
}

void loop() {
  pollRadio();
}
