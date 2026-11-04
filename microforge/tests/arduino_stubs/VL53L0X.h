#pragma once
#include <Wire.h>
class VL53L0X {
 public:
  bool init(bool io_2v8 = true);
  void setTimeout(uint16_t timeout);
  uint16_t readRangeSingleMillimeters();
  bool timeoutOccurred();
};
