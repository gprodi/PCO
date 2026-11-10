#pragma once
#include <Arduino.h>
class DateTime { public: DateTime(const char*, const char*); char* toString(char*); uint8_t hour() const; uint8_t minute() const; uint8_t day() const; uint8_t month() const; };
class RTC_DS3231 { public: bool begin(); bool lostPower(); void adjust(const DateTime&); DateTime now(); };
