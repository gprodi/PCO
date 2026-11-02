#pragma once
#include <Arduino.h>
#define WIFI_STA 1
#define WL_CONNECTED 3
class IPAddress {};
class WiFiClass { public: void mode(int); void begin(const char*, const char*); int status(); IPAddress localIP(); };
extern WiFiClass WiFi;
