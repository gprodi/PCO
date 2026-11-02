#pragma once
#include <Arduino.h>
class MFRC522 {
 public:
  struct Uid { byte size; byte uidByte[10]; } uid;
  MFRC522(byte ss, byte rst);
  void PCD_Init(); bool PICC_IsNewCardPresent(); bool PICC_ReadCardSerial(); void PICC_HaltA();
};
