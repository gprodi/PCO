#pragma once
#include <Wire.h>
class Adafruit_INA219 {
 public:
  Adafruit_INA219(uint8_t addr = 0x40);
  bool begin(TwoWire* theWire = &Wire);
  float getBusVoltage_V();
  float getShuntVoltage_mV();
  float getCurrent_mA();
  float getPower_mW();
};
