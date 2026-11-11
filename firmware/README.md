# Clock firmware 0.4.0

`AmmeterClock/AmmeterClock.ino` supports Uno R3 and Uno R4 WiFi without external libraries. Install the appropriate official Arduino board package. The R4 uses the included WiFiS3 library; R3 builds omit networking. No external RTC is required or currently read by this firmware.

## Behavior

- D2 = hour button; D3 = minute button. Normally-open buttons connect to ground, using internal pull-ups. Onboard and external buttons have identical behavior.
- Each press advances one hour/minute and resets seconds. Debounce is 30 ms; holding repeats after 800 ms, then every 200 ms. Minutes carry into hours. Hours display 1–12 and minutes 0–59.
- Button or USB time setting pauses NTP until restart or an explicit Resume NTP request. This override is deliberately not persisted. Both buttons work on R4 WiFi as well as R3.
- R4 connects to saved 2.4 GHz Wi-Fi, gets UTC from Cloudflare’s `162.159.200.1` without a DNS lookup, then synchronizes hourly. Connection/NTP failures retry approximately once a minute; the clock continues ticking. NTP replies must match the server address, port and request cookie and pass mode/stratum/time checks. NTP is not authenticated.
- Without a valid time, outputs stay at zero. After reset/power loss, R4 waits for NTP or manual setting; R3 needs USB time setting or buttons. Neither board restores a stale saved timestamp. Millis rollover is handled. Powered holdover uses the onboard oscillator and will drift.
- Timezone is a standard UTC offset in minutes, plus no DST, US DST, or EU DST. The setup tool has presets and a custom offset. Other regional DST rules are not implemented.
- Wi-Fi credentials, timezone, calibration, and output enable are saved with a version/checksum. Incomplete/corrupt settings fall back to defaults. Clock ticks/buttons do not write EEPROM. Credentials are stored in plaintext on the board; serial status never returns them.
- New installations have outputs **disabled**. Explicitly enable after checking the meters and calibration. A DAC communication fault latches updates off until restart and attempts zero writes; software cannot verify analog outputs or prevent the DAC's earlier EEPROM power-on behavior.
- Correct Rev F4 DAC mapping: **D / pin 9 = hours, C / pin 8 = minutes**. A/B are unused and initialized to zero. Older schematic channel names and comments incorrectly call these A/B; do not copy that mapping.
- Default calibration: hour code 3750 at the 12 mark (~12 V); minute code 4095 at the 60 mark (~73 µA before coil resistance with the 56 kΩ series resistor). Requires a **0–100 µA** movement and a calibrated dial; this is not a milliamp driver. Values are bounded 1–4095.

WiFiS3 operations are synchronous: association has a one-second configured timeout; modem calls may also temporarily delay button sampling. Network retries are bounded in frequency, but guaranteed real-time button handling under a malfunctioning Wi-Fi modem has not been established.

## Test pattern

With meter outputs enabled, **Run test pattern** sweeps both outputs together for 61 seconds. Minutes step 0–60 once per second; hours step 0–12 once every five seconds. Both endpoints are held for one second before returning to the live clock. The pattern uses the saved calibration codes and does not change time, timezone, NTP/manual mode, calibration, or EEPROM. Stop, disable outputs, changing calibration, or either physical setting button cancels it. DAC failure cancels it and latches updates off. The timed pattern continues independently if USB disconnects and then returns to the clock; its full-scale minute endpoint is about 73 µA with this board, not 100 mA.

## USB protocol

115200 baud, newline-terminated ASCII commands. Replies are `OK {json}` or `ERR reason`. No echo. Unknown/malformed/oversize commands are rejected; an overflowing line is discarded through its newline. Maximum command length is 223 bytes. Fields below are decimal unless specified.

| Command | Action |
| --- | --- |
| `STATUS` | Firmware/board/time, source, manual override, DAC, enabled/calibration, timezone and Wi-Fi state; no credentials |
| `TIME <UTC Unix seconds>` | Set 2024–2099 UTC time; pause NTP until restart/resume |
| `ZONE <standard UTC offset minutes> <rule>` | Save offset −720 to +840; rule 0=none, 1=US, 2=EU |
| `WIFI <SSID hex> <password hex>` | R4 only; UTF-8 hex encoding, no control characters; `-` denotes empty/open-network password |
| `WIFI_CLEAR` | Erase saved credentials and disconnect |
| `SYNC` | R4 only: clear manual override and request NTP |
| `SCALE <hour code at 12> <minute code at 60>` | Save bounded calibration codes |
| `TEST START` / `TEST STOP` | Start/stop the timed sweep; starting requires enabled outputs and responsive DAC |
| `OUTPUT 0` / `OUTPUT 1` | Disable/enable; enabling requires a valid time and responsive DAC |

The firmware uses volatile MCP4728 multi-write commands, internal 2.048 V reference, gain 2; it never programs DAC EEPROM.

## Build and checks

