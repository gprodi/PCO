#pragma once
#include <Adafruit_Sensor.h>
class Adafruit_BME280 { public: bool begin(uint8_t addr); float readTemperature(); float readHumidity(); float readPressure(); float readAltitude(float); };
