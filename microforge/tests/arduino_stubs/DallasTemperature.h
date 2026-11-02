#pragma once
#include <OneWire.h>
class DallasTemperature { public: DallasTemperature(OneWire*); void begin(); void requestTemperatures(); float getTempCByIndex(uint8_t); };
