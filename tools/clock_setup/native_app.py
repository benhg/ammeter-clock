"""Native Qt Widgets desktop setup. USB calls run off the UI thread; no browser/server."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
from PySide6 import QtCore,QtWidgets
from app import Device,ROOT,find_cli,run_cli
from timezones import zone_names
from wifi_update import find_uploader

VERSION='0.6.0'
class WorkSignals(QtCore.QObject):
    done=QtCore.Signal(object,object)
class Work(QtCore.QRunnable):
    def __init__(self,fn):super().__init__();self.fn=fn;self.signals=WorkSignals()
    def run(self):
        try:self.signals.done.emit(self.fn(),None)
        except Exception as e:self.signals.done.emit(None,str(e))

def label(text):
    w=QtWidgets.QLabel(text);w.setWordWrap(True);return w

def spin(low,high,value):
    w=QtWidgets.QSpinBox();w.setRange(low,high);w.setValue(value);return w

class Window(QtWidgets.QMainWindow):
    def __init__(self,device=None,auto_refresh=True):
        super().__init__();self.device=device or Device();self.state=None;self.working=False;self.worker=None;self.step=0;self.closing=False;self.polling=False;self.clock_epoch=None;self.clock_received=0;self.after_flash=None;self.flash_port=None
        self.setWindowTitle('KN6UBF Clock Setup');self.resize(900,810)
        root=QtWidgets.QWidget();self.setCentralWidget(root);layout=QtWidgets.QVBoxLayout(root)
        title=label('KN6UBF · Clock Setup');font=title.font();font.setPointSize(22);title.setFont(font);layout.addWidget(title)
        self.notice=label('Plug the Arduino into USB. Connect if clock firmware is installed, or install it below.');layout.addWidget(self.notice)
        box=QtWidgets.QGroupBox('USB connection');row=QtWidgets.QGridLayout(box);layout.addWidget(box)
        self.ports=QtWidgets.QComboBox();self.ports.setMinimumWidth(300);self.ports.setAccessibleName("USB device")
        self.boards=QtWidgets.QComboBox();self.boards.setAccessibleName('Arduino model');self.boards.addItem('Uno R4 WiFi','uno-r4-wifi');self.boards.addItem('Uno R3','uno-r3')
        self.refresh_btn=self.button('Refresh devices',self.refresh);self.connect_btn=self.button('Connect',self.connect);self.disconnect_btn=self.button('Disconnect',self.disconnect)
        row.addWidget(self.ports,0,0,1,3);row.addWidget(self.refresh_btn,0,3);row.addWidget(self.connect_btn,1,0);row.addWidget(self.disconnect_btn,1,1)
        self.connection=label('Not connected');row.addWidget(self.connection,1,2,1,2)
        self.tabs=QtWidgets.QTabWidget();layout.addWidget(self.tabs)
        self.time_page,self.time_layout=self.page('Clock')
        self.clock=label('— : — : —');f=self.clock.font();f.setPointSize(32);self.clock.setFont(f);self.time_layout.addWidget(self.clock)
        self.clock_status=label('Connect to read the clock.');self.time_layout.addWidget(self.clock_status)
        zone=QtWidgets.QFormLayout();zone.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow);self.zone=QtWidgets.QComboBox()
        self.zone.setEditable(True);self.zone.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        for name in zone_names():self.zone.addItem(name,name)
        self.zone.addItem('Custom UTC offset',None)
        self.zone.setCurrentIndex(self.zone.findData('America/Los_Angeles'))
        self.zone.completer().setFilterMode(QtCore.Qt.MatchContains);self.zone.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.offset=spin(-720,840,-480);self.dst=QtWidgets.QComboBox();self.dst.addItems(['No daylight saving','US daylight saving','EU daylight saving'])
        zone.addRow('Timezone',self.zone);zone.addRow('UTC offset (minutes)',self.offset);zone.addRow('Daylight saving',self.dst);self.zone_form=zone;self.time_layout.addLayout(zone)
        self.time_layout.addWidget(label('City time zones include daylight-saving rules. Choose Custom UTC offset to enter an offset manually.'))
        self.zone.currentIndexChanged.connect(self.zone_changed);self.zone.currentTextChanged.connect(self.zone_changed);self.zone_changed()
        self.time_btn=self.button('Set from computer',self.set_time);self.zone_btn=self.button('Save timezone',self.save_zone);self.sync_btn=self.button('Resume Wi-Fi / NTP',lambda:self.command({'action':'sync'}))
        self.time_layout.addWidget(self.time_btn);self.time_layout.addWidget(self.zone_btn);self.time_layout.addWidget(self.sync_btn)
        self.time_layout.addWidget(label('HOUR / MINUTE buttons advance time; hold to repeat. On R4, hold both for 3 seconds to resume NTP.'))
        self.time_layout.addStretch()
        self.wifi_page,self.wifi_layout=self.page('Wi-Fi')
        self.wifi_status=label('Wi-Fi requires an Uno R4 WiFi.');self.wifi_layout.addWidget(self.wifi_status)
        self.scan_hint=label('Connect an R4 WiFi to search for networks.');self.wifi_layout.addWidget(self.scan_hint)
        self.scan_btn=self.button('Search nearby networks',self.scan);self.wifi_layout.addWidget(self.scan_btn)
        form=QtWidgets.QFormLayout();form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow);self.ssid=QtWidgets.QComboBox();self.ssid.setEditable(True);self.ssid.setInsertPolicy(QtWidgets.QComboBox.NoInsert);form.addRow('Network name',self.ssid)
        self.password=QtWidgets.QLineEdit();self.password.setEchoMode(QtWidgets.QLineEdit.Password);form.addRow('Password',self.password);self.wifi_layout.addLayout(form)
        self.show_password=QtWidgets.QCheckBox('Show password');self.show_password.toggled.connect(lambda v:self.password.setEchoMode(QtWidgets.QLineEdit.Normal if v else QtWidgets.QLineEdit.Password));self.wifi_layout.addWidget(self.show_password)
        self.open_network=QtWidgets.QCheckBox('This network has no password');self.open_network.toggled.connect(lambda _:self.controls());self.wifi_layout.addWidget(self.open_network)
        self.ssid.activated.connect(self.network_selected)
        self.wifi_save=self.button('Save Wi-Fi and sync clock',self.save_wifi);self.wifi_forget=self.button('Forget saved network',lambda:self.command({'action':'wifi_clear'}));self.wifi_layout.addWidget(self.wifi_save);self.wifi_layout.addWidget(self.wifi_forget)
        self.wifi_layout.addWidget(label('Search uses the R4’s radio. You can also type a hidden network name. Credentials are sent over USB and stored only on the clock. Use a 2.4 GHz network.'));self.wifi_layout.addStretch()
        self.cal_page,self.cal_layout=self.page('Calibration')
        self.seconds=QtWidgets.QCheckBox('Seconds meter connected (Rev 2)');self.cal_layout.addWidget(self.seconds)
        self.cal_start=self.button('Start calibration wizard',self.start_cal);self.cal_layout.addWidget(self.cal_start)
        self.cal_text=label('Zero the needles mechanically, match a held 12:30 reference, then test and save.');self.cal_layout.addWidget(self.cal_text)
        self.adjust=QtWidgets.QGroupBox('Adjust the reference needle');a=QtWidgets.QHBoxLayout(self.adjust)
        self.lower=self.button('↓ Lower needle',lambda:self.adjust_scale(-1));self.higher=self.button('↑ Raise needle',lambda:self.adjust_scale(1));self.amount=QtWidgets.QComboBox()
        for name,n in [('Coarse',100),('Normal',25),('Fine',5),('Very fine',1)]:self.amount.addItem(name,n)
        self.amount.setCurrentIndex(1);a.addWidget(self.lower);a.addWidget(self.higher);a.addWidget(self.amount);self.cal_layout.addWidget(self.adjust)
        self.verify=QtWidgets.QGroupBox('Test fixed values or sweep');v=QtWidgets.QGridLayout(self.verify);self.hold_h=spin(0,12,6);self.hold_m=spin(0,60,15);self.hold_s=spin(0,60,45)
        for i,(name,w) in enumerate([('Hours',self.hold_h),('Minutes',self.hold_m),('Seconds',self.hold_s)]):v.addWidget(label(name),0,i);v.addWidget(w,1,i)
        self.hold_btn=self.button('Hold these values',self.hold);self.sweep_btn=self.button('Sweep all meters',lambda:self.cal('sweep',duration=self.sweep_seconds.value()));self.stop_btn=self.button('Stop sweep / hold values',self.hold)
        v.addWidget(self.hold_btn,2,0);v.addWidget(self.sweep_btn,2,1);v.addWidget(self.stop_btn,2,2);self.cal_layout.addWidget(self.verify)
        nav=QtWidgets.QHBoxLayout();self.back=self.button('Back',lambda:self.go(self.step-1));self.next=self.button('Next',lambda:self.go(self.step+1));self.save=self.button('Save & run clock',lambda:self.cal('save'));self.cancel=self.button('Cancel · discard changes',lambda:self.cal('cancel'))
        for w in [self.back,self.next,self.save,self.cancel]:nav.addWidget(w)
        self.cal_layout.addLayout(nav);self.cal_layout.addWidget(label('Only Save writes calibration. Cancel restores prior settings. After ten idle minutes outputs are held at zero.'))
        timing=QtWidgets.QHBoxLayout();timing.addWidget(label('Sweep duration'));self.sweep_seconds=spin(5,600,61);self.sweep_seconds.setSuffix(' seconds');timing.addWidget(self.sweep_seconds);self.cal_layout.addLayout(timing)
        self.enable=self.button('Enable live meters',self.enable_outputs);self.disable=self.button('Disable meters',lambda:self.command({'action':'output','enabled':False}));self.test=self.button('Run saved calibration sweep',self.start_sweep);self.test_stop=self.button('Stop test',lambda:self.command({'action':'test','operation':'stop'}))
        for w in [self.enable,self.disable,self.test,self.test_stop]:self.cal_layout.addWidget(w)
        self.cal_layout.addStretch()
        self.flash_page,self.flash_layout=self.page('Install / update firmware')
        self.flash_layout.addWidget(label('First-time setup only, or when updating: select your Arduino model and install the bundled clock firmware. Then return to USB connection and click Connect. Existing clock firmware does not need reinstalling each time.'))
        self.flash_layout.addWidget(self.boards);self.flash_btn=self.button('Install clock firmware',self.flash);self.flash_layout.addWidget(self.flash_btn)
        self.wifi_version=label('R4 Wi-Fi module: connect to read its version.');self.flash_layout.addWidget(self.wifi_version)
        self.wifi_update_hint=label('R4 WiFi only: update the separate Wi-Fi module to qualified version 0.6.1. Internet access is required. The app then guides a full power cycle and restores clock firmware.');self.flash_layout.addWidget(self.wifi_update_hint)
        self.wifi_update_btn=self.button('Update R4 Wi-Fi firmware',self.update_wifi);self.flash_layout.addWidget(self.wifi_update_btn)
        self.wifi_restore_btn=self.button('I have reconnected — restore clock firmware',self.restore_wifi);self.flash_layout.addWidget(self.wifi_restore_btn)
        self.log=QtWidgets.QPlainTextEdit();self.log.setReadOnly(True);self.flash_layout.addWidget(self.log)
        self.footer=label('Native desktop app · '+VERSION);layout.addWidget(self.footer)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(2500)
        self.clock_timer=QtCore.QTimer(self);self.clock_timer.timeout.connect(self.tick_clock);self.clock_timer.start(100)
        self.job_timer=QtCore.QTimer(self);self.job_timer.timeout.connect(self.poll_job);self.job_timer.start(500)
        self.ports.currentIndexChanged.connect(self.select_board);self.controls()
        if getattr(self.device,'wifi_pending',None):self.tabs.setCurrentWidget(self.flash_page);self.notice.setText('Unfinished Wi-Fi update: unplug all power, reconnect, then restore clock firmware below.')
        if auto_refresh:QtCore.QTimer.singleShot(0,self.refresh)
    def button(self,text,fn):
        w=QtWidgets.QPushButton(text);w.clicked.connect(lambda checked=False:fn());return w
    def page(self,title):
        page=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(page);self.tabs.addTab(page,title);return page,layout
    def run(self,fn,success=None,message=None):
        if self.working or self.device.busy:return
        self.working=True
        if not self.polling:self.controls()
        self.worker=Work(fn)
        def finish(value,error):
            self.working=False
            if error:
                self.notice.setText(error)
                if not self.device.serial:self.state=None;self.connection.setText('Not connected — install clock firmware if this is first-time setup.');self.tabs.setCurrentWidget(self.flash_page)
            else:
                if success:success(value)
                if message:self.notice.setText(message)
            self.polling=False;self.controls();self.worker=None
        self.worker.signals.done.connect(finish,QtCore.Qt.QueuedConnection);QtCore.QThreadPool.globalInstance().start(self.worker)
    def refresh(self):
        def done(rows):
            previous=self.ports.currentData();self.ports.clear()
            for r in rows:self.ports.addItem(r['name']+' · '+r['port'],r)
            matched=False
            if previous:
                for i in range(self.ports.count()):
                    if self.ports.itemData(i)['port']==previous['port']:self.ports.setCurrentIndex(i);matched=True;break
            if not matched:
                for i,r in enumerate(rows):
                    if r.get('recognized'):self.ports.setCurrentIndex(i);break
            self.select_board()
            if not rows:self.notice.setText('No USB device found. Check the data cable, then refresh.')
        self.run(self.device.boards,done)
    def select_board(self):
        row=self.ports.currentData() or {};index=self.boards.findData(row.get('board'))
        if index>=0:self.boards.setCurrentIndex(index)
        self.controls()
    def connect(self):
        row=self.ports.currentData()
        if row:self.run(lambda:self.device.connect(row['port']),lambda s:self.render(s,True),'Connected to the clock.')
    def disconnect(self):
        def work():
            with self.device.lock:
                if self.state and self.state.get('cal_active'):self.device.command(dict(action='calibration',operation='cancel'))
                self.device.close()
        def done(_):self.state=None;self.clock_epoch=None;self.clock.setText('— : — : —');self.connection.setText('Disconnected');self.password.clear()
        self.run(work,done,'Disconnected.')
    def command(self,data,after=None,message=None):
        def done(s):
            self.render(s)
            if after:after(s)
        self.run(lambda:self.device.command(data),done,message)
    def selected_zone(self):
        text=self.zone.currentText()
        if text=='Custom UTC offset':return None
        if text not in self.names:raise ValueError('Choose a timezone from the list, or Custom UTC offset.')
        return text
    @property
    def names(self):return zone_names()
    def zone_changed(self,*_):
        custom=self.zone.currentText()=='Custom UTC offset'
        self.offset.setEnabled(custom);self.dst.setEnabled(custom)
        for w in [self.offset,self.dst]:w.setVisible(custom);self.zone_form.labelForField(w).setVisible(custom)
        self.controls() if hasattr(self,'scan_btn') and hasattr(self,'flash_btn') else None
    def zone_data(self):return dict(action='zone',offset=self.offset.value(),dst=self.dst.currentIndex())
    def apply_zone(self,name,custom):
        return self.device.set_timezone(name) if name else self.device.command(custom)
    def save_zone(self):
        try:name=self.selected_zone()
        except ValueError as e:self.notice.setText(str(e));return
        if name and not self.state.get('timezone_supported'):self.flash(('zone',name));return
        custom=self.zone_data();self.run(lambda:self.apply_zone(name,custom),self.render,'Timezone saved on the clock.')
    def set_time(self):
        try:name=self.selected_zone()
        except ValueError as e:self.notice.setText(str(e));return
        if name and not self.state.get('timezone_supported'):self.flash(('time',name));return
        custom=self.zone_data()
        def work():self.apply_zone(name,custom);return self.device.command(dict(action='time',epoch=int(time.time())))
        self.run(work,self.render,'Clock set from this computer. NTP paused until Resume NTP or the button gesture.')
    def tick_clock(self):
        if self.state and self.state.get('time_valid') and self.clock_epoch is not None:
            epoch=int(self.clock_epoch+max(0,time.monotonic()-self.clock_received))
            self.clock.setText(time.strftime('%H:%M:%S',time.gmtime(epoch)))
        else:self.clock.setText('— : — : —')
    def render(self,s,load=False):
        self.state=s;self.connection.setText('Connected · '+s['board']+' · firmware '+s.get('firmware','unknown'))
        now=time.monotonic()
        if not s.get('time_valid'):self.clock_epoch=None
        elif self.clock_epoch is None or load or abs(s['local_epoch']-(self.clock_epoch+now-self.clock_received))>1.5:self.clock_epoch=s['local_epoch'];self.clock_received=now
        self.tick_clock()
        self.clock_status.setText(('NTP paused · manually set' if s.get('manual_override') else 'Time source: '+s.get('source','unset'))+' · '+('Meters enabled' if s.get('enabled') else 'Meters disabled'))
        if s.get('cal_timeout'):self.notice.setText('Calibration timed out. Outputs held at zero. Start again or enable meters.')
        self.wifi_status.setText('Wi-Fi connected' if s.get('wifi_connected') else 'Network saved; waiting for connection' if s.get('wifi_configured') else 'No network configured')
        if s.get('timezone_stale'):self.notice.setText('Refresh the saved timezone schedule from this app.')
        if load:
            self.seconds.setChecked(bool(s.get('seconds_enabled')));self.offset.setValue(s.get('offset',0));self.dst.setCurrentIndex(s.get('dst',0))
            name=s.get('timezone_name') or {(-480,1):'America/Los_Angeles',(-420,1):'America/Denver',(-360,1):'America/Chicago',(-300,1):'America/New_York',(0,0):'UTC'}.get((s.get('offset'),s.get('dst')))
            self.zone.setCurrentIndex(self.zone.findData(name) if name else self.zone.count()-1);self.zone_changed()
            if s.get('cal_active'):self.step=len(self.steps())-1
        self.render_cal();self.controls()
    def controls(self):
        ready=bool(self.state) and not self.working and not self.device.busy;active=bool(self.state and self.state.get('cal_active'))
        pending=bool(getattr(self.device,'wifi_pending',None))
        free=not self.working and not self.device.busy
        if pending:ready=False
        self.refresh_btn.setEnabled(free and not active);self.ports.setEnabled(free and not self.state);self.connect_btn.setEnabled(free and not pending and not self.state and self.ports.count()>0);self.disconnect_btn.setEnabled(ready)
        self.flash_btn.setEnabled(free and not pending and not active and self.ports.count()>0);self.boards.setEnabled(free and not active)
        r4=(self.ports.currentData() or {}).get('board')=='uno-r4-wifi'
        self.wifi_update_btn.setEnabled(free and r4 and not active)
        self.wifi_update_btn.setText('I have reconnected — retry Wi-Fi update' if pending else 'Update R4 Wi-Fi firmware')
        self.wifi_restore_btn.setVisible(pending);self.wifi_restore_btn.setEnabled(free and pending)
        if pending:self.wifi_update_hint.setText('Unplug ALL power for five seconds, then reconnect. Restore clock firmware only after this power cycle. If the Wi-Fi update failed, retry it after reconnecting. Recovery is saved if you close the app.')
        else:self.wifi_update_hint.setText('R4 WiFi only: update the separate Wi-Fi module to qualified version 0.6.1. Internet access is required. The app then guides a full power cycle and restores clock firmware.')
        self.wifi_version.setText('R4 Wi-Fi module: '+str((self.state or {}).get('wifi_firmware','connect after installing current clock firmware to read version')))
        self.time_page.setEnabled(ready and not active)
        synced=bool(self.state and self.state.get('wifi_connected') and not self.state.get('manual_override') and self.state.get('source')=='ntp')
        self.sync_btn.setEnabled(ready and not active and bool(self.state.get('wifi_supported')) and not synced if self.state else False)
        self.sync_btn.setToolTip('Wi-Fi and NTP are already active.' if synced else 'Resume automatic network time.')
        custom=self.zone.currentText()=='Custom UTC offset'
        self.offset.setEnabled(custom);self.dst.setEnabled(custom)
        upgrade=not custom and bool(self.state) and not self.state.get('timezone_supported')
        self.zone_btn.setText('Update firmware & save timezone' if upgrade else 'Save timezone')
        self.time_btn.setText('Update firmware & set time' if upgrade else 'Set from computer')
        wifi_ready=ready and not active and bool(self.state and self.state.get('wifi_supported'))
        for w in [self.ssid,self.wifi_save,self.wifi_forget,self.open_network]:w.setEnabled(wifi_ready)
        self.scan_btn.setEnabled(wifi_ready)
        connected=bool(self.state and self.state.get('wifi_connected'))
        upgrade=self.scan_needs_upgrade()
        self.scan_btn.setText('Update firmware & search' if upgrade else 'Disconnect & search for networks' if connected else 'Search nearby networks')
        self.scan_hint.setText('Update firmware to enable scanning. This button updates, reconnects USB, and searches.' if upgrade else 'Disconnect to search for Wi-Fi networks. The button disconnects Wi-Fi, searches, then reconnects to the saved network. USB stays connected.' if connected else 'Search with the clock’s radio. USB stays connected.')
        self.password.setEnabled(wifi_ready and not self.open_network.isChecked());self.show_password.setEnabled(wifi_ready and not self.open_network.isChecked())
        self.cal_page.setEnabled(ready)
        self.cal_start.setText('Update firmware & calibrate' if self.state and not self.state.get('test_duration_supported') else 'Start calibration wizard')
        self.sweep_seconds.setEnabled(ready)
        self.cal_start.setEnabled(ready and not active and bool(self.state.get('dac_ready')) and 'cal_active' in self.state if self.state else False)
        self.seconds.setEnabled(ready and not active)
        for w in [self.enable,self.test,self.test_stop]:w.setEnabled(ready and not active)
        self.disable.setEnabled(ready)
    def poll(self):
        if self.state and not self.working and not self.device.busy:
            if isinstance(QtWidgets.QApplication.focusWidget(),(QtWidgets.QLineEdit,QtWidgets.QSpinBox,QtWidgets.QComboBox)):return
            self.polling=True;self.command(dict(action='status'))
    def scan_needs_upgrade(self):
        return bool(self.state and (not self.state.get('wifi_scan_supported') or (self.state.get('wifi_connected') and not self.state.get('wifi_scan_disconnect_supported'))))
    def scan_results(self,result):
        rows,status=result;self.render(status)
        current=self.ssid.currentText();self.ssid.clear()
        for r in rows:self.ssid.addItem(r['ssid'],r)
        if current:self.ssid.setEditText(current)
        self.notice.setText(f'{len(rows)} networks found. Reconnecting to the saved network automatically. Select one or type its name.')
    def scan(self):
        if self.scan_needs_upgrade():self.flash(('scan',None));return
        self.notice.setText('Disconnecting Wi-Fi and searching with the R4 radio… USB stays connected.')
        def work():return self.device.scan_networks(),self.device.command(dict(action='status'))
        self.run(work,self.scan_results)
    def network_selected(self,index):
        r=self.ssid.itemData(index)
        if r:self.open_network.setChecked(r['open']);self.notice.setText(f"{r['rssi']} dBm · "+('Open network' if r['open'] else 'Password required'))
    def save_wifi(self):
        data=dict(action='wifi',ssid=self.ssid.currentText(),password='' if self.open_network.isChecked() else self.password.text())
        def work():self.device.command(data);return self.device.command(dict(action='sync'))
        def done(s):self.password.clear();self.show_password.setChecked(False);self.render(s)
        self.run(work,done,'Wi-Fi saved. Waiting for network time.')
    def steps(self):return ['zero','hour','minute']+(['second'] if self.state and self.state.get('draft_seconds_enabled') else [])+['verify']
    def cal(self,operation,after=None,**values):self.command(dict(action='calibration',operation=operation,**values),after)
    def start_sweep(self):
        if not self.state.get('test_duration_supported'):self.flash(('test',self.sweep_seconds.value()));return
        self.command(dict(action='test',operation='start',duration=self.sweep_seconds.value()))
    def start_cal(self):
        if not self.state.get('test_duration_supported'):self.flash(('calibration',self.seconds.isChecked()));return
        self.step=0;self.cal('begin',seconds=self.seconds.isChecked())
    def go(self,step):
        steps=self.steps()
        if not 0<=step<len(steps):return
        kind=steps[step];values=(0,0,0) if kind=='zero' else (6,15,45) if kind=='verify' else (12,30,30)
        def done(s):self.step=step;self.render_cal()
        self.cal('target',done,hour=values[0],minute=values[1],second=values[2])
    def render_cal(self):
        active=bool(self.state and self.state.get('cal_active'));steps=self.steps();kind=steps[min(self.step,len(steps)-1)]
        for w in [self.back,self.next,self.save,self.cancel]:w.setVisible(active)
        self.adjust.setVisible(active and kind in ['hour','minute','second']);self.verify.setVisible(active and kind=='verify')
        self.back.setVisible(active and self.step>0);self.next.setVisible(active and kind!='verify');self.save.setVisible(active and kind=='verify')
        self.hold_s.setEnabled(bool(self.state and self.state.get('draft_seconds_enabled')))
        if active:
            instructions='All outputs are zero. Adjust each mechanical screw until its needle rests at zero.' if kind=='zero' else 'Check fixed values or sweep. Save returns to live time and enables the meters.' if kind=='verify' else f'Hold 12:30'+(':30' if self.state.get('draft_seconds_enabled') else '')+f'. Adjust the {kind} needle to '+('12.' if kind=='hour' else '30.')
            self.cal_text.setText(f'Step {self.step+1} of {len(steps)} · '+instructions)
        else:self.cal_text.setText('Start the wizard to zero, adjust and test the needles. Firmware 0.3.0 or later required.')
    def adjust_scale(self,direction):
        kind=self.steps()[self.step];values={k:self.state['draft_'+k] for k in ['hour','minute','second']};values[kind]+=direction*self.amount.currentData()
        if not 1<=values[kind]<=4095:self.notice.setText('Adjustment limit reached. Check meter rating and wiring.');return
        self.cal('scale',**values)
    def hold(self):self.cal('target',hour=self.hold_h.value(),minute=self.hold_m.value(),second=self.hold_s.value() if self.state.get('draft_seconds_enabled') else 0)
    def enable_outputs(self):
        if QtWidgets.QMessageBox.question(self,'Enable meters','Have you checked the meter wiring and calibration?')==QtWidgets.QMessageBox.Yes:self.command(dict(action='output',enabled=True))
    def update_wifi(self):
        pending=bool(getattr(self.device,'wifi_pending',None))
        text=('Have you unplugged ALL power for five seconds and reconnected the original R4?' if pending else
              'Update the R4 Wi-Fi module to 0.6.1? This replaces the current sketch temporarily. Keep USB connected until the update finishes. Then unplug/replug when prompted and restore clock firmware here. Compatible calibration and Wi-Fi settings are retained. Internet access is required.')
        if QtWidgets.QMessageBox.question(self,'Update R4 Wi-Fi firmware',text)!=QtWidgets.QMessageBox.Yes:return
        row=self.ports.currentData()
        def done(_):
            self.state=None;self.clock_epoch=None;self.connection.setText('Updating R4 Wi-Fi module…');self.tabs.setCurrentWidget(self.flash_page)
        self.run(lambda:self.device.update_wifi(row['port'],retrying=pending),done)
    def restore_wifi(self):
        if QtWidgets.QMessageBox.question(self,'Confirm power cycle','Have you unplugged ALL power for five seconds and reconnected the original R4? Never restore while the board is in ESP download mode.')!=QtWidgets.QMessageBox.Yes:return
        self.after_flash=('status',);self.flash_port=(getattr(self.device,'wifi_pending',None) or {}).get('port')
        def done(_):self.state=None;self.connection.setText('Restoring clock firmware…')
        self.run(lambda:self.device.restore_clock(power_cycled=True),done)
    def flash(self,after=None):
        text='Replace the Arduino sketch with clock firmware? Compatible saved calibration and Wi-Fi settings are retained.'
        if after:text+=' Then reconnect automatically and '+('disconnect Wi-Fi to search for networks.' if after[0]=='scan' else 'apply the selected timezone.' if after[0] in ('zone','time') else 'start calibration or the selected sweep.')
        if QtWidgets.QMessageBox.question(self,'Install firmware',text)!=QtWidgets.QMessageBox.Yes:return
        row=self.ports.currentData();board=self.boards.currentData();self.flash_port=row['port'];self.after_flash=after
        def done(_):self.state=None;self.clock_epoch=None;self.connection.setText('Installing firmware…');self.notice.setText('Installing firmware. Keep USB connected.');self.controls()
        self.run(lambda:self.device.flash(row['port'],board),done)
    def resume_after_flash(self,action):
        def work():
            deadline=time.monotonic()+15
            while True:
                rows=self.device.boards();row=next((r for r in rows if r['port']==self.flash_port),None)
                if not row:
                    candidates=[r for r in rows if r.get('board')=='uno-r4-wifi']
                    if len(candidates)==1:row=candidates[0]
                if row:break
                if time.monotonic()>=deadline:raise RuntimeError('Firmware installed. Refresh USB devices and connect to finish.')
                time.sleep(.25)
            status=self.device.connect(row['port'])
            if action[0]=='status':return status
            if action[0]=='scan':
                if not status.get('wifi_scan_disconnect_supported'):raise RuntimeError('Update did not enable Wi-Fi scanning. Check the firmware version.')
                return self.device.scan_networks(),self.device.command(dict(action='status'))
            if action[0]=='test':return self.device.command(dict(action='test',operation='start',duration=action[1]))
            if action[0]=='calibration':return self.device.command(dict(action='calibration',operation='begin',seconds=action[1]))
            status=self.device.set_timezone(action[1])
            if action[0]=='time':status=self.device.command(dict(action='time',epoch=int(time.time())))
            return status
        def done(s):
            if action[0]=='scan':self.scan_results(s)
            else:
                self.render(s,True)
                if action[0]=='calibration':self.step=0;self.render_cal()
        self.run(work,done)
    def poll_job(self):
        job=self.device.job_state()
        if self.device.busy and job['state']!='running':return
        if job['state']=='running':self.log.setPlainText(job['log']);self.controls()
        elif job['state']=='reconnect':
            self.log.setPlainText(job['log']);self.notice.setText('Unplug all power for five seconds, reconnect, then restore clock firmware below.');self.connection.setText('Waiting for power cycle');self.controls()
        elif job['state'] in ['done','error'] and job['log']!=self.log.toPlainText():
            self.log.setPlainText(job['log']);self.notice.setText('Firmware installed. Refresh USB devices, then Connect.' if job['state']=='done' else 'Firmware installation failed. See the log.');self.controls()
            after=self.after_flash;self.after_flash=None
            if job['state']=='done':
                if after:self.resume_after_flash(after)
                else:self.refresh()
    def closeEvent(self,event):
        if self.working or self.device.busy:
            event.ignore();self.notice.setText('Wait for the current USB operation to finish before closing.');return
        if self.state and self.state.get('cal_active'):
            event.ignore()
            def done(_):self.state=None;self.device.close();self.close()
            self.command(dict(action='calibration',operation='cancel'),done);return
        self.device.close();event.accept()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test');args=parser.parse_args()
    application=QtWidgets.QApplication(sys.argv[:1]);application.setApplicationName('KN6UBF Clock Setup');application.setOrganizationName('KN6UBF')
    window=Window(auto_refresh=not bool(args.self_test))
    if args.self_test:
        assert (ROOT/'firmware/AmmeterClock/AmmeterClock.ino').is_file()
        result=run_cli([find_cli(),'version'],capture_output=True,text=True,check=True,timeout=30)
        updater=run_cli([find_uploader(__import__('app').BUNDLE,ROOT),'version'],capture_output=True,text=True,check=True,timeout=30)
        window.show();application.processEvents();assert window.connect_btn.text()=='Connect'
        Path(args.self_test).write_text(json.dumps(dict(frozen=bool(getattr(sys,'frozen',False)),cli=result.stdout.strip(),ui='native-qt',version=VERSION,wifi_updater=updater.stdout.strip())))
        window.close();return
    window.show();sys.exit(application.exec())
if __name__=='__main__':main()
