import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

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
    def test_serial_framing(self):
        device=app.Device(); device.serial=FakeSerial()
        self.assertEqual(device.request('STATUS'),{'protocol':1})
        self.assertEqual(device.serial.sent,[b'STATUS\n'])
    def test_http_auth_and_input(self):
        server=app.Server(('127.0.0.1',0))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path, data=None, token=None, origin=None):
            headers={}
            if token: headers['X-Clock-Token']=token
            if origin: headers['Origin']=origin
            if data is not None: headers['Content-Type']='application/json'
            return urlopen(Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers))
        try:
            self.assertIn(b'Clock setup',request('/').read())
            with self.assertRaises(HTTPError) as denied: request('/api/job')
            self.assertEqual(denied.exception.code,403); denied.exception.close()
            with self.assertRaises(HTTPError) as denied: request('/api/job',token=server.token,origin='https://example.com')
            self.assertEqual(denied.exception.code,403); denied.exception.close()
            result=json.load(request('/api/job',token=server.token)); self.assertEqual(result['state'],'idle')
            with self.assertRaises(HTTPError) as invalid: request('/api/command',{'action':'output','enabled':'yes'},server.token)
            self.assertEqual(invalid.exception.code,400); invalid.exception.close()
            with patch.object(server.device,'boards',return_value=[dict(port='test',board='uno-r4-wifi',recognized=True)]):
                with self.assertRaises(ValueError): server.device.flash('test','uno-r3')
            with self.assertRaises(HTTPError) as missing: request('/../../README.md')
            self.assertEqual(missing.exception.code,404); missing.exception.close()
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
