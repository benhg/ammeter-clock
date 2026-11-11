# KN6UBF analog meter clock

An Arduino Uno shield driving a 0–15 V hour meter and 0–100 µA minute meter.
The built, calibrated clock uses Rev F4 (root KiCad project). **Rev 2** adds a
seconds meter and rotates J5 for easier external-button wiring. It lives separately
under [hardware/rev2](hardware/rev2/README.md), with its own fabrication archive.
Rev 2 passes ERC, DRC, netlist, Uno geometry and interface simulations; its new
mechanicals and seconds channel still need a physical prototype.

[Clock Setup](https://benhg.github.io/ammeter-clock/) configures time, timezone,
Wi-Fi and calibration over USB. [Download a desktop app](https://github.com/benhg/ammeter-clock/releases)
for Windows, macOS or Linux to flash firmware as well. The native desktop app uses Qt Widgets and includes Python and Arduino CLI;
first flash downloads board support. Firmware installation is separate from connecting.

Firmware 0.3.0 adds a guided calibration wizard: mechanical zero, held 12:30
reference, lower/raise adjustments, optional seconds, arbitrary test values and a
sweep before saving. Existing firmware settings migrate with hour/minute calibration
and Wi-Fi retained; seconds defaults off. The running clock is not flashed automatically.

Both onboard and external HOUR/MINUTE buttons work on R3 and R4 WiFi. Holding
both for three seconds resumes Wi-Fi/NTP on R4; individual time adjustments pause
NTP until that gesture, USB Resume NTP or restart. An RTC is optional and not read
by this firmware; R3 must be set again after power loss. R4 can resync over Wi-Fi.

- [Firmware, serial protocol and limitations](firmware/README.md)
- [Setup app instructions](tools/clock_setup/README.md)
- [Rev 2 design, checks and fabrication files](hardware/rev2/README.md)

The shield uses a customer-installed Pololu U3V16F15 15 V module in U4's socket.
Meter outputs default disabled on a new installation. The minute/second drivers
have 56 kΩ series resistors and require microamp movements, not milliamp meters.
Manufacturer macro-model simulations impose the 15 V supply; they do not simulate
the Pololu converter or the DAC's EEPROM power-on state.

Desktop app / firmware 0.4.0 adds R4 Wi-Fi network search, native password visibility
control and a dedicated USB connection panel. Customer macOS releases now require
Developer ID signing and Apple notarization.

Version 0.5.0 adds a smooth one-second app clock, disconnect-and-search Wi-Fi,
searchable IANA zones with saved daylight-saving transitions, editable custom
offsets, and 5–600 second meter sweeps. Resume NTP is disabled while already active.
