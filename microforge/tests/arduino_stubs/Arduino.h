// Stub minimal de l'API Arduino : sert UNIQUEMENT à vérifier la syntaxe C++ des firmwares générés
// (g++ -fsyntax-only). La vraie compilation se fait avec arduino-cli dans la CI.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstddef>
#include <cstdlib>
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
using std::isnan;
using std::abs;
void pinMode(uint8_t, uint8_t);
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

#if defined(ESP32)
#include <ctime>
bool getLocalTime(struct tm*, uint32_t ms = 5000);
void configTzTime(const char*, const char*, const char* = nullptr, const char* = nullptr);
#endif
