import os,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/clock_setup'))
from PySide6 import QtWidgets
import native_app

class Device:
    def __init__(self):
        self.serial=None;self.busy=False;self.commands=[];self.job={'state':'idle','log':''}
        import threading
        self.lock=threading.RLock()
        self.s=dict(board='uno-r4-wifi',firmware='0.4.0',local_epoch=1793215800,time_valid=True,source='ntp',manual_override=False,wifi_supported=True,wifi_scan_supported=True,wifi_connected=True,enabled=True,dac_ready=True,cal_active=False,seconds_enabled=False,offset=-480,dst=1,hour_scale=3719,minute_scale=3413,second_scale=3360)
    def boards(self):return [dict(port='test',name='Test R4',board='uno-r4-wifi',recognized=True)]
    def connect(self,port):self.serial=True;return dict(self.s)
    def close(self):self.serial=None
    def scan_networks(self):return [dict(ssid='Test WiFi',rssi=-40,open=False),dict(ssid='Open WiFi',rssi=-60,open=True)]
    def command(self,data):
        self.commands.append(data)
        if data['action']=='calibration':
            op=data['operation']
            if op=='begin':self.original=dict(self.s);self.s.update(cal_active=True,draft_hour=3719,draft_minute=3413,draft_second=3360,draft_seconds_enabled=data['seconds'])
            if op=='target':self.s.update(cal_hour=data['hour'],cal_minute=data['minute'],cal_second=data['second'])
            if op=='scale':self.s.update(draft_hour=data['hour'],draft_minute=data['minute'],draft_second=data['second'])
            if op=='cancel':self.s=dict(self.original)
            if op=='save':self.s.update(cal_active=False,hour_scale=self.s['draft_hour'],minute_scale=self.s['draft_minute'])
        return dict(self.s)
    def flash(self,port,board):self.commands.append(('flash',port,board));self.close();self.job={'state':'done','log':'Installed'};return {}
    def job_state(self):return dict(self.job)

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    def setUp(self):self.device=Device();self.w=native_app.Window(self.device,auto_refresh=False);self.w.timer.stop();self.w.job_timer.stop()
    def tearDown(self):self.w.state=None;self.w.close();self.qt.processEvents()
    def wait(self):
        until=time.monotonic()+3
        while self.w.working and time.monotonic()<until:self.qt.processEvents();time.sleep(.005)
        self.assertFalse(self.w.working)
    def click(self,w):w.click();self.wait()
    def connect(self):self.w.refresh();self.wait();self.click(self.w.connect_btn)
    def test_connect_without_upload_and_password_toggle(self):
        with patch('socket.socket',side_effect=AssertionError('No server permitted')):
            self.connect()
        self.assertIn('Connected',self.w.connection.text());self.assertFalse(self.device.commands)
        self.w.password.setText('a password');self.w.show_password.setChecked(True)
        self.assertEqual(self.w.password.echoMode(),QtWidgets.QLineEdit.Normal)
        self.w.show_password.setChecked(False);self.assertEqual(self.w.password.echoMode(),QtWidgets.QLineEdit.Password)
        self.click(self.w.scan_btn);self.assertEqual(self.w.ssid.count(),2)
        self.w.ssid.setCurrentIndex(1);self.w.ssid.activated.emit(1);self.assertTrue(self.w.open_network.isChecked())
        self.click(self.w.wifi_save);self.assertEqual(self.device.commands[-2],dict(action='wifi',ssid='Open WiFi',password=''));self.assertEqual(self.device.commands[-1],dict(action='sync'))
    def test_wizard(self):
        self.connect();self.click(self.w.cal_start);self.assertTrue(self.w.state['cal_active']);self.assertIn('All outputs are zero',self.w.cal_text.text())
        self.click(self.w.next);self.assertEqual(self.device.commands[-1]['hour'],12)
        self.click(self.w.lower);self.assertEqual(self.w.state['draft_hour'],3694)
        self.click(self.w.next);self.click(self.w.next);self.assertTrue(self.w.verify.isHidden()==False)
        self.w.hold_m.setValue(47);self.click(self.w.hold_btn);self.assertEqual(self.device.commands[-1]['minute'],47)
        self.click(self.w.sweep_btn);self.assertEqual(self.device.commands[-1]['operation'],'sweep')
        self.click(self.w.save);self.assertFalse(self.w.state['cal_active']);self.assertEqual(self.w.state['hour_scale'],3694)
        self.click(self.w.cal_start);self.click(self.w.cancel);self.assertFalse(self.w.state['cal_active'])
    def test_first_time_install_is_separate(self):
        self.w.refresh();self.wait();self.assertTrue(self.w.connect_btn.isEnabled());self.assertTrue(self.w.flash_btn.isEnabled());self.assertIsNone(self.w.state)
        with patch.object(QtWidgets.QMessageBox,'question',return_value=QtWidgets.QMessageBox.Yes):self.click(self.w.flash_btn)
        self.assertEqual(self.device.commands[-1],('flash','test','uno-r4-wifi'));self.w.poll_job();self.wait();self.assertIn('Refresh USB',self.w.notice.text())
    def test_connect_failure_points_to_install_panel(self):
        self.w.refresh();self.wait()
        def unavailable(_):raise RuntimeError('No clock reply. Install firmware first.')
        self.device.connect=unavailable;self.click(self.w.connect_btn)
        self.assertEqual(self.w.tabs.currentWidget(),self.w.flash_page)
        self.assertIn('No clock reply',self.w.notice.text())

    def test_old_firmware_manual_wifi_still_works(self):
        del self.device.s['wifi_scan_supported'];self.connect();self.assertFalse(self.w.scan_btn.isEnabled());self.assertTrue(self.w.wifi_save.isEnabled())

if __name__=='__main__':unittest.main()
