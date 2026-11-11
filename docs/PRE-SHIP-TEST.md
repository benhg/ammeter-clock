# Pre-shipment clock checks

Run on every assembled clock. Record unit ID, board revision, Arduino model,
clock firmware version, Wi-Fi module version (R4), calibration codes, date and tester.
These are functional acceptance checks, not regulatory certification.

## R4 WiFi firmware preparation

1. Update the ESP32-S3 connectivity firmware using Arduino's official Firmware
   Updater or Firmware Uploader. Use the release qualified for the production batch;
   **0.6.1 is the currently bench-tested version**. Qualify newer releases before
   substituting them. Updating our clock sketch alone does not update this module.
2. Disconnect all power and reconnect after the connectivity update. Do not upload
   the clock sketch while the board is still in ESP download mode.
3. Upload the approved clock firmware again: the connectivity updater overwrites
   the clock sketch. Check `STATUS` for the expected `firmware` and `wifi_firmware`.

Arduino's procedure:
https://support.arduino.cc/hc/en-us/articles/9670986058780-Update-the-connectivity-module-firmware-on-UNO-R4-WiFi

## Functional acceptance

1. Complete electrical bring-up and calibrate each fitted meter with the setup app.
   Verify zero, reference values, full sweep and return to live time. Save the codes.
2. Test both setting buttons. On R4, hold both for three seconds to resume NTP;
   confirm manual override clears.
3. On R4, configure the test Wi-Fi network and intended timezone. Fully power off
   and restart. Without setting time from the computer, require `source: "ntp"`,
   `time_valid: true`, `ntp_state: "synced"` and `ntp_checks: 7`. Check displayed time
   against a trusted clock and confirm saved calibration is unchanged. A Wi-Fi
   connection alone is not a passing time-sync test. Investigate any sync failure.
4. On R4, disconnect/search/reconnect Wi-Fi and confirm NTP sync resumes. Confirm
   the app can disconnect and reconnect USB, and the clock continues running.
5. For R3, omit Wi-Fi checks; set time over USB and verify buttons and calibration.
6. Remove factory Wi-Fi credentials with `WIFI_CLEAR`, confirm
   `wifi_configured: false`, and verify calibration remains saved. Do not ship with
   staff network credentials. Explain that R4 needs customer Wi-Fi setup after a
   power loss; without an RTC it cannot retain time while unpowered.

## Observed NTP issue

The bench R4 initially reported connectivity firmware 0.2.1 and failed at UDP
`endPacket()`. After updating to 0.6.1, retrying and restoring the clock sketch,
real NTP replies passed all validation checks. An initial send also failed after
that update, so the old module version is not established as the sole cause.
Clock firmware now retries failed packet sends after five seconds and reports
which send stage failed. Successful sync retains the hourly refresh interval.
