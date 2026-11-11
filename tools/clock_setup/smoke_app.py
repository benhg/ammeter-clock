"""Smoke-test a built app without Python/Arduino CLI supplied by PATH."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

parser=argparse.ArgumentParser();parser.add_argument('--executable',type=Path);args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
name='KN6UBF Clock Setup'
system=platform.system()
folder=root/'dist-clock'/((name+'.app') if system=='Darwin' else name)
executable=folder/'Contents/MacOS'/name if system=='Darwin' else folder/(name+'.exe' if system=='Windows' else name)
manifest=root/'dist-clock/build-result.json'
if manifest.exists():executable=Path(json.loads(manifest.read_text())['executable'])
if args.executable:executable=args.executable
with tempfile.TemporaryDirectory() as tmp:
    result=Path(tmp)/'result.json'
    env=os.environ.copy();env.pop('ARDUINO_CLI',None)
    if system=='Linux':env.setdefault('QT_QPA_PLATFORM','offscreen')
    # Frozen app must find its own CLI, never a CI runner's installation.
    subprocess.run([str(executable),'--self-test',str(result)],env=env,check=True,timeout=60)
    data=json.loads(result.read_text());assert data['frozen'] and '1.5.1' in data['cli'],data
    assert data['ui']=='native-qt'
print('PASS: standalone executable, bundled CLI/firmware/assets, and native Qt window')
