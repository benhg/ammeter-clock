#pragma once
#include <vector>
struct WireMock {
  std::vector<std::vector<uint8_t>> writes;
  uint8_t failingAddress = 0;
  void begin() {}
  void beginTransmission(uint8_t a) { writes.push_back({a}); }
  void write(uint8_t b) { writes.back().push_back(b); }
  uint8_t endTransmission() { return writes.back()[0] == failingAddress ? 2 : 0; }
};
extern WireMock Wire;
