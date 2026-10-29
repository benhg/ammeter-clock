#include <cassert>
#include <iostream>
#include "Arduino.h"
#include "Wire.h"
#include "EEPROM.h"
uint32_t fakeNow = 0;
int pins[4] = {HIGH,HIGH,HIGH,HIGH};
SerialMock Serial;
WireMock Wire;
EEPROMMock EEPROM;
#include "../firmware/AmmeterClock/AmmeterClock.ino"
void send(const std::string &s) {
  Serial.output.clear(); Serial.input = s+"\n";
  while (Serial.available()) readCommands();
}
int main() {
  setup(); assert(dacReady && !settings.enabled && !timeValid);
  for (int i=0;i<4;++i) assert(Wire.writes[i][1] == 0x40+i*2);
  send("OUTPUT 1"); assert(Serial.output == "ERR set_time_first\n");
  send("ZONE -480 1"); assert(settings.offsetMinutes == -480 && settings.dst == 1);
  send("TIME 1793215800"); assert(timeValid && manualOverride);
  send("STATUS"); assert(Serial.output.find("\"manual_override\":true")!=std::string::npos);
  send("SCALE 3750 4095"); send("OUTPUT 1"); assert(settings.enabled);
  // 2026-01-01 20:30 UTC = 12:30 Pacific standard time.
  setClock(dateEpoch(2026,1,1)+20*3600+30*60,"usb");
  auto packet = [](uint8_t c,uint16_t code){return std::vector<uint8_t>{0x60,uint8_t(0x40|(c<<1)),uint8_t(0x90|(code>>8)),uint8_t(code)};};
  assert(Wire.writes[Wire.writes.size()-2] == packet(3,3750));
  assert(Wire.writes.back() == packet(2,2047));
  unsigned writes = EEPROM.writes;
  fakeNow += 61000; loop(); assert(utcEpoch == dateEpoch(2026,1,1)+20*3600+31*60+1);
  assert(EEPROM.writes == writes); // no flash wear from clock ticks
  // Bounce rejected, initial press accepted, hold repeat and release.
  pins[2]=LOW; loop(); fakeNow+=10; loop(); assert(!hourButton.stable);
  fakeNow+=21; loop(); assert(hourButton.stable && manualOverride && !strcmp(timeSource,"buttons"));
  uint32_t t = utcEpoch;
  fakeNow+=799; loop(); assert(utcEpoch == t);
  fakeNow+=1; loop(); assert(utcEpoch == t+3600);
  pins[2]=HIGH; loop(); fakeNow+=31; loop(); assert(!hourButton.stable);
  // Rollover preserves fractional seconds.
  lastTick=UINT32_MAX-499; fakeNow=500; t=utcEpoch; loop(); assert(utcEpoch==t+1);
  // Invalid input cannot silently change saved settings.
  send("SCALE 4096 20"); assert(settings.hourScale==3750 && Serial.output.find("ERR ")==0);
  send("TIME 42949672960"); assert(Serial.output.find("ERR ")==0);
  send("ZONE -900 0"); assert(settings.offsetMinutes==-480);
  send("TIME 1793215800 extra"); assert(Serial.output.find("ERR ")==0);
  send("SYNC"); assert(Serial.output=="ERR wifi_not_supported\n");
  send(std::string(300,'X')); assert(Serial.output=="ERR line_too_long\n");
  send("STATUS"); assert(Serial.output.find("OK {")==0);
  // Persisted config survives reload, corrupt or incomplete writes are rejected.
  Settings saved; EEPROM.get(0,saved); assert(valid(saved));
  saved.password[0]='X'; assert(!valid(saved));
  EEPROM.data[0]=0; EEPROM.get(0,saved); assert(!valid(saved));
  // Failed writes latch outputs off, including future updates.
  Wire.failingAddress=DAC_ADDRESS; updateGauges(); assert(!dacReady);
  size_t n=Wire.writes.size(); updateGauges(); assert(Wire.writes.size()==n);
  // US DST exact transition boundaries (Pacific).
  Settings s=defaults(); s.offsetMinutes=-480; s.dst=1;
  uint32_t spring=dateEpoch(2026,3,8)+10*3600;
  assert(!summerTime(spring-1,s) && summerTime(spring,s));
  uint32_t fall=dateEpoch(2026,11,1)+9*3600;
  assert(summerTime(fall-1,s) && !summerTime(fall,s));
  s.offsetMinutes=60;s.dst=2;
  assert(!summerTime(dateEpoch(2026,3,29)+3599,s));
  assert(summerTime(dateEpoch(2026,3,29)+3600,s));
  assert(!summerTime(dateEpoch(2026,10,25)+3600,s));
  assert(yearOf(dateEpoch(2099,12,31))==2099);
  uint8_t reply[48] = {}, cookie[8] = {1,2,3,4,5,6,7,8};
  reply[0]=0x24; reply[1]=2; memcpy(reply+24,cookie,8);
  uint32_t expected=dateEpoch(2040,1,1), ntp=expected+2208988800UL, received=0;
  for(int i=0;i<4;++i) reply[40+i]=uint8_t(ntp>>(24-8*i));
  assert(ntpReply(reply,48,cookie,received) && received==expected);
  reply[24]^=1; assert(!ntpReply(reply,48,cookie,received)); reply[24]^=1;
  reply[0]=0xe4; assert(!ntpReply(reply,48,cookie,received)); reply[0]=0x24;
  reply[1]=0; assert(!ntpReply(reply,48,cookie,received)); reply[1]=2;
  assert(!ntpReply(reply,0,cookie,received));
  char text[8];assert(decodeHex("41422043",text,sizeof(text)) && !strcmp(text,"AB C"));
  assert(!decodeHex("00",text,sizeof(text)) && !decodeHex("gg",text,sizeof(text)));
  assert(!decodeHex("4142434445464748",text,sizeof(text)));
  std::cout << "PASS: firmware commands, DAC mapping, timing, buttons, persistence, rollover, DST, and faults\n";
}
