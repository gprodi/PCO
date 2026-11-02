#pragma once
#include <Arduino.h>
class LedControl { public: LedControl(int, int, int, int); void shutdown(int, bool); void setIntensity(int, int); void clearDisplay(int); void setRow(int, int, byte); void setColumn(int, int, byte); };
