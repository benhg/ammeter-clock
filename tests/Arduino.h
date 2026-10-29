#pragma once
#include <cstdint>
#include <string>
#include <sstream>
#define HIGH 1
#define LOW 0
#define INPUT_PULLUP 2
using __FlashStringHelper = char;
#define F(x) x
extern uint32_t fakeNow;
extern int pins[4];
inline uint32_t millis() { return fakeNow; }
inline int digitalRead(uint8_t p) { return pins[p]; }
inline void pinMode(uint8_t, int) {}
struct SerialMock {
  std::string input, output;
  void begin(int) {}
  int available() { return input.size(); }
  char read() { char c = input.front(); input.erase(0,1); return c; }
  template<typename T> void print(T value) { std::ostringstream s; s << value; output += s.str(); }
  void print(uint8_t value) { print(unsigned(value)); }
  template<typename T> void println(T value) { print(value); output += '\n'; }
};
extern SerialMock Serial;
