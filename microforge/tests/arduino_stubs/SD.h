#pragma once
#include <Arduino.h>
#define FILE_WRITE 1
class File : public Print { public: explicit operator bool() const; void close(); };
class SDClass { public: bool begin(uint8_t); File open(const char*, uint8_t = 0); };
extern SDClass SD;
