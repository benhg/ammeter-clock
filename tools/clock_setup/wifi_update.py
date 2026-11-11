"""R4 connectivity updates: persist the unplug boundary before touching the board."""
import json
import os
from pathlib import Path
import shutil
import sys

WIFI_FIRMWARE = '0.6.1'  # Qualified on the assembled clock; not an untested latest version.
CALIBRATION_KEYS = ('hour_scale','minute_scale','second_scale','seconds_enabled','offset','dst','enabled','timezone_name','wifi_configured')

def state_path():
    if sys.platform == 'darwin':base=Path.home()/'Library/Application Support'
    elif sys.platform == 'win32':base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    else:base=Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))
    return base/'KN6UBF Clock Setup'/'wifi-update.json'

def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with open(temporary,'w',opener=lambda p,f:os.open(p,f,0o600)) as stream:json.dump(value,stream)
    temporary.replace(path)

def load(path):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError:return None
    except (ValueError,OSError) as exc:raise RuntimeError('Cannot read Wi-Fi update recovery record; do not flash until it is recovered.') from exc

def find_uploader(bundle, root):
    name='arduino-fwuploader.exe' if sys.platform=='win32' else 'arduino-fwuploader'
    for path in (bundle/'bin'/name,root/'.tools/package-bin'/name,shutil.which(name)):
        if path and Path(path).is_file():return str(path)
    raise RuntimeError('Arduino Wi-Fi updater is missing. Install the complete desktop app.')

def match_board(rows, record):
    candidates=[r for r in rows if r.get('board')=='uno-r4-wifi']
    serial=record.get('serial_number')
    matches=[r for r in candidates if r.get('serial_number')==serial] if serial else [r for r in candidates if r['port']==record['port']]
    if len(matches)!=1:raise RuntimeError('Reconnect the original R4 WiFi and refresh devices. No unique matching clock was found.')
    return matches[0]
