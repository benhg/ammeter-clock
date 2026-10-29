'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('clock-token') || '';
if(token) sessionStorage.setItem('clock-token',token);
history.replaceState(null, '', '/');
let connected = false, status = null, busy = false, pollBusy = false, flashing = false;
const notice = (text, error=false) => { $('notice').textContent=text; $('notice').classList.toggle('error',error); };
async function api(path, body) {
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
  $('password').disabled=!connected||!status?.wifi_supported||busy||flashing||$('open-network').checked;
}
function render(s, loadFields=false){
  status=s; connected=true;
  $('clock').textContent=s.time_valid ? new Date(s.local_epoch*1000).toISOString().slice(11,19) : '— : — : —';
  $('source').textContent= s.time_valid ? `${s.board} · ${s.source==='ntp'?'NTP synchronized':s.source==='buttons'?'Set with buttons':'Set from computer'}${s.manual_override?' · NTP paused until restart':''}` : `${s.board} · waiting for time`;
  $('wifi-state').textContent=!s.wifi_supported?'Uno R3 has no onboard Wi-Fi. Use computer time or the buttons.':s.wifi_connected?'Connected to Wi-Fi. '+(s.manual_override?'NTP is paused.':s.source==='ntp'?'NTP has set the clock.':'Waiting for an NTP reply.') : s.wifi_configured?'Network saved; waiting for Wi-Fi connection.':'No network configured.';
  $('output-state').textContent=!s.dac_ready?'DAC is not responding. Outputs cannot be verified; check hardware and restart.':s.enabled?(s.time_valid?'Meters enabled.':'Meters enabled in settings, held at zero until time is set.'):'Meters disabled; zero output requested.';
  if(loadFields){
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
$('disconnect').onclick=()=>run(async()=>{await api('disconnect',{});connected=false;status=null;$('source').textContent='Disconnected';},'Disconnected.');
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
if(!token)notice('Open the complete URL printed by the setup launcher, including its # token.',true);
else run(refresh);