```sh
arduino-cli core install arduino:avr
arduino-cli core install arduino:renesas_uno
arduino-cli compile --fqbn arduino:avr:uno firmware/AmmeterClock
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/AmmeterClock
c++ -std=c++17 -Itests tests/firmware_test.cpp -o /tmp/clock-test
/tmp/clock-test
python3 -m unittest discover -s tests -p 'test_clock_setup.py'
```

`BringUpHour1V` and `BringUpMinute1V` are separate fixed-output bench sketches, intended for disconnected needle meters. They do not implement setup commands. Flash the main clock firmware before using the setup tool.

## Firmware 0.3.0: calibration and seconds

The setup app's wizard holds all outputs at zero for mechanical screw adjustment,
then 12:30 (12:30:30 with seconds). Raise/lower changes draft DAC scale codes in
RAM. Measured-reading correction computes `old code × target / reading`; values
outside 1–4095 are rejected. Verify with fixed values or a 61-second sweep.
Only Save writes calibration, enables outputs and returns to the running time.
Cancel restores the previous output/calibration settings. Closing the USB connection
through the app cancels; unexpected disconnect leaves the held reference until the
ten-minute inactivity timeout, which holds outputs at zero. Status polling does not
extend that timeout. Restart retains the previously saved settings.

Settings schema 2 migrates valid schema 1 data without losing Wi-Fi, hour/minute
scale, timezone or enabled state. Seconds is disabled by default for existing boards.
Rev 2 uses DAC B (pin 7) for seconds; D/pin9 and C/pin8 remain hours/minutes.

| Command | Effect |
| --- | --- |
| `SECONDS 0/1` | Persist optional seconds output enable |
| `CAL BEGIN 0/1` | Begin draft calibration; argument indicates a seconds meter |
| `CAL TARGET h m s` | Hold hours 0–12, minutes/seconds 0–60 |
| `CAL SCALE h m s` | Adjust draft full-span codes, each 1–4095 |
| `CAL SWEEP` | Sweep draft scales, then return to held target |
| `CAL SAVE` | Persist drafts/seconds option, enable outputs, return to live time |
| `CAL CANCEL` | Discard drafts and restore previous settings |

Hold HOUR + MINUTE together for three seconds on R4 WiFi to clear manual override
and request NTP. It preserves Wi-Fi/calibration and suppresses individual button
changes during the gesture. R3 cancels a test/calibration with the gesture but has
no network to sync. Synchronous WiFiS3 modem operations may briefly delay sampling.

Local tests include `tests/firmware_test.cpp` and `tests/firmware_r4_test.cpp`;
the latter uses Wi-Fi/UDP mocks to check the physical-button chord through a valid
NTP reply and seconds output. These do not replace a real modem/needle test.

## Wi-Fi search (0.4.0)

`WIFI_SCAN` on R4 returns `OK {"networks":[{"ssid_hex":"…","rssi":-40,"open":false}]}`.
SSID bytes are hex encoded so quotes/non-ASCII cannot corrupt framing. Up to 32
access points are returned. The native app deduplicates SSIDs by strongest RSSI and
allows manual entry. Negative modem scan results return `ERR wifi_scan_failed`;
R3 returns `ERR wifi_not_supported`. Scanning is refused during calibration/sweeps.
Scan timeout in the host is 45 seconds; a synchronous scan may temporarily delay
needle/button updates, after which elapsed clock time is caught up. It writes no
settings, connects to no network, and preserves manual/NTP mode.

## Firmware 0.5.0

`WIFI_SCAN` disconnects the radio first, invalidates outstanding UDP requests, and
schedules reconnection to saved credentials afterward, including on scan failure.
USB, calibration, credentials and manual-time override are preserved.

`TEST START [seconds]` and `CAL SWEEP [seconds]` accept durations 5–600 seconds;
omitting the duration preserves the 61-second pattern. Both endpoints are included.
An active wizard sweep suspends its idle deadline and resets it upon completion.

Named IANA zones use a host-generated transition schedule. `TZ BEGIN <hex name>
<from UTC> <until UTC> <initial offset minutes>`, followed by `TZ ADD <UTC epoch>
<offset minutes>` and `TZ SAVE`, replaces the schedule atomically. `TZ CANCEL`
abandons the draft. Two 424-byte EEPROM banks start at byte 176; 56 six-byte
transitions fit in each bank. Headers and transitions are CRC protected; no table is
kept in SRAM. `ZONE` explicitly clears named-zone banks and restores legacy custom
US/EU/no-DST behavior. Original settings layout and saved calibration are unchanged.

STATUS advertises timezone/variable-duration/disconnect-scan capabilities and the
saved zone name. It reports stale schedules. The app supplies at least ten future
years using pinned tzdata (capped at 2100), and can refresh schedules after legislative
changes. It checked every one of the 598 included zone IDs, requiring at most 26
entries for the current generated range. Expired/out-of-range schedules fall back
to the custom offset; reconnect and save the zone again when stale is reported.
