#pragma once
#include <vector>
#include <cstring>
struct WiFiUDP {
 std::vector<unsigned char> incoming,outgoing;
 IPAddress remote{162,159,200,1};int port=123,sends=0;
 int begin(int){return 1;}
 void stop(){incoming.clear();}
 int parsePacket(){return incoming.size();}
 int read(unsigned char* dst,size_t n){n=std::min(n,incoming.size());memcpy(dst,incoming.data(),n);incoming.clear();return n;}
 int remotePort(){return port;}
 IPAddress remoteIP(){return remote;}
 int beginPacket(IPAddress,int){outgoing.clear();return 1;}
 void write(unsigned char* data,size_t n){outgoing.assign(data,data+n);}
 int endPacket(){++sends;return 1;}
};
