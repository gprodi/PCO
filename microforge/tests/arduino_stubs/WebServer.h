#pragma once
#include <Arduino.h>
#include <functional>
class WebServer { public: WebServer(int); void on(const char*, std::function<void()>); void begin(); void handleClient(); void send(int, const char*, const String&); };
