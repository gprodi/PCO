#pragma once
#include <Arduino.h>
#define NEO_GRB 0x52
#define NEO_KHZ800 0x0000
class Adafruit_NeoPixel {
 public:
  Adafruit_NeoPixel(uint16_t n, int16_t pin, uint16_t type);
  void begin(); void show(); void setBrightness(uint8_t); uint16_t numPixels() const;
  void setPixelColor(uint16_t, uint32_t);
  static uint32_t Color(uint8_t, uint8_t, uint8_t);
  static uint32_t ColorHSV(uint16_t hue, uint8_t sat = 255, uint8_t val = 255);
};
