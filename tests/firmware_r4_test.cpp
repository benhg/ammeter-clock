#include <cassert>
#include <iostream>
#include "Arduino.h"
#include "Wire.h"
#include "EEPROM.h"
uint32_t fakeNow=0;int pins[4]={HIGH,HIGH,HIGH,HIGH};SerialMock Serial;WireMock Wire;EEPROMMock EEPROM;
#define ARDUINO_UNOR4_WIFI
#include "../firmware/AmmeterClock/AmmeterClock.ino"
void send(const std::string&s){Serial.output.clear();Serial.input=s+"\n";while(Serial.available())readCommands();}
int main(){
 setup();send("WIFI_SCAN");assert(WiFi.scannedDisconnected);assert(Serial.output.find("5465737420224e6574776f726b22")!=std::string::npos);assert(Serial.output.find("\"open\":true")!=std::string::npos);WiFi.scanCount=-1;send("WIFI_SCAN");assert(Serial.output=="ERR wifi_scan_failed\n");WiFi.scanCount=2;strcpy(settings.ssid,"test");send("TIME 1793215800");send("SECONDS 1");send("OUTPUT 1");
 auto writes=EEPROM.writes;auto epoch=utcEpoch;auto hour=settings.hourScale;auto minute=settings.minuteScale;
 // Slightly staggered physical press: grace period suppresses individual changes.
 pins[2]=LOW;loop();fakeNow+=40;loop();pins[3]=LOW;fakeNow+=60;loop();
 assert(chordTracking&&manualOverride);fakeNow+=2999;loop();assert(manualOverride);
 fakeNow+=1;loop();assert(!manualOverride&&ntpDue&&chordFired);
 assert(EEPROM.writes==writes&&settings.hourScale==hour&&settings.minuteScale==minute);
 assert(utcEpoch==epoch+3);pins[2]=HIGH;pins[3]=HIGH;fakeNow+=50;loop();
 fakeNow+=250;loop();assert(ntpWaiting&&udp.sends==1);
 // Accept a matching NTP reply and route the seconds fraction to DAC B.
 udp.incoming.assign(48,0);udp.incoming[0]=0x24;udp.incoming[1]=1;
 memcpy(udp.incoming.data()+24,ntpCookie,8);
 uint32_t expected=dateEpoch(2026,11,10)+12*3600+34*60+45;
 uint32_t n=expected+2208988800UL;
 for(int i=0;i<4;++i)udp.incoming[40+i]=(n>>(24-8*i))&255;
 fakeNow+=250;loop();assert(utcEpoch==expected&&!manualOverride&&!ntpWaiting);
 assert(std::string(timeSource)=="ntp");
 auto packet=Wire.writes.back();uint16_t code=((packet[2]&15)<<8)|packet[3];
 assert(packet[1]==0x42&&code==settings.secondScale*45/60);
 // Wizard suspends network; cancellation restores original network mode.
 send("CAL BEGIN 1");auto sends=udp.sends;fakeNow+=1000;loop();assert(udp.sends==sends);fakeNow+=600000;loop();
 assert(!calActive&&calExpired); // inactivity deadline zeros outputs, then network resumes
 assert(Wire.writes.back()[3]==0);
 assert(EEPROM.writes==writes);std::cout<<"PASS: R4 button chord, NTP reply, seconds DAC and calibration timeout\n";
}
