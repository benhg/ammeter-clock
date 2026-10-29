#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace ClockCore {
constexpr uint8_t HOUR_CHANNEL = 3, MINUTE_CHANNEL = 2;
constexpr uint32_t MIN_EPOCH = 1704067200UL; // 2024-01-01
constexpr uint32_t MAX_EPOCH = 4102444800UL; // 2100-01-01, exclusive
// Explicit packed layout and checksum: reject incomplete writes or old versions.
struct __attribute__((packed)) Settings {
  uint32_t magic;
  uint8_t version;
  int16_t offsetMinutes; // standard-time UTC offset
  uint8_t dst; // 0=none, 1=US, 2=EU
  uint16_t hourScale, minuteScale;
  uint8_t enabled;
  char ssid[33], password[65];
  uint16_t checksum;
};
inline uint16_t checksum(const Settings &s) {
  const uint8_t *p = reinterpret_cast<const uint8_t*>(&s);
  uint16_t crc = 0xffff;
  for (size_t i = 0; i < offsetof(Settings, checksum); ++i) {
    crc ^= uint16_t(p[i]) << 8;
    for (uint8_t j = 0; j < 8; ++j) crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
  }
  return crc;
}
inline Settings defaults() {
  Settings s = {};
  s.magic = 0x434C4B32UL; s.version = 1;
  s.hourScale = 3750; s.minuteScale = 4095;
  s.checksum = checksum(s);
  return s;
}
inline bool valid(const Settings &s) {
  return s.magic == 0x434C4B32UL && s.version == 1 && s.checksum == checksum(s)
    && s.offsetMinutes >= -720 && s.offsetMinutes <= 840 && s.dst <= 2
    && s.hourScale > 0 && s.hourScale <= 4095 && s.minuteScale > 0 && s.minuteScale <= 4095
    && s.enabled <= 1 && s.ssid[32] == 0 && s.password[64] == 0;
}
inline bool leap(uint16_t y) { return y % 4 == 0 && (y % 100 != 0 || y % 400 == 0); }
inline uint8_t monthDays(uint16_t y, uint8_t m) {
  static const uint8_t days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  return days[m-1] + (m == 2 && leap(y));
}
inline uint32_t dateEpoch(uint16_t y, uint8_t m, uint8_t d) {
  uint32_t days = 0;
  for (uint16_t i = 1970; i < y; ++i) days += leap(i) ? 366 : 365;
  for (uint8_t i = 1; i < m; ++i) days += monthDays(y, i);
  return (days + d - 1) * 86400UL;
}
inline uint16_t yearOf(uint32_t epoch) {
  uint32_t days = epoch / 86400UL; uint16_t y = 1970;
  while (days >= uint16_t(leap(y) ? 366 : 365)) days -= leap(y++) ? 366 : 365;
  return y;
}
inline uint8_t sunday(uint16_t y, uint8_t m, uint8_t nth) {
  uint8_t first = 1 + (7 - (dateEpoch(y,m,1) / 86400UL + 4) % 7) % 7;
  if (nth) return first + 7 * (nth - 1);
  while (first + 7 <= monthDays(y,m)) first += 7;
  return first;
}
inline bool summerTime(uint32_t utc, const Settings &s) {
  uint16_t y = yearOf(utc);
  uint32_t start, end;
  if (s.dst == 1) {
    start = dateEpoch(y,3,sunday(y,3,2)) + 7200UL - int32_t(s.offsetMinutes)*60;
    end = dateEpoch(y,11,sunday(y,11,1)) + 7200UL - int32_t(s.offsetMinutes+60)*60;
  } else if (s.dst == 2) {
    start = dateEpoch(y,3,sunday(y,3,0)) + 3600UL;
    end = dateEpoch(y,10,sunday(y,10,0)) + 3600UL;
  } else return false;
  return utc >= start && utc < end;
}
inline uint32_t localEpoch(uint32_t utc, const Settings &s) {
  return utc + int32_t(s.offsetMinutes + (summerTime(utc,s) ? 60 : 0))*60;
}
struct Button {
  bool raw = false, stable = false;
  uint32_t changed = 0, lastFire = 0;
  bool repeating = false;
  bool poll(bool down, uint32_t now) {
    if (down != raw) { raw = down; changed = now; }
    if (raw != stable && uint32_t(now-changed) >= 30) {
      stable = raw; repeating = false;
      if (stable) { lastFire = now; return true; }
    }
    if (stable && raw && uint32_t(now-lastFire) >= (repeating ? 200UL : 800UL)) {
      repeating = true; lastFire = now; return true;
    }
    return false;
  }
};
// Validate a server reply and match its originate timestamp to this request.
inline bool ntpReply(const uint8_t *p, size_t size, const uint8_t cookie[8], uint32_t &epoch) {
  if (size < 48) return false;
  uint8_t version = (p[0] >> 3) & 7;
  if ( (p[0]&7) != 4 || (p[0]>>6) == 3 || version < 3 || version > 4
      || p[1] < 1 || p[1] > 15 || memcmp(p+24,cookie,8)) return false;
  uint32_t ntp = uint32_t(p[40])<<24 | uint32_t(p[41])<<16 | uint32_t(p[42])<<8 | p[43];
  epoch = ntp - 2208988800UL; // modulo arithmetic handles NTP's 2036 era rollover
  return epoch >= MIN_EPOCH && epoch < MAX_EPOCH;
}
// Reject control bytes/NUL, allow UTF-8 credentials transmitted as hex.
inline bool decodeHex(const char *input, char *out, size_t capacity) {
  size_t n = strlen(input);
  if (strcmp(input,"-") == 0) { out[0] = 0; return true; }
  if (!n || n % 2 || n / 2 >= capacity) return false;
  for (size_t i = 0; i < n; i += 2) {
    uint8_t value = 0;
    for (uint8_t j = 0; j < 2; ++j) {
      char c = input[i+j];
      int digit = c >= '0' && c <= '9' ? c-'0' : c >= 'a' && c <= 'f' ? c-'a'+10 : c >= 'A' && c <= 'F' ? c-'A'+10 : -1;
      if (digit < 0) return false;
      value = value*16 + digit;
    }
    if (value < 32 || value == 127) return false;
    out[i/2] = char(value);
  }
  out[n/2] = 0; return true;
}
}
