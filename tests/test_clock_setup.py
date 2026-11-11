import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('clock_setup', ROOT/'tools/clock_setup/app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class FakeSerial:
    def __init__(self): self.lines=[]; self.sent=[]
    def reset_input_buffer(self): self.lines=[]
    def write(self, data):
        self.sent.append(data)
        self.lines=[b'boot noise\n', b'OK {"protocol":1}\n']
    def flush(self): pass
    def readline(self, _): return self.lines.pop(0) if self.lines else b''
    def close(self): pass

class SetupTests(unittest.TestCase):
    def test_credentials_and_bounds(self):
        self.assertEqual(app.make_command({'action':'wifi','ssid':'A B','password':'abc defg'}),'WIFI 412042 6162632064656667')
        for data in [dict(action='wifi',ssid='x\n',password='12345678'),
                     dict(action='wifi',ssid='x',password='123'),
                     dict(action='wifi',ssid='é'*17,password='12345678'),
                     dict(action='scale',hour=4096,minute=20),
                     dict(action='zone',offset=True,dst=1),
                     dict(action='output',enabled='true'),
                     dict(action='time',epoch=0)]:
            with self.subTest(data=data), self.assertRaises(ValueError): app.make_command(data)
        self.assertEqual(app.make_command(dict(action='wifi',ssid='test',password='')),'WIFI 74657374 -')
    def test_pattern_commands(self):
        self.assertEqual(app.make_command(dict(action='test',operation='start')),'TEST START')
        self.assertEqual(app.make_command(dict(action='test',operation='stop')),'TEST STOP')
        with self.assertRaises(ValueError): app.make_command(dict(action='test',operation='restart'))

    def test_calibration_commands(self):
        for operation,values,expected in [
            ('begin',dict(seconds=True),'CAL BEGIN 1'),
            ('target',dict(hour=12,minute=30,second=30),'CAL TARGET 12 30 30'),
            ('scale',dict(hour=3719,minute=3413,second=3360),'CAL SCALE 3719 3413 3360'),
            ('save',{},'CAL SAVE'),('cancel',{},'CAL CANCEL'),('sweep',{},'CAL SWEEP')]:
            self.assertEqual(app.make_command(dict(action='calibration',operation=operation,**values)),expected)
        for values in [dict(operation='target',hour=13,minute=30,second=0),
                       dict(operation='scale',hour=0,minute=1,second=1),
                       dict(operation='begin',seconds='yes'),dict(operation='unknown')]:
            with self.assertRaises(ValueError):app.make_command(dict(action='calibration',**values))
        self.assertEqual(app.make_command(dict(action='seconds',enabled=False)),'SECONDS 0')

    def test_variable_sweep_durations(self):
        self.assertEqual(app.make_command(dict(action='test',operation='start',duration=5)),'TEST START 5')
        self.assertEqual(app.make_command(dict(action='calibration',operation='sweep',duration=600)),'CAL SWEEP 600')
        for n in [4,601,True,10.5]:
            with self.assertRaises(ValueError):app.make_command(dict(action='test',operation='start',duration=n))

    def test_serial_framing(self):
        device=app.Device(); device.serial=FakeSerial()
        self.assertEqual(device.request('STATUS'),{'protocol':1})
        self.assertEqual(device.serial.sent,[b'STATUS\n'])
    def test_first_flash_installs_board_support(self):
        device=app.Device(); device.busy=True; calls=[]
        def run(command, **_):
            calls.append(command)
            if command[1:3]==['core','list']:
                return subprocess.CompletedProcess(command,1,'','No package index yet')
            return subprocess.CompletedProcess(command,0,'ok','')
        with patch.object(app,'find_cli',return_value='cli'), patch.object(app,'run_cli',side_effect=run):
            device._flash('COM1','uno-r3')
        self.assertEqual(device.job_state()['state'],'done')
        self.assertFalse(device.busy)
        self.assertIn(['cli','core','update-index'],calls)
        self.assertIn(['cli','core','install','arduino:avr'],calls)
        self.assertEqual(calls[-1][1],'upload')

    def test_usb_enumeration_ignores_pseudo_ports(self):
        from types import SimpleNamespace
        ports=[SimpleNamespace(device='/dev/cu.wlan-debug',vid=None,pid=None,description='debug'),
               SimpleNamespace(device='/dev/cu.usbmodem1',vid=0x2341,pid=0x1002,description='R4'),
               SimpleNamespace(device='/dev/cu.usbserial1',vid=0x1a86,pid=0x7523,description='clone')]
        with patch('serial.tools.list_ports.comports',return_value=ports):rows=app.Device().boards()
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['board'],'uno-r4-wifi');self.assertFalse(rows[1]['recognized'])

    def test_scan_deduplicates_and_preserves_names(self):
        device=app.Device()
        rows=[dict(ssid_hex=name.encode().hex(),rssi=rssi,open=opened) for name,rssi,opened in [('A "quoted" network',-70,False),('A "quoted" network',-30,False),('Open',-50,True),('',-10,True)]]
        with patch.object(device,'request',return_value={'networks':rows}) as request:
            networks=device.scan_networks()
        request.assert_called_once_with('WIFI_SCAN')
        self.assertEqual([x['rssi'] for x in networks],[-30,-50])
        self.assertTrue(networks[1]['open'])

if __name__=='__main__': unittest.main()
