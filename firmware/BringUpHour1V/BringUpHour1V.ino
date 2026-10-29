#include <Arduino.h>
#include <Wire.h>

// Bench test: needle meters DISCONNECTED. No clock progression or EEPROM writes.
// DAC D (PCB pin 9) = 312 mV nominal; hour amplifier gain 3.2 gives J2 ~0.9984 V.
// DAC A/B/C stay at zero. Check the actual output with a DC voltmeter.
constexpr uint8_t DAC_ADDRESS = 0x60;
constexpr uint8_t HOUR_CHANNEL = 3;
constexpr uint16_t HOUR_TEST_CODE = 312;
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
  if (ready) ready = writeDAC(HOUR_CHANNEL, HOUR_TEST_CODE);
  if (!ready) zeroAll();
}

void loop() {
  const uint32_t now = millis();
  if (uint32_t(now - lastReport) < 1000) return;
  lastReport = now;
  if (ready) {
    bool ok = writeDAC(HOUR_CHANNEL, HOUR_TEST_CODE);
    for (uint8_t channel = 0; channel < HOUR_CHANNEL; ++channel) {
      if (!writeDAC(channel, 0)) ok = false;
    }
    if (!ok) { ready = false; zeroAll(); }
  }
  if (ready) Serial.println(F("1V bench test: DAC acknowledged. Expected J2 ~1V, J3 ~0V; measure to verify."));
  else Serial.println(F("DAC communication failed; zero requested. Check hardware and restart."));
}
