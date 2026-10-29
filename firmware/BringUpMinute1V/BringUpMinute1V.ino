#include <Arduino.h>
#include <Wire.h>

// Bench test: needle meters DISCONNECTED. No clock progression or EEPROM writes.
// DAC C (PCB pin 8) = 1.000 V nominal through the minute 56k resistor.
// With needle meters disconnected, a high-impedance voltmeter reads J3 ~1 V.
// DAC A/B/D stay at zero; J2 should read ~0 V.
constexpr uint8_t DAC_ADDRESS = 0x60;
constexpr uint8_t MINUTE_CHANNEL = 2;
constexpr uint16_t MINUTE_TEST_CODE = 1000;
bool ready = false;
uint32_t lastReport = 0;

bool writeDAC(uint8_t channel, uint16_t code) {
  Wire.beginTransmission(DAC_ADDRESS);
  Wire.write(uint8_t(0x40 | ((channel & 3) << 1)));
  Wire.write(uint8_t(0x90 | ((code >> 8) & 0x0F)));
  Wire.write(uint8_t(code & 0xFF));
  return Wire.endTransmission() == 0;
}

bool zeroAll() {
  bool ok = true;
  for (uint8_t channel = 0; channel < 4; ++channel) {
    if (!writeDAC(channel, 0)) ok = false;
  }
  return ok;
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  ready = zeroAll();
  if (ready) ready = writeDAC(MINUTE_CHANNEL, MINUTE_TEST_CODE);
  if (!ready) zeroAll();
}

void loop() {
  const uint32_t now = millis();
  if (uint32_t(now - lastReport) < 1000) return;
  lastReport = now;
  if (ready) {
    bool ok = writeDAC(MINUTE_CHANNEL, MINUTE_TEST_CODE);
    for (uint8_t channel = 0; channel < 4; ++channel) {
      if (channel != MINUTE_CHANNEL && !writeDAC(channel, 0)) ok = false;
    }
    if (!ok) { ready = false; zeroAll(); }
  }
  if (ready) Serial.println(F("Minute 1V test: DAC acknowledged. Expected J2 ~0V, unloaded J3 ~1V; measure to verify."));
  else Serial.println(F("DAC communication failed; zero requested. Check hardware and restart."));
}
