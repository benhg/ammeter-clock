#include <cassert>
#include <iostream>
#include "Arduino.h"
#include "Wire.h"
#include "EEPROM.h"
uint32_t fakeNow=0;int pins[4]={HIGH,HIGH,HIGH,HIGH};SerialMock Serial;WireMock Wire;EEPROMMock EEPROM;
#include "../firmware/AmmeterClock/AmmeterClock.ino"
void send(const std::string&s){Serial.output.clear();Serial.input=s+"\n";while(Serial.available())readCommands();}
int main(){
 setup();auto spring=dateEpoch(2026,3,8)+10*3600;auto fall=dateEpoch(2026,11,1)+9*3600;
 auto start=dateEpoch(2024,1,1),until=dateEpoch(2037,1,1);
 send("TZ BEGIN 416d65726963612f4c6f735f416e67656c6573 "+std::to_string(start)+" "+std::to_string(until)+" -480");assert(TimeZoneStore::pending>=0);
 send("TZ ADD "+std::to_string(spring)+" -420");send("TZ ADD "+std::to_string(fall)+" -480");send("TZ SAVE");assert(Serial.output=="OK {}\n");
 assert(clockLocalEpoch(spring-1)==spring-1-480*60);assert(clockLocalEpoch(spring)==spring-420*60);
 assert(clockLocalEpoch(fall-1)==fall-1-420*60);assert(clockLocalEpoch(fall)==fall-480*60);
 TimeZoneStore::load();assert(TimeZoneStore::active==0);assert(TimeZoneStore::current.count==2);
 auto writes=EEPROM.writes;for(int i=0;i<10;++i)clockLocalEpoch(spring+i);assert(EEPROM.writes==writes);
 // An interrupted replacement cannot invalidate the previous bank.
 send("TZ BEGIN 417369612f4b6174686d616e6475 "+std::to_string(start)+" "+std::to_string(until)+" 345");
 TimeZoneStore::load();assert(TimeZoneStore::active==0&&TimeZoneStore::offset(spring)==-420);
 send("TZ BEGIN 417369612f4b6174686d616e6475 "+std::to_string(start)+" "+std::to_string(until)+" 345");send("TZ SAVE");
 TimeZoneStore::load();assert(TimeZoneStore::active==1&&TimeZoneStore::offset(spring)==345);
 EEPROM.data[TimeZoneStore::address(1)+10]^=1;TimeZoneStore::load();assert(TimeZoneStore::active==0);
 send("TZ BEGIN 555443 5999034496 6102444800 0");assert(Serial.output=="ERR invalid_timezone_command\n");
 send("ZONE 345 0");TimeZoneStore::load();assert(TimeZoneStore::active==-1);assert(clockLocalEpoch(spring)==spring+345*60);
 std::cout<<"PASS: timezone transition boundaries, fractional offsets, persistence, CRC, interrupted updates and custom fallback\n";
}
