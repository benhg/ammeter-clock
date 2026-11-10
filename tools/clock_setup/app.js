'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('clock-token') || '';
if(token) sessionStorage.setItem('clock-token',token);
history.replaceState(null, '', location.pathname);
const webMode=document.documentElement.dataset.mode==='web'||(!['127.0.0.1','localhost'].includes(location.hostname));
const usb=webMode?new ClockUSB(navigator.serial):null;
let wizardStep=null;
let connected = false, status = null, busy = false, pollBusy = false, flashing = false;
const notice = (text, error=false) => { $('notice').textContent=text; $('notice').classList.toggle('error',error); };
async function api(path, body) {
  if(webMode)return usb.api(path,body);
  const options = {headers:{'X-Clock-Token':token}};
  if(body!==undefined){ options.method='POST'; options.headers['Content-Type']='application/json'; options.body=JSON.stringify(body); }
  const response=await fetch('/api/'+path,options);
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function controls(){
  document.querySelectorAll('[data-connected]').forEach(e=>e.disabled=!connected||busy||flashing);
  document.querySelectorAll('[data-wifi]').forEach(e=>e.disabled=!connected||!status?.wifi_supported||busy||flashing);
  for(const id of ['connect','flash','refresh','board','port']) $(id).disabled=busy||flashing;
  $('disconnect').disabled=!connected||busy||flashing;
  if(webMode){$('flash').hidden=true;$('quit').hidden=true;}
  $('test-start').disabled=!connected||busy||flashing||!status?.enabled||!status?.dac_ready||!('test_active' in (status||{}))||status?.test_active;
  $('test-stop').disabled=!connected||busy||flashing||!status?.test_active;
  $('wiz-start').disabled=!connected||busy||flashing||!status?.dac_ready||!('cal_active' in (status||{}))||status?.cal_active;
  $('wiz-seconds').disabled=!connected||busy||flashing||status?.cal_active;
  if(status?.cal_active){
    document.querySelectorAll('section:not(:has(#wizard)) [data-connected], section:not(:has(#wizard)) [data-wifi], #advanced-calibration [data-connected]').forEach(e=>e.disabled=true);
    $('flash').disabled=true;
  }
  $('password').disabled=!connected||!status?.wifi_supported||busy||flashing||$('open-network').checked||status?.cal_active;
}
function render(s, loadFields=false){
  status=s; connected=true;
  $('clock').textContent=s.time_valid ? new Date(s.local_epoch*1000).toISOString().slice(11,19) : '— : — : —';
  $('source').textContent= s.time_valid ? `${s.board} · ${s.source==='ntp'?'NTP synchronized':s.source==='buttons'?'Set with buttons':'Set from computer'}${s.manual_override?' · NTP paused until restart':''}` : `${s.board} · waiting for time`;
  $('wifi-state').textContent=!s.wifi_supported?'Uno R3 has no onboard Wi-Fi. Use computer time or the buttons.':s.wifi_connected?'Connected to Wi-Fi. '+(s.manual_override?'NTP is paused.':s.source==='ntp'?'NTP has set the clock.':'Waiting for an NTP reply.') : s.wifi_configured?'Network saved; waiting for Wi-Fi connection.':'No network configured.';
  $('output-state').textContent=!s.dac_ready?'DAC is not responding. Outputs cannot be verified; check hardware and restart.':s.enabled?(s.time_valid?'Meters enabled.':'Meters enabled in settings, held at zero until time is set.'):'Meters disabled; zero output requested.';
  if(s.test_active)$('output-state').textContent=`Test pattern: hours ${s.test_hour}/12 · minutes ${s.test_minute}/60${s.seconds_enabled?` · seconds ${s.test_minute}/60`:""}. Returns to the current time automatically.`;
  $('test-hint').textContent=('test_active' in s)?'With meters enabled, sweep hours 0–12 and minutes 0–60 over 61 seconds, then return to the current time. Calibration and saved time are unchanged. Either physical button also stops the test.':'Flash firmware 0.2.2 or newer to use the test pattern.';
  if(s.cal_timeout)notice('Calibration timed out. Outputs are held at zero; start again or enable meters to resume.',true);
  wizardRender(s);
  if(loadFields){
    $('wiz-seconds').checked=Boolean(s.seconds_enabled);
    $('hour-scale').value=s.hour_scale; $('minute-scale').value=s.minute_scale;
    const value=`${s.offset},${s.dst}`;
    $('zone').value=Array.from($('zone').options).some(o=>o.value===value)?value:'custom';
    $('offset').value=s.offset; $('dst').value=s.dst; zoneChanged();
  }
  controls();
}
async function run(task,message){
  if(busy||flashing)return;
  busy=true; controls();
  try{await task(); if(message)notice(message);}catch(e){notice(e.message,true);}finally{busy=false;controls();}
}
async function refresh(){
  const previous=$('port').value, {boards}=await api('boards'); $('port').replaceChildren();
  if(!boards.length) $('port').add(new Option('No serial devices found',''));
  for(const b of boards){ const option=new Option(`${b.name} · ${b.port}`,b.port);option.dataset.board=b.board||'';$('port').add(option); }
  if(boards.some(b=>b.port===previous))$('port').value=previous;
  else {const supported=boards.find(b=>b.board);if(supported)$('port').value=supported.port;}
  selectBoard();
}
function selectBoard(){const board=$('port').selectedOptions[0]?.dataset.board;if(board)$('board').value=board;}
function zoneChanged(){$('custom-zone').hidden=$('zone').value!=='custom';}
function zoneData(){const [offset,dst]=$('zone').value==='custom'?[Number($('offset').value),Number($('dst').value)]:$('zone').value.split(',').map(Number);return {action:'zone',offset,dst};}
async function command(data, load=false){const s=await api('command',data);render(s,load);return s;}
$('refresh').onclick=()=>run(refresh,'USB device list refreshed.');
$('port').onchange=selectBoard; $('zone').onchange=zoneChanged; $('open-network').onchange=controls;
$('connect').onclick=()=>run(async()=>render(await api('connect',{port:$('port').value}),true),'Connected.');
$('disconnect').onclick=()=>run(async()=>{if(status?.cal_active)await cal('cancel');await api('disconnect',{});connected=false;status=null;$('source').textContent='Disconnected';},'Disconnected.');
$('save-zone').onclick=()=>run(()=>command(zoneData()),'Timezone saved.');
$('set-time').onclick=()=>run(async()=>{await command(zoneData());await command({action:'time',epoch:Math.floor(Date.now()/1000)});},'Clock set from this computer. NTP is paused until restart or Resume NTP.');
$('sync').onclick=()=>run(()=>command({action:'sync'}),'NTP resumed. The clock will sync when Wi-Fi is connected.');
$('wifi-form').onsubmit=e=>{e.preventDefault();run(async()=>{await command({action:'wifi',ssid:$('ssid').value,password:$('open-network').checked?'':$('password').value});$('password').value='';},'Wi-Fi settings saved on the Arduino. Connecting may take a minute.');};
$('clear-wifi').onclick=()=>run(async()=>{await command({action:'wifi_clear'});$('ssid').value='';$('password').value='';},'Network credentials erased from the clock configuration.');
$('save-scale').onclick=()=>run(()=>command({action:'scale',hour:Number($('hour-scale').value),minute:Number($('minute-scale').value)}),'Calibration saved.');
$('enable').onclick=()=>{if(!$('calibrated').checked){notice('Check the meter wiring, ratings, and calibration before enabling.',true);return;}run(()=>command({action:'output',enabled:true}),'Meter outputs enabled.');};
$('disable').onclick=()=>run(()=>command({action:'output',enabled:false}),'Meter outputs disabled.');
$('flash').onclick=()=>run(async()=>{
  if(!confirm('Replace the Arduino sketch with the clock firmware? Remove any temporary J3 short first.'))return;
  await api('flash',{port:$('port').value,board:$('board').value});flashing=true;connected=false;status=null;notice('Building and uploading firmware…');
  const timer=setInterval(async()=>{try{const job=await api('job');$('log').textContent=job.log;if(job.state!=='running'){clearInterval(timer);flashing=false;controls();notice(job.state==='done'?'Firmware uploaded. Refresh ports, then connect.':'Upload failed; open the firmware log.',job.state!=='done');await refresh();}}catch(e){clearInterval(timer);flashing=false;controls();notice(e.message,true);}},1000);
});
setInterval(async()=>{if(!connected||busy||flashing||pollBusy)return;pollBusy=true;try{render(await api('command',{action:'status'}));}catch(e){connected=false;controls();notice(e.message,true);}finally{pollBusy=false;}},2500);
controls();
if(webMode){
  $('desktop-downloads').hidden=false;
  $('flash-hint').textContent='Already flashed? Connect here to set time, Wi-Fi, and calibration directly over USB. To install firmware, download the desktop app below.';
  if(!navigator.serial)notice('This browser does not support USB serial. Open this page in desktop Chrome or Edge, or download the app below.',true);
  else notice('Connect your clock with a USB data cable, then click Connect and choose its USB device.');
  run(refresh);
}else if(!token)notice('Open the complete URL printed by the setup launcher, including its # token.',true);
else run(refresh);

$('quit').onclick=()=>run(async()=>{if(status?.cal_active)await cal('cancel');await api('quit',{});connected=false;$('quit').disabled=true;},'Setup app closed. You can close this browser tab.');

$('test-start').onclick=()=>run(()=>command({action:'test',operation:'start'}),'Test pattern running. It will return to the current time automatically.');
$('test-stop').onclick=()=>run(()=>command({action:'test',operation:'stop'}),'Test stopped. Current time restored.');

function wizardSteps(s){return s.draft_seconds_enabled?['zero','hour','minute','second','verify']:['zero','hour','minute','verify'];}
function wizardRender(s){
  const supported='cal_active' in s;
  $('wiz-availability').textContent=supported?'The wizard supports both Rev 1 and Rev 2 meters. Use the original 0–100 µA scale at its 0–60 marks, or a calibrated replacement dial.':'Flash firmware 0.3.0 or newer for guided calibration.';
  $('wizard').hidden=!s.cal_active;
  if(!s.cal_active){wizardStep=null;return;}
  if(!wizardStep)wizardStep='verify'; // reconnect resumes review, never changes the held reference
  const steps=wizardSteps(s),index=steps.indexOf(wizardStep);
  $('wiz-progress').textContent=`Step ${index+1} of ${steps.length}`;
  const titles={zero:'Set the mechanical zero',hour:'Calibrate hours',minute:'Calibrate minutes',second:'Calibrate seconds',verify:'Check the dial at other points'};
  $('wiz-title').textContent=titles[wizardStep];
  $('wiz-instructions').textContent=wizardStep==='zero'?'All meter outputs are at zero. Gently adjust each meter’s mechanical zero screw until its needle rests exactly on 0. Do this before correcting the electrical scale.':wizardStep==='verify'?'Check several points, then save when the needles look right. The clock will return to live time with its previous NTP/manual mode.':`The reference is held at 12:30${s.draft_seconds_enabled?':30':''}. Adjust only the ${wizardStep} needle until it matches the reference mark. Use Coarse for large changes and Fine near the mark.`;
  const adjustment=['hour','minute','second'].includes(wizardStep);
  $('wiz-adjust').hidden=!adjustment;$('wiz-verify').hidden=wizardStep!=='verify';
  $('wiz-reference').textContent=`${wizardStep==='hour'?'Hour needle → 12':wizardStep==='second'?'Second needle → 30':'Minute needle → 30'}`;
  $('hold-second-label').hidden=!s.draft_seconds_enabled;
  $('wiz-back').hidden=index===0;$('wiz-next').hidden=wizardStep==='verify';$('wiz-save').hidden=wizardStep!=='verify';
  $('wiz-next').textContent=wizardStep==='zero'?'Zero adjusted · Next':'Needle is correct · Next';
  $('wiz-test-state').textContent=s.test_active?`Sweeping: ${s.test_hour} hours / ${s.test_minute} minutes${s.draft_seconds_enabled?' / '+s.test_minute+' seconds':''}. It returns to the held values automatically.`:`Holding ${s.cal_hour} / ${s.cal_minute}${s.draft_seconds_enabled?' / '+s.cal_second:''}.`;
}
async function cal(operation,values={}){return command({action:'calibration',operation,...values});}
async function wizardGo(step){
  await cal('target',step==='zero'?{hour:0,minute:0,second:0}:step==='verify'?{hour:6,minute:15,second:45}:{hour:12,minute:30,second:30});
  wizardStep=step;$('wiz-reading').value='';wizardRender(status);
}
$('wiz-start').onclick=()=>run(async()=>{wizardStep='zero';await cal('begin',{seconds:$('wiz-seconds').checked});},'Calibration started. All outputs are held at zero.');
$('wiz-next').onclick=()=>run(async()=>{const steps=wizardSteps(status);await wizardGo(steps[steps.indexOf(wizardStep)+1]);});
$('wiz-back').onclick=()=>run(async()=>{const steps=wizardSteps(status);await wizardGo(steps[steps.indexOf(wizardStep)-1]);});
async function wizardAdjust(direction){
  const field='draft_'+wizardStep;
  const value=status[field]+direction*Number($('wiz-size').value);
  if(value<1||value>4095)throw new Error('Adjustment limit reached. Check the meter rating and wiring.');
  const values={hour:status.draft_hour,minute:status.draft_minute,second:status.draft_second};values[wizardStep]=value;await cal('scale',values);
}
$('wiz-lower').onclick=()=>run(()=>wizardAdjust(-1));$('wiz-higher').onclick=()=>run(()=>wizardAdjust(1));
$('wiz-match').onclick=()=>run(async()=>{
  const values={hour:status.draft_hour,minute:status.draft_minute,second:status.draft_second};
  values[wizardStep]=calibrationScale(values[wizardStep],wizardStep==='hour'?12:30,Number($('wiz-reading').value));await cal('scale',values);
});
$('wiz-hold').onclick=()=>run(()=>cal('target',{hour:Number($('hold-hour').value),minute:Number($('hold-minute').value),second:status.draft_seconds_enabled?Number($('hold-second').value):0}));
$('wiz-sweep').onclick=()=>run(()=>cal('sweep'),'Sweep running; the held reference returns automatically.');
$('wiz-stop').onclick=()=>run(()=>cal('target',{hour:status.cal_hour,minute:status.cal_minute,second:status.cal_second}));
$('wiz-cancel').onclick=()=>run(()=>cal('cancel'),'Calibration cancelled. Previous settings restored.');
$('wiz-save').onclick=()=>run(()=>cal('save'),'Calibration saved. Clock outputs enabled; live time restored.');
