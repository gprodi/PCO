#pragma once
#include <Adafruit_Sensor.h>
class Adafruit_BMP280 {
 public:
  bool begin(uint8_t addr = 0x77, uint8_t chipid = 0x58);
  float readTemperature();
  float readPressure();
  float readAltitude(float seaLevelhPa = 1013.25);
};
