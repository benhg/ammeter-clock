# KN6UBF Clock Setup — native desktop app 0.4.0

Qt Widgets application for Windows, macOS and Linux. There is no embedded browser,
localhost server, HTTP API or browser tab. USB and Arduino CLI operations run in a
background worker, with native controls for configuration and calibration.

## Customer flow

1. Plug the Uno into USB. Select its USB device in the **USB connection** panel.
   If clock firmware is already installed, click **Connect** immediately.
2. First-time setup or updating: use the separate **Install / update firmware** tab.
   Confirm the Arduino model, install firmware, then refresh USB devices and connect.
   The first install downloads Arduino board support. Close other serial applications.
3. In **Clock**, save a timezone and set computer time, or resume NTP on R4 WiFi.
4. In **Wi-Fi**, search nearby networks, select one or type a hidden network name.
   Search uses the R4 radio and requires firmware 0.4.0. Older firmware still accepts
   manually entered credentials. **Show password** reveals only the text currently
   entered; the stored password is never read back. Saving clears the password field
   and resumes NTP. Credentials are stored on the Arduino, not in the desktop app.
5. In **Calibration**, choose optional seconds, adjust mechanical zero at no output,
   then use lower/raise at a held 12:30 reference (12:30:30 with seconds). Verify fixed
   values or sweep, then Save. Drafts remain in RAM until Save; Cancel restores prior
   settings. Ten idle minutes hold outputs at zero. Closing normally cancels a wizard;
   unexpected disconnect uses the firmware timeout.

Both onboard and external buttons work on R3/R4. Hold both for three seconds on R4
to resume NTP after manual time adjustment. The RTC remains optional/not used.
Scanning may pause displayed needle updates/button processing while the WiFiS3
modem blocks; elapsed time is caught up afterward. No live board is flashed by builds.

## Build and tests

```sh
python -m pip install -r tools/clock_setup/requirements.txt pyinstaller==6.22.0
python -m unittest discover -s tests -p 'test_*.py'
python tools/clock_setup/build_app.py
python tools/clock_setup/smoke_app.py
```

Use `QT_QPA_PLATFORM=offscreen` for headless native-widget tests. `native_app.py` is
the desktop entry point; `app.py` contains the USB/flasher backend. The optional
GitHub Pages Web Serial UI remains separate and is not bundled in the desktop app.
Qt (PySide6 Essentials) is LGPLv3; License texts and source links are bundled under `licenses/`. Source: https://doc.qt.io/qtforpython-6/licenses.html .

## macOS signing and notarization

Customer releases must use a **Developer ID Application** certificate with its
matching private key in the build machine's Keychain. An Apple Development
certificate does not qualify. Create the Developer ID certificate in Xcode or Apple's
developer portal. A certificate made from an externally generated CSR must be paired
with that CSR's private key and imported into Keychain before building.

Set up a notarization credential profile with Apple's `xcrun notarytool
store-credentials clock-notary` (interactive prompts; never commit secrets), then:

```sh
export MACOS_SIGNING_IDENTITY='Developer ID Application: Your Name (TEAMID)'
export MACOS_NOTARY_PROFILE=clock-notary
python tools/clock_setup/build_app.py
```

PyInstaller signs nested binaries and the bundle with hardened runtime. The build
verifies Developer ID signing, submits to Apple, requires Accepted, staples the
notarization ticket, validates it and runs Gatekeeper assessment before archiving.
Unsigned local development builds are allowed; they are not customer releases.

Tagged GitHub releases fail closed without signing secrets. Configure the six
repository secrets named in `configure_macos_ci.py`; it imports the .p12 into an
ephemeral runner keychain, configures notarization, and never prints key material or
passwords. Do not put .p12/private keys in this repository. Windows signing is not
configured; Windows reputation warnings are independent of Apple's notarization.
