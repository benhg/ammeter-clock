import sys,tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/clock_setup'))
import app,wifi_update

class WifiUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'update.json';self.d=app.Device(self.path)
        self.row=dict(port='usb1',board='uno-r4-wifi',recognized=True,serial_number='original')
        self.d.boards=lambda:[self.row]
        self.saved=dict(protocol=1,firmware='0.5.0',wifi_firmware='0.6.1',hour_scale=3719,minute_scale=3413,cal_active=False)
        self.d.connect=lambda port:dict(self.saved)
    def start(self):
        with patch.object(app.wifi_update,'find_uploader',return_value='uploader'),patch.object(app.threading,'Thread'):
            self.d.update_wifi('usb1')
    def test_requires_r4_and_persists_recovery_without_credentials(self):
        self.row['board']='uno-r3'
        with self.assertRaises(ValueError):self.start()
        self.assertFalse(self.path.exists())
        self.row['board']='uno-r4-wifi';self.saved['password']='do not save'
        self.start();record=wifi_update.load(self.path)
        self.assertEqual(record['saved']['hour_scale'],3719);self.assertNotIn('password',record['saved'])
        reloaded=app.Device(self.path);self.assertEqual(reloaded.wifi_pending,record)
        with self.assertRaises(RuntimeError):reloaded.flash('usb1','uno-r4-wifi')
        with self.assertRaises(RuntimeError):reloaded.restore_clock()
    def test_updater_success_and_error_both_require_power_cycle(self):
        self.start()
        for code in (0,1):
            self.d.busy=True
            with patch.object(app,'run_cli',return_value=SimpleNamespace(returncode=code,stdout='vendor log',stderr='')) as run:
                self.d._update_wifi('uploader','usb1')
            self.assertIn('ESP32-S3@0.6.1',run.call_args.args[0])
            self.assertEqual(self.d.job_state()['state'],'reconnect');self.assertFalse(self.d.busy)
            self.assertTrue(self.path.exists())
    def test_matching_original_board_including_changed_port(self):
        self.start();self.d.busy=False
        self.row['port']='usb2'
        with patch.object(app.threading,'Thread') as thread:self.d.restore_clock(power_cycled=True)
        self.assertEqual(thread.call_args.kwargs['args'],('usb2','uno-r4-wifi',True))
        self.d.busy=False;self.row['serial_number']='other'
        with self.assertRaises(RuntimeError):self.d.restore_clock(power_cycled=True)
    def test_restore_checks_versions_and_calibration_before_clearing_record(self):
        self.start()
        def run(cmd,**kwargs):
            output=json.dumps({'platforms':[{'id':'arduino:renesas_uno','installed_version':'1.6.0'}]}) if cmd[1:3]==['core','list'] else ''
            return SimpleNamespace(returncode=0,stdout=output,stderr='')
        with patch.object(app,'find_cli',return_value='cli'),patch.object(app,'run_cli',side_effect=run):
            self.saved['hour_scale']=1;self.d._flash('usb1','uno-r4-wifi',True)
            self.assertEqual(self.d.job_state()['state'],'error');self.assertTrue(self.path.exists())
            self.saved['hour_scale']=3719;self.d._flash('usb1','uno-r4-wifi',True)
        self.assertEqual(self.d.job_state()['state'],'done');self.assertFalse(self.path.exists());self.assertIsNone(self.d.wifi_pending)
    def test_wrong_clock_cannot_be_selected_for_retry(self):
        self.start();self.d.busy=False
        original=self.row.copy();other=dict(self.row,port='usb2',serial_number='other');self.d.boards=lambda:[original,other]
        with self.assertRaises(RuntimeError):self.d.update_wifi('usb2',retrying=True)

if __name__=='__main__':unittest.main()
