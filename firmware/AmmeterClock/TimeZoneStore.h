#pragma once
// Two CRC-protected EEPROM banks preserve the previous zone during an update.
// No transition table is held in SRAM, keeping Uno R3 compatible.
namespace TimeZoneStore {
constexpr int BASE=176,BANK_SIZE=424,MAX_CHANGES=56;
constexpr uint32_t MAGIC=0x545A4331UL;
struct __attribute__((packed)) Header {
 uint32_t magic,sequence,from,until;int16_t offset;uint8_t count;char name[64];uint16_t crc;
};
struct __attribute__((packed)) Change {uint32_t epoch;int16_t offset;};
static_assert(sizeof(Header)+MAX_CHANGES*sizeof(Change)<=BANK_SIZE,"Zone bank overflow");
static_assert(BASE+2*BANK_SIZE<=1024,"Uno R3 EEPROM overflow");
Header current={},draft={};int8_t active=-1,pending=-1;
inline int address(int bank){return BASE+bank*BANK_SIZE;}
inline void crcByte(uint16_t&crc,uint8_t b){crc^=uint16_t(b)<<8;for(uint8_t i=0;i<8;++i)crc=(crc&0x8000)?(crc<<1)^0x1021:crc<<1;}
inline uint16_t checksum(const Header&h,int bank){
 uint16_t crc=0xffff;const uint8_t*p=reinterpret_cast<const uint8_t*>(&h);
 for(size_t i=4;i<offsetof(Header,crc);++i)crcByte(crc,p[i]);
 for(int i=0;i<h.count*int(sizeof(Change));++i){uint8_t v;EEPROM.get(address(bank)+sizeof(Header)+i,v);crcByte(crc,v);}
 return crc;
}
inline bool nameValid(const char*s){
 if(!s[0]||s[63])return false;
 for(uint8_t i=0;s[i];++i){char c=s[i];if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='/'||c=='_'||c=='-'||c=='+'||c=='.'))return false;}
 return true;
}
inline bool valid(const Header&h,int bank){
 if(h.magic!=MAGIC||h.count>MAX_CHANGES||!nameValid(h.name)||h.from<ClockCore::MIN_EPOCH||h.until>ClockCore::MAX_EPOCH||h.until<=h.from||h.offset < -720||h.offset>840)return false;
 uint32_t last=h.from;
 for(uint8_t i=0;i<h.count;++i){Change c;EEPROM.get(address(bank)+sizeof(Header)+i*sizeof(Change),c);if(c.epoch<=last||c.epoch>=h.until||c.offset < -720||c.offset>840)return false;last=c.epoch;}
 return h.crc==checksum(h,bank);
}
inline void load(){
 active=pending=-1;current={};
 for(uint8_t bank=0;bank<2;++bank){Header h;EEPROM.get(address(bank),h);if(valid(h,bank)&&(active<0||int32_t(h.sequence-current.sequence)>0)){current=h;active=bank;}}
}
inline void clear(){for(uint8_t b=0;b<2;++b)for(uint8_t i=0;i<4;++i)EEPROM.update(address(b)+i,0);active=pending=-1;current={};}
inline bool begin(const char*name,uint32_t from,uint32_t until,int16_t offset){
 if(!nameValid(name)||from<ClockCore::MIN_EPOCH||until>ClockCore::MAX_EPOCH||until<=from||offset < -720||offset>840)return false;
 pending=active==0?1:0;draft={};draft.magic=MAGIC;draft.sequence=active<0?1:current.sequence+1;draft.from=from;draft.until=until;draft.offset=offset;strncpy(draft.name,name,63);
 for(uint8_t i=0;i<4;++i)EEPROM.update(address(pending)+i,0);return true;
}
inline bool add(uint32_t epoch,int16_t offset){
 if(pending<0||draft.count>=MAX_CHANGES||epoch<=draft.from||epoch>=draft.until||offset < -720||offset>840)return false;
 if(draft.count){Change last;EEPROM.get(address(pending)+sizeof(Header)+(draft.count-1)*sizeof(Change),last);if(epoch<=last.epoch)return false;}
 Change c={epoch,offset};const uint8_t*p=reinterpret_cast<const uint8_t*>(&c);int a=address(pending)+sizeof(Header)+draft.count*sizeof(Change);
 for(uint8_t i=0;i<sizeof(Change);++i)EEPROM.update(a+i,p[i]);++draft.count;return true;
}
inline bool commit(){
 if(pending<0)return false;draft.crc=checksum(draft,pending);const uint8_t*p=reinterpret_cast<const uint8_t*>(&draft);int a=address(pending);
 for(size_t i=4;i<sizeof(Header);++i)EEPROM.update(a+i,p[i]);for(uint8_t i=0;i<4;++i)EEPROM.update(a+i,p[i]);
 current=draft;active=pending;pending=-1;return true;
}
inline bool covers(uint32_t epoch){return active>=0&&epoch>=current.from&&epoch<current.until;}
inline int16_t offset(uint32_t epoch){
 int16_t result=current.offset;
 for(uint8_t i=0;i<current.count;++i){Change c;EEPROM.get(address(active)+sizeof(Header)+i*sizeof(Change),c);if(epoch<c.epoch)break;result=c.offset;}
 return result;
}
}
