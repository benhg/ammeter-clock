#include <Arduino.h>
#include <Wire.h>
#include <EEPROM.h>
#include <stdlib.h>
#include "ClockCore.h"
#if defined(ARDUINO_UNOR4_WIFI)
#include <WiFiS3.h>
#include <WiFiUdp.h>
#define CLOCK_WIFI 1
#else
#define CLOCK_WIFI 0
#endif
using namespace ClockCore;
constexpr uint8_t DAC_ADDRESS = 0x60;
Settings settings;
Button hourButton, minuteButton;
bool dacReady = false, timeValid = false, manualOverride = false;
uint32_t utcEpoch = MIN_EPOCH, lastTick = 0;
const char *timeSource = "unset";
char inputLine[224];
uint16_t inputLength = 0;
bool inputOverflow = false;
#if CLOCK_WIFI
WiFiUDP udp;
IPAddress ntpAddress;
bool udpReady = false, ntpWaiting = false, ntpDue = true;
uint32_t lastNetwork = 0, lastAttempt = 0, ntpSentAt = 0;
uint32_t lastNtpAttempt = 0, ntpInterval = 60000;
uint8_t ntpCookie[8];
int wifiState = WL_IDLE_STATUS;
const char *ntpState = "waiting_wifi";
uint32_t ntpPackets = 0;
int ntpLastSize = 0;
uint8_t ntpChecks = 0;
#endif

