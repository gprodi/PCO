#pragma once
#include <stdint.h>
class SPIClass {
 public:
  void begin();
  void begin(int8_t sck, int8_t miso, int8_t mosi, int8_t ss = -1);  // ESP32
  void setRX(uint8_t);  // RP2040 (arduino-pico)
  void setTX(uint8_t);
  void setSCK(uint8_t);
};
extern SPIClass SPI;
