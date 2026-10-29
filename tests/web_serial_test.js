'use strict';
const assert=require('node:assert/strict');
const ClockUSB=require('../tools/clock_setup/web_serial.js');
(async()=>{
  assert.equal(ClockUSB.command({action:'wifi',ssid:'A B',password:'abc defg'}),'WIFI 412042 6162632064656667');
  assert.throws(()=>ClockUSB.command({action:'wifi',ssid:'x',password:'short'}));
  assert.throws(()=>ClockUSB.command({action:'wifi',ssid:'é'.repeat(17),password:'12345678'}));
  assert.throws(()=>ClockUSB.command({action:'scale',hour:4096,minute:4095}));
  assert.throws(()=>ClockUSB.command({action:'output',enabled:'true'}));
  assert.equal(ClockUSB.command({action:'zone',offset:-480,dst:1}),'ZONE -480 1');
  assert.equal(ClockUSB.command({action:'test',operation:'start'}),'TEST START');
  assert.throws(()=>ClockUSB.command({action:'test',operation:'restart'}));
  let deliver, writes=[], released=0, closed=0;
  const port={
    getInfo:()=>({usbVendorId:0x2341,usbProductId:0x1002}),
    open:async()=>{},setSignals:async()=>{},close:async()=>{closed++;},
    readable:{getReader:()=>({read:()=>new Promise(resolve=>{deliver=resolve;}),cancel:async()=>deliver({done:true}),releaseLock:()=>{released++;}})},
    writable:{getWriter:()=>({write:async bytes=>{
      const text=new TextDecoder().decode(bytes); writes.push(text);
      queueMicrotask(()=>deliver({value:new TextEncoder().encode(text==='STATUS\n'?'noise\nOK {"protocol":1,"enabled":false}\n':'OK {}\n'),done:false}));
    },releaseLock:()=>{released++;}})}
  };
  const usb=new ClockUSB({getPorts:async()=>[port],requestPort:async()=>port});
  const boards=await usb.boards();assert.equal(boards.boards[1].board,'uno-r4-wifi');
  const status=await usb.connect('choose');assert.equal(status.protocol,1);
  await Promise.all([usb.request('TIME 1793215800'),usb.request('STATUS')]);
  assert.deepEqual(writes,['STATUS\n','TIME 1793215800\n','STATUS\n']);
  await usb.close();assert.equal(released,2);assert.equal(closed,1);
  assert.equal(usb.port,null);
  console.log('PASS: Web Serial encoding, validation, chooser, framing, request serialization, and close');
})().catch(error=>{console.error(error);process.exitCode=1;});