bool writeDAC(uint8_t channel, uint16_t code) {
  if (code > 4095) code = 4095;
  Wire.beginTransmission(DAC_ADDRESS);
  Wire.write(uint8_t(0x40 | ((channel & 3) << 1)));
  Wire.write(uint8_t(0x90 | ((code >> 8) & 0x0F)));
  Wire.write(uint8_t(code));
  return Wire.endTransmission() == 0;
}
void zeroOutputs() {
  bool ok = true;
  for (uint8_t c = 0; c < 4; ++c) if (!writeDAC(c,0)) ok = false;
  dacReady = ok;
}
void updateGauges() {
  if (!dacReady) return;
  uint32_t local = localEpoch(utcEpoch, settings);
  uint8_t hour = (local / 3600) % 12;
  if (!hour) hour = 12;
  bool drive = settings.enabled && timeValid;
  uint16_t h = drive ? uint32_t(hour)*settings.hourScale/12 : 0;
  uint16_t m = drive ? uint32_t(local/60%60)*settings.minuteScale/60 : 0;
  bool hOK = writeDAC(HOUR_CHANNEL,h);
  bool mOK = writeDAC(MINUTE_CHANNEL,m);
  if (!hOK || !mOK) {
    zeroOutputs(); dacReady = false; // latch until restart; never imply zero was verified
  }
}
void saveSettings() {
  settings.checksum = checksum(settings);
  // Invalidate before update; publish the magic only after the payload is stored.
  for (uint8_t i = 0; i < 4; ++i) EEPROM.update(i,0);
  const uint8_t *p = reinterpret_cast<const uint8_t*>(&settings);
  for (size_t i = 4; i < sizeof(settings); ++i) EEPROM.update(i,p[i]);
  for (uint8_t i = 0; i < 4; ++i) EEPROM.update(i,p[i]);
}
void setClock(uint32_t epoch, const char *source) {
  utcEpoch = epoch; lastTick = millis(); timeValid = true; timeSource = source;
  updateGauges();
}
void ok() { Serial.println(F("OK {}")); }
void error(const __FlashStringHelper *message) { Serial.print(F("ERR ")); Serial.println(message); }
void printStatus() {
  Serial.print(F("OK {\"protocol\":1,\"firmware\":\"0.2.0\",\"board\":\""));
#if CLOCK_WIFI
  Serial.print(F("uno-r4-wifi"));
#else
  Serial.print(F("uno-r3"));
#endif
  Serial.print(F("\",\"epoch\":")); Serial.print(utcEpoch);
  Serial.print(F(",\"local_epoch\":")); Serial.print(localEpoch(utcEpoch,settings));
  Serial.print(F(",\"time_valid\":")); Serial.print(timeValid ? F("true") : F("false"));
  Serial.print(F(",\"source\":\"")); Serial.print(timeSource);
  Serial.print(F("\",\"manual_override\":")); Serial.print(manualOverride ? F("true") : F("false"));
  Serial.print(F(",\"dac_ready\":")); Serial.print(dacReady ? F("true") : F("false"));
  Serial.print(F(",\"enabled\":")); Serial.print(settings.enabled ? F("true") : F("false"));
  Serial.print(F(",\"hour_scale\":")); Serial.print(settings.hourScale);
  Serial.print(F(",\"minute_scale\":")); Serial.print(settings.minuteScale);
  Serial.print(F(",\"offset\":")); Serial.print(settings.offsetMinutes);
  Serial.print(F(",\"dst\":")); Serial.print(settings.dst);
  Serial.print(F(",\"wifi_supported\":")); Serial.print(CLOCK_WIFI ? F("true") : F("false"));
  Serial.print(F(",\"wifi_configured\":")); Serial.print(settings.ssid[0] ? F("true") : F("false"));
  Serial.print(F(",\"wifi_connected\":"));
#if CLOCK_WIFI
  Serial.print(wifiState == WL_CONNECTED ? F("true") : F("false"));
#else
  Serial.print(F("false"));
#endif
#if CLOCK_WIFI
  Serial.print(F(",\"wifi_code\":")); Serial.print(wifiState);
  Serial.print(F(",\"ntp_state\":\"")); Serial.print(ntpState);
  Serial.print(F("\",\"ntp_packets\":")); Serial.print(ntpPackets);
  Serial.print(F(",\"ntp_size\":")); Serial.print(ntpLastSize);
  Serial.print(F(",\"ntp_checks\":")); Serial.print(ntpChecks);
#endif
  Serial.println(F("}"));
}
bool number(const char *s, long minimum, long maximum, long &out) {
  if (!s || !*s) return false;
  char *end; out = strtol(s,&end,10);
  return !*end && out >= minimum && out <= maximum;
}
void command(char *line) {
  char *context;
  char *cmd = strtok_r(line," ",&context);
  char *a = strtok_r(nullptr," ",&context);
  char *b = strtok_r(nullptr," ",&context);
  char *extra = strtok_r(nullptr," ",&context);
  if (!cmd) return;
  long x,y;
  if (!strcmp(cmd,"STATUS") && !a) { printStatus(); return; }
  if (!strcmp(cmd,"TIME") && a && !b) {
    char *end; unsigned long epoch = strtoul(a,&end,10);
    if (*end || a[0] == '-' || epoch < MIN_EPOCH || epoch >= MAX_EPOCH) { error(F("time_range")); return; }
    manualOverride = true; setClock(epoch,"usb"); ok(); return;
  }
  if (!strcmp(cmd,"ZONE") && !extra && number(a,-720,840,x) && number(b,0,2,y)) {
    settings.offsetMinutes = x; settings.dst = y; saveSettings(); updateGauges(); ok(); return;
  }
  if (!strcmp(cmd,"SCALE") && !extra && number(a,1,4095,x) && number(b,1,4095,y)) {
    settings.hourScale = x; settings.minuteScale = y; saveSettings(); updateGauges(); ok(); return;
  }
  if (!strcmp(cmd,"OUTPUT") && !b && number(a,0,1,x)) {
    if (x && !dacReady) { error(F("dac_unavailable")); return; }
    if (x && !timeValid) { error(F("set_time_first")); return; }
    settings.enabled = x; saveSettings(); updateGauges(); ok(); return;
  }
  if (!strcmp(cmd,"WIFI") && a && b && !extra) {
#if CLOCK_WIFI
    char ssid[33] = {}, password[65] = {};
    if (!decodeHex(a,ssid,sizeof(ssid)) || !ssid[0] || !decodeHex(b,password,sizeof(password))
        || (strlen(password) && strlen(password) < 8)) { error(F("wifi_credentials")); return; }
    memcpy(settings.ssid,ssid,sizeof(ssid)); memcpy(settings.password,password,sizeof(password));
    saveSettings(); udp.stop(); udpReady = false; ntpWaiting = false;
    WiFi.disconnect(); wifiState = WL_IDLE_STATUS; lastAttempt = millis()-60000UL; ntpDue = true;
    ok(); return;
#else
    error(F("wifi_not_supported")); return;
#endif
  }
  if (!strcmp(cmd,"WIFI_CLEAR") && !a) {
    memset(settings.ssid,0,sizeof(settings.ssid)); memset(settings.password,0,sizeof(settings.password)); saveSettings();
#if CLOCK_WIFI
    udp.stop(); WiFi.disconnect(); udpReady = false; ntpWaiting = false; wifiState = WL_IDLE_STATUS;
#endif
    ok(); return;
  }
  if (!strcmp(cmd,"SYNC") && !a) {
#if CLOCK_WIFI
    manualOverride = false; ntpWaiting = false; ntpDue = true; ok(); return;
#else
    error(F("wifi_not_supported")); return;
#endif
  }
  error(F("invalid_command"));
}
void readCommands() {
  // Bounded work per loop keeps buttons responsive under serial noise.
  for (uint8_t count = 0; count < 64 && Serial.available(); ++count) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (inputOverflow) error(F("line_too_long"));
      else { inputLine[inputLength] = 0; command(inputLine); }
      memset(inputLine,0,sizeof(inputLine)); inputLength = 0; inputOverflow = false;
    } else if (c < 32 || inputLength >= sizeof(inputLine)-1) inputOverflow = true;
    else inputLine[inputLength++] = c;
  }
}
#if CLOCK_WIFI
void networkTick(uint32_t now) {
  if (!settings.ssid[0] || uint32_t(now-lastNetwork) < 250) return;
  lastNetwork = now;
  wifiState = WiFi.status();
  if (wifiState != WL_CONNECTED) {
    if (udpReady) { udp.stop(); udpReady = false; ntpWaiting = false; }
    if (uint32_t(now-lastAttempt) >= 60000) {
      lastAttempt = now;
      // Library calls are synchronous; cap association wait to one second.
      WiFi.setTimeout(1000);
      wifiState = settings.password[0] ? WiFi.begin(settings.ssid,settings.password) : WiFi.begin(settings.ssid);
      ntpDue = true; ntpState = "connecting";
    }
    return;
  }
  if (!udpReady) { udpReady = udp.begin(2390); if (!udpReady) { ntpState = "udp_failed"; return; } ntpDue = true; }
  if (manualOverride) { ntpState = "paused"; return; }
  int length = udp.parsePacket();
  if (length) {
    uint8_t packet[48];
    int read = udp.read(packet,sizeof(packet));
    ++ntpPackets; ntpLastSize = read;
    ntpChecks = (udp.remotePort() == 123 ? 1 : 0) | (udp.remoteIP() == ntpAddress ? 2 : 0)
      | (read == 48 && !memcmp(packet+24,ntpCookie,8) ? 4 : 0);
    ntpState = "rejected_reply";
    uint32_t epoch;
    if (ntpWaiting && length >= 48 && read == 48 && udp.remotePort() == 123
        && udp.remoteIP() == ntpAddress && ntpReply(packet,sizeof(packet),ntpCookie,epoch)) {
      setClock(epoch,"ntp"); ntpWaiting = false; ntpInterval = 3600000UL; ntpState = "synced";
    }
  }
  if (ntpWaiting && uint32_t(now-ntpSentAt) >= 5000) { ntpWaiting = false; ntpState = "reply_timeout"; }
  if (!ntpWaiting && (ntpDue || uint32_t(now-lastNtpAttempt) >= ntpInterval)) {
    ntpDue = false; lastNtpAttempt = now; ntpInterval = 60000;
    // Official Cloudflare anycast fallback keeps time sync independent of DNS.
    // https://developers.cloudflare.com/time-services/ntp/usage/
    if (WiFi.hostByName("pool.ntp.org",ntpAddress) != 1) ntpAddress = IPAddress(162,159,200,1);
    ntpState = "send_failed";
    uint8_t packet[48] = {};
    packet[0] = 0x23; // NTP v4 client, synchronized-state unknown.
    for (uint8_t i = 0; i < 8; ++i) ntpCookie[i] = uint8_t(random(1,256));
    memcpy(packet+40,ntpCookie,8);
    if (udp.beginPacket(ntpAddress,123)) {
      udp.write(packet,sizeof(packet));
      if (udp.endPacket()) { ntpWaiting = true; ntpSentAt = millis(); ntpState = "awaiting_reply"; }
    }
  }
}
#endif
void setup() {
  Serial.begin(115200); pinMode(2,INPUT_PULLUP); pinMode(3,INPUT_PULLUP); Wire.begin();
  EEPROM.get(0,settings); if (!valid(settings)) settings = defaults();
  zeroOutputs(); lastTick = millis(); updateGauges();
#if CLOCK_WIFI
  randomSeed(micros()); lastAttempt = millis()-60000UL;
#endif
}
void loop() {
  uint32_t now = millis();
  uint32_t elapsed = uint32_t(now-lastTick)/1000;
  if (elapsed) { utcEpoch += elapsed; lastTick += elapsed*1000; updateGauges(); }
  readCommands();
  now = millis();
  bool h = hourButton.poll(digitalRead(2) == LOW,now);
  bool m = minuteButton.poll(digitalRead(3) == LOW,now);
  if (h || m) {
    if (!timeValid) { utcEpoch = MIN_EPOCH - int32_t(settings.offsetMinutes)*60; timeValid = true; }
    utcEpoch -= localEpoch(utcEpoch,settings)%60;
    if (h) utcEpoch += 3600;
    if (m) utcEpoch += 60;
    manualOverride = true;
#if CLOCK_WIFI
    ntpWaiting = false;
#endif
    lastTick = now; timeSource = "buttons"; updateGauges();
  }
#if CLOCK_WIFI
  networkTick(millis());
#endif
}
