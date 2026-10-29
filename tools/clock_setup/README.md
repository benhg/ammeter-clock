# KN6UBF USB clock setup

A local browser interface backed by Python, pyserial and Arduino CLI. It flashes the included firmware, sets the time from the computer, configures timezone/Wi-Fi, reports status, saves calibration and enables/disables meters. Both Uno R3 and R4 WiFi are supported; Wi-Fi controls are available only on R4 WiFi.

## Downloadable apps

Open [Clock Setup](https://benhg.github.io/ammeter-clock/) for Windows x64, macOS Apple silicon/Intel, and Linux x64 downloads. Extract the archive and open **KN6UBF Clock Setup** (`.exe` on Windows, `.app` on macOS, executable on Linux). Keep the extracted folder together on Windows/Linux. The app opens a local browser UI; Python, pyserial, firmware source and a checksum-verified official Arduino CLI 1.5.1 are bundled. The first flash automatically downloads the required Arduino board package and needs Internet access. Click **Quit setup app** when finished.

The macOS builds are ad-hoc signed, not Developer ID signed or notarized; Windows binaries are unsigned. These are portable downloads, not system installers. Linux requires a graphical browser, glibc 2.35 or newer, and permission to access USB serial devices. Packages contain no Wi-Fi credentials. Customer-specific signing/notarization is not configured.

The Pages UI also supports direct USB setup through desktop Chrome/Edge using Web Serial. It can set time, Wi-Fi, calibration and output enable on already-flashed boards. Firmware flashing uses the downloaded app. Safari/Firefox users can use the app's local UI. Close other serial monitors/apps before connecting; a USB port can only be used by one application at a time.

## Run from source on macOS

Prerequisites: Python 3 and [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/). Board support downloads automatically on first flash, or install it beforehand:

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli core install arduino:renesas_uno
```

Double-click `Launch.command`. It creates `.venv-clock`, installs the pinned pyserial dependency, starts the local server and opens the browser. Keep its Terminal window open; Ctrl+C stops it. If the CLI is not on PATH, set `ARDUINO_CLI` to its absolute path before starting. This source launcher is an alternative to the standalone downloads.

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

## Build and release apps

Install `pyinstaller==6.22.0` alongside `requirements.txt`, then run `python tools/clock_setup/build_app.py` and `python tools/clock_setup/smoke_app.py` on the target OS. Output is in `dist-clock/`. Arduino CLI comes from its official GitHub release and is checked against that release's SHA256 manifest before bundling. Its license is included.

Tagging `v*` runs `.github/workflows/desktop.yml`: four native build runners, host tests, packaged CLI/assets/server smoke checks, then release downloads and SHA256 checksums. Every build must pass before the release is published. Website changes on main deploy through `.github/workflows/pages.yml`; Pages source must be GitHub Actions.

Web Serial tests: `node tests/web_serial_test.js`. `python tools/clock_setup/build_pages.py` creates `_site-clock/` with only public UI assets. Wi-Fi credentials travel directly to the board, not to GitHub Pages. The website loads no third-party scripts.
