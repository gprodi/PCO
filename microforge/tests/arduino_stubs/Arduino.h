// Stub minimal de l'API Arduino : sert UNIQUEMENT à vérifier la syntaxe C++ des firmwares générés
// (g++ -fsyntax-only). La vraie compilation se fait avec arduino-cli dans la CI.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstddef>
#include <cstdlib>
#include <algorithm>
typedef uint8_t byte;
typedef bool boolean;
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define HEX 16
#define DEC 10
#define PI 3.14159265358979f
#define F(x) (x)
#define A0 14
#define A1 15
#define A2 16
#define A3 17
#define A4 18
#define A5 19
#define A6 20
#define A7 21
#define A8 22
#define A9 23
#define A10 24
#define A11 25
#define A12 26
#define A13 27
#define A14 28
#define A15 29
#define A16 30
#define A17 31
// Macros réelles du cœur AVR (variants/standard/pins_arduino.h) : un firmware qui déclare
// une constante du même nom ne compile pas. On les reproduit pour détecter ces collisions.
#ifdef ARDUINO_ARCH_AVR
#define PIN_SPI_SS (10)
#define PIN_SPI_MOSI (11)
#define PIN_SPI_MISO (12)
#define PIN_SPI_SCK (13)
#define PIN_WIRE_SDA (18)
#define PIN_WIRE_SCL (19)
#endif
// STM32duino : les broches se nomment PA0…PC15 (valeurs propres à chaque variante).
#ifdef ARDUINO_ARCH_STM32
#define PA0 200
#define PA1 201
#define PA2 202
#define PA3 203
#define PA4 204
#define PA5 205
#define PA6 206
#define PA7 207
#define PA8 208
#define PA9 209
#define PA10 210
#define PA11 211
#define PA12 212
#define PA13 213
#define PA14 214
#define PA15 215
#define PB0 216
#define PB1 217
#define PB2 218
#define PB3 219
#define PB4 220
#define PB5 221
#define PB6 222
#define PB7 223
#define PB8 224
#define PB9 225
#define PB10 226
#define PB11 227
#define PB12 228
#define PB13 229
#define PB14 230
#define PB15 231
#define PC13 232
#define PC14 233
#define PC15 234
#define PH0 235
#define PH1 236
#endif
using std::isnan;
using std::abs;
// Comme arduino-esp32 / arduino-pico (sur AVR ce sont des macros) : mêmes types obligatoires des deux côtés
using std::min;
using std::max;
void pinMode(uint8_t, uint8_t);
#define MSBFIRST 1
#define LSBFIRST 0
void shiftOut(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder, uint8_t val);
uint8_t shiftIn(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder);
void digitalWrite(uint8_t, uint8_t);
int digitalRead(uint8_t);
int analogRead(uint8_t);
void analogWrite(uint8_t, int);
unsigned long millis();
unsigned long micros();
void delay(unsigned long);
void delayMicroseconds(unsigned int);
unsigned long pulseIn(uint8_t, uint8_t, unsigned long timeout = 1000000UL);
void tone(uint8_t, unsigned int, unsigned long duration = 0);
void noTone(uint8_t);
long random(long);
long random(long, long);
void randomSeed(unsigned long);
long map(long, long, long, long, long);
template <class T, class L, class H> T constrain(T x, L a, H b) { return x < a ? a : (x > b ? b : x); }

class StringSumHelper;
class String {
 public:
  String(const char* s = "");
  String(const String&);
  explicit String(char c);
  explicit String(unsigned char, unsigned char base = 10);
  explicit String(int, unsigned char base = 10);
  explicit String(unsigned int, unsigned char base = 10);
  explicit String(long, unsigned char base = 10);
  explicit String(unsigned long, unsigned char base = 10);
  explicit String(float, unsigned char decimals = 2);
  explicit String(double, unsigned char decimals = 2);
  String& operator=(const String&);
  String& operator+=(const String&);
  String& operator+=(const char*);
  String& operator+=(char);
  bool operator==(const String&) const;
  bool operator==(const char*) const;
  bool operator!=(const String&) const;
  unsigned int length() const;
  String substring(unsigned int, unsigned int) const;
  String substring(unsigned int) const;
  void toUpperCase();
  const char* c_str() const;
  friend StringSumHelper& operator+(const StringSumHelper&, const String&);
  friend StringSumHelper& operator+(const StringSumHelper&, const char*);
  friend StringSumHelper& operator+(const StringSumHelper&, char);
  friend StringSumHelper& operator+(const StringSumHelper&, int);
  friend StringSumHelper& operator+(const StringSumHelper&, unsigned long);
  friend StringSumHelper& operator+(const StringSumHelper&, float);
};
class StringSumHelper : public String {
 public:
  StringSumHelper(const String& s) : String(s) {}
  StringSumHelper(const char* p) : String(p) {}
  StringSumHelper(char c) : String(c) {}
  StringSumHelper(int n) : String(n) {}
};

class Print {
 public:
  template <class T> size_t print(T) { return 0; }
  template <class T> size_t print(T, int) { return 0; }
  template <class T> size_t println(T) { return 0; }
  template <class T> size_t println(T, int) { return 0; }
  size_t println() { return 0; }
};
class HardwareSerial : public Print {
 public:
  void begin(unsigned long);
  int available();
  int read();
};
extern HardwareSerial Serial;

#if defined(ESP32) || defined(ESP8266)
// c_types.h des SDK Espressif (inclus par Arduino.h) : ces noms sont déjà pris ;
// un « const int OK = 64; » dans un croquis ne compile pas (CI 134, robot-infrarouge).
typedef enum { OK = 0, FAIL, PENDING, BUSY, CANCEL } STATUS;
#endif

#if defined(ESP32)
#include <ctime>
bool getLocalTime(struct tm*, uint32_t ms = 5000);
void configTzTime(const char*, const char*, const char* = nullptr, const char* = nullptr);
#endif
