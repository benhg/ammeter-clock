#!/usr/bin/env python3
"""USB/Arduino backend shared by the native desktop app. No HTTP server."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(getattr(sys, "_MEIPASS", ROOT))
if getattr(sys, "frozen", False):
    ROOT = BUNDLE
BOARDS = {"uno-r3": ("arduino:avr:uno", "arduino:avr"),
          "uno-r4-wifi": ("arduino:renesas_uno:unor4wifi", "arduino:renesas_uno")}


def find_cli():
    executable = "arduino-cli.exe" if sys.platform == "win32" else "arduino-cli"
    candidates = [os.environ.get("ARDUINO_CLI"), str(BUNDLE / "bin" / executable), shutil.which("arduino-cli"),
                  str(ROOT / ".tools/arduino-cli"), "/tmp/ammeter-arduino-tools/arduino-cli"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Arduino CLI not found. Install it or set ARDUINO_CLI to its path.")


def run_cli(command, **kwargs):
    # Frozen apps must not pass bundled shared-library paths into vendor tools.
    env = os.environ.copy()
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(key + "_ORIG", None)
        env.pop(key, None)
        if original:
            env[key] = original
    return subprocess.run(command, env=env,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                          **kwargs)


def credential_hex(value, maximum, *, empty=True):
    if not isinstance(value, str):
        raise ValueError("Credentials must be text")
    raw = value.encode("utf-8")
    if len(raw) > maximum or (not empty and not raw) or any(c < 32 or c == 127 for c in raw):
        raise ValueError(f"Credential must be {'0' if empty else '1'}–{maximum} UTF-8 bytes without control characters")
    return raw.hex() or "-"


def integer(data, key, low, high):
    value = data.get(key)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer between {low} and {high}")
    return value


def make_command(data):
    action = data.get("action")
    if action == "status":
        return "STATUS"
    if action == "time":
        return f"TIME {integer(data, 'epoch', 1704067200, 4102444799)}"
    if action == "zone":
        return f"ZONE {integer(data, 'offset', -720, 840)} {integer(data, 'dst', 0, 2)}"
    if action == "scale":
        return f"SCALE {integer(data, 'hour', 1, 4095)} {integer(data, 'minute', 1, 4095)}"
    if action == "output":
        if type(data.get("enabled")) is not bool:
            raise ValueError("enabled must be a boolean")
        return f"OUTPUT {int(data['enabled'])}"
    if action == "test":
        if data.get("operation") not in ("start", "stop"):
            raise ValueError("Choose start or stop")
        return "TEST " + data["operation"].upper()
    if action == "seconds":
        if type(data.get("enabled")) is not bool: raise ValueError("enabled must be a boolean")
        return f"SECONDS {int(data['enabled'])}"
    if action == "calibration":
        operation = data.get("operation")
        if operation == "begin":
            if type(data.get("seconds")) is not bool: raise ValueError("seconds must be a boolean")
            return f"CAL BEGIN {int(data['seconds'])}"
        if operation in ("cancel", "save", "sweep"): return "CAL " + operation.upper()
        if operation == "target":
            return f"CAL TARGET {integer(data,'hour',0,12)} {integer(data,'minute',0,60)} {integer(data,'second',0,60)}"
        if operation == "scale":
            return f"CAL SCALE {integer(data,'hour',1,4095)} {integer(data,'minute',1,4095)} {integer(data,'second',1,4095)}"
        raise ValueError("Unknown calibration operation")
    if action == "wifi":
        ssid = credential_hex(data.get("ssid"), 32, empty=False)
        password = data.get("password")
        encoded = credential_hex(password, 64)
        if password and len(password.encode("utf-8")) < 8:
            raise ValueError("Wi-Fi password must be empty for an open network or at least 8 bytes")
        if len(password.encode("utf-8")) == 64 and any(c not in "0123456789abcdefABCDEF" for c in password):
            raise ValueError("A 64-byte Wi-Fi key must be hexadecimal")
        return f"WIFI {ssid} {encoded}"
    if action == "wifi_scan":
        return "WIFI_SCAN"
    if action == "wifi_clear":
        return "WIFI_CLEAR"
    if action == "sync":
        return "SYNC"
    raise ValueError("Unknown action")


class Device:
    def __init__(self):
        self.lock = threading.RLock()
        self.serial = None
        self.port = None
        self.busy = False
        self.job = {"state": "idle", "log": ""}
        self.job_lock = threading.Lock()

    def boards(self):
        # Enumeration works before Arduino board support is installed.
        from serial.tools import list_ports
        rows = []
        for port in list_ports.comports():
            # macOS exposes Bluetooth/debug pseudo-ports alongside USB.
            if port.vid is None and not any(name in port.device.lower() for name in ("usb", "ttyacm", "ttyusb")): continue
            board = None
            if port.vid in (0x2341, 0x2a03):
                if port.pid in (0x1002, 0x0069):
                    board = "uno-r4-wifi"
                elif port.pid in (0x0043, 0x0001):
                    board = "uno-r3"
            rows.append({"port":port.device,"name":port.description or port.device,
                         "board":board,"recognized":board is not None})
        return rows

    def close(self):
        if self.serial:
            self.serial.close()
        self.serial = None
        self.port = None

    def request(self, command):
        if not self.serial:
            raise RuntimeError("Connect to the clock first")
        try:
            self.serial.reset_input_buffer()
            self.serial.write((command + "\n").encode("ascii"))
            self.serial.flush()
            deadline = time.monotonic() + (45 if command == "WIFI_SCAN" else 12)
            while time.monotonic() < deadline:
                line = self.serial.readline(8192).decode("utf-8", errors="replace").strip()
                if line.startswith("OK "):
                    return json.loads(line[3:])
                if line.startswith("ERR "):
                    raise RuntimeError("Clock rejected the request: " + line[4:])
            self.close()
            raise RuntimeError("No clock reply. Flash the clock firmware, check the USB connection, and reconnect.")
        except (OSError, ValueError) as exc:
            self.close()
            raise RuntimeError("USB communication failed; reconnect the clock") from exc

    def connect(self, port):
        with self.lock:
            if self.busy:
                raise RuntimeError("Flashing is in progress")
            if port not in {row["port"] for row in self.boards()}:
                raise ValueError("Choose a currently detected serial port")
            import serial
            self.close()
            try:
                self.serial = serial.Serial(port, 115200, timeout=0.25, write_timeout=2)
                self.port = port
                time.sleep(2.5)  # R3 resets when DTR opens; native-USB R4 may not.
                status = self.request("STATUS")
                if status.get("protocol") != 1:
                    raise RuntimeError("Unsupported clock protocol; flash the bundled firmware")
                return status
            except Exception:
                self.close()
                raise

    def command(self, data):
        command = make_command(data)
        with self.lock:
            if self.busy:
                raise RuntimeError("Flashing is in progress")
            self.request(command) if command != "STATUS" else None
            return self.request("STATUS")

    def scan_networks(self):
        with self.lock:
            if self.busy: raise RuntimeError("Flashing is in progress")
            reply = self.request("WIFI_SCAN")
        strongest = {}
        for network in reply.get("networks", []):
            name = bytes.fromhex(network["ssid_hex"]).decode("utf-8", errors="replace")
            if not name: continue
            row = dict(ssid=name, rssi=network["rssi"], open=network["open"])
            if name not in strongest or row['rssi'] > strongest[name]['rssi']: strongest[name] = row
        return sorted(strongest.values(), key=lambda r:r['rssi'], reverse=True)

    def job_state(self):
        with self.job_lock:
            return dict(self.job)

    def set_job(self, state=None, log=None):
        with self.job_lock:
            if state:
                self.job["state"] = state
            if log is not None:
                self.job["log"] = log[-24000:]

    def flash(self, port, board):
        if board not in BOARDS:
            raise ValueError("Choose Uno R3 or Uno R4 WiFi")
        rows = self.boards()
        row = next((row for row in rows if row["port"] == port), None)
        if not row:
            raise ValueError("Choose a currently detected port")
        if row["recognized"] and row["board"] != board:
            raise ValueError("Selected board does not match the detected Arduino")
        with self.lock:
            if self.busy:
                raise RuntimeError("Flashing is already in progress")
            self.busy = True
            self.close()
            self.set_job("running", "Preparing firmware…\n")
        threading.Thread(target=self._flash, args=(port, board), daemon=True).start()
        return {"started": True}

    def _flash(self, port, board):
        log = ""
        try:
            cli = find_cli()
            fqbn, core = BOARDS[board]
            cores = run_cli([cli,"core","list","--json"],capture_output=True,text=True,timeout=60)
            installed = json.loads(cores.stdout).get("platforms", []) if cores.returncode == 0 else []
            if not any(p.get("id") == core and p.get("installed_version") for p in installed):
                log += "First run: downloading Arduino board support. This may take several minutes.\n"
                self.set_job(log=log)
                for setup in ([cli,"core","update-index"], [cli,"core","install",core]):
                    result = run_cli(setup,capture_output=True,text=True,timeout=900)
                    log += result.stdout + result.stderr
                    self.set_job(log=log)
                    if result.returncode:
                        raise RuntimeError("Board support download failed; check the Internet connection and retry")
            with tempfile.TemporaryDirectory(prefix="ammeter-build-") as build:
                commands = [([cli,"compile","--fqbn",fqbn,"--build-path",build,str(ROOT/"firmware/AmmeterClock")],"Compiling"),
                            ([cli,"upload","--fqbn",fqbn,"--port",port,"--input-dir",build,str(ROOT/"firmware/AmmeterClock")],"Uploading")]
                for command, label in commands:
                    log += label + "…\n"; self.set_job(log=log)
                    result = run_cli(command,capture_output=True,text=True,timeout=240)
                    log += result.stdout + result.stderr
                    self.set_job(log=log)
                    if result.returncode:
                        raise RuntimeError(label + " failed; see the log")
            self.set_job("done",log + "\nFirmware uploaded. Refresh ports and connect to configure.\n")
        except Exception as exc:
            self.set_job("error",log + "\n" + str(exc))
        finally:
            with self.lock:
                self.busy = False
