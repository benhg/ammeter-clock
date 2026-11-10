'use strict';
// Exercise the real UI handlers against a transport fixture, without USB hardware.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const {calibrationScale}=require('../tools/clock_setup/calibration.js');
assert.equal(calibrationScale(4095,30,36),3413);
assert.equal(calibrationScale(3750,12,12.1),3719);
for(const reading of [0,-1,NaN,Infinity,.01])assert.throws(()=>calibrationScale(3750,12,reading));
const nodes={};const node=id=>nodes[id]??=( {id,value:'',checked:false,hidden:false,disabled:false,textContent:'',options:[],selectedOptions:[],dataset:{},classList:{toggle(){}},replaceChildren(){this.options=[];},add(o){this.options.push(o);this.selectedOptions=[o];this.value=o.value;}} );
const html=fs.readFileSync('tools/clock_setup/index.html','utf8');
for(const m of html.matchAll(/id="([^"]+)"/g))node(m[1]);
node('zone').options=[{value:'-480,1'}];node('wiz-size').value='25';
let state={board:'uno-r4-wifi',time_valid:true,local_epoch:1793215800,source:'ntp',manual_override:false,wifi_supported:true,wifi_connected:true,enabled:true,dac_ready:true,hour_scale:3719,minute_scale:3413,second_scale:3360,seconds_enabled:false,offset:-480,dst:1,test_active:false,cal_active:false};
let saved,commands=[];
async function fetch(url,opts){let s=JSON.parse(opts?.body||'{}');if(url==='/api/boards')return{ok:true,json:async()=>({boards:[]})};
 if(url==='/api/command'){
 commands.push(s);assert.equal(s.action,'calibration');
 if(s.operation==='begin'){saved={...state};Object.assign(state,{cal_active:true,draft_seconds_enabled:s.seconds,draft_hour:state.hour_scale,draft_minute:state.minute_scale,draft_second:state.second_scale,cal_hour:0,cal_minute:0,cal_second:0});}
 if(s.operation==='target')Object.assign(state,{cal_hour:s.hour,cal_minute:s.minute,cal_second:s.second,test_active:false});
 if(s.operation==='scale')Object.assign(state,{draft_hour:s.hour,draft_minute:s.minute,draft_second:s.second});
 if(s.operation==='sweep')state.test_active=true;
 if(s.operation==='cancel')state={...saved};
 if(s.operation==='save'){Object.assign(state,{hour_scale:state.draft_hour,minute_scale:state.draft_minute,second_scale:state.draft_second,seconds_enabled:state.draft_seconds_enabled,cal_active:false});}
 }return{ok:true,json:async()=>({...state})};}
const context=vm.createContext({document:{getElementById:node,querySelectorAll:()=>[],documentElement:{dataset:{}}},location:{hash:'#token',hostname:'localhost',pathname:'/'},history:{replaceState(){}},sessionStorage:{getItem(){},setItem(){}},fetch,setInterval(){},Option:function(text,value){this.value=value;this.dataset={};},Date,console,calibrationScale});
vm.runInContext(fs.readFileSync('tools/clock_setup/app.js','utf8'),context);
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 await tick();vm.runInContext('render('+JSON.stringify(state)+',true)',context);
 node('wiz-seconds').checked=true;await node('wiz-start').onclick();
 assert.equal(node('wiz-title').textContent,'Set the mechanical zero');assert.equal(state.cal_hour,0);
 await node('wiz-next').onclick();assert.equal(state.cal_hour,12);assert.equal(state.cal_minute,30);
 await node('wiz-lower').onclick();assert.equal(state.draft_hour,3694);assert.equal(state.hour_scale,3719);
 node('wiz-reading').value='12';await node('wiz-match').onclick();
 await node('wiz-next').onclick();assert.equal(node('wiz-title').textContent,'Calibrate minutes');
 await node('wiz-next').onclick();assert.equal(node('wiz-title').textContent,'Calibrate seconds');
 await node('wiz-higher').onclick();assert.equal(state.draft_second,3385);
 await node('wiz-next').onclick();assert.equal(node('wiz-title').textContent,'Check the dial at other points');
 node('hold-hour').value='9';node('hold-minute').value='47';node('hold-second').value='15';await node('wiz-hold').onclick();assert.equal(state.cal_second,15);
 await node('wiz-sweep').onclick();assert(state.test_active);await node('wiz-stop').onclick();assert(!state.test_active);assert.equal(state.cal_minute,47);
 await node('wiz-save').onclick();assert(!state.cal_active);assert.equal(state.hour_scale,3694);assert.equal(state.second_scale,3385);
 await node('wiz-start').onclick();await node('wiz-next').onclick();await node('wiz-higher').onclick();await node('wiz-cancel').onclick();assert.equal(state.hour_scale,3694);
 assert.equal(node('wizard').hidden,true);assert.equal(state.source,'ntp');
 console.log('PASS: wizard zero, reference, adjustments, optional seconds, fixed tests, sweep, save and cancel');
})().catch(e=>{console.error(e);process.exitCode=1;});
