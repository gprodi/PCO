#pragma once
#include <Arduino.h>
class DateTime { public: DateTime(const char*, const char*); char* toString(char*); };
class RTC_DS3231 { public: bool begin(); bool lostPower(); void adjust(const DateTime&); DateTime now(); };
