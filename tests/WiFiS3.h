#pragma once
#include <array>
struct IPAddress {
 std::array<unsigned char,4> octets{};
 IPAddress()=default;
 IPAddress(int a,int b,int c,int d):octets{(unsigned char)a,(unsigned char)b,(unsigned char)c,(unsigned char)d}{}
 bool operator==(const IPAddress& other)const{return octets==other.octets;}
};
constexpr int WL_IDLE_STATUS=0,WL_CONNECTED=3;
struct WiFiMock {
 int state=WL_CONNECTED;
 int status(){return state;}
 void setTimeout(int){}
 int begin(const char*,const char* = nullptr){return state;}
 void disconnect(){state=WL_IDLE_STATUS;}
};
inline WiFiMock WiFi;
inline void randomSeed(unsigned long){}
inline unsigned long micros(){return fakeNow*1000;}
inline long random(long lo,long){return lo;}
