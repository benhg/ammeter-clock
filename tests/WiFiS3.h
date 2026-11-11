#pragma once
#include <array>
struct IPAddress {
 std::array<unsigned char,4> octets{};
 IPAddress()=default;
 IPAddress(int a,int b,int c,int d):octets{(unsigned char)a,(unsigned char)b,(unsigned char)c,(unsigned char)d}{}
 bool operator==(const IPAddress& other)const{return octets==other.octets;}
};
constexpr int WL_IDLE_STATUS=0,WL_CONNECTED=3;
constexpr int ENC_TYPE_NONE=5;
struct WiFiMock {
 int scanCount=2,disconnects=0;bool scannedDisconnected=false;
 int scanNetworks(){scannedDisconnected=state!=WL_CONNECTED;return scanCount;}
 const char* SSID(int i){return i==0?"Test \"Network\"":"Open network";}
 int RSSI(int i){return -40-i*20;}
 int encryptionType(int i){return i?ENC_TYPE_NONE:2;}
 int state=WL_CONNECTED;
 int status(){return state;}
 void setTimeout(int){}
 int begin(const char*,const char* = nullptr){return state=WL_CONNECTED;}
 void disconnect(){++disconnects;state=WL_IDLE_STATUS;}
};
inline WiFiMock WiFi;
inline void randomSeed(unsigned long){}
inline unsigned long micros(){return fakeNow*1000;}
inline long random(long lo,long){return lo;}
