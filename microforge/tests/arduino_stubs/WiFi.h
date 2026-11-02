#pragma once
#include <Arduino.h>
#define WIFI_STA 1
#define WL_CONNECTED 3
class IPAddress {};
inline Print& operator<<(Print& p, const IPAddress&) { return p; }
class WiFiClass { public: void mode(int); void begin(const char*, const char*); int status(); IPAddress localIP(); };
extern WiFiClass WiFi;
#if defined(ARDUINO_ARCH_RP2040)
// arduino-pico : client NTP intégré au cœur
class NTPClass { public: void begin(const char*, const char* = nullptr); };
extern NTPClass NTP;
#endif
