#pragma once
#include <Arduino.h>
// Sous-ensemble de l'API IRremote 4.x utilisé par MicroForge.
enum decode_type_t { UNKNOWN = 0, NEC = 8 };
#define IRDATA_FLAGS_IS_REPEAT 0x01
struct IRData { decode_type_t protocol; uint16_t address; uint16_t command; uint8_t flags; };
class IRrecv { public: void begin(uint8_t, bool = true); bool decode(); void resume(); IRData decodedIRData; };
extern IRrecv IrReceiver;
