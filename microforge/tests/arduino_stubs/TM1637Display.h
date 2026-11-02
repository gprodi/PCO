#pragma once
#include <Arduino.h>
class TM1637Display { public: TM1637Display(uint8_t, uint8_t); void setBrightness(uint8_t); void showNumberDec(int, bool = false); void showNumberDecEx(int, uint8_t, bool = false); };
