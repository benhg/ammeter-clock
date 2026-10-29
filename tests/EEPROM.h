#pragma once
#include <cstring>
struct EEPROMMock {
  unsigned char data[1024] = {};
  unsigned writes = 0;
  template<typename T> void get(int address, T &value) { memcpy(&value,data+address,sizeof(T)); }
  void update(int address, unsigned char value) { if(data[address]!=value) {data[address]=value; ++writes;} }
};
extern EEPROMMock EEPROM;
