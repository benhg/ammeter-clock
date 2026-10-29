#!/usr/bin/env python3
"""Local USB flasher/setup UI. No cloud service or saved host-side Wi-Fi secrets."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent
BOARDS = {"uno-r3": ("arduino:avr:uno", "arduino:avr"),
          "uno-r4-wifi": ("arduino:renesas_uno:unor4wifi", "arduino:renesas_uno")}


def find_cli():
    candidates = [os.environ.get("ARDUINO_CLI"), shutil.which("arduino-cli"),
                  str(ROOT / ".tools/arduino-cli"), "/tmp/ammeter-arduino-tools/arduino-cli"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Arduino CLI not found. Install it or set ARDUINO_CLI to its path.")


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
    if action == "wifi":
        ssid = credential_hex(data.get("ssid"), 32, empty=False)
        password = data.get("password")
        encoded = credential_hex(password, 64)
        if password and len(password.encode("utf-8")) < 8:
            raise ValueError("Wi-Fi password must be empty for an open network or at least 8 bytes")
        if len(password.encode("utf-8")) == 64 and any(c not in "0123456789abcdefABCDEF" for c in password):
            raise ValueError("A 64-byte Wi-Fi key must be hexadecimal")
        return f"WIFI {ssid} {encoded}"
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
        result = subprocess.run([find_cli(), "board", "list", "--json"], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError("Unable to list boards: " + result.stderr[-1000:])
        data = json.loads(result.stdout)
        rows = []
        for item in data.get("detected_ports", []):
            port = item["port"]
            if port.get("protocol") != "serial":
                continue
            matches = item.get("matching_boards", [])
            supported = next((key for key, (fqbn, _) in BOARDS.items()
                              if any(m.get("fqbn") == fqbn for m in matches)), None)
            rows.append({"port": port["address"], "name": matches[0]["name"] if matches else port.get("label", port["address"]),
                         "board": supported, "recognized": bool(matches)})
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
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                line = self.serial.readline(2048).decode("utf-8", errors="replace").strip()
                if line.startswith("OK "):
                    return json.loads(line[3:])
                if line.startswith("ERR "):
                    raise RuntimeError("Clock rejected the request: " + line[4:])
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
            cores = subprocess.run([cli,"core","list","--json"],capture_output=True,text=True,timeout=30,check=True)
            installed = json.loads(cores.stdout).get("platforms", [])
            if not any(p.get("id") == core and p.get("installed_version") for p in installed):
                raise RuntimeError(f"Install board support first: arduino-cli core update-index, then arduino-cli core install {core}")
            with tempfile.TemporaryDirectory(prefix="ammeter-build-") as build:
                commands = [([cli,"compile","--fqbn",fqbn,"--build-path",build,str(ROOT/"firmware/AmmeterClock")],"Compiling"),
                            ([cli,"upload","--fqbn",fqbn,"--port",port,"--input-dir",build,str(ROOT/"firmware/AmmeterClock")],"Uploading")]
                for command, label in commands:
                    log += label + "…\n"; self.set_job(log=log)
                    result = subprocess.run(command,capture_output=True,text=True,timeout=240)
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


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.device = Device()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log request bodies, credentials, or capability tokens.

    def send(self, status, payload, content_type="application/json"):
        body = json.dumps(payload).encode() if content_type == "application/json" else payload
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        origin = self.headers.get("Origin")
        expected = f"http://127.0.0.1:{self.server.server_port}"
        return (self.headers.get("Host") == expected[7:]
                and (origin is None or origin == expected)
                and secrets.compare_digest(self.headers.get("X-Clock-Token", ""),self.server.token))

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            if not self.authorized():
                self.send(403,{"error":"Unauthorized local request"}); return
            try:
                if path == "/api/boards":
                    self.send(200,{"boards":self.server.device.boards()})
                elif path == "/api/job":
                    self.send(200,self.server.device.job_state())
                else:
                    self.send(404,{"error":"Not found"})
            except Exception as exc:
                self.send(400,{"error":str(exc)})
            return
        files = {"/":("index.html","text/html; charset=utf-8"),
                 "/app.js":("app.js","text/javascript; charset=utf-8"),
                 "/style.css":("style.css","text/css; charset=utf-8")}
        if path not in files:
            self.send(404,{"error":"Not found"}); return
        name, content_type = files[path]
        self.send(200,(STATIC/name).read_bytes(),content_type)

    def do_POST(self):
        if not self.authorized():
            self.send(403,{"error":"Unauthorized local request"}); return
        try:
            size = int(self.headers.get("Content-Length",0))
            if size <= 0 or size > 8192:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data,dict):
                raise ValueError("Expected an object")
            device = self.server.device
            if self.path == "/api/connect":
                result = device.connect(data.get("port"))
            elif self.path == "/api/command":
                result = device.command(data)
            elif self.path == "/api/flash":
                result = device.flash(data.get("port"),data.get("board"))
            elif self.path == "/api/disconnect":
                with device.lock:
                    device.close()
                result = {}
            else:
                self.send(404,{"error":"Not found"}); return
            self.send(200,result)
        except Exception as exc:
            self.send(400,{"error":str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=0,help="Local web port (default: choose a free port)")
    parser.add_argument("--no-browser",action="store_true")
    args = parser.parse_args()
    server = Server(("127.0.0.1",args.port))
    url = f"http://127.0.0.1:{server.server_port}/#{server.token}"
    print("Clock setup: " + url,flush=True)
    print("Keep this process running. Ctrl+C closes the tool.",flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.device.close()
        server.server_close()


if __name__ == "__main__":
    main()
