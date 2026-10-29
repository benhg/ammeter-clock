'use strict';
// USB transport for the static Pages UI. Credentials never leave this browser's USB port.
class ClockUSB {
  constructor(serial) { this.serial=serial; this.ports=[]; this.port=null; this.pending=null; this.buffer=''; this.queue=Promise.resolve(); }
  async boards() {
    if(!this.serial) return {boards:[]};
    this.ports=await this.serial.getPorts();
    return {boards:[{port:'choose',name:'Choose a USB device…',board:null},...this.ports.map((p,i)=>{
      const info=p.getInfo();
      const board=info.usbVendorId===0x2341 && [0x0069,0x1002].includes(info.usbProductId)?'uno-r4-wifi':null;
      return {port:String(i),name:board?'Uno R4 WiFi (authorized USB device)':'Authorized USB device '+(i+1),board};
    })]};
  }
  async connect(id) {
    if(!this.serial) throw new Error('Use Chrome or Edge on a desktop, or download the app below.');
    // The chooser must be invoked before any await, while the click gesture is active.
    const selection=id==='choose'||!id?this.serial.requestPort():Promise.resolve(this.ports[Number(id)]);
    const port=await selection;
    if(!port) throw new Error('Choose a USB device.');
    await this.close();
    try {
      await port.open({baudRate:115200}); this.port=port;
      await port.setSignals({dataTerminalReady:true});
      this.writer=port.writable.getWriter(); this.reader=port.readable.getReader();
      this.readTask=this.readLoop();
      await new Promise(resolve=>setTimeout(resolve,2500)); // R3 DTR reset
      const status=await this.request('STATUS');
      if(status.protocol!==1) throw new Error('Flash the clock firmware using the downloaded app first.');
      return status;
    } catch(error) { await this.close(); throw error; }
  }
  async readLoop() {
    const decoder=new TextDecoder();
    try {
      while(true) {
        const {value,done}=await this.reader.read(); if(done) break;
        this.buffer+=decoder.decode(value,{stream:true});
        if(this.buffer.length>8192) throw new Error('Unexpected USB response; reconnect.');
        let newline;
        while((newline=this.buffer.indexOf('\n'))>=0) {
          const line=this.buffer.slice(0,newline).trim(); this.buffer=this.buffer.slice(newline+1);
          if(!this.pending) continue;
          if(line.startsWith('OK ')) {
            const pending=this.pending; this.pending=null;
            try {pending.resolve(JSON.parse(line.slice(3)));} catch(_) {pending.reject(new Error('Invalid clock response.'));}
          } else if(line.startsWith('ERR ')) {const pending=this.pending;this.pending=null;pending.reject(new Error('Clock rejected request: '+line.slice(4)));}
        }
      }
    } catch(error) {if(this.pending){this.pending.reject(new Error('USB connection lost. Reconnect the clock.'));this.pending=null;}}
    finally {this.reader.releaseLock(); if(this.pending){this.pending.reject(new Error('USB connection closed.'));this.pending=null;}}
  }
  request(command) {
    const operation=async()=>{
      if(!this.port||!this.writer) throw new Error('Connect to the clock first.');
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{
          if(this.pending?.resolve===success){this.pending=null;reject(new Error('No clock response. Use the downloaded app to flash the firmware, then reconnect.'));this.close().catch(()=>{});}
        },15000);
        const success=result=>{clearTimeout(timer);resolve(result);};
        const failure=error=>{clearTimeout(timer);reject(error);};
        this.pending={resolve:success,reject:failure};
        this.writer.write(new TextEncoder().encode(command+'\n')).catch(error=>{this.pending=null;failure(error);});
      });
    };
    const result=this.queue.then(operation); this.queue=result.catch(()=>{}); return result;
  }
  async close() {
    if(this.pending){this.pending.reject(new Error('Disconnected.'));this.pending=null;}
    if(this.reader){try{await this.reader.cancel();}catch(_){} await this.readTask;this.reader=null;}
    if(this.writer){this.writer.releaseLock();this.writer=null;}
    if(this.port){try{await this.port.close();}catch(_){}this.port=null;}
    this.buffer='';
  }
  static hex(value,max,empty=true) {
    const bytes=new TextEncoder().encode(value);
    if(bytes.length>max||(!empty&&!bytes.length)||bytes.some(c=>c<32||c===127))throw new Error('Invalid credential length or control character.');
    return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('')||'-';
  }
  static command(data) {
    const number=(key,min,max)=>{const n=data[key];if(!Number.isInteger(n)||n<min||n>max)throw new Error('Invalid '+key);return n;};
    switch(data.action){
      case 'status':return 'STATUS';
      case 'time':return 'TIME '+number('epoch',1704067200,4102444799);
      case 'zone':return `ZONE ${number('offset',-720,840)} ${number('dst',0,2)}`;
      case 'scale':return `SCALE ${number('hour',1,4095)} ${number('minute',1,4095)}`;
      case 'output':if(typeof data.enabled!=='boolean')throw new Error('Invalid output setting');return 'OUTPUT '+Number(data.enabled);
      case 'wifi':{
        const password=data.password, length=new TextEncoder().encode(password).length;
        if(length&&length<8)throw new Error('Password must be at least 8 bytes or empty for an open network.');
        if(length===64&&!/^[0-9a-fA-F]{64}$/.test(password))throw new Error('A 64-byte key must be hexadecimal.');
        return `WIFI ${this.hex(data.ssid,32,false)} ${this.hex(password,64)}`;
      }
      case 'wifi_clear':return 'WIFI_CLEAR';
      case 'sync':return 'SYNC';
      default:throw new Error('Unknown clock action.');
    }
  }
  async api(path,data){
    if(path==='boards')return this.boards();
    if(path==='connect')return this.connect(data.port);
    if(path==='disconnect'){await this.close();return {};}
    if(path==='command'){const command=ClockUSB.command(data);if(command!=='STATUS')await this.request(command);return this.request('STATUS');}
    throw new Error('Firmware flashing is available in the downloaded desktop app.');
  }
}
if(typeof module!=='undefined')module.exports=ClockUSB;
