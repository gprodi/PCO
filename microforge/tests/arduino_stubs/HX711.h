#pragma once
#include <Arduino.h>
class HX711 { public: void begin(byte, byte); void set_scale(float); void tare(); bool is_ready(); float get_units(byte); };
