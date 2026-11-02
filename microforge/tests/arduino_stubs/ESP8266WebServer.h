#pragma once
#include <Arduino.h>
#include <functional>
class ESP8266WebServer { public: ESP8266WebServer(int); void on(const char*, std::function<void()>); void begin(); void handleClient(); void send(int, const char*, const String&); };
