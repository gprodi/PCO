#pragma once
#include <Adafruit_Sensor.h>
#include <Arduino.h>
class Adafruit_MPU6050 { public: bool begin(uint8_t addr); bool getEvent(sensors_event_t*, sensors_event_t*, sensors_event_t*); };
