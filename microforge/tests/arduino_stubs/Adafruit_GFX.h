#pragma once
#include <Arduino.h>
class Adafruit_GFX : public Print { public: void setCursor(int16_t, int16_t); void setTextSize(uint8_t); void setTextColor(uint16_t); };
