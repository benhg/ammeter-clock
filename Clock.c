#include <Wire.h>
#include <Adafruit_MCP4725.h>

#define DAC_HOUR_ADDRESS  0x60
#define DAC_MINUTE_ADDRESS 0x61

void setDAC(byte address, int value) {
    Wire.beginTransmission(address);
    Wire.write((value >> 8) & 0xFF); // High byte
    Wire.write(value & 0xFF);       // Low byte
    Wire.endTransmission();
}

// Set Hour DAC
setDAC(DAC_HOUR_ADDRESS, 2048);

// Set Minute DAC
setDAC(DAC_MINUTE_ADDRESS, 4096);

// DAC setup
Adafruit_MCP4725 dacHour;  // For hours hand
Adafruit_MCP4725 dacMinute; // For minutes hand

// Pin definitions for buttons
const int buttonHourPin = 2;    // Button to advance hours
const int buttonMinutePin = 3;  // Button to advance minutes

// Variables to track time
int currentHour = 0;   // Set starting hour (0-11)
int currentMinute = 0; // Set starting minute (0-59)

// Debounce variables
unsigned long lastHourPress = 0;
unsigned long lastMinutePress = 0;
const unsigned long debounceDelay = 200; // ms

// DAC range (12-bit DAC: 0-4095)
const int hourMaxValue = 4095;  // Corresponds to 12V for the hour hand
const int minuteMaxValue = 4095; // Corresponds to 60mA for the minute hand

void setup() {
  // Initialize DACs
  dacHour.begin(0x60);  // Hour DAC I2C address
  dacMinute.begin(0x61); // Minute DAC I2C address

  // Set button pins as inputs with pullup resistors
  pinMode(buttonHourPin, INPUT_PULLUP);
  pinMode(buttonMinutePin, INPUT_PULLUP);

  // Set initial time on the gauges
  updateGauges();
}

void loop() {
  // Handle hour button press
  if (digitalRead(buttonHourPin) == LOW && millis() - lastHourPress > debounceDelay) {
    lastHourPress = millis();
    advanceHour();
  }

  // Handle minute button press
  if (digitalRead(buttonMinutePin) == LOW && millis() - lastMinutePress > debounceDelay) {
    lastMinutePress = millis();
    advanceMinute();
  }
}

void advanceHour() {
  currentHour = (currentHour + 1) % 12; // Increment hour, wrap around at 12
  updateGauges();
}

void advanceMinute() {
  currentMinute = (currentMinute + 1) % 60; // Increment minute, wrap around at 60
  if (currentMinute == 0) {  // If minutes wrap, advance hour
    advanceHour();
  }
  updateGauges();
}

void updateGauges() {
  // Map hour and minute to DAC values
  int hourDACValue = map(currentHour, 0, 11, 0, hourMaxValue);
  int minuteDACValue = map(currentMinute, 0, 59, 0, minuteMaxValue);

  // Set DAC values
  dacHour.setVoltage(hourDACValue, false);
  dacMinute.setVoltage(minuteDACValue, false);
}
