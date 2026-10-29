# KN6UBF USB clock setup

A local browser interface backed by Python, pyserial and Arduino CLI. It flashes the included firmware, sets the time from the computer, configures timezone/Wi-Fi, reports status, saves calibration and enables/disables meters. Both Uno R3 and R4 WiFi are supported; Wi-Fi controls are available only on R4 WiFi.

## Start on macOS

Prerequisites: Python 3 and [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/). Run these once to install board support:

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli core install arduino:renesas_uno
```

Double-click `Launch.command`. It creates `.venv-clock`, installs the pinned pyserial dependency, starts the local server and opens the browser. Keep its Terminal window open; Ctrl+C stops it. If the CLI is not on PATH, set `ARDUINO_CLI` to its absolute path before starting. This is a source launcher, not yet a signed, standalone customer installer.

Or run manually on macOS/Linux/Windows:

```sh
python3 -m venv .venv-clock
.venv-clock/bin/python -m pip install -r tools/clock_setup/requirements.txt
.venv-clock/bin/python tools/clock_setup/app.py
```

Windows: use `.venv-clock\Scripts\python.exe` in the last two commands. Close Arduino IDE Serial Monitor before connecting. Linux may require serial-device permissions.

## Use

1. Plug in the Uno with a USB data cable. Remove any temporary J3 bench-test short.
2. Choose the detected device and correct model. Click **Flash firmware** if it does not already have main firmware 0.2.0. The bundled bench sketches cannot answer setup commands.
3. After flashing, refresh devices and connect. The R3 resets when the USB serial connection opens, so configure time after connecting.
4. Choose a timezone. **Use computer time** saves it and sets UTC from the computer. Check the computer's own date/time first.
5. On R4 WiFi, enter SSID/password and save. Saving a network does not override an intentional manual time setting: click **Resume NTP**, or restart, to allow network time. Status distinguishes Wi-Fi connectivity from an actual NTP synchronization. Network association can take a minute.
6. Leave outputs disabled until meter wiring/calibration is checked. When ready, save calibration codes, check the confirmation and enable. Disable sends zero requests and persists the disabled state.

Hours and minutes can also be adjusted with either onboard or external buttons. Hold to repeat. On R4 this pauses NTP until restart/resume. Without NTP or an external RTC, reset/power loss loses the running time. The external RTC connector remains optional and isn't read in this release.

The service listens only on `127.0.0.1`, chooses a free port and requires the URL's per-launch capability token for API requests. No remote assets or cloud account. The per-launch token is retained in this browser tab’s session storage so refresh works. Reopen the complete launcher URL to connect from a new tab. Credentials are not logged, returned, put in subprocess arguments, or saved on the computer. They are stored unencrypted in Arduino EEPROM. Forget network clears the clock's saved credentials; it is not a forensic erase guarantee.

Flashing verifies a recognized Arduino model against the selected board, compiles locally and uploads using Arduino CLI. Compatible saved settings survive a firmware upload. Failures appear in the upload log; the GUI does not claim success until the CLI finishes successfully. Firmware uploads disconnect the current setup session. Reconnect afterward.

## Validation

Host tests: `python3 -m unittest discover -s tests -p 'test_clock_setup.py'`.
Firmware tests/builds: see [firmware README](../../firmware/README.md).
Real Wi-Fi credentials and an access point are required to verify association/NTP on hardware; automated tests do not establish Wi-Fi RF performance or physical button wiring.
