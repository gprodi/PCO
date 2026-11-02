#pragma once
#include <Arduino.h>
class Servo { public: uint8_t attach(int); uint8_t attach(int, int, int); void write(int); };
