"""Smoke-test a built app without Python/Arduino CLI supplied by PATH."""
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import tempfile
import time
import urllib.request

root=Path(__file__).resolve().parents[2]
name='KN6UBF Clock Setup'
system=platform.system()
folder=root/'dist-clock'/((name+'.app') if system=='Darwin' else name)
executable=folder/'Contents/MacOS'/name if system=='Darwin' else folder/(name+'.exe' if system=='Windows' else name)
with tempfile.TemporaryDirectory() as tmp:
    result=Path(tmp)/'result.json'
    env=os.environ.copy();env.pop('ARDUINO_CLI',None)
    # Frozen app must find its own CLI, never a CI runner's installation.
    subprocess.run([str(executable),'--self-test',str(result)],env=env,check=True,timeout=60)
    data=json.loads(result.read_text());assert data['frozen'] and '1.5.1' in data['cli'],data
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    process=subprocess.Popen([str(executable),'--no-browser','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for i in range(60):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as response:
                    assert b'Clock setup' in response.read();break
            except OSError:
                if process.poll() is not None:raise RuntimeError('App exited before serving the UI')
                time.sleep(.25)
        else:raise RuntimeError('App did not serve the UI')
    finally:
        process.terminate();process.wait(timeout=10)
print('PASS: standalone executable, bundled CLI/firmware/assets, and local web UI')
