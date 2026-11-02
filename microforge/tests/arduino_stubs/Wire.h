#pragma once
#include <Arduino.h>
class TwoWire {
 public:
  void begin();
  void begin(int sda, int scl);   // ESP32, ESP8266
  void setSDA(uint8_t);           // RP2040 (arduino-pico)
  void setSCL(uint8_t);
};
extern TwoWire Wire;
