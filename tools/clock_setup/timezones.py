"""Pinned IANA data; compact UTC transition schedules for the clock's EEPROM."""
from datetime import datetime,timezone
from importlib.resources import files
from zoneinfo import ZoneInfo

MAX_CHANGES=56

def zone_names():return sorted(files('tzdata').joinpath('zones').read_text().splitlines())
def load_zone(name):
    if name not in zone_names():raise ValueError('Choose a timezone from the list, or choose Custom.')
    with files('tzdata.zoneinfo').joinpath(*name.split('/')).open('rb') as f:return ZoneInfo.from_file(f,key=name)
def offset_at(zone,epoch):
    seconds=datetime.fromtimestamp(epoch,timezone.utc).astimezone(zone).utcoffset().total_seconds()
    if seconds%60:raise ValueError('Timezone requires an unsupported sub-minute offset')
    return int(seconds/60)
def schedule(name,now):
    zone=load_zone(name);year=datetime.fromtimestamp(now,timezone.utc).year
    start=int(datetime(max(2024,year-10),1,1,tzinfo=timezone.utc).timestamp())
    until=int(datetime(min(2100,year+11),1,1,tzinfo=timezone.utc).timestamp())
    initial=last=offset_at(zone,start);changes=[];left=start
    # Modern/future IANA rules have at most one offset change in a six-hour window.
    while left<until-1:
        right=min(left+21600,until-1);new=offset_at(zone,right)
        if new!=last:
            lo,hi=left,right
            while hi-lo>1:
                mid=(lo+hi)//2
                if offset_at(zone,mid)==last:lo=mid
                else:hi=mid
            changes.append((hi,new));last=new
        left=right
    if len(changes)>MAX_CHANGES:raise ValueError('This timezone has too many transitions for the clock; choose Custom.')
    return dict(name=name,start=start,until=until,offset=initial,current_offset=offset_at(zone,now),changes=changes)
